"""The expensive half of the health check: pHash leakage and missing-box inference.

Both run inside the `health` worker job and are cached on the job row. `cached()` is the only read
path used by the analytics request; it never touches an image or a model.
"""

from collections import Counter
import math
import threading

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..adapters import model_conf, resolve
from ..models import Image, Job, Project, TrainedModel
from . import imaging, versioning

DEFAULT_CONF = 0.4  # fallback when the model has no best-F1 confidence
MISSING_IOU = 0.3
MISSING_LIMIT = 500  # keep the cached job row bounded on a big unlabelled dataset

_PHASH_CACHE: dict[tuple, dict] = {}
_ENQ_LOCK = threading.Lock()  # one uvicorn process: serialise the enqueue read-then-insert


def signature(db: Session, project: Project) -> list:
    """Cheap dataset fingerprint: changes whenever an image is added, edited or deleted."""
    return list(
        db.execute(
            select(func.count(Image.id), func.max(Image.updated), func.count(Image.deleted_at)).where(
                Image.project_id == project.id
            )
        ).one()
    )


def latest_job(db: Session, project: Project) -> Job | None:
    return db.scalar(
        select(Job).where(Job.project_id == project.id, Job.kind == "health").order_by(Job.created.desc()).limit(1)
    )


def job_state(db: Session, project: Project) -> str:
    """Part of the analytics cache key: a new model or a job transition invalidates the cached checks."""
    j = latest_job(db, project)
    m = latest_model(db, project)
    return f"{j.id if j else ''}:{j.status if j else ''}:{m.id if m else ''}"


def job_summary(db: Session, project: Project) -> tuple[dict | None, bool]:
    """(latest health job without its payload, cached-run-predates-the-dataset).

    The router only merges these two values; the summary/staleness rules live here."""
    jobs = db.scalars(
        select(Job).where(Job.project_id == project.id, Job.kind == "health").order_by(Job.created.desc()).limit(5)
    ).all()
    done = next((j for j in jobs if j.status == "done"), None)
    stale = bool(done and (done.result or {}).get("signature") != signature(db, project))
    if not jobs:
        return None, stale
    j = jobs[0]
    return {
        "id": j.id,
        "kind": j.kind,
        "status": j.status,
        "progress": j.progress,
        "params": j.params,
        "error": j.error,
        "created": j.created,
        "started": j.started,
        "finished": j.finished,
    }, stale


def iou(a: tuple, b: tuple) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def box(ann: dict) -> tuple[float, float, float, float] | None:
    """Tolerate legacy/hand-edited JSON that has no usable shape."""
    if not isinstance(ann, dict) or not isinstance(ann.get("shape"), dict):
        return None
    try:
        out = imaging.bbox_of(ann)
        if out is None:
            return None
        out = tuple(float(v) for v in out)
    except (KeyError, TypeError, ValueError):
        return None
    return out if all(math.isfinite(v) for v in out) else None


def is_human(ann: dict) -> bool:
    """Ground truth is a human label (or a pre-`source` annotation), never a model's own box."""
    return isinstance(ann, dict) and ann.get("source") in (None, "human")


def latest_model(db: Session, project: Project) -> TrainedModel | None:
    return db.scalar(
        select(TrainedModel)
        .where(TrainedModel.project_id == project.id, TrainedModel.status == "ready")
        .order_by(TrainedModel.created.desc())
        .limit(1)
    )


def _missing_boxes(
    db: Session, project: Project, rows: list[Image], model: TrainedModel | None, conf: float | None
) -> list[dict]:
    """Predictions above the model threshold with IoU < 0.3 to every human ground-truth box."""
    if project.type == "classification" or model is None:
        return []
    try:
        resolved = resolve(f"trained:{model.id}", db, workspace_id=project.workspace_id)
    except ValueError:  # deleted between the query and the resolve
        return []
    conf = DEFAULT_CONF if conf is None else conf
    out = []
    for img in rows:
        if len(out) >= MISSING_LIMIT:
            break
        if not img.width or not img.height:
            continue
        try:
            im = imaging.load(img.path)
        except Exception:  # unreadable image: nothing to compare against
            continue
        gts = [b for b in (box(a) for a in img.annotations or [] if is_human(a)) if b]
        # a model failure (GPU busy, missing weights, broken adapter) must fail the job, never be
        # cached as "no missing boxes" — the UI keeps the previous result and shows the error
        pred = resolved.predict(im, conf=conf)
        for p in pred.get("predictions") or []:
            if p.get("confidence", 0) < conf or not all(k in p for k in ("x", "y", "width", "height")):
                continue
            # predictions are centre boxes in pixels; health compares normalised boxes
            found = (
                (p["x"] - p["width"] / 2) / img.width,
                (p["y"] - p["height"] / 2) / img.height,
                p["width"] / img.width,
                p["height"] / img.height,
            )
            if all(iou(found, gt) < MISSING_IOU for gt in gts):
                out.append({"image_id": img.id, "box": [round(v, 4) for v in found], "class": p.get("class")})
                if len(out) >= MISSING_LIMIT:
                    break
    return out


def _leakage_pairs(project: Project, rows: list[Image]) -> int:
    """phash_groups re-decodes every image, so cache it on the pixel-level identity of the project.

    Annotations do not change pixels: `created`/count change only on upload or delete, so routine
    labelling saves reuse the groups."""
    key = (project.id, len(rows), max((r.created for r in rows), default=0.0))
    groups = _PHASH_CACHE.get(key)
    if groups is None:
        groups = versioning.phash_groups(rows)
        _PHASH_CACHE[key] = groups
        while len(_PHASH_CACHE) > 256:
            _PHASH_CACHE.pop(next(iter(_PHASH_CACHE)))
    sizes = Counter(groups.values())
    return sum(n * (n - 1) // 2 for n in sizes.values() if n > 1)


def scan_health(db: Session, project: Project) -> dict:
    """The `health` job body: the two expensive checks, stored on the job row with the signature."""
    sig = signature(db, project)
    model = latest_model(db, project)
    conf = model_conf(model) if model else None
    conf = DEFAULT_CONF if conf is None else conf
    rows = db.scalars(select(Image).where(Image.project_id == project.id, Image.deleted_at.is_(None))).all()
    return {
        "signature": sig,
        "model_id": model.id if model else None,
        "conf": conf if model else None,
        "checks": {
            "leakage_pairs": _leakage_pairs(project, rows),
            "missing_boxes": _missing_boxes(db, project, rows, model, conf),
        },
    }


def enqueue(db: Session, project: Project, imgsz: int = 640) -> Job | None:
    """Queue one scan; a click while one is running returns that job instead of piling up."""
    with _ENQ_LOCK:
        active = db.scalar(
            select(Job)
            .where(Job.project_id == project.id, Job.kind == "health", Job.status.in_(("queued", "running")))
            .order_by(Job.created.desc())
            .limit(1)
        )
        if active:
            return active
        model = latest_model(db, project)
        j = Job(
            workspace_id=project.workspace_id,
            project_id=project.id,
            kind="health",
            params={"imgsz": imgsz, "signature": signature(db, project), "model_id": model.id if model else None},
        )
        db.add(j)
        db.commit()
        return j


def cached(db: Session, project: Project) -> tuple[dict, bool]:
    """(cached checks for the current model, whether auto-enqueue is blocked).

    The newest completed scan is reused even when the dataset moved on (`health_stale` tells the page).
    A failed or still-running scan for this exact dataset/model blocks a new automatic enqueue, so a
    broken scan is retried only from the explicit button, not on every analytics poll."""
    model = latest_model(db, project)
    model_id = model.id if model else None
    sig = signature(db, project)
    jobs = db.scalars(
        select(Job).where(Job.project_id == project.id, Job.kind == "health").order_by(Job.created.desc()).limit(5)
    ).all()
    for j in jobs:
        if j.status == "done" and (j.result or {}).get("model_id") == model_id:
            return (j.result or {}).get("checks") or {}, False
    for j in jobs:
        p = j.params or {}
        if (
            p.get("model_id") == model_id
            and list(p.get("signature") or []) == list(sig)
            and j.status in ("queued", "running", "failed")
        ):
            return {}, True
    return {}, False
