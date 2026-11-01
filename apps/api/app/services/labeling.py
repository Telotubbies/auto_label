"""Pure labeling-quality metrics: IoU matching, set agreement, consensus merge, honeypot scoring.

No database imports here — the ops layer (`labeling_ops`) feeds these functions plain annotation dicts.
"""
import secrets
from collections import Counter

Box = tuple[float, float, float, float]
MIN_K, MAX_K = 2, 10


def _clamp(box: Box) -> Box:
    """Normalised xywh -> xywh inside [0, 1] with non-negative w/h."""
    x, y, w, h = (float(v) for v in box)
    x1, y1 = min(max(x, 0.0), 1.0), min(max(y, 0.0), 1.0)
    x2, y2 = min(max(x + max(w, 0.0), 0.0), 1.0), min(max(y + max(h, 0.0), 0.0), 1.0)
    return x1, y1, max(0.0, x2 - x1), max(0.0, y2 - y1)


def bbox_iou(a: Box, b: Box) -> float:
    ax, ay, aw, ah = _clamp(a)
    bx, by, bw, bh = _clamp(b)
    if aw <= 0 or ah <= 0 or bw <= 0 or bh <= 0:
        return 0.0
    ix = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def shape_box(shape: dict) -> Box | None:
    """bbox -> itself; polygon -> bounds of its points; class labels have no geometry."""
    kind = (shape or {}).get("kind")
    if kind == "bbox":
        return (float(shape.get("x", 0.0)), float(shape.get("y", 0.0)),
                float(shape.get("w", 0.0)), float(shape.get("h", 0.0)))
    if kind == "polygon":
        pts = shape.get("points") or []
        xs, ys = pts[0::2], pts[1::2]
        if not xs or not ys:
            return None
        return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
    return None


def annotation_iou(a: dict, b: dict, iou_threshold: float = 0.5) -> float:
    """Similarity of two annotations: 0 unless the class matches; IoU below the threshold also scores 0."""
    if a.get("classId") != b.get("classId"):
        return 0.0
    sa, sb = a.get("shape") or {}, b.get("shape") or {}
    if sa.get("kind") == "class" or sb.get("kind") == "class":
        return 1.0 if sa.get("kind") == sb.get("kind") == "class" else 0.0
    ba, bb = shape_box(sa), shape_box(sb)
    if ba is None or bb is None:
        return 0.0
    iou = bbox_iou(ba, bb)
    return iou if iou >= iou_threshold else 0.0


def sets_agreement(a: list[dict], b: list[dict], iou_threshold: float = 0.5) -> float:
    """1:1 greedy match by descending IoU; 2 * matches / (|a| + |b|)."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    pairs = []
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            iou = annotation_iou(x, y, iou_threshold)
            if iou > 0:
                pairs.append((iou, i, j))
    pairs.sort(key=lambda p: (-p[0], p[1], p[2]))
    used_a: set[int] = set()
    used_b: set[int] = set()
    for _, i, j in pairs:
        if i not in used_a and j not in used_b:
            used_a.add(i)
            used_b.add(j)
    return 2 * len(used_a) / (len(a) + len(b))


def group_agreement(sets: list[list[dict]], iou_threshold: float = 0.5) -> float:
    """Mean pairwise agreement; a single set (or none) is trivially in agreement with itself."""
    if len(sets) < 2:
        return 1.0
    scores = [sets_agreement(sets[i], sets[j], iou_threshold)
              for i in range(len(sets)) for j in range(i + 1, len(sets))]
    return sum(scores) / len(scores)


def _merged_annotation(members: list[dict]) -> dict:
    shapes = [m.get("shape") or {} for m in members]
    if shapes and all(s.get("kind") == "class" for s in shapes):
        shape: dict = {"kind": "class"}
    elif (shapes and all(s.get("kind") == "polygon" for s in shapes)
          and len({len(s.get("points") or []) for s in shapes}) == 1):
        mean = [sum(v) / len(v) for v in zip(*[s.get("points") or [] for s in shapes])]
        shape = {"kind": "polygon", "points": mean}
    else:
        boxes = [b for b in (shape_box(s) for s in shapes) if b is not None]
        if boxes:
            shape = {"kind": "bbox", **{k: sum(b[i] for b in boxes) / len(boxes) for i, k in enumerate("xywh")}}
        else:
            shape = {"kind": "class"}
    class_id = Counter(m.get("classId") for m in members).most_common(1)[0][0]
    return {"id": "m" + secrets.token_hex(4), "classId": class_id, "shape": shape, "source": "human"}


def merge_sets(sets: list[list[dict]], iou_threshold: float = 0.5) -> list[dict]:
    """Cluster same-class annotations across sets; keep clusters backed by a strict majority of sets."""
    nodes = [(si, ann) for si, anns in enumerate(sets) for ann in anns or []]
    parent = list(range(len(nodes)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            if nodes[i][0] == nodes[j][0]:
                continue                       # never merge two labels of the same labeler into one
            if annotation_iou(nodes[i][1], nodes[j][1], iou_threshold) > 0:
                parent[find(i)] = find(j)
    clusters: dict[int, list[tuple[int, dict]]] = {}
    for i in range(len(nodes)):
        clusters.setdefault(find(i), []).append(nodes[i])
    need = len(sets) // 2 + 1
    merged = [_merged_annotation([ann for _, ann in members])
              for members in clusters.values() if len({si for si, _ in members}) >= need]
    merged.sort(key=_sort_key)
    return merged


def _sort_key(ann: dict) -> tuple[float, float]:
    box = shape_box(ann.get("shape") or {})
    return (round(box[1], 9), round(box[0], 9)) if box else (0.0, 0.0)


def honeypot_score(gt: list[dict], submitted: list[dict], iou_threshold: float = 0.5) -> float:
    return round(sets_agreement(gt, submitted, iou_threshold), 4)
