"""Dataset health checks: object sizes, label-quality flags, missing boxes and pHash leakage.

Object-size buckets and geometry flags are cheap and read straight from the image rows. The two
expensive checks — pHash grouping and model inference for missing boxes — run in the `health` worker
job and are cached on the job row; the analytics request only reads that row back.
"""

from collections import Counter
import math
import threading

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..adapters import model_conf, resolve
from ..models import Image, Job, Project, TrainedModel
from . import imaging, versioning

SMALL_PX = 32.0  # COCO: small objects are under 32x32 px at the training size
MEDIUM_PX = 96.0
TINY_PX = 2.0  # below this a box cannot be drawn/inspected reliably
DEFAULT_CONF = 0.4  # fallback when the model has no best-F1 confidence
DUPLICATE_IOU = 0.9
MISSING_IOU = 0.3
SMALL_SHARE = 0.3  # recommend a larger imgsz when this share of objects is small
MISSING_LIMIT = 500  # keep the cached job row bounded on a big unlabelled dataset
HUMAN = (None, "human")  # only human/no-source labels are ground truth (PM ruling)
EPS = 1e-6

_PHASH_CACHE: dict[tuple, dict] = {}
_ENQ_LOCK = (
    threading.Lock()
)  # one uvicorn process: serialise the enqueue read-then-insert


def signature(db: Session, project: Project) -> list:
    """Cheap dataset fingerprint: changes whenever an image is added, edited or deleted."""
    return list(
        db.execute(
            select(
                func.count(Image.id),
                func.max(Image.updated),
                func.count(Image.deleted_at),
            ).where(Image.project_id == project.id)
        ).one()
    )


def latest_job(db: Session, project: Project) -> Job | None:
    return db.scalar(
        select(Job)
        .where(Job.project_id == project.id, Job.kind == "health")
        .order_by(Job.created.desc())
        .limit(1)
    )


def job_state(db: Session, project: Project) -> str:
    """Part of the analytics cache key: a new model or a job transition invalidates the cached checks."""
    j = latest_job(db, project)
    m = _latest_model(db, project)
    return f"{j.id if j else ''}:{j.status if j else ''}:{m.id if m else ''}"


def job_summary(db: Session, project: Project) -> tuple[dict | None, bool]:
    """(latest health job without its payload, cached-run-predates-the-dataset).

    The router only merges these two values; the summary/staleness rules live here."""
    jobs = db.scalars(
        select(Job)
        .where(Job.project_id == project.id, Job.kind == "health")
        .order_by(Job.created.desc())
        .limit(5)
    ).all()
    done = next((j for j in jobs if j.status == "done"), None)
    stale = bool(
        done and (done.result or {}).get("signature") != signature(db, project)
    )
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


def _iou(a: tuple, b: tuple) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def _box(ann: dict) -> tuple[float, float, float, float] | None:
    """Tolerate legacy/hand-edited JSON that has no usable shape."""
    if not isinstance(ann, dict) or not isinstance(ann.get("shape"), dict):
        return None
    try:
        box = imaging.bbox_of(ann)
        if box is None:
            return None
        box = tuple(float(v) for v in box)
    except (KeyError, TypeError, ValueError):
        return None
    return box if all(math.isfinite(v) for v in box) else None


def _human(ann: dict) -> bool:
    """Ground truth is a human label (or a pre-`source` annotation), never a model's own box."""
    return isinstance(ann, dict) and ann.get("source") in HUMAN


def _quality_flags(img: Image, anns: list[dict], imgsz: int) -> list[dict]:
    out, seen = [], []
    for a in anns:
        box = _box(a)
        if box is None:  # classification labels carry no geometry
            continue
        x, y, w, h = box
        wpx, hpx = w * imgsz, h * imgsz
        kind = None
        if w <= 0 or h <= 0:
            kind = "zero_area"
        elif x < -EPS or y < -EPS or x + w > 1 + EPS or y + h > 1 + EPS:
            kind = "out_of_bounds"
        elif wpx < TINY_PX or hpx < TINY_PX:
            kind = "tiny"
        elif _human(a):
            for prev_ann, prev_box in seen:
                if (
                    _human(prev_ann)
                    and prev_ann.get("classId") == a.get("classId")
                    and _iou(prev_box, box) >= DUPLICATE_IOU
                ):
                    kind = "duplicate"
                    break
        if kind:
            out.append({"kind": kind, "image_id": img.id, "annotation_id": a.get("id")})
        if kind != "zero_area" and _human(a):
            seen.append((a, box))
    return out


def _latest_model(db: Session, project: Project) -> TrainedModel | None:
    return db.scalar(
        select(TrainedModel)
        .where(TrainedModel.project_id == project.id, TrainedModel.status == "ready")
        .order_by(TrainedModel.created.desc())
        .limit(1)
    )


def _missing_boxes(
    db: Session,
    project: Project,
    rows: list[Image],
    model: TrainedModel | None,
    conf: float | None,
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
        gts = [b for b in (_box(a) for a in img.annotations or [] if _human(a)) if b]
        # a model failure (GPU busy, missing weights, broken adapter) must fail the job, never be
        # cached as "no missing boxes" — the UI keeps the previous result and shows the error
        pred = resolved.predict(im, conf=conf)
        for p in pred.get("predictions") or []:
            if p.get("confidence", 0) < conf or not all(
                k in p for k in ("x", "y", "width", "height")
            ):
                continue
            # predictions are centre boxes in pixels; health compares normalised boxes
            box = (
                (p["x"] - p["width"] / 2) / img.width,
                (p["y"] - p["height"] / 2) / img.height,
                p["width"] / img.width,
                p["height"] / img.height,
            )
            if all(_iou(box, gt) < MISSING_IOU for gt in gts):
                out.append(
                    {
                        "image_id": img.id,
                        "box": [round(v, 4) for v in box],
                        "class": p.get("class"),
                    }
                )
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


def compute_checks(db: Session, project: Project, imgsz: int = 640) -> dict:
    """Everything a scan produces, computed now. Used by the worker job and by direct callers/tests."""
    rows = db.scalars(
        select(Image).where(Image.project_id == project.id, Image.deleted_at.is_(None))
    ).all()
    buckets = Counter()
    flags: list[dict] = []
    for img in rows:
        anns = img.annotations or []
        for a in anns:
            box = _box(a)
            if box is None:
                continue
            area = box[2] * imgsz * box[3] * imgsz
            buckets[
                "small"
                if area < SMALL_PX**2
                else "medium"
                if area < MEDIUM_PX**2
                else "large"
            ] += 1
        flags.extend(_quality_flags(img, anns, imgsz))
    model = _latest_model(db, project)
    conf = model_conf(model) if model else None
    return {
        "imgsz": imgsz,
        "size_buckets": {k: buckets[k] for k in ("small", "medium", "large")},
        "label_quality": flags,
        "missing_boxes": _missing_boxes(
            db, project, rows, model, DEFAULT_CONF if conf is None else conf
        ),
        "leakage_pairs": _leakage_pairs(project, rows),
    }


def scan_health(db: Session, project: Project) -> dict:
    """The `health` job body: the two expensive checks, stored on the job row with the signature."""
    sig = signature(db, project)
    model = _latest_model(db, project)
    conf = model_conf(model) if model else None
    conf = DEFAULT_CONF if conf is None else conf
    rows = db.scalars(
        select(Image).where(Image.project_id == project.id, Image.deleted_at.is_(None))
    ).all()
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
            .where(
                Job.project_id == project.id,
                Job.kind == "health",
                Job.status.in_(("queued", "running")),
            )
            .order_by(Job.created.desc())
            .limit(1)
        )
        if active:
            return active
        model = _latest_model(db, project)
        j = Job(
            workspace_id=project.workspace_id,
            project_id=project.id,
            kind="health",
            params={
                "imgsz": imgsz,
                "signature": signature(db, project),
                "model_id": model.id if model else None,
            },
        )
        db.add(j)
        db.commit()
        return j


def _cached(db: Session, project: Project) -> dict:
    """The latest completed scan for the current model; {} while a fresh one is needed."""
    model = _latest_model(db, project)
    model_id = model.id if model else None
    jobs = db.scalars(
        select(Job)
        .where(Job.project_id == project.id, Job.kind == "health")
        .order_by(Job.created.desc())
        .limit(5)
    ).all()
    for j in jobs:
        r = j.result or {}
        if j.status == "done" and r.get("model_id") == model_id:
            return r.get("checks") or {}
    return {}


def checks(
    db: Session, project: Project, imgsz: int = 640, *, auto_scan: bool = True
) -> dict:
    """Health data for the analytics page: cheap buckets/flags now, pHash + missing boxes from the job.

    `auto_scan=False` keeps annotators from queueing GPU work just by opening the page."""
    rows = db.scalars(
        select(Image).where(Image.project_id == project.id, Image.deleted_at.is_(None))
    ).all()
    buckets = Counter()
    flags: list[dict] = []
    for img in rows:
        anns = img.annotations or []
        for a in anns:
            box = _box(a)
            if box is None:
                continue
            area = box[2] * imgsz * box[3] * imgsz
            buckets[
                "small"
                if area < SMALL_PX**2
                else "medium"
                if area < MEDIUM_PX**2
                else "large"
            ] += 1
        flags.extend(_quality_flags(img, anns, imgsz))
    cached = _cached(db, project)
    if not cached and auto_scan:
        enqueue(db, project)
    return {
        "imgsz": imgsz,
        "size_buckets": {k: buckets[k] for k in ("small", "medium", "large")},
        "label_quality": flags,
        "missing_boxes": cached.get("missing_boxes") or [],
        "leakage_pairs": cached.get("leakage_pairs") or 0,
    }


def recommendations(checks: dict) -> list[dict]:
    """Plain-language next steps for the Health page; `suggest` carries the one-click values."""
    out = []
    buckets = checks.get("size_buckets") or {}
    total = sum(buckets.values())
    imgsz = checks.get("imgsz") or 640
    if total and buckets.get("small", 0) / total >= SMALL_SHARE:
        target = 1024 if imgsz <= 768 else 1280
        pct = round(buckets["small"] / total * 100)
        out.append(
            {
                "key": "imgsz",
                "message": f"{pct} % objects are small at {imgsz} → try {target} or tiling",
                "suggest": {"imgsz": target},
            }
        )
    if flags := checks.get("label_quality") or []:
        n = len(flags)
        out.append(
            {
                "key": "label_quality",
                "message": f"{n} {'annotation looks' if n == 1 else 'annotations look'} wrong (tiny, out of bounds, "
                "zero area or duplicate) — review the flagged images",
                "suggest": {"filter": "label_quality"},
            }
        )
    if boxes := checks.get("missing_boxes") or []:
        n = len(boxes)
        out.append(
            {
                "key": "missing_boxes",
                "message": f"{n} model {'detection has' if n == 1 else 'detections have'} no matching label "
                "— check for missing boxes",
                "suggest": {"filter": "missing_boxes"},
            }
        )
    if pairs := checks.get("leakage_pairs") or 0:
        out.append(
            {
                "key": "leakage",
                "message": f"{pairs} near-duplicate image {'pair' if pairs == 1 else 'pairs'} may leak across "
                "splits — version again with near-duplicate grouping",
                "suggest": {"fix": "leakage"},
            }
        )
    return out
