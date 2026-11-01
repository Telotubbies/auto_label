"""Derived evaluation analytics: confidence sweep, per-class PR, calibration and slice AP.

All inputs are the stored `TrainedModel.metrics["eval"]` detail sample (Task 8 caps it at 120 images
and 100 predictions per image) plus the project's image metadata. No inference, no writes.
"""

from __future__ import annotations

import contextlib
import io
import json
import math
import threading
from pathlib import Path

from PIL import Image as PImage
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import DATA_DIR
from ..models import Batch, Image, TrainedModel

SWEEP = [
    round(0.05 * i, 2) for i in range(1, 20)
]  # 0.05 .. 0.95, same grid as evaluate()
IOU = 0.5
BIN_LABELS = [
    f"{lo:.1f}–{min(1.0, lo + 0.1):.1f}"
    for lo in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
]
SIZE_BUCKETS = (
    ("< 0.3 MP", 0.0, 0.3),
    ("0.3–1 MP", 0.3, 1.0),
    ("1–4 MP", 1.0, 4.0),
    ("> 4 MP", 4.0, math.inf),
)
BRIGHTNESS_BUCKETS = (
    ("dark", 0.0, 0.35),
    ("normal", 0.35, 0.65),
    ("bright", 0.65, 1.01),
)
MAX_SLICE_VALUES = 8
DIMENSIONS = ("size", "tag", "batch", "split", "brightness", "source")

_COCO_LOCK = (
    threading.Lock()
)  # redirect_stdout is process-wide; serialise pycocotools calls
_BRIGHT: dict[tuple[str, float], float | None] = {}
_BRIGHT_LOCK = threading.Lock()


def classes_for(
    ev: dict, detections: list[dict], fallback: list[str] | None
) -> list[str]:
    """Class names as they appear in the evaluation (a rename after eval must not empty the charts)."""
    names = [c.get("class") for c in ev.get("per_class") or [] if c.get("class")]
    names += [p.get("cls") for d in detections for p in d.get("pred") or []]
    names += [g.get("cls") for d in detections for g in d.get("gt") or []]
    return list(dict.fromkeys(n for n in names if n)) or list(fallback or [])


def _iou(a: list[float], b: list[float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def match(gt: list[dict], pred: list[dict], conf: float) -> list[tuple[int, int]]:
    """Greedy class-aware (gt index, pred index) pairs at IoU >= 0.5, predictions by score."""
    used: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for pi in sorted(range(len(pred)), key=lambda i: -pred[i].get("conf", 0)):
        p = pred[pi]
        if p.get("conf", 0) < conf:
            continue
        best_iou, best_gi = IOU, -1
        for gi, g in enumerate(gt):
            if gi in used or g.get("cls") != p.get("cls"):
                continue
            value = _iou(g.get("bbox") or [], p.get("bbox") or [])
            if value >= best_iou:
                best_iou, best_gi = value, gi
        if best_gi >= 0:
            used.add(best_gi)
            pairs.append((best_gi, pi))
    return pairs


def f1_curve(detections: list[dict]) -> list[dict]:
    out = []
    for conf in SWEEP:
        tp = fp = fn = 0
        for d in detections:
            gt, pred = d.get("gt") or [], d.get("pred") or []
            pairs = match(gt, pred, conf)
            above = sum(1 for p in pred if p.get("conf", 0) >= conf)
            tp += len(pairs)
            fp += above - len(pairs)
            fn += len(gt) - len(pairs)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (
            2 * precision * recall / (precision + recall) if precision + recall else 0.0
        )
        out.append(
            {
                "conf": conf,
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
            }
        )
    return out


def per_class_pr(detections: list[dict], classes: list[str]) -> list[dict]:
    out = []
    for cls in classes:
        has_gt = any(
            any(g.get("cls") == cls for g in d.get("gt") or []) for d in detections
        )
        has_pred = any(
            any(p.get("cls") == cls for p in d.get("pred") or []) for d in detections
        )
        if not (has_gt or has_pred):
            continue
        points = []
        for conf in SWEEP:
            tp = fp = fn = 0
            for d in detections:
                gt = [g for g in d.get("gt") or [] if g.get("cls") == cls]
                pred = [p for p in d.get("pred") or [] if p.get("cls") == cls]
                pairs = match(gt, pred, conf)
                above = sum(1 for p in pred if p.get("conf", 0) >= conf)
                tp += len(pairs)
                fp += above - len(pairs)
                fn += len(gt) - len(pairs)
            points.append(
                {
                    "recall": round(tp / (tp + fn), 4) if tp + fn else 0.0,
                    "precision": round(tp / (tp + fp), 4) if tp + fp else 0.0,
                }
            )
        points.sort(key=lambda p: p["recall"])
        out.append({"class": cls, "points": points})
    return out


def calibration(detections: list[dict]) -> dict:
    """Reliability diagram inputs: per confidence bin, mean confidence vs observed precision (IoU >= 0.5)."""
    bins = [
        {"bin": label, "conf": 0.0, "accuracy": 0.0, "count": 0} for label in BIN_LABELS
    ]
    conf_sum = [0.0] * len(BIN_LABELS)
    hit_sum = [0] * len(BIN_LABELS)
    total = 0
    brier = 0.0
    for d in detections:
        gt, pred = d.get("gt") or [], d.get("pred") or []
        matched = {pi for _, pi in match(gt, pred, 0.0)}
        for pi, p in enumerate(pred):
            conf = float(p.get("conf") or 0.0)
            idx = min(len(BIN_LABELS) - 1, max(0, int(conf * 10)))
            ok = pi in matched
            bins[idx]["count"] += 1
            conf_sum[idx] += conf
            hit_sum[idx] += int(ok)
            total += 1
            brier += (conf - (1.0 if ok else 0.0)) ** 2
    ece = 0.0
    for i, b in enumerate(bins):
        if b["count"]:
            b["conf"] = round(conf_sum[i] / b["count"], 4)
            b["accuracy"] = round(hit_sum[i] / b["count"], 4)
            ece += (b["count"] / total) * abs(b["accuracy"] - b["conf"])
    return {
        "bins": bins,
        "ece": round(ece, 4),
        "brier": round(brier / total, 4) if total else 0.0,
    }


def slices(
    db: Session, m: TrainedModel, detections: list[dict], split: str, classes: list[str]
) -> list[dict]:
    if not detections:
        return []
    meta = image_meta(db, m, detections, split)
    groups: dict[str, dict[str, list[str]]] = {dim: {} for dim in DIMENSIONS}
    for d in detections:
        info = meta.get(d["file"], {})
        for dim, value in _slice_values(d, info):
            groups[dim].setdefault(value, []).append(d["file"])

    out = []
    for dim, values in groups.items():
        kept = sorted(values.items(), key=lambda kv: (-len(kv[1]), kv[0]))[
            :MAX_SLICE_VALUES
        ]
        for value, files in kept:
            wanted = set(files)
            subset = [d for d in detections if d["file"] in wanted]
            scores = ap_scores(subset, classes)
            out.append(
                {
                    "dimension": dim,
                    "value": value,
                    "images": len(files),
                    "instances": sum(len(d.get("gt") or []) for d in subset),
                    "AP": scores["AP"],
                    "AP50": scores["AP50"],
                }
            )
    return out


def _slice_values(d: dict, info: dict) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    w = int(info.get("width") or d.get("width") or 0)
    h = int(info.get("height") or d.get("height") or 0)
    mp = (w * h) / 1_000_000 if w and h else 0.0
    for label, lo, hi in SIZE_BUCKETS:
        if lo <= mp < hi:
            values.append(("size", label))
            break
    for tag in info.get("tags") or []:
        values.append(("tag", str(tag)))
    if info.get("batch"):
        values.append(("batch", str(info["batch"])))
    values.append(("split", str(info.get("split") or "unknown")))
    bright = info.get("brightness")
    if bright is not None:
        for label, lo, hi in BRIGHTNESS_BUCKETS:
            if lo <= bright < hi:
                values.append(("brightness", label))
                break
    values.append(("source", str(info.get("source") or "human")))
    return values


def image_meta(
    db: Session, m: TrainedModel, detections: list[dict], split: str
) -> dict[str, dict]:
    """Map eval file name -> Image row via the version manifest (split/file -> source image id)."""
    by_key: dict[str, str] = {}
    by_name: dict[str, str] = {}
    manifest = DATA_DIR / "versions" / m.version_id / "manifest.json"
    if manifest.exists():
        try:
            for item in json.loads(manifest.read_text()).get("items") or []:
                name = Path(item.get("file", "")).name
                by_key[f"{item.get('split')}/{name}"] = item.get("source")
                by_name.setdefault(name, item.get("source"))
        except (OSError, ValueError):
            by_key, by_name = {}, {}
    ids = {i for i in by_key.values() if i} | {i for i in by_name.values() if i}
    rows = (
        {
            r.id: r
            for r in db.scalars(
                select(Image).where(Image.id.in_(ids), Image.project_id == m.project_id)
            ).all()
        }
        if ids
        else {}
    )
    batch_ids = {r.batch_id for r in rows.values() if r.batch_id}
    batches = (
        {
            b.id: b.name
            for b in db.scalars(select(Batch).where(Batch.id.in_(batch_ids))).all()
        }
        if batch_ids
        else {}
    )

    meta: dict[str, dict] = {}
    for d in detections:
        name = Path(d["file"]).name
        row = rows.get(by_key.get(f"{split}/{name}") or by_name.get(name))
        if row is None:
            meta[d["file"]] = {
                "width": d.get("width"),
                "height": d.get("height"),
                "split": split,
                "tags": [],
                "batch": None,
                "source": "human",
                "brightness": None,
            }
            continue
        meta[d["file"]] = {
            "width": row.width,
            "height": row.height,
            "split": row.split,
            "tags": list(row.tags or []),
            "batch": batches.get(row.batch_id),
            "source": _label_source(row.annotations or []),
            "brightness": _brightness(row),
        }
    return meta


def _label_source(annotations: list[dict]) -> str:
    sources = {(a.get("source") or "human") for a in annotations}
    human = "human" in sources
    ai = bool(sources - {"human"})
    if human and ai:
        return "mixed"
    return "ai" if ai else "human"


def _brightness(row: Image) -> float | None:
    rel = row.thumb or row.path
    if not rel:
        return None
    path = DATA_DIR / rel
    try:
        key = (str(path), path.stat().st_mtime)
    except OSError:
        return None
    with _BRIGHT_LOCK:
        if key in _BRIGHT:
            return _BRIGHT[key]
    try:
        with PImage.open(path) as im:
            grey = im.convert("L").resize((32, 32))
            value = round(sum(grey.tobytes()) / (255 * 1024), 4)
    except (OSError, ValueError):
        value = None
    with _BRIGHT_LOCK:
        _BRIGHT[key] = value
        if len(_BRIGHT) > 4096:
            _BRIGHT.clear()
    return value


def ap_scores(records: list[dict], classes: list[str]) -> dict:
    """COCO AP/AP50 for a subset of stored detections (boxes; masks are not stored per detection)."""
    name_to_id = {name: i + 1 for i, name in enumerate(classes)}
    images, anns, dets = [], [], []
    for i, r in enumerate(records):
        images.append(
            {
                "id": i + 1,
                "file_name": r.get("file", str(i)),
                "width": r.get("width") or 1,
                "height": r.get("height") or 1,
            }
        )
        for g in r.get("gt") or []:
            cid = name_to_id.get(g.get("cls"))
            box = g.get("bbox") or []
            if cid is None or len(box) != 4:
                continue
            anns.append(
                {
                    "id": len(anns) + 1,
                    "image_id": i + 1,
                    "category_id": cid,
                    "bbox": list(box),
                    "area": max(1.0, float(box[2]) * float(box[3])),
                    "iscrowd": 0,
                }
            )
        for p in r.get("pred") or []:
            cid = name_to_id.get(p.get("cls"))
            box = p.get("bbox") or []
            if cid is None or len(box) != 4:
                continue
            dets.append(
                {
                    "image_id": i + 1,
                    "category_id": cid,
                    "bbox": list(box),
                    "score": float(p.get("conf") or 0.0),
                }
            )
    if not anns:
        return {"AP": None, "AP50": None}
    if not dets:
        return {"AP": 0.0, "AP50": 0.0}
    coco = COCO()
    coco.dataset = {
        "images": images,
        "annotations": anns,
        "categories": [{"id": i + 1, "name": n} for i, n in enumerate(classes)],
    }
    with _COCO_LOCK, contextlib.redirect_stdout(io.StringIO()):
        coco.createIndex()
        dt = coco.loadRes(dets)
        ev = COCOeval(coco, dt, "bbox")
        ev.evaluate()
        ev.accumulate()
        ev.summarize()
        stats = list(ev.stats)
    return {"AP": _stat(stats[0]), "AP50": _stat(stats[1])}


def _stat(value: float) -> float | None:
    if value is None or not math.isfinite(value) or value < 0:
        return None
    return round(min(float(value), 1.0), 4)
