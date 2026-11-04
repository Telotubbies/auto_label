"""Pure aggregation for the Insights Studio dataset analytics.

Every function takes image rows, classes and audit rows and returns the JSON payload a chart
needs: no DB access, no file IO. `insights` owns caching and the router stays thin.
"""

import math
import time
from collections import Counter

from . import imaging, labeler_stats

SPLITS = ("train", "valid", "test")
SMALL_PX = 32.0  # COCO small objects are under 32x32 px at the training size
MEDIUM_PX = 96.0
SCATTER_MAX = 2000
CELLS = 10
ASPECT_BUCKETS = ("<0.5", "0.5–1", "1–2", "2–4", "≥4")
ANN_BUCKETS = tuple(str(i) for i in range(20)) + ("20+",)
DAY = 86400
WINDOW_DAYS = 90


def box(ann) -> tuple[float, float, float, float] | None:
    """Normalized (x, y, w, h) for a usable annotation; tolerates hand-edited/legacy JSON."""
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


def _maps(classes: list) -> tuple[dict, list]:
    return {c.id: c.name for c in classes}, [c.name for c in classes]


def _split(row, split_of: dict | None) -> str:
    return (split_of or {}).get(row.id, row.split)


def _source(ann: dict) -> str:
    src = ann.get("source")
    return src if isinstance(src, str) and src.strip() else "human"


def _class_name(names: dict, ann: dict) -> str | None:
    cid = ann.get("classId")
    return names.get(cid) if isinstance(cid, str) else None


def _annotations(row) -> list[dict]:
    return [a for a in (row.annotations or []) if isinstance(a, dict)]


def summary(rows: list, classes: list, split_of: dict | None = None) -> dict:
    """Headline counts, split totals, per-class instances/images and label sources."""
    names, _ = _maps(classes)
    splits: Counter = Counter()
    counts: Counter = Counter()
    images: Counter = Counter()
    sources: Counter = Counter()
    annotations = null = 0
    for row in rows:
        anns = _annotations(row)
        splits[_split(row, split_of)] += 1
        annotations += len(anns)
        null += not anns
        present = set()
        for ann in anns:
            sources[_source(ann)] += 1
            name = _class_name(names, ann)
            if name:
                counts[name] += 1
                present.add(name)
        for name in present:
            images[name] += 1
    total_sources = sum(sources.values())
    return {
        "images": len(rows),
        "annotations": annotations,
        "null_images": null,
        "splits": {s: splits.get(s, 0) for s in SPLITS},
        "classes": [
            {
                "id": c.id,
                "name": c.name,
                "color": c.color,
                "count": counts.get(c.name, 0),
                "images": images.get(c.name, 0),
            }
            for c in classes
        ],
        "sources": [
            {
                "source": src,
                "annotations": n,
                "share": round(n / total_sources, 4) if total_sources else 0.0,
            }
            for src, n in sorted(sources.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
    }


def distribution(rows: list, classes: list, split_of: dict | None = None) -> dict:
    """Class × split, instances vs images, class co-occurrence and annotations-per-image."""
    names, order = _maps(classes)
    per_split = {name: {s: 0 for s in SPLITS} for name in order}
    instances: Counter = Counter()
    images: Counter = Counter()
    co: dict[str, Counter] = {name: Counter() for name in order}
    per_image: Counter = Counter()
    for row in rows:
        anns = _annotations(row)
        per_image[min(len(anns), 20)] += 1
        present = set()
        for ann in anns:
            name = _class_name(names, ann)
            if not name:
                continue
            instances[name] += 1
            split = _split(row, split_of)
            if split in SPLITS:
                per_split[name][split] += 1
            present.add(name)
        for name in present:
            images[name] += 1
            for other in present:
                co[name][other] += 1
    return {
        "split_classes": [{"class": name, **per_split[name]} for name in order],
        "instances_vs_images": [
            {
                "class": name,
                "instances": instances.get(name, 0),
                "images": images.get(name, 0),
            }
            for name in order
        ],
        "cooccurrence": {
            "classes": order,
            "matrix": [[co[a][b] for b in order] for a in order],
        },
        "annotations_per_image": [
            {
                "bucket": bucket,
                "images": per_image.get(int(bucket) if bucket != "20+" else 20, 0),
            }
            for bucket in ANN_BUCKETS
        ],
    }


def geometry(rows: list, classes: list, imgsz: int = 640, split_of: dict | None = None) -> dict:
    """Box scatter, COCO S/M/L areas, aspect ratios and a per-class 10x10 centre heatmap."""
    names, order = _maps(classes)
    scatter: list[dict] = []
    areas: Counter = Counter()
    aspect: Counter = Counter()
    centres = {name: [0] * (CELLS * CELLS) for name in order}
    for row in rows:
        for ann in row.annotations or []:
            bounds = box(ann)
            if bounds is None:
                continue
            x, y, w, h = bounds
            name = _class_name(names, ann) or "unknown"
            scatter.append(
                {
                    "w": round(w, 6),
                    "h": round(h, 6),
                    "class": name,
                    "split": _split(row, split_of),
                    "area": round(w * h, 6),
                }
            )
            px_area = (w * imgsz) * (h * imgsz)
            areas["small" if px_area < SMALL_PX**2 else "medium" if px_area < MEDIUM_PX**2 else "large"] += 1
            ratio = w / h if h else math.inf
            aspect[
                "<0.5"
                if ratio < 0.5
                else "0.5–1"
                if ratio < 1
                else "1–2"
                if ratio < 2
                else "2–4"
                if ratio < 4
                else "≥4"
            ] += 1
            cells = centres.get(name)
            if cells is not None:
                cx = min(0.999999, max(0.0, x + w / 2))
                cy = min(0.999999, max(0.0, y + h / 2))
                cells[int(cy * CELLS) * CELLS + int(cx * CELLS)] += 1
    sampled = len(scatter) > SCATTER_MAX
    if sampled:  # deterministic stride keeps the chart bounded without random sampling
        scatter = scatter[:: math.ceil(len(scatter) / SCATTER_MAX)][:SCATTER_MAX]
    return {
        "imgsz": imgsz,
        "box_scatter": scatter,
        "area_buckets": {k: areas.get(k, 0) for k in ("small", "medium", "large")},
        "aspect": [{"bucket": b, "count": aspect.get(b, 0)} for b in ASPECT_BUCKETS],
        "centres": [{"class": name, "cells": centres[name]} for name in order],
        "sampled": sampled,
    }


def _date(ts: float) -> str:
    # Same local-day bucket as labeler_stats.throughput, so one dashboard cannot split a day.
    return time.strftime("%Y-%m-%d", time.localtime(float(ts)))


def labeling(rows: list, audits: list, users: dict, events: list) -> dict:
    """Throughput per labeler/day, review decisions and provenance-based AI acceptance.

    Throughput and acceptance come from `labeler_stats`, the same definition the QA dashboard
    uses, so the two pages cannot report different numbers for the same saves.
    """
    review: dict[str, dict] = {}
    for audit in audits:
        approved = (audit.meta or {}).get("approved")
        if approved not in (True, False):
            continue
        date = _date(audit.created)
        entry = review.setdefault(date, {"date": date, "approved": 0, "rejected": 0, "rate": 0.0})
        entry["approved" if approved else "rejected"] += 1
    for entry in review.values():
        total = entry["approved"] + entry["rejected"]
        entry["rate"] = round(entry["rejected"] / total, 4) if total else 0.0
    review_rows = [review[d] for d in sorted(review)]

    throughput = [
        {"date": row["date"], "labeler_id": row["user_id"], "labeler": users.get(row["user_id"]) or "Unassigned",
         "annotations": row["annotations"], "images": row["images"]}
        for row in labeler_stats.throughput(events)
    ]

    # Human/AI-source counts describe what is on the images now; acceptance is the shared
    # provenance measure (AI ids still present on accepted images), not a second definition.
    human = 0
    by_source: Counter = Counter()
    for row in rows:
        for ann in row.annotations or []:
            if not isinstance(ann, dict):
                continue
            src = ann.get("source")
            if not isinstance(src, str) or not src.strip() or src == "human":
                human += 1
            else:
                by_source[src] += 1
    kept, seen = labeler_stats.project_ai_acceptance(events, {row.id: row for row in rows})
    top = sorted(by_source.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
    return {
        "throughput": throughput,
        "throughput_basis": "label_event",
        "review": review_rows,
        "ai": {
            "human": human,
            "ai": seen,
            "accepted_ai": kept,
            "acceptance_rate": labeler_stats.rate(kept, seen),
            "by_source": [{"source": src, "count": n} for src, n in top],
        },
    }
