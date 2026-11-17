"""One unclamped xywh box-IoU, shared by evaluation, insights, health and suspects.

Not `labeling.bbox_iou`: that one clamps to the image first, which changes the score for
out-of-frame ground truth.
"""

from collections.abc import Sequence


def box_iou(a: Sequence[float], b: Sequence[float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0
