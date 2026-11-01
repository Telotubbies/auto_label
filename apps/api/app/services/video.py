"""Video frame planning, scene-change detection and timeline interpolation.

Frame indices are 0-based positions in the decoded stream; annotation geometry stays
normalized 0..1 so the same shapes work on every resolution.
"""
import copy
import math

import cv2
import numpy as np

EXTRACT_MODES = ("fps", "every", "scene")
DEFAULT_SCENE_THRESHOLD = 0.35
MAX_INTERPOLATION_SPAN = 240        # frames between two keyframes before interpolation is refused


def plan_frames(frame_count: int, fps: float, mode: str, target_fps: float = 1.0, every_s: float = 1.0,
                max_frames: int = 2000) -> list[int]:
    """Frame indices to keep: one every 1/target_fps second, every `every_s` seconds, or the
    scene-mode fallback to target_fps sampling. The result is ascending and thinned evenly to
    `max_frames` (the first frame is always kept)."""
    if mode not in EXTRACT_MODES:
        raise ValueError(f"unknown extraction mode {mode!r}; use one of {', '.join(EXTRACT_MODES)}")
    if target_fps <= 0:
        raise ValueError("target_fps must be greater than 0")
    if every_s <= 0:
        raise ValueError("every_s must be greater than 0")
    if frame_count < 0:
        raise ValueError("frame_count must be 0 or greater")
    if max_frames < 1:
        raise ValueError("max_frames must be at least 1")
    if frame_count == 0:
        return []
    fps = fps if fps > 0 else 1.0
    step = max(1, round(fps * every_s)) if mode == "every" else max(1, round(fps / target_fps))
    indices = list(range(0, frame_count, step))
    if len(indices) > max_frames:
        stride = math.ceil(len(indices) / max_frames)
        indices = indices[::stride][:max_frames]
    return indices


def is_scene_change(prev_hist, hist, threshold: float = DEFAULT_SCENE_THRESHOLD) -> bool:
    """Bhattacharyya distance between two normalized grayscale histograms.

    A missing/empty histogram means "no previous frame", i.e. the first frame is a cut."""
    if prev_hist is None or hist is None:
        return True
    a = np.asarray(prev_hist, dtype=np.float32).reshape(-1, 1)
    b = np.asarray(hist, dtype=np.float32).reshape(-1, 1)
    if a.size == 0 or b.size == 0 or a.shape != b.shape:
        return True
    if float(a.sum()) <= 0 or float(b.sum()) <= 0:
        return True
    distance = float(cv2.compareHist(a, b, cv2.HISTCMP_BHATTACHARYYA))
    return distance > threshold


def _number(value) -> float | None:
    """Finite float or None (bool is not geometry)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    v = float(value)
    return v if math.isfinite(v) else None


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _shortest_angle(a: float, b: float) -> float:
    """Signed shortest rotation from `a` to `b`, in (-pi, pi]."""
    delta = math.fmod(b - a, 2 * math.pi)
    if delta > math.pi:
        delta -= 2 * math.pi
    elif delta <= -math.pi:
        delta += 2 * math.pi
    return delta


def _normalize_angle(angle: float) -> float:
    """Wrap into [-pi, pi)."""
    return (angle + math.pi) % (2 * math.pi) - math.pi


def _interpolate_obb(a: dict, b: dict, t: float) -> dict | None:
    keys = ("cx", "cy", "w", "h", "angle")
    av = [_number(a.get(k)) for k in keys]
    bv = [_number(b.get(k)) for k in keys]
    if any(v is None for v in av + bv):
        return None
    angle = _normalize_angle(av[4] + _shortest_angle(av[4], bv[4]) * t)
    return {"kind": "obb", "cx": _lerp(av[0], bv[0], t), "cy": _lerp(av[1], bv[1], t),
            "w": _lerp(av[2], bv[2], t), "h": _lerp(av[3], bv[3], t), "angle": angle}


def _interpolate_keypoints(a: dict, b: dict, t: float) -> dict | None:
    pa, pb = a.get("points"), b.get("points")
    if not isinstance(pa, list) or not isinstance(pb, list) or len(pa) != len(pb) or len(pa) % 3:
        return None
    points: list[float] = []
    for i in range(0, len(pa), 3):
        xa, ya, va = _number(pa[i]), _number(pa[i + 1]), _number(pa[i + 2])
        xb, yb, vb = _number(pb[i]), _number(pb[i + 1]), _number(pb[i + 2])
        if None in (xa, ya, va, xb, yb, vb):
            return None
        if va > 0 and vb > 0:                       # only move joints seen in both endpoints
            x, y = _lerp(xa, xb, t), _lerp(ya, yb, t)
        else:
            x, y = xa, ya
        visibility = 2 if va == 2 and vb == 2 else 1 if va > 0 or vb > 0 else 0
        points.extend((x, y, float(visibility)))
    return {"kind": "keypoints", "points": points}


def interpolate_shape(a: dict, b: dict, t: float) -> dict:
    """Linear blend of two annotation shapes at `t` (clamped to 0..1).

    Bbox and polygon points blend componentwise; obb angles take the shortest way around;
    keypoints move only when visible at both ends. Mismatched or invalid input falls back to
    a deep copy of `a`. Inputs are never mutated."""
    if not isinstance(a, dict) or not isinstance(b, dict) or a.get("kind") != b.get("kind"):
        return copy.deepcopy(a) if isinstance(a, dict) else {}
    amount = _number(t)
    if amount is None:
        amount = 0.0
    amount = min(1.0, max(0.0, amount))
    kind = a.get("kind")
    if kind == "bbox":
        keys = ("x", "y", "w", "h")
        av = [_number(a.get(k)) for k in keys]
        bv = [_number(b.get(k)) for k in keys]
        if any(v is None for v in av + bv):
            return copy.deepcopy(a)
        return {"kind": "bbox", **{k: _lerp(av[i], bv[i], amount) for i, k in enumerate(keys)}}
    if kind == "obb":
        out = _interpolate_obb(a, b, amount)
        return out if out is not None else copy.deepcopy(a)
    if kind == "keypoints":
        out = _interpolate_keypoints(a, b, amount)
        return out if out is not None else copy.deepcopy(a)
    if kind == "polygon":
        pa, pb = a.get("points"), b.get("points")
        if (not isinstance(pa, list) or not isinstance(pb, list) or len(pa) != len(pb)
                or len(pa) < 6 or len(pa) % 2):
            return copy.deepcopy(a)
        av = [_number(v) for v in pa]
        bv = [_number(v) for v in pb]
        if any(v is None for v in av + bv):
            return copy.deepcopy(a)
        return {"kind": "polygon", "points": [_lerp(x, y, amount) for x, y in zip(av, bv)]}
    return copy.deepcopy(a)


def _new_ann_id() -> str:
    from ..models import new_id
    return "a" + new_id()


def interpolate_tracks(frames: list[tuple[int, list[dict]]], from_index: int, to_index: int,
                       interpolate=interpolate_shape) -> dict[int, list[dict]]:
    """Interpolated annotations for the frames strictly between two keyframes.

    `frames` is [(frame_index, annotations)] (endpoints included). A track is interpolated only
    when the same trackId appears on both endpoints with the same classId. Returns
    {frame_index: [new annotations]} for the intermediate frames that already exist."""
    by_index = {idx: anns or [] for idx, anns in frames}
    if from_index == to_index or from_index not in by_index or to_index not in by_index:
        return {}
    start, end = (from_index, to_index) if from_index < to_index else (to_index, from_index)
    span = end - start
    if span <= 0 or span > MAX_INTERPOLATION_SPAN:
        return {}
    end_by_track = {a.get("trackId"): a for a in by_index[end] if a.get("trackId")}
    out: dict[int, list[dict]] = {}
    for index in sorted(i for i in by_index if start < i < end):
        t = (index - start) / span
        wrote: list[dict] = []
        for a in by_index[start]:
            track_id = a.get("trackId")
            if not track_id:
                continue
            b = end_by_track.get(track_id)
            if b is None or b.get("classId") != a.get("classId"):
                continue
            wrote.append({"id": _new_ann_id(), "classId": a.get("classId"),
                          "shape": interpolate(a.get("shape") or {}, b.get("shape") or {}, t),
                          "source": "interpolated", "trackId": track_id, "keyframe": False})
        if wrote:
            out[index] = wrote
    return out
