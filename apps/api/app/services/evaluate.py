"""Evaluate a trained model against a version's held-out COCO split.

Returns COCO AP/AR, per-class AP, a confidence sweep (F1 + PR curve), a confusion
matrix at the best confidence, the worst images, and per-image detections that the
UI uses for its confidence slider.
"""
import contextlib
import io
import json
import math
import time
from pathlib import Path

from PIL import Image as PImage
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval

from ..adapters.catalog import resolve
from ..models import Version
from . import exporters, versioning

COCO_KEYS = ("AP", "AP50", "AP75", "APs", "APm", "APl", "AR1", "AR10", "AR100", "ARs", "ARm", "ARl")
SWEEP = [round(0.05 * i, 2) for i in range(1, 20)]      # 0.05 .. 0.95
MIN_CONF = 0.001                                        # keep everything for the sweep
IOU = 0.5
DETAIL_CONF = 0.05
MAX_DETAIL_IMAGES = 120
MAX_DETAIL_PREDS = 100
MAX_WORST = 12


def evaluate(model_ref: str, version_dir: Path, task: str, db=None,
             workspace_id: str | None = None) -> dict:
    """Score `model_ref` on the version's test split (valid when test is empty)."""
    if task == "classify":
        return _empty("test", "classification models are not evaluated with COCO metrics")

    coco_dir = _export_dir(Path(version_dir), db)
    split, note = _pick_split(coco_dir)
    if "skipped" in note:
        return _empty(split, note)

    ann_path = coco_dir / split / "_annotations.coco.json"
    coco, images = _load_ground_truth(ann_path)
    categories = coco.dataset["categories"]
    names = [c["name"] for c in categories]
    cat_ids = {c["name"]: c["id"] for c in categories}
    cat_names = {c["id"]: c["name"] for c in categories}

    model = resolve(model_ref, db, workspace_id=workspace_id)
    detections, records, latencies = [], [], []
    for img in images:
        im = PImage.open(coco_dir / split / img["file_name"]).convert("RGB")
        started = time.perf_counter()
        out = model.predict(im, conf=MIN_CONF, iou=IOU, classes=names)
        latencies.append(time.perf_counter() - started)

        preds = []
        for p in out.get("predictions", []):
            if p.get("class") not in cat_ids:           # not a category of this version
                continue
            box = [p["x"] - p["width"] / 2, p["y"] - p["height"] / 2, p["width"], p["height"]]
            preds.append({"cls": p["class"], "conf": float(p["confidence"]), "bbox": box})
            detections.append({"image_id": img["id"], "category_id": cat_ids[p["class"]],
                               "bbox": box, "score": float(p["confidence"])})
        records.append({"file": img["file_name"], "width": img["width"], "height": img["height"],
                        "gt": [{"cls": cat_names[a["category_id"]], "bbox": list(a["bbox"])}
                               for a in coco.imgToAnns.get(img["id"], [])],
                        "pred": preds})

    dt = coco.loadRes(detections) if detections else None
    stats = _coco_stats(coco, dt)
    per_class = []
    for cat in categories:
        s = _coco_stats(coco, dt, [cat["id"]])
        per_class.append({"class": cat["name"], "AP": _stat(s[0]), "AP50": _stat(s[1])})

    curve, f1_best = _sweep(records)
    return {
        "split": split,
        "note": note,
        "coco": {k: _stat(stats[i]) for i, k in enumerate(COCO_KEYS)},
        "per_class": per_class,
        "f1_best": f1_best,
        "confusion": _confusion(records, names + ["background"], f1_best["conf"]),
        "pr_curve": curve,
        "worst": _worst(records, f1_best["conf"]),
        "latency_ms": round(sum(latencies) / len(latencies) * 1000, 1) if latencies else 0.0,
        "detections": _detections(records),
        "split_images": len(images),
    }


def _empty(split: str, note: str) -> dict:
    return {"split": split, "note": note,
            "coco": {k: 0.0 for k in COCO_KEYS},
            "per_class": [], "f1_best": {"conf": 0.4, "f1": 0.0},
            "confusion": {"labels": [], "matrix": [], "images": []},
            "pr_curve": [], "worst": [], "latency_ms": 0.0, "detections": [], "split_images": 0}


def _export_dir(version_dir: Path, db) -> Path:
    if db is not None:
        version = db.get(Version, version_dir.name)
        if version is not None:
            return versioning.cached_export(version, "coco")
    return exporters.cached_export(version_dir, "coco")


def _pick_split(coco_dir: Path) -> tuple[str, str]:
    for split, note in (("test", ""),
                        ("valid", "the test split is empty — evaluated on the valid split instead")):
        path = coco_dir / split / "_annotations.coco.json"
        if path.exists() and json.loads(path.read_text()).get("images"):
            return split, note
    return "valid", "no test or valid images — evaluation skipped"


def _load_ground_truth(path: Path) -> tuple[COCO, list]:
    data = json.loads(path.read_text())
    for i, ann in enumerate(data["annotations"]):
        ann["id"] = i + 1                    # pycocotools treats gt id 0 as "unmatched"
    coco = COCO()
    coco.dataset = data
    coco.createIndex()
    return coco, data["images"]


def _coco_stats(coco: COCO, dt, cat_ids: list[int] | None = None) -> list[float]:
    if dt is None:
        return [0.0] * len(COCO_KEYS)
    ev = COCOeval(coco, dt, "bbox")
    if cat_ids is not None:
        ev.params.catIds = list(cat_ids)
    with contextlib.redirect_stdout(io.StringIO()):    # pycocotools prints a table per call
        ev.evaluate()
        ev.accumulate()
        ev.summarize()
    return [float(v) for v in ev.stats]


def _stat(value: float) -> float:
    if not math.isfinite(value) or value < 0:      # -1 marks an absent/undefined metric
        return 0.0
    return round(min(value, 1.0), 4)


def _iou(a: list[float], b: list[float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def _match(gt: list[dict], pred: list[dict], conf: float, same_class: bool = True) -> list[tuple[int, int]]:
    """Greedy (gt index, pred index) pairs at IoU >= 0.5, preds by descending score.

    same_class=False is only used for the confusion matrix: a helmet box predicted as a vest must
    land in the helmet→vest cell, not in two background cells.
    """
    used: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for pi in sorted(range(len(pred)), key=lambda i: -pred[i]["conf"]):
        p = pred[pi]
        if p["conf"] < conf:
            continue
        best_iou, best_gi = IOU, -1
        for gi, g in enumerate(gt):
            if gi in used or (same_class and g["cls"] != p["cls"]):
                continue
            iou = _iou(g["bbox"], p["bbox"])
            if iou >= best_iou:
                best_iou, best_gi = iou, gi
        if best_gi >= 0:
            used.add(best_gi)
            pairs.append((best_gi, pi))
    return pairs


def _sweep(records: list[dict]) -> tuple[list[dict], dict]:
    curve, best = [], {"conf": SWEEP[0], "f1": 0.0}
    for conf in SWEEP:
        tp = fp = fn = 0
        for r in records:
            pairs = _match(r["gt"], r["pred"], conf)
            above = sum(1 for p in r["pred"] if p["conf"] >= conf)
            tp += len(pairs)
            fp += above - len(pairs)
            fn += len(r["gt"]) - len(pairs)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        curve.append({"recall": round(recall, 4), "precision": round(precision, 4)})
        if f1 > best["f1"]:                          # strict: ties keep the lower conf
            best = {"conf": conf, "f1": round(f1, 4)}
    curve.sort(key=lambda p: p["recall"])
    return curve, best


def _confusion(records: list[dict], labels: list[str], conf: float) -> dict:
    index = {name: i for i, name in enumerate(labels)}
    bg = len(labels) - 1
    matrix = [[0] * len(labels) for _ in labels]
    images: list[list[list[str]]] = [[[] for _ in labels] for _ in labels]

    def add(row: int, col: int, file: str) -> None:
        matrix[row][col] += 1
        if file not in images[row][col]:
            images[row][col].append(file)

    for r in records:
        pairs = _match(r["gt"], r["pred"], conf, same_class=False)
        matched_gt = {gi for gi, _ in pairs}
        matched_preds = {pi for _, pi in pairs}
        for gi, pi in pairs:
            add(index[r["gt"][gi]["cls"]], index[r["pred"][pi]["cls"]], r["file"])
        for gi, g in enumerate(r["gt"]):
            if gi not in matched_gt:
                add(index[g["cls"]], bg, r["file"])
        for pi, p in enumerate(r["pred"]):
            if p["conf"] >= conf and pi not in matched_preds:
                add(bg, index[p["cls"]], r["file"])
    return {"labels": labels, "matrix": matrix, "images": images}


def _worst(records: list[dict], conf: float) -> list[str]:
    scored = []
    for r in records:
        pairs = _match(r["gt"], r["pred"], conf)
        above = sum(1 for p in r["pred"] if p["conf"] >= conf)
        scored.append(((above - len(pairs)) + (len(r["gt"]) - len(pairs)), r["file"]))
    scored.sort(key=lambda item: -item[0])
    return [name for _, name in scored[:MAX_WORST]]


def _detections(records: list[dict]) -> list[dict]:
    out = []
    for r in records[:MAX_DETAIL_IMAGES]:
        preds = sorted((p for p in r["pred"] if p["conf"] >= DETAIL_CONF),
                       key=lambda p: -p["conf"])[:MAX_DETAIL_PREDS]
        out.append({"file": r["file"], "width": r["width"], "height": r["height"],
                    "gt": [{"cls": g["cls"], "bbox": [round(v, 2) for v in g["bbox"]]}
                           for g in r["gt"]],
                    "pred": [{"cls": p["cls"], "conf": p["conf"],
                              "bbox": [round(v, 2) for v in p["bbox"]]} for p in preds]})
    return out
