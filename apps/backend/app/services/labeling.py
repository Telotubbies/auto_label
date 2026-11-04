"""Pure labeling-quality metrics: IoU matching, set agreement, consensus merge, honeypot scoring.

No database imports here — the ops layer (`labeling_ops`) feeds these functions plain annotation dicts.
"""
import secrets
from collections import Counter

Box = tuple[float, float, float, float]
MIN_K, MAX_K = 2, 10
MAX_DRAFT_ANNOTATIONS = 1000      # keeps one draft's synchronous pass bounded (API runs as one process)
MAX_IMAGE_ANNOTATIONS = 2000      # sum across the submitted drafts of one image: the agreement/merge bound


def _clamp(box: Box) -> Box:
    """Normalised xywh -> xywh inside [0, 1] with non-negative w/h."""
    x, y, w, h = (float(v) for v in box)
    x1, y1 = min(max(x, 0.0), 1.0), min(max(y, 0.0), 1.0)
    x2, y2 = min(max(x + max(w, 0.0), 0.0), 1.0), min(max(y + max(h, 0.0), 0.0), 1.0)
    return x1, y1, max(0.0, x2 - x1), max(0.0, y2 - y1)


def bbox_iou(a: Box, b: Box) -> float:
    return _clamped_iou(_clamp(a), _clamp(b))


def _clamped_iou(a: Box, b: Box) -> float:
    """IoU of two already-clamped boxes; the hot path of every candidate pair."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
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


def _prepared(anns: list[dict]) -> list[tuple[dict, str | None, str | None, Box | None]]:
    """(annotation, class, kind, clamped bounds) computed once per annotation, never per pair."""
    out: list[tuple[dict, str | None, str | None, Box | None]] = []
    for ann in anns or []:
        shape = ann.get("shape") or {}
        kind = shape.get("kind")
        box = None
        if kind != "class":
            raw = shape_box(shape)
            if raw is not None:
                box = _clamp(raw)
                if box[2] <= 0 or box[3] <= 0:
                    box = None
        out.append((ann, ann.get("classId"), kind, box))
    return out


def _overlap_pairs(items: list[tuple[int, str | None, Box]]):
    """Yield (i, j) for different-group, same-class boxes whose bounds overlap.

    One x-interval sweep over precomputed boxes: candidates are ordered by their left edge and the
    scan stops at the first box starting past the current right edge, so boxes that cannot overlap
    are never compared and each pair is yielded once.
    """
    order = sorted(range(len(items)), key=lambda i: items[i][2][0])
    for pos, i in enumerate(order):
        group_i, class_i, (x1, y1, w, h) = items[i]
        x2, y2 = x1 + w, y1 + h
        for q in range(pos + 1, len(order)):
            j = order[q]
            group_j, class_j, (bx1, by1, bw, bh) = items[j]
            if bx1 >= x2:
                break
            if group_i == group_j or class_i != class_j:
                continue
            if by1 >= y2 or by1 + bh <= y1:
                continue
            yield i, j


def sets_agreement(a: list[dict], b: list[dict], iou_threshold: float = 0.5) -> float:
    """1:1 greedy match by descending IoU; 2 * matches / (|a| + |b|).

    Boxes are prepared once and candidate pairs come from a class-bucketed x-interval sweep, so the
    score is identical to the all-pairs definition without enumerating non-overlapping pairs.
    """
    return _sets_agreement(_prepared(a), _prepared(b), iou_threshold)


def _sets_agreement(left: list, right: list, iou_threshold: float = 0.5) -> float:
    """`sets_agreement` over already-prepared drafts, so a group comparison prepares each one once."""
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    pairs: list[tuple[float, int, int]] = []
    # class labels have no geometry: every same-class pair from the two sides matches
    for i, (_, cls_a, kind_a, _) in enumerate(left):
        if kind_a != "class":
            continue
        for j, (_, cls_b, kind_b, _) in enumerate(right):
            if kind_b == "class" and cls_a == cls_b:
                pairs.append((1.0, i, j))
    owners: list[tuple[int, int]] = []
    items: list[tuple[int, str | None, Box]] = []
    for group, prepared in ((0, left), (1, right)):
        for index, (_, cls, kind, box) in enumerate(prepared):
            if kind != "class" and box is not None:
                owners.append((group, index))
                items.append((group, cls, box))
    for u, v in _overlap_pairs(items):
        group_u, index_u = owners[u]
        group_v, index_v = owners[v]
        i, j = (index_u, index_v) if group_u == 0 else (index_v, index_u)
        iou = _clamped_iou(items[u][2], items[v][2])
        if iou > 0 and iou >= iou_threshold:
            pairs.append((iou, i, j))
    pairs.sort(key=lambda p: (-p[0], p[1], p[2]))
    used_a: set[int] = set()
    used_b: set[int] = set()
    for _, i, j in pairs:
        if i not in used_a and j not in used_b:
            used_a.add(i)
            used_b.add(j)
    return 2 * len(used_a) / (len(left) + len(right))


def group_agreement(sets: list[list[dict]], iou_threshold: float = 0.5) -> float:
    """Mean pairwise agreement; a single set (or none) is trivially in agreement with itself."""
    if len(sets) < 2:
        return 1.0
    prepared = [_prepared(anns) for anns in sets]
    scores = [_sets_agreement(prepared[i], prepared[j], iou_threshold)
              for i in range(len(sets)) for j in range(i + 1, len(sets))]
    return sum(scores) / len(scores)


def _merged_annotation(members: list[dict]) -> dict:
    shapes = [m.get("shape") or {} for m in members]
    if shapes and all(s.get("kind") == "class" for s in shapes):
        shape: dict = {"kind": "class"}
    elif (shapes and all(s.get("kind") == "polygon" for s in shapes)
          and len({len(s.get("points") or []) for s in shapes}) == 1):
        mean = [sum(v) / len(v) for v in zip(*[s.get("points") or [] for s in shapes], strict=True)]
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
    """Cluster same-class annotations across sets; keep clusters backed by a strict majority of sets.

    Boxes are prepared once and candidate pairs come from the same class-bucketed x-interval sweep
    as `sets_agreement`, so large or dense drafts never trigger the full pairwise scan.
    """
    nodes: list[tuple[int, dict, str | None, str | None, Box | None]] = []
    for si, anns in enumerate(sets):
        for ann, cls, kind, box in _prepared(anns):
            nodes.append((si, ann, cls, kind, box))
    parent = list(range(len(nodes)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    by_class: dict[str | None, list[int]] = {}
    for i, node in enumerate(nodes):
        by_class.setdefault(node[2], []).append(i)

    for indices in by_class.values():
        # class labels have no geometry: every same-class pair from different labelers matches
        class_like = [i for i in indices if nodes[i][3] == "class"]
        for pos, i in enumerate(class_like):
            for j in class_like[pos + 1:]:
                if nodes[i][0] != nodes[j][0]:
                    parent[find(i)] = find(j)
        # geometry: sweep by x, compare only boxes whose bounds can overlap (once per pair)
        owners: list[int] = []
        items: list[tuple[int, str | None, Box]] = []
        for i in indices:
            if nodes[i][3] == "class" or nodes[i][4] is None:
                continue
            owners.append(i)
            items.append((nodes[i][0], nodes[i][2], nodes[i][4]))
        for u, v in _overlap_pairs(items):
            if _clamped_iou(items[u][2], items[v][2]) >= iou_threshold:
                parent[find(owners[u])] = find(owners[v])

    clusters: dict[int, list[tuple[int, dict]]] = {}
    for i in range(len(nodes)):
        clusters.setdefault(find(i), []).append((nodes[i][0], nodes[i][1]))
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
