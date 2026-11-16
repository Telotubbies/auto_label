"""Batch inference jobs: run one model over a project batch, a video's frames or a bucket prefix.

Inputs are always resolved inside the job's project/workspace. Outputs are one CSV row per
detection, one COCO document, or annotations written back to the dataset (a connector source is
materialised into a new batch first). GPU access goes through the adapter lease path, which loads
and evicts models through app.gpu.scheduler. Re-running a job appends its annotations; it never
replaces an earlier result.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from collections.abc import Callable
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select

from ..adapters import Cancelled, resolve
from ..config import DATA_DIR
from ..db import SessionLocal
from ..deps import plan
from ..jobs import check as check_cancel
from ..models import Batch, Connector, Image, Job, LabelClass, Project, Video, Workspace, new_id, set_annotations
from . import connectors, csvsafe, imaging, metering, ml

log = logging.getLogger("labeldesk.batch_inference")
MAX_IMAGES = 500
OUTPUTS = ("csv", "coco", "dataset")


class SourceNotFound(LookupError):
    """The batch/video/connector does not exist in this project or workspace."""


class SourceInvalid(ValueError):
    """The source exists but cannot be used as batch-inference input."""


def source_images(db, project: Project, source: dict) -> list[Image]:
    """The project images a batch/video source resolves to; raises SourceNotFound/SourceInvalid."""
    kind = (source or {}).get("kind")
    if kind == "batch":
        batch = db.get(Batch, source.get("batch_id") or "")
        if batch is None or batch.project_id != project.id:
            raise SourceNotFound("batch not found")
        q = select(Image).where(Image.project_id == project.id, Image.batch_id == batch.id, Image.deleted_at.is_(None))
        rows = list(db.scalars(q.order_by(Image.created, Image.id)).all())
    elif kind == "video":
        video = db.get(Video, source.get("video_id") or "")
        if video is None or video.project_id != project.id or video.deleted_at:
            raise SourceNotFound("video not found")
        if video.status != "ready":
            raise SourceInvalid("video frames are still being extracted")
        q = select(Image).where(Image.project_id == project.id, Image.video_id == video.id, Image.deleted_at.is_(None))
        rows = list(db.scalars(q.order_by(Image.frame_index, Image.created)).all())
    else:
        raise SourceInvalid("source kind must be batch, video or connector")
    if not rows:
        raise SourceInvalid("the selected source has no images")
    if len(rows) > MAX_IMAGES:
        raise SourceInvalid(f"at most {MAX_IMAGES} images per batch inference job")
    return rows


# --- inference -----------------------------------------------------------------------


def _predict(r, im, params: dict) -> dict:
    kw: dict = {}
    if params.get("confidence") is not None:
        kw["conf"] = float(params["confidence"])
    if params.get("classes"):
        kw["classes"] = list(params["classes"])
    return r.predict(im, **kw)


def _error_message(exc: Exception | None) -> str:
    """Only our own validation/runtime messages are safe to store on the job."""
    if exc is None:
        return "no input could be read"
    if isinstance(exc, (ValueError, RuntimeError)) and str(exc):
        return str(exc)
    return "model unavailable"


def _collect(rows: list[dict], images: list[dict], name: str, im, pred: dict) -> None:
    """Flatten one prediction into CSV/COCO rows; classification results carry no box."""
    images.append({"name": name, "width": im.width, "height": im.height})
    image_id = len(images)  # 1-based COCO id of this input (names may repeat across folders)
    for p in pred.get("predictions") or []:
        label = str(p.get("class") or "")
        if not label:
            continue
        box = None
        if all(isinstance(p.get(k), (int, float)) for k in ("x", "y", "width", "height")):
            x1 = float(p["x"]) - float(p["width"]) / 2
            y1 = float(p["y"]) - float(p["height"]) / 2
            box = (x1, y1, x1 + float(p["width"]), y1 + float(p["height"]))
        points = None
        if isinstance(p.get("points"), list) and len(p["points"]) >= 3:
            points = [v for pt in p["points"] for v in (float(pt["x"]), float(pt["y"]))]
        rows.append(
            {
                "image": name,
                "image_id": image_id,
                "class": label,
                "confidence": p.get("confidence"),
                "box": box,
                "points": points,
            }
        )


def _ensure_class(db, project: Project, name: str) -> LabelClass:
    from ..routers.projects import ensure_class  # local import: routers import services

    return ensure_class(db, project, name)


def _annotate(db, project: Project, img: Image, pred: dict) -> int:
    """Append the prediction's annotations to an image, creating missing classes on first sight."""
    classes = {row.name: row for row in db.scalars(select(LabelClass).where(LabelClass.project_id == project.id))}
    for p in pred.get("predictions") or []:
        name = str(p.get("class") or "")
        if name and name not in classes:
            classes[name] = _ensure_class(db, project, name)
    anns = ml.to_annotations(pred, {name: row.id for name, row in classes.items()})
    if not anns:
        return 0
    set_annotations(db, img, (img.annotations or []) + anns)
    if img.status == "unassigned":
        img.status = "review"
    return len(anns)


def _store(
    db, project: Project, ws: Workspace, batch: Batch, name: str, data: bytes, im, job: Job, capacity: list[int]
) -> Image:
    """Materialise one bucket object as a project image (reusing an identical image in the project)."""
    from ..routers.images import safe_name

    digest = hashlib.sha256(data).hexdigest()
    existing = db.scalar(
        select(Image).where(Image.project_id == project.id, Image.sha256 == digest, Image.deleted_at.is_(None))
    )
    if existing is not None:
        return existing
    if capacity[0] <= 0:
        raise RuntimeError("plan image limit reached")
    try:
        metering.check(db, ws, "storage_bytes", len(data))
    except HTTPException as exc:
        raise RuntimeError(str(exc.detail)) from exc
    img = Image(
        id=new_id(),
        project_id=project.id,
        batch_id=batch.id,
        name=safe_name(name),
        sha256=digest,
        width=im.width,
        height=im.height,
        size=len(data),
        path="",
        thumb="",
        split="train",
        status="unassigned",
        tags=[],
        assignee_id=job.created_by,
    )
    img.path, img.thumb = imaging.store(f"projects/{project.id}/images", img.id, im)
    db.add(img)
    set_annotations(db, img, [])
    metering.record(db, ws.id, "storage_bytes", len(data), project_id=project.id, image_id=img.id)
    capacity[0] -= 1
    return img


# --- output writers ------------------------------------------------------------------


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        fh.write("\ufeff")                              # BOM so Excel reads Thai class names correctly
        w = csv.writer(fh)
        w.writerow(["image", "class", "confidence", "x_min", "y_min", "x_max", "y_max"])
        for row in rows:
            box = row["box"] or ("", "", "", "")
            conf = "" if row["confidence"] is None else round(float(row["confidence"]), 4)
            w.writerow([csvsafe.cell(row["image"]), csvsafe.cell(row["class"]), conf,
                        *(round(v, 2) if v != "" else "" for v in box)])


def _write_coco(path: Path, images: list[dict], rows: list[dict]) -> None:
    names = sorted({row["class"] for row in rows})
    cat = {name: i + 1 for i, name in enumerate(names)}
    annotations = []
    for i, row in enumerate(rows, start=1):
        entry = {"id": i, "image_id": row["image_id"], "category_id": cat[row["class"]], "iscrowd": 0}
        if row["confidence"] is not None:
            entry["score"] = round(float(row["confidence"]), 4)
        if row["box"]:
            x1, y1, x2, y2 = row["box"]
            entry["bbox"] = [round(x1, 2), round(y1, 2), round(x2 - x1, 2), round(y2 - y1, 2)]
            entry["area"] = round((x2 - x1) * (y2 - y1), 2)
        if row["points"]:
            entry["segmentation"] = [[round(v, 2) for v in row["points"]]]
        annotations.append(entry)
    doc = {
        "info": {"description": "LabelDesk batch inference", "version": "1.0"},
        "images": [
            {"id": i + 1, "file_name": im["name"], "width": im["width"], "height": im["height"]}
            for i, im in enumerate(images)
        ],
        "annotations": annotations,
        "categories": [{"id": cid, "name": name, "supercategory": "none"} for name, cid in cat.items()],
    }
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


# --- job handler ---------------------------------------------------------------------


def run(job: Job, progress: Callable[[float], None] | None = None) -> dict:
    """Run one batch inference job. `progress` receives 0..1; cancelling raises ``Cancelled``."""
    params = job.params or {}
    fmt = params.get("output") or "csv"
    if fmt not in OUTPUTS:
        raise RuntimeError(f"unknown output format {fmt!r}")
    source = params.get("source") or {}
    model_ref = str(params.get("model_ref") or "")
    with SessionLocal() as db:
        project = db.get(Project, job.project_id)
        if project is None or project.deleted_at:
            raise RuntimeError("project not found")
        ws = db.get(Workspace, job.workspace_id)
        if ws is None:
            raise RuntimeError("workspace not found")
        try:
            r = resolve(model_ref, db, workspace_id=job.workspace_id)
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc
        if fmt == "dataset" and r.adapter.family == "vlm":
            raise RuntimeError(
                "VLM output cannot be written to the dataset without SAM 3.1 refinement; choose CSV or COCO"
            )
        if fmt == "coco" and r.variant.endswith("-cls"):
            raise RuntimeError("COCO export needs detection boxes; a classification model has none")
        rows: list[dict] = []
        images: list[dict] = []
        annotated = processed = failed = 0
        clamped = False
        last_error: Exception | None = None
        out_batch = None
        capacity = [0]
        connector = None
        objects: list[dict] = []
        project_images: list[Image] = []

        if source.get("kind") == "connector":
            connector = db.get(Connector, source.get("connector_id") or "")
            if connector is None or connector.workspace_id != job.workspace_id:
                raise RuntimeError("connector not found")
            try:
                objects = [
                    o
                    for o in connectors.list_objects(
                        connector, prefix=source.get("prefix") or "", limit=int(source.get("limit") or MAX_IMAGES)
                    )
                    if imaging.ext_ok(str(o.get("key") or ""))
                ]
            except HTTPException as exc:              # a 502 must not reach the user as "HTTPException: …"
                raise RuntimeError(str(exc.detail)) from exc
            if not objects:
                raise RuntimeError("no image objects found at that prefix")
            total = len(objects)
            if fmt == "dataset":
                out_batch = Batch(
                    project_id=project.id,
                    name=params.get("name") or "Batch inference",
                    source="batch_inference",
                    created_by=job.created_by,
                )
                db.add(out_batch)
                db.flush()
                have = db.scalar(
                    select(func.count(Image.id))
                    .join(Project)
                    .where(Project.workspace_id == ws.id, Image.deleted_at.is_(None))
                )
                capacity[0] = max(0, plan(ws)["images"] - int(have or 0))
        else:
            project_images = source_images(db, project, source)
            total = len(project_images)

        for i in range(total):
            check_cancel(job)                          # I22: stop before the next billable call
            if metering.remaining(db, ws, "ai_calls") <= 0:
                clamped = True                         # stop at the allowance instead of overrunning it
                break
            try:
                if connector is not None:
                    name = str(objects[i]["key"])
                    data = connectors.fetch_bytes(connector, name)
                    im = imaging.open_image(data)
                else:
                    img = project_images[i]
                    name, data, im = img.name, None, imaging.load(img.path)
                pred = _predict(r, im, params)
            except Cancelled:
                raise                                  # the GPU wait or the user's cancel: stop the job
            except Exception as exc:
                failed += 1
                last_error = exc
                log.warning("batch inference skipped input %s: %s", i, exc)
                continue
            processed += 1
            _collect(rows, images, name, im, pred)
            if fmt == "dataset":
                if connector is not None:
                    target = _store(db, project, ws, out_batch, name, data, im, job, capacity)
                    annotated += _annotate(db, project, target, pred)
                else:
                    annotated += _annotate(db, project, project_images[i], pred)
            metering.record(db, ws.id, "ai_calls", 1, project_id=project.id, kind="batch_infer")
            db.commit()
            if progress:
                progress((i + 1) / max(1, total))

        if processed == 0 and not clamped:         # I1: a clamp before image 1 is a done, zero-work job
            raise RuntimeError(
                f"inference failed for every image ({failed} unreadable or unsupported): {_error_message(last_error)}"
            )
        if out_batch is not None and not db.scalar(select(func.count(Image.id)).where(Image.batch_id == out_batch.id)):
            db.delete(out_batch)                       # every object deduped: do not leave an empty batch
            db.commit()
            out_batch = None
        result = {"format": fmt, "images": processed, "predictions": len(rows), "failed": failed,
                  "quota_clamped": clamped}
        if fmt == "dataset":
            result["annotations"] = annotated
            if out_batch is not None:
                result["batch_id"] = out_batch.id
        else:
            out_dir = DATA_DIR / "batch_inference" / project.id / job.id   # I2: inside the project's erasure boundary
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / ("predictions.csv" if fmt == "csv" else "predictions.coco.json")
            if fmt == "csv":
                _write_csv(path, rows)
            else:
                _write_coco(path, images, rows)
            result["file"] = path.relative_to(DATA_DIR).as_posix()
            result["bytes"] = path.stat().st_size
        return result
