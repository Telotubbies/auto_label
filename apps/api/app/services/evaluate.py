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
from pycocotools import mask as mask_utils
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
TIDE_FOREGROUND = 0.1            # a prediction/gt pair closer than this is background/dupe
TIDE_TYPES = ("cls", "loc", "both", "dupe", "bkg", "missed")


def evaluate(model_ref: str, version_dir: Path, task: str, db=None,
             workspace_id: str | None = None) -> dict:
    """Score `model_ref` on the version's test split (valid when test is empty)."""
    if task == "classify":
        return _empty("test", "classification models are not evaluated with COCO metrics")

    coco_dir = _export_dir(Path(version_dir), db)
    split, note = _pick_split(coco_dir)
    if "skipped" in note:
        return _empty(split, note)

    iou_type = "segm" if task == "segment" else "bbox"
    ann_path = coco_dir / split / "_annotations.coco.json"
    coco, images = _load_ground_truth(ann_path, iou_type)
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
            preds.append({"cls": p["class"], "conf": float(p["confidence"]), "bbox": box,
                          "points": p.get("points")})
            detections.append(_detection(img["id"], preds[-1], cat_ids, iou_type))
        records.append({"file": img["file_name"], "image_id": img["id"],
                        "width": img["width"], "height": img["height"],
                        "gt": [{"cls": cat_names[a["category_id"]], "bbox": list(a["bbox"]),
                                "segm": a.get("segmentation")}
                               for a in coco.imgToAnns.get(img["id"], [])],
                        "pred": preds})

    with contextlib.redirect_stdout(io.StringIO()):        # loadRes prints progress too
        dt = coco.loadRes(detections) if detections else None
    stats = _coco_stats(coco, dt, iou_type)
    per_class = []
    for cat in categories:
        s = _coco_stats(coco, dt, iou_type, [cat["id"]])
        per_class.append({"class": cat["name"], "AP": _stat(s[0]), "AP50": _stat(s[1])})

    curve, f1_best = _sweep(records)        # F1/confusion stay box-based: the UI shows boxes
    tide = _tide(coco, records, iou_type, cat_ids, _stat(stats[0]), f1_best["conf"])
    return {
        "split": split,
        "note": note,
        "iou": iou_type,
        "coco": {k: _stat(stats[i]) for i, k in enumerate(COCO_KEYS)},
        "tide": tide,
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
    return {"split": split, "note": note, "iou": "bbox",
            "coco": {k: 0.0 for k in COCO_KEYS},
            "tide": {k: 0.0 for k in TIDE_TYPES},
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


def _load_ground_truth(path: Path, iou_type: str = "bbox") -> tuple[COCO, list]:
    data = json.loads(path.read_text())
    for i, ann in enumerate(data["annotations"]):
        ann["id"] = i + 1                    # pycocotools treats gt id 0 as "unmatched"
        if iou_type == "segm":
            if not ann.get("segmentation"):  # bbox-only annotation in a segmentation project
                x, y, w, h = ann["bbox"]
                ann["segmentation"] = [[x, y, x + w, y, x + w, y + h, x, y + h]]
            ann["area"] = max(_poly_area(ann["segmentation"][0]), 1.0)
    coco = COCO()
    coco.dataset = data
    with contextlib.redirect_stdout(io.StringIO()):
        coco.createIndex()
    return coco, data["images"]


def _detection(image_id: int, p: dict, cat_ids: dict, iou_type: str) -> dict:
    """One COCO result record for a prediction; `p` carries class, score, box and mask points."""
    box = list(p["bbox"])
    det = {"image_id": image_id, "category_id": cat_ids[p["cls"]], "bbox": box, "score": p["conf"]}
    if iou_type == "segm":
        det["segmentation"] = [_polygon(p, box)]
    return det


def _rect(box: list[float]) -> list[float]:
    x, y, w, h = box
    return [x, y, x + w, y, x + w, y + h, x, y + h]


def _polygon(p: dict, box: list[float]) -> list[float]:
    """Prediction mask polygon in pixels; a box rectangle when the adapter returned no mask points."""
    pts = p.get("points")
    if pts and len(pts) >= 3:
        return [v for q in pts for v in (q["x"], q["y"])]
    return _rect(box)


def _gt_polygon(g: dict, box: list[float]) -> list[float]:
    """Ground-truth mask polygon in pixels; a box rectangle when the gt has no mask."""
    segm = g.get("segm")
    return list(segm[0]) if segm else _rect(box)


def _mask_iou(a: list[float], b: list[float], h: int, w: int) -> float:
    """Mask IoU between two flat pixel polygons (pycocotools rasterisation)."""
    try:
        ra, rb = mask_utils.frPyObjects([a, b], h, w)
        return float(mask_utils.iou([ra], [rb], [0])[0][0])
    except Exception:                      # a degenerate polygon has no area to match
        return 0.0


def _poly_area(flat: list[float]) -> float:
    """Shoelace area of a flat [x1,y1,x2,y2,...] polygon."""
    xs, ys = flat[0::2], flat[1::2]
    return abs(sum(xs[i] * ys[(i + 1) % len(xs)] - xs[(i + 1) % len(xs)] * ys[i]
                   for i in range(len(xs)))) / 2 if len(xs) >= 3 else 0.0


def _coco_stats(coco: COCO, dt, iou_type: str = "bbox", cat_ids: list[int] | None = None) -> list[float]:
    if dt is None:
        return [0.0] * len(COCO_KEYS)
    ev = COCOeval(coco, dt, iou_type)
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
        errors = (above - len(pairs)) + (len(r["gt"]) - len(pairs))
        if errors > 0:                       # only images the model actually got wrong
            scored.append((errors, r["file"]))
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


# --- TIDE error buckets -------------------------------------------------------------------
# `tidecv` is not a dependency, so the six buckets are classified here and each one is scored by
# re-running COCOeval on a corrected detection list. Six extra evaluations per model is fine:
# this runs in the training worker, not on the request path.

def _tide_classify(rec: dict, conf: float, iou_type: str) -> tuple[list, list[int]]:
    """Per-prediction TIDE label plus the gt indices left uncovered.

    Greedy on descending score against the highest-IoU unused gt at IoU >= TIDE_FOREGROUND,
    ignoring class: a confident box that lands on the wrong class still explains that gt.
    Segmentation projects match on mask IoU, because a mask-only error is invisible to the boxes.
    Predictions below `conf` (the operating threshold) are never corrected.
    """
    gt, pred = rec["gt"], rec["pred"]
    size = (rec["height"], rec["width"])

    def pair_iou(g: dict, p: dict) -> float:
        if iou_type == "segm":
            return _mask_iou(_gt_polygon(g, g["bbox"]), _polygon(p, p["bbox"]), *size)
        return _iou(g["bbox"], p["bbox"])

    used: set[int] = set()
    matched_cls: dict[int, str] = {}
    fixes: list[tuple[str, int] | None] = [None] * len(pred)
    for pi in sorted(range(len(pred)), key=lambda i: -pred[i]["conf"]):
        p = pred[pi]
        if p["conf"] < conf:
            continue
        best_iou, best_gi = TIDE_FOREGROUND, -1
        for gi, g in enumerate(gt):
            if gi in used:
                continue
            iou = pair_iou(g, p)
            if iou >= best_iou:
                best_iou, best_gi = iou, gi
        if best_gi < 0:
            # nothing near this box: a duplicate when it repeats an already-matched same-class gt
            dupe = any(cls == p["cls"] and pair_iou(gt[gi], p) >= TIDE_FOREGROUND
                       for gi, cls in matched_cls.items())
            fixes[pi] = ("dupe" if dupe else "bkg", -1)
            continue
        used.add(best_gi)
        matched_cls[best_gi] = gt[best_gi]["cls"]
        same = gt[best_gi]["cls"] == p["cls"]
        if same:
            fixes[pi] = None if best_iou >= IOU else ("loc", best_gi)
        else:
            fixes[pi] = ("cls", best_gi) if best_iou >= IOU else ("both", best_gi)
    return fixes, [gi for gi in range(len(gt)) if gi not in used]


def _tide_corrected(records: list[dict], classified: list, cat_ids: dict,
                    iou_type: str, kind: str) -> list[dict]:
    """The detection list with every error of one TIDE type repaired, everything else untouched."""
    out = []
    for r, (fixes, missed) in zip(records, classified):
        for p, fix in zip(r["pred"], fixes):
            if fix is None or fix[0] != kind:       # untouched detection goes through as-is
                out.append(_detection(r["image_id"], p, cat_ids, iou_type))
                continue
            if kind in ("dupe", "bkg"):             # dropping the false positive is the fix
                continue
            g = r["gt"][fix[1]]
            det = _detection(r["image_id"], p, cat_ids, iou_type)
            if kind in ("cls", "both"):
                det["category_id"] = cat_ids[g["cls"]]
            if kind in ("loc", "both"):
                det["bbox"] = list(g["bbox"])
                if iou_type == "segm":              # the mask must follow the corrected box
                    det["segmentation"] = [_gt_polygon(g, det["bbox"])]
            out.append(det)
        if kind == "missed":
            for gi in missed:                       # a perfect detection on every missed gt
                g = r["gt"][gi]
                det = {"image_id": r["image_id"], "category_id": cat_ids[g["cls"]],
                       "bbox": list(g["bbox"]), "score": 1.0}
                if iou_type == "segm":
                    det["segmentation"] = [_gt_polygon(g, det["bbox"])]
                out.append(det)
    return out


def _load_res(coco: COCO, detections: list[dict]):
    if not detections:                             # loadRes cannot index an empty result list
        return None
    with contextlib.redirect_stdout(io.StringIO()):
        return coco.loadRes(detections)


def _tide(coco: COCO, records: list[dict], iou_type: str, cat_ids: dict,
          ap_base: float, conf: float) -> dict:
    """dAP recovered per TIDE error type: max(0, AP_fixed - AP_base), 4 decimals."""
    classified = [_tide_classify(r, conf, iou_type) for r in records]
    out = {}
    for kind in TIDE_TYPES:
        detections = _tide_corrected(records, classified, cat_ids, iou_type, kind)
        ap_fixed = _stat(_coco_stats(coco, _load_res(coco, detections), iou_type)[0])
        out[kind] = max(0.0, round(ap_fixed - ap_base, 4))
    return out
