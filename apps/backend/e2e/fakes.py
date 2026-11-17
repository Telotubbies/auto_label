"""Deterministic stand-ins for the worker's slow, GPU-bound and far-side work.

`e2e/app.py` swaps these into the seams the pytest suite already uses (`worker.HANDLERS`,
`worker.ADAPTERS`, `worker.scheduler`), so a journey spec watches the real app finish a job in
milliseconds. Nothing in this file is imported by `app.main`: no fake ships in the API image.
"""
import json
import logging
import zipfile
from contextlib import contextmanager
from pathlib import Path

from PIL import Image as PImage
from sqlalchemy import select

from app.adapters.base import Availability
from app.config import DATA_DIR
from app.db import SessionLocal
from app.models import (Batch, Image, Job, LabelClass, Project, TrainedModel, Version, Video, new_id,
                        set_annotations)
from app.services import imaging

log = logging.getLogger("labeldesk.worker")

# Fixed metrics: Compare, the model table and the overview read these, so a journey asserts
# numbers instead of a GPU result. They are a fixture, never a product claim.
METRICS = {"map50": 0.874, "map5095": 0.612, "precision": 0.83, "recall": 0.79}
EPOCHS = 3
FRAMES = 3
FAMILIES = ("hf", "rfdetr", "sam3", "tensorrt", "ultralytics", "vlm")
# Every family key the registry knows, so a resolve can never reach a real checkpoint.


class FakeAdapter:
    """A deterministic detector: boxes and one polygon, both placed from the image size."""

    def __init__(self, family: str = "fake") -> None:
        self.family = family

    def probe(self) -> Availability:
        return Availability(ok=True)

    def capabilities(self, variant: str) -> set[str]:
        return {"detect", "segment", "classify", "predict"}

    def predict(self, variant: str, im: PImage.Image, *, classes: list[str] | None = None,
                prompt: str | None = None, weights: str | None = None, conf: float = 0.4,
                iou: float = 0.5) -> dict:
        w, h = im.size
        boxes = (("person", 0.10, 0.10, 0.30, 0.40), ("helmet", 0.55, 0.20, 0.20, 0.15))
        predictions = [{"class": name, "class_id": i, "confidence": round(0.9 - 0.1 * i, 2),
                        "x": round(w * x, 1), "y": round(h * y, 1),
                        "width": round(w * bw, 1), "height": round(h * bh, 1)}
                       for i, (name, x, y, bw, bh) in enumerate(boxes)]
        predictions[0]["points"] = [round(w * 0.1, 1), round(h * 0.1, 1), round(w * 0.4, 1),
                                    round(h * 0.1, 1), round(w * 0.4, 1), round(h * 0.5, 1),
                                    round(w * 0.1, 1), round(h * 0.5, 1)]
        return {"model": f"{self.family}:{variant}", "image": {"width": w, "height": h},
                "time": 0.001, "predictions": predictions}


ADAPTER = FakeAdapter()


class _Scheduler:
    """The fake jobs take no card, so the lease is a no-op that still answers every caller."""

    holder = ""

    @contextmanager
    def exclusive(self, reason: str):
        yield

    @contextmanager
    def training_scope(self):
        yield


def _done(job: Job, middle: str) -> dict:
    """The three-line job log and the phase the tray reads; every fake ends this way."""
    return {"log": [f"start {job.kind} {job.id} ws={job.workspace_id}", middle,
                    f"done {job.kind} {job.id} ws={job.workspace_id}"],
            "phase": "done"}


def _boxes(classes: list[LabelClass], image_id: str) -> list[dict]:
    """Two committed annotations, placed from the image size like the adapter's predictions."""
    return [{"id": f"a{image_id}{i}", "classId": cls.id, "confidence": round(0.9 - 0.1 * i, 2),
             "source": "fake", "shape": {"kind": "bbox", "x": round(0.10 + 0.45 * i, 2),
                                         "y": 0.10, "w": 0.30, "h": 0.40}}
            for i, cls in enumerate(classes[:2])]


def run_version(job: Job) -> dict:
    with SessionLocal() as db:
        v = db.get(Version, job.params["version_id"])
        if v is None:
            raise RuntimeError("version not found")
        rows = db.scalars(select(Image).where(Image.project_id == v.project_id, Image.status == "done",
                                              Image.deleted_at.is_(None))).all()
        splits = {name: sum(1 for img in rows if img.split == name) for name in ("train", "valid", "test")}
        names = list(db.scalars(select(LabelClass.name).where(LabelClass.project_id == v.project_id)
                                .order_by(LabelClass.created)))
        v.status = "ready"
        v.stats = {"images": len(rows), "source_images": len(rows), "splits": splits, "classes": {},
                   "class_names": names, "leakage_moved": 0, "tiles_skipped": 0}
        db.commit()
        return {"version_id": v.id, **v.stats, **_done(job, f"generated {len(rows)} images")}


def run_export(job: Job) -> dict:
    with SessionLocal() as db:
        v = db.get(Version, job.params["version_id"])
        if v is None:
            raise RuntimeError("version not found")
        fmt = job.params["format"]
        out = DATA_DIR / "exports" / v.id / f"{fmt}.zip"
        out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out, "w") as z:              # a fixed timestamp keeps the bytes identical
            z.writestr(zipfile.ZipInfo("dataset/README.txt", (2026, 1, 1, 0, 0, 0)),
                       f"LabelDesk e2e export ({fmt})\n")
        return {"version_id": v.id, "format": fmt, "file": out.relative_to(DATA_DIR).as_posix(),
                "bytes": out.stat().st_size, **_done(job, f"wrote the {fmt} archive")}


def run_train(job: Job) -> dict:
    with SessionLocal() as db:
        tm = db.get(TrainedModel, job.params["model_id"])
        if tm is None:
            raise RuntimeError("model not found")
        root = DATA_DIR / "models" / tm.id
        root.mkdir(parents=True, exist_ok=True)
        (root / "best.pt").write_bytes(b"labeldesk-e2e-weights\n")
        metrics = {**METRICS, "eval": {"map50": METRICS["map50"], "map5095": METRICS["map5095"]}}
        (root / "metrics.json").write_text(json.dumps(metrics, sort_keys=True), encoding="utf-8")
        tm.status, tm.weights = "ready", f"models/{tm.id}/best.pt"
        tm.history = [{"epoch": e, "metrics/mAP50": round(0.60 + e * 0.05, 2)} for e in range(1, EPOCHS + 1)]
        tm.metrics = metrics
        stages = {name: {"status": "done", "t": 0.0} for name in
                  ("queue", "acquire_gpu", "materialise", "resolve_weights", "build_config", "train",
                   "evaluate", "register", "release")}
        db.commit()
        return {"model_id": tm.id, **tm.metrics, "stages": stages,
                **_done(job, f"trained {EPOCHS} epochs, mAP50 {METRICS['map50']}")}


def run_autolabel(job: Job) -> dict:
    with SessionLocal() as db:
        p = db.get(Project, job.project_id)
        classes = db.scalars(select(LabelClass).where(LabelClass.project_id == p.id)
                             .order_by(LabelClass.created)).all()
        rows = db.scalars(select(Image).where(Image.project_id == p.id, Image.deleted_at.is_(None),
                                              Image.n_annotations == 0)).all()
        labelled = boxes = 0
        for img in rows:
            anns = _boxes(list(classes), img.id)
            if not anns:
                break
            set_annotations(db, img, (img.annotations or []) + anns)
            img.status = "review"
            labelled += 1
            boxes += len(anns)
        db.commit()
        return {"images": labelled, "selected": len(rows), "labeled": labelled, "annotations": boxes,
                "quota_clamped": False, **_done(job, f"labelled {labelled} images, {boxes} boxes")}


def run_extract_frames(job: Job) -> dict:
    """The batch of frames a video upload shows; the pixels are a flat frame, never a decode."""
    with SessionLocal() as db:
        v = db.get(Video, job.params["video_id"])
        if v is None:
            raise RuntimeError("video not found")
        batch = Batch(project_id=v.project_id, name=f"Video · {v.name}", source="video")
        db.add(batch)
        db.flush()
        frame = PImage.new("RGB", (v.width or 320, v.height or 180), (32, 40, 56))
        stem = Path(v.name).stem or "video"
        for i in range(FRAMES):
            img = Image(id=new_id(), project_id=v.project_id, batch_id=batch.id, video_id=v.id,
                        frame_index=i, name=f"{stem}_f{i:06d}.jpg", sha256=f"{v.id}-{i}",
                        width=frame.width, height=frame.height, split="train", status="unassigned")
            img.path, img.thumb = imaging.store(f"projects/{v.project_id}/images", img.id, frame)
            img.size = (DATA_DIR / img.path).stat().st_size
            db.add(img)
            set_annotations(db, img, [])
        # shortcut: no storage metering; a fake frame is not billable and the plan never fills up
        v.status, v.error, v.batch_id = "ready", "", batch.id
        v.frame_count, v.fps = FRAMES, v.fps or 10.0
        v.duration = v.frame_count / v.fps
        db.commit()
        return {"video_id": v.id, "frames": FRAMES, "batch_id": batch.id,
                **_done(job, f"sampled {FRAMES} frames")}


def run_export_engine(job: Job) -> dict:
    with SessionLocal() as db:
        tm = db.get(TrainedModel, job.params["model_id"])
        if tm is None:
            raise RuntimeError("model not found")
        rel = f"engines/{tm.id}.engine"
        dest = DATA_DIR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"labeldesk-e2e-engine\n")
        tm.runtime_refs = {**(tm.runtime_refs or {}), "pt": tm.weights, "engine": rel}
        db.commit()
        return {"model_id": tm.id, "format": "engine", "engine": rel, "bytes": dest.stat().st_size,
                **_done(job, f"built {rel}")}


def run_infer_video(job: Job) -> dict:
    """No video-inference table ships yet; the fake answers with the shape its handler will return."""
    return {"video_id": (job.params or {}).get("video_id", ""), "frames": FRAMES, "annotations": FRAMES,
            **_done(job, f"scored {FRAMES} frames")}


def run_engine_apply(job: Job) -> dict:
    params = job.params or {}
    installed = [engine.get("id") for engine in params.get("engines", [])]
    return {"host": params.get("host", ""), "action": params.get("action", "install"),
            "installed": installed, **_done(job, f"applied {len(installed)} engine(s)")}


def run_model_pull(job: Job) -> dict:
    params = job.params or {}
    return {"host": params.get("host", ""), "model": params.get("model", ""),
            "variant": params.get("variant", ""), "bytes": 0,
            **_done(job, f"pulled {params.get('model', '')}")}


def run_health(job: Job) -> dict:
    checks = {"imgsz": 640, "size_buckets": {"small": 0, "medium": 3, "large": 0},
              "label_quality": {"missing_boxes": 0, "single_class": 0}, "missing_boxes": [],
              "leakage_pairs": 0, "quality": {"sharpness": 0.52, "luminance": 0.48}}
    return {**checks, **_done(job, "scanned the dataset")}


HANDLERS = {"version": run_version, "export": run_export, "train": run_train,
            "autolabel": run_autolabel, "infer_video": run_infer_video,
            "export_engine": run_export_engine, "extract_frames": run_extract_frames,
            "engine_apply": run_engine_apply, "model_pull": run_model_pull, "health": run_health}


def install() -> None:
    """Swap the worker's runtime seams for the fakes. Idempotent, and the only write a fake makes."""
    from app import worker

    worker.HANDLERS.update(HANDLERS)
    worker.ADAPTERS.clear()
    worker.ADAPTERS.update({family: FakeAdapter(family) for family in FAMILIES})
    worker.scheduler = _Scheduler()
    for kind in HANDLERS:                     # the fake worker must claim every kind it can finish
        if kind not in worker.LOCAL_JOB_KINDS:
            worker.LOCAL_JOB_KINDS.append(kind)
