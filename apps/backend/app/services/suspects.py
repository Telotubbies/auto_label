"""ObjectLab-style suspect-label scoring.

For every human box we ask the project's latest model what it sees at that place:

* ``wrong_class`` — a detection matches the box (IoU >= 0.5) but names another class.
* ``shifted_box`` — the best detection is the same object (0.3 <= IoU < 0.5), badly aligned.
* ``extra_box`` — nothing matches (IoU < 0.3); the score uses the model's strongest confidence
  in the image, so a model with no detections never queues a label.

The score is a 0..1 ranking hint, not a verdict: reviewers confirm or dismiss every item and the
queue precision becomes the feedback statistic. This module is pure; the cached scan and feedback
storage live in ``suspect_queue``.
"""

from .boxes import box_iou

MATCH_IOU = 0.5
SHIFT_IOU = 0.3
KINDS = ("wrong_class", "shifted_box", "extra_box")


def _name(value: object) -> str:
    return str(value or "").strip().casefold()


def _predictions(predictions: list[dict], width: int, height: int) -> list[tuple[tuple, dict]]:
    """Usable predictions as (normalised x, y, w, h) plus the raw dict."""
    out = []
    if not width or not height:
        return out
    for p in predictions or []:
        if not isinstance(p, dict):
            continue
        try:
            x, y, w, h = (float(p[k]) for k in ("x", "y", "width", "height"))
            conf = float(p.get("confidence") or 0.0)
        except (KeyError, TypeError, ValueError):
            continue
        if w <= 0 or h <= 0:
            continue
        out.append((((x - w / 2) / width, (y - h / 2) / height, w / width, h / height), {**p, "confidence": conf}))
    return out


def score_image(
    annotations: list[dict],
    predictions: list[dict],
    class_names: dict[str, str],
    width: int,
    height: int,
) -> list[dict]:
    """Score one image's human labels against its model predictions, highest first."""
    from .health_scan import box, is_human  # shared geometry/ground-truth rules; avoids a third copy

    preds = _predictions(predictions, width, height)
    if not preds:
        return []  # no model opinion: neither class nor geometry can be judged
    max_conf = max(p[1]["confidence"] for p in preds)
    items = []
    for ann in annotations or []:
        if not is_human(ann):
            continue
        truth = box(ann)
        if truth is None:
            continue
        best, best_iou = None, -1.0
        for norm, raw in preds:
            iou = box_iou(truth, norm)
            if iou > best_iou:
                best, best_iou = raw, iou
        own = _name(class_names.get(ann.get("classId")))
        seen = _name(best.get("class"))
        kind, score = None, 0.0
        if best_iou >= MATCH_IOU:
            if own and seen and own != seen:
                kind, score = "wrong_class", best["confidence"] * best_iou
        elif best_iou >= SHIFT_IOU:
            kind, score = "shifted_box", best["confidence"] * (1 - best_iou)
        else:
            kind, score = "extra_box", max_conf * (0.5 - best_iou / 2)
        if kind:
            items.append(
                {
                    "annotation_id": ann.get("id"),
                    "kind": kind,
                    "score": round(min(1.0, max(0.0, score)), 3),
                    "class_id": ann.get("classId"),
                    "class": class_names.get(ann.get("classId"), ""),
                    "predicted_class": best.get("class") if kind != "extra_box" else None,
                    "iou": round(best_iou, 3),
                }
            )
    return sorted(items, key=lambda x: (-x["score"], str(x["annotation_id"])))
