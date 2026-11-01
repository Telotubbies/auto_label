"""Health-check read models and recommendations.

Object-size buckets and geometry flags are cheap and read straight from the image rows. The two
expensive checks — pHash grouping and model inference for missing boxes — live in `health_scan`, run
in the `health` worker job, and are cached on the job row; the analytics request only reads that row.
"""

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Image, Project
from . import health_scan
from .health_scan import (  # re-exported for routers/worker/tests
    box,
    cached,
    enqueue,
    is_human,
    job_state,
    job_summary,
    scan_health,
    signature,
)

SMALL_PX = 32.0  # COCO: small objects are under 32x32 px at the training size
MEDIUM_PX = 96.0
TINY_PX = 2.0  # below this a box cannot be drawn/inspected reliably
DUPLICATE_IOU = 0.9
SMALL_SHARE = 0.3  # recommend a larger imgsz when this share of objects is small
EPS = 1e-6

__all__ = [
    "checks",
    "compute_checks",
    "enqueue",
    "job_state",
    "job_summary",
    "recommendations",
    "scan_health",
    "signature",
]


def _quality_flags(img: Image, anns: list[dict], imgsz: int) -> list[dict]:
    out, seen = [], []
    for a in anns:
        b = box(a)
        if b is None:  # classification labels carry no geometry
            continue
        x, y, w, h = b
        wpx, hpx = w * imgsz, h * imgsz
        kind = None
        if w <= 0 or h <= 0:
            kind = "zero_area"
        elif x < -EPS or y < -EPS or x + w > 1 + EPS or y + h > 1 + EPS:
            kind = "out_of_bounds"
        elif wpx < TINY_PX or hpx < TINY_PX:
            kind = "tiny"
        elif is_human(a):
            for prev_ann, prev_box in seen:
                if (
                    is_human(prev_ann)
                    and prev_ann.get("classId") == a.get("classId")
                    and health_scan.iou(prev_box, b) >= DUPLICATE_IOU
                ):
                    kind = "duplicate"
                    break
        if kind:
            out.append({"kind": kind, "image_id": img.id, "annotation_id": a.get("id")})
        if kind != "zero_area" and is_human(a):
            seen.append((a, b))
    return out


def _annotation_summary(rows: list[Image], imgsz: int) -> tuple[dict, list[dict]]:
    """The bucket/flag loop shared by `compute_checks` (job/tests) and `checks` (analytics read)."""
    buckets = Counter()
    flags: list[dict] = []
    for img in rows:
        anns = img.annotations or []
        for a in anns:
            b = box(a)
            if b is None:
                continue
            area = b[2] * imgsz * b[3] * imgsz
            buckets["small" if area < SMALL_PX**2 else "medium" if area < MEDIUM_PX**2 else "large"] += 1
        flags.extend(_quality_flags(img, anns, imgsz))
    return {k: buckets[k] for k in ("small", "medium", "large")}, flags


def _rows(db: Session, project: Project) -> list[Image]:
    return db.scalars(select(Image).where(Image.project_id == project.id, Image.deleted_at.is_(None))).all()


def compute_checks(db: Session, project: Project, imgsz: int = 640) -> dict:
    """Everything a scan produces, computed now. Used by direct callers/tests, never by analytics."""
    buckets, flags = _annotation_summary(_rows(db, project), imgsz)
    scanned = scan_health(db, project)["checks"]
    return {
        "imgsz": imgsz,
        "size_buckets": buckets,
        "label_quality": flags,
        "missing_boxes": scanned.get("missing_boxes") or [],
        "leakage_pairs": scanned.get("leakage_pairs") or 0,
    }


def checks(db: Session, project: Project, imgsz: int = 640, *, auto_scan: bool = True) -> dict:
    """Health data for the analytics page: cheap buckets/flags now, pHash + missing boxes from the job.

    `auto_scan=False` keeps annotators from queueing GPU work just by opening the page. A failed or
    running scan for this dataset/model blocks a new automatic enqueue (no retry loop on polling)."""
    buckets, flags = _annotation_summary(_rows(db, project), imgsz)
    scanned, blocked = cached(db, project)
    if not scanned and auto_scan and not blocked:
        enqueue(db, project)
    return {
        "imgsz": imgsz,
        "size_buckets": buckets,
        "label_quality": flags,
        "missing_boxes": scanned.get("missing_boxes") or [],
        "leakage_pairs": scanned.get("leakage_pairs") or 0,
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
