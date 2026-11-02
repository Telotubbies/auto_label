"""SAM-assisted tracking: propagate one annotation's box across the next frames.

Each step re-prompts SAM with the previous box. When SAM returns a mask, the next prompt
box is the mask's bounding box and (for segmentation projects) the annotation becomes that
polygon; otherwise the previous box is carried forward unchanged.
"""
import logging
import math

log = logging.getLogger(__name__.rsplit(".", 1)[-1])


def _finite(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    v = float(value)
    return v if math.isfinite(v) else None


def _bbox_from_points(xs: list[float], ys: list[float]) -> tuple[float, float, float, float] | None:
    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)


def box_of_shape(shape: dict) -> tuple[float, float, float, float] | None:
    """Normalized (x, y, w, h) for bbox, obb, polygon and keypoints shapes."""
    if not isinstance(shape, dict):
        return None
    kind = shape.get("kind")
    if kind == "bbox":
        vals = [_finite(shape.get(k)) for k in "xywh"]
        if any(v is None for v in vals):
            return None
        return vals[0], vals[1], vals[2], vals[3]
    if kind == "obb":
        vals = [_finite(shape.get(k)) for k in ("cx", "cy", "w", "h", "angle")]
        if any(v is None for v in vals):
            return None
        cx, cy, w, h, angle = vals
        cos, sin = math.cos(angle), math.sin(angle)
        xs, ys = [], []
        for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
            xs.append(cx + dx * cos - dy * sin)
            ys.append(cy + dx * sin + dy * cos)
        return _bbox_from_points(xs, ys)
    if kind == "polygon":
        pts = shape.get("points")
        if not isinstance(pts, list) or len(pts) < 6 or len(pts) % 2:
            return None
        xs = [_finite(v) for v in pts[0::2]]
        ys = [_finite(v) for v in pts[1::2]]
        if any(v is None for v in xs + ys):
            return None
        return _bbox_from_points(xs, ys)
    if kind == "keypoints":
        pts = shape.get("points")
        if not isinstance(pts, list) or len(pts) < 3 or len(pts) % 3:
            return None
        xs, ys = [], []
        for i in range(0, len(pts), 3):
            x, y, visibility = _finite(pts[i]), _finite(pts[i + 1]), _finite(pts[i + 2])
            if None in (x, y, visibility):
                return None
            if visibility > 0:
                xs.append(x)
                ys.append(y)
        return _bbox_from_points(xs, ys)
    return None


def _box_shape(box: tuple[float, float, float, float]) -> dict:
    return {"kind": "bbox", "x": box[0], "y": box[1], "w": box[2], "h": box[3]}


def _box_px(box: tuple[float, float, float, float], width: int, height: int) -> tuple[float, float, float, float]:
    x, y, w, h = box
    return x * width, y * height, (x + w) * width, (y + h) * height


def _polygon_box(points: list[float]) -> tuple[float, float, float, float] | None:
    if not isinstance(points, list) or len(points) < 6 or len(points) % 2:
        return None
    xs = [_finite(points[i]) for i in range(0, len(points), 2)]
    ys = [_finite(points[i]) for i in range(1, len(points), 2)]
    if any(v is None for v in xs + ys):
        return None
    return _bbox_from_points(xs, ys)


def merge_track(annotations: list[dict], new_ann: dict, track_id: str) -> tuple[list[dict], bool]:
    """Add one tracked annotation, replacing an interpolated/SAM row on that frame.

    A keyframe or a human edit wins: the frame is left untouched. Returns (annotations, written).
    """
    anns = list(annotations or [])
    if any(a.get("trackId") == track_id and (a.get("keyframe") or a.get("source") not in ("interpolated", "sam3"))
           for a in anns):
        return anns, False
    anns = [a for a in anns if not (a.get("trackId") == track_id and not a.get("keyframe"))]
    anns.append(new_ann)
    return anns, True


def track_forward(frames, seed_shape: dict, sam_box=None, project_type: str = "object-detection") -> list[dict]:
    """Propagate `seed_shape` across `frames` (PIL images), re-prompting SAM each step.

    Returns one shape per frame. A failing SAM call never aborts the run: the previous box is
    kept and a warning is logged. Keypoint projects get bbox shapes (the editor converts them).
    """
    previous = box_of_shape(seed_shape)
    if previous is None:
        return []
    shapes: list[dict] = []
    for im in frames:
        width, height = im.width, im.height
        chosen = previous
        polygon = None
        if sam_box is not None:
            try:
                result = sam_box(im, _box_px(previous, width, height))
                if result:
                    points, _score = result
                    box = _polygon_box(points)
                    if box is not None:
                        polygon, chosen = points, box
            except Exception as e:                       # one bad frame must not drop the track
                log.warning("SAM box prompt failed on a frame: %s", e)
        if polygon is not None and project_type == "instance-segmentation":
            shapes.append({"kind": "polygon", "points": [float(v) for v in polygon]})
        else:
            shapes.append(_box_shape(chosen))
        previous = chosen
    return shapes
