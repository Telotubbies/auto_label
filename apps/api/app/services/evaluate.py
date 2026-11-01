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
                        "gt": [{"id": a["id"], "cls": cat_names[a["category_id"]],
                                "bbox": list(a["bbox"]), "segm": a.get("segmentation")}
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
    tide = _tide(coco, records, iou_type, cat_ids, _stat(stats[1]))
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


def _poly_mask(segm, h: int, w: int):
    """Compressed RLE for a COCO segmentation: polygon list (all parts), RLE, or None."""
    if isinstance(segm, dict):
        counts = segm.get("counts")
        if isinstance(counts, (bytes, str)):
            return segm                        # already compressed
        return mask_utils.frPyObjects(segm, h, w) if counts is not None else None
    if isinstance(segm, list) and segm and isinstance(segm[0], (list, tuple)):
        rles = mask_utils.frPyObjects([list(p) for p in segm], h, w)
        return mask_utils.merge(rles) if len(rles) > 1 else rles[0]
    return None


def _mask_iou(gt_segm, pred_poly: list[float], h: int, w: int) -> float:
    """Mask IoU between a gt segmentation (multi-polygon parts or RLE) and a prediction polygon."""
    try:
        gt = _poly_mask(gt_segm, h, w)
        pred = _poly_mask([pred_poly], h, w)
        if gt is None or pred is None:
            return 0.0
        return float(mask_utils.iou([gt], [pred], [0])[0][0])
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
# Bolya et al. 2020: true positives are matched per class with COCO matching at IoU 0.5, then
# every remaining detection is labelled in the paper's order (cls -> dupe -> loc -> both -> bkg)
# and each oracle fix is scored as a delta in AP50. `tidecv` is not a dependency; six extra AP50
# runs per model are fine because this runs in the training worker, not on the request path.

def _pair_iou(rec: dict, iou_type: str):
    """IoU function for one image: mask IoU for segmentation, box IoU otherwise."""
    size = (rec["height"], rec["width"])

    def iou(g: dict, p: dict) -> float:
        if iou_type == "segm":
            return _mask_iou(g.get("segm"), _polygon(p, p["bbox"]), *size)
        return _iou(g["bbox"], p["bbox"])

    return iou


def _tide_match(gt: list[dict], pred: list[dict], pair_iou) -> dict[int, int]:
    """COCO-style per-class greedy matching at IoU >= 0.5: prediction index -> gt index.

    TIDE ignores `iscrowd` annotations and COCO's small/medium/large area ranges; AP50 already
    applies those ranges downstream, so the buckets stay comparable with the reported metric.
    """
    used: set[int] = set()
    tps: dict[int, int] = {}
    for pi in sorted(range(len(pred)), key=lambda i: -pred[i]["conf"]):
        best_iou, best_gi = IOU, -1
        for gi, g in enumerate(gt):
            if gi in used or g["cls"] != pred[pi]["cls"]:
                continue
            iou = pair_iou(g, pred[pi])
            if iou >= best_iou:
                best_iou, best_gi = iou, gi
        if best_gi >= 0:
            used.add(best_gi)
            tps[pi] = best_gi
    return tps


def _best_gt(gt: list[dict], p: dict, pair_iou, same: bool, lo: float,
             hi: float = math.inf) -> int:
    """Highest-IoU gt in the given class relation and IoU band, or -1."""
    found, best_iou = -1, -1.0
    for gi, g in enumerate(gt):
        if (g["cls"] == p["cls"]) != same:
            continue
        iou = pair_iou(g, p)
        if lo <= iou < hi and iou > best_iou:
            best_iou, found = iou, gi
    return found


def _tide_classify(rec: dict, iou_type: str) -> tuple[list, list[int], set[int]]:
    """TIDE labels for every scored detection, the uncovered gt indices and the TP gt set.

    TPs are matched first (per class at IoU 0.5); each remaining detection is then labelled in
    Bolya et al.'s order: cls -> dupe -> loc -> both -> bkg.
    """
    gt, pred = rec["gt"], rec["pred"]
    pair_iou = _pair_iou(rec, iou_type)
    tps = _tide_match(gt, pred, pair_iou)
    tp_gt = set(tps.values())
    tp_score = {gi: pred[pi]["conf"] for pi, gi in tps.items()}

    fixes: list[tuple[str, int] | None] = [None] * len(pred)
    for pi, p in enumerate(pred):
        if pi in tps:
            continue
        gi = _best_gt(gt, p, pair_iou, False, IOU)              # wrong class, IoU >= 0.5
        if gi >= 0:
            fixes[pi] = ("cls", gi)
            continue
        gi = max((i for i, g in enumerate(gt)
                  if g["cls"] == p["cls"] and tp_score.get(i, 0.0) > p["conf"]
                  and pair_iou(g, p) >= IOU),                   # repeats a higher-scored TP
                 key=lambda i: pair_iou(gt[i], p), default=-1)
        if gi >= 0:
            fixes[pi] = ("dupe", gi)
            continue
        gi = _best_gt(gt, p, pair_iou, True, TIDE_FOREGROUND, IOU)
        if gi >= 0:
            fixes[pi] = ("loc", gi)
            continue
        gi = _best_gt(gt, p, pair_iou, False, TIDE_FOREGROUND, IOU)
        if gi >= 0:
            fixes[pi] = ("both", gi)
            continue
        fixes[pi] = ("bkg", -1)
    # a gt targeted by a cls/loc/both fix is covered by that detection, so it is not also missed
    covered = {fix[1] for fix in fixes if fix is not None and fix[0] in ("cls", "loc", "both")}
    missed = [gi for gi in range(len(gt)) if gi not in tp_gt and gi not in covered]
    return fixes, missed, tp_gt


def _tide_corrected(records: list[dict], classified: list, cat_ids: dict,
                    iou_type: str, kind: str) -> list[dict]:
    """Detection list with one TIDE error type repaired by its oracle fix."""
    out = []
    for r, (fixes, _, tp_gt) in zip(records, classified):
        for p, fix in zip(r["pred"], fixes):
            det = _detection(r["image_id"], p, cat_ids, iou_type)
            if fix is None or fix[0] != kind:       # untouched detection goes through as-is
                out.append(det)
                continue
            if kind in ("dupe", "bkg"):             # dropping the false positive is the fix
                continue
            gi = fix[1]
            if gi in tp_gt:                         # the fix would duplicate an existing TP
                out.append(det)
                continue
            g = r["gt"][gi]
            if kind in ("cls", "both"):
                det["category_id"] = cat_ids[g["cls"]]
            if kind in ("loc", "both"):
                det["bbox"] = list(g["bbox"])
                if iou_type == "segm":              # the mask must follow the corrected box
                    # encompass the gt mask (multi-part polygons, compressed or uncompressed RLE)
                    det["segmentation"] = (_poly_mask(g["segm"], r["height"], r["width"])
                                           or [_rect(g["bbox"])])
            out.append(det)
    return out


def _gt_without_missed(coco: COCO, records: list[dict], classified: list) -> COCO:
    """The ground truth with every missed annotation removed (the missed oracle fix)."""
    drop = {r["gt"][gi]["id"]
            for r, (_, missed, _) in zip(records, classified) for gi in missed}
    if not drop:
        return coco
    data = {**coco.dataset,
            "annotations": [a for a in coco.dataset["annotations"] if a["id"] not in drop]}
    gt = COCO()
    gt.dataset = data
    with contextlib.redirect_stdout(io.StringIO()):
        gt.createIndex()
    return gt


def _load_res(coco: COCO, detections: list[dict]):
    if not detections:                             # loadRes cannot index an empty result list
        return None
    with contextlib.redirect_stdout(io.StringIO()):
        return coco.loadRes(detections)


def _tide(coco: COCO, records: list[dict], iou_type: str, cat_ids: dict,
          ap_base: float) -> dict:
    """ΔAP50 per TIDE error type; a fix that hurts is reported negative (no clamping)."""
    classified = [_tide_classify(r, iou_type) for r in records]
    out = {}
    for kind in TIDE_TYPES:
        gt = _gt_without_missed(coco, records, classified) if kind == "missed" else coco
        detections = _tide_corrected(records, classified, cat_ids, iou_type, kind)
        ap_fixed = _stat(_coco_stats(gt, _load_res(gt, detections), iou_type)[1])
        out[kind] = round(ap_fixed - ap_base, 4)
    return out
