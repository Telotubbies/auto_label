"""SAHI-style slice inference with every knob exposed: slice grid, post-processing, match metric.

Slicing: separate slice width/height and overlap ratios, an auto rule, an extra full-image pass, and a
minimum visible-area ratio for boxes a slice edge clipped. Post-processing: NMS, NMM, GREEDYNMM and
LSNMS, matched by IOU or IOS above a threshold, class-aware or class-agnostic.

Boxes are the API's centre format (x, y, width, height in pixels, confidence, class_id). A merged box
spans the union of its members, takes the strongest member's score and class, and keeps that member's
polygon (polygons cannot be unioned without masks).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, replace

from PIL import Image as PImage

POSTPROCESS = ("NMS", "NMM", "GREEDYNMM", "LSNMS")
METRICS = ("IOU", "IOS")
MIN_SLICE, MAX_SLICE = 64, 4096
MAX_OVERLAP = 0.9
MAX_SLICES = 400            # one synchronous request must not fan out to thousands of crops


# --- matching and post-processing -----------------------------------------------------------------

def _corners(b: dict) -> tuple[float, float, float, float]:
    return b["x"] - b["width"] / 2, b["y"] - b["height"] / 2, b["x"] + b["width"] / 2, b["y"] + b["height"] / 2


def match_value(a: dict, b: dict, metric: str) -> float:
    """IOU = intersection / union; IOS = intersection / the smaller box (catches a box inside another)."""
    if metric not in METRICS:
        raise ValueError(f"match metric must be one of {', '.join(METRICS)}")
    ax1, ay1, ax2, ay2 = _corners(a)
    bx1, by1, bx2, by2 = _corners(b)
    inter = max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))
    area_a, area_b = a["width"] * a["height"], b["width"] * b["height"]
    denom = (area_a + area_b - inter) if metric == "IOU" else min(area_a, area_b)
    return inter / denom if denom > 0 else 0.0


def _union(a: dict, b: dict) -> dict:
    """The union box of two predictions with the stronger one's score, class and polygon."""
    strong, weak = (a, b) if (a.get("confidence") or 0) >= (b.get("confidence") or 0) else (b, a)
    ax1, ay1, ax2, ay2 = _corners(a)
    bx1, by1, bx2, by2 = _corners(b)
    x1, y1, x2, y2 = min(ax1, bx1), min(ay1, by1), max(ax2, bx2), max(ay2, by2)
    out = dict(strong)
    out.update(x=round((x1 + x2) / 2, 1), y=round((y1 + y2) / 2, 1), width=round(x2 - x1, 1), height=round(y2 - y1, 1))
    return out


def _same_group(a: dict, b: dict, agnostic: bool) -> bool:
    return agnostic or a.get("class_id") == b.get("class_id")


def postprocess(preds: list[dict], *, kind: str = "NMS", metric: str = "IOU", threshold: float = 0.5,
                class_agnostic: bool = False) -> list[dict]:
    """Collapse the duplicates that overlapping slices create. Returns boxes strongest first."""
    if kind not in POSTPROCESS:
        raise ValueError(f"postprocess must be one of {', '.join(POSTPROCESS)}")
    if metric not in METRICS:
        raise ValueError(f"match metric must be one of {', '.join(METRICS)}")
    ordered = sorted(preds, key=lambda p: -float(p.get("confidence") or 0.0))
    if kind in ("NMS", "LSNMS"):                 # LSNMS is NMS made fast for huge counts: same boxes
        kept: list[dict] = []
        for p in ordered:
            if not any(_same_group(k, p, class_agnostic) and match_value(k, p, metric) > threshold for k in kept):
                kept.append(p)
        return kept
    out: list[dict] = []
    absorbed = [False] * len(ordered)
    for i, anchor in enumerate(ordered):
        if absorbed[i]:
            continue
        merged = dict(anchor)
        for j in range(i + 1, len(ordered)):
            if absorbed[j] or not _same_group(anchor, ordered[j], class_agnostic):
                continue
            # NMM tests against the original anchor; GREEDYNMM against the box as it has grown so far
            reference = merged if kind == "GREEDYNMM" else anchor
            if match_value(reference, ordered[j], metric) > threshold:
                merged = _union(merged, ordered[j])
                absorbed[j] = True
        out.append(merged)
    return out


# --- slice grid -----------------------------------------------------------------------------------

def _starts(total: int, size: int, overlap: float) -> list[int]:
    if total <= size:
        return [0]
    step = max(1, int(size * (1 - overlap)))
    starts = list(range(0, total - size + 1, step))
    if starts[-1] != total - size:               # the last slice always reaches the edge
        starts.append(total - size)
    return starts


@dataclass(frozen=True)
class SliceConfig:
    slice_width: int = 640
    slice_height: int = 640
    overlap_width_ratio: float = 0.2
    overlap_height_ratio: float = 0.2
    auto: bool = False
    perform_standard_pred: bool = False
    min_area_ratio: float = 0.1
    postprocess_type: str = "GREEDYNMM"
    postprocess_match_metric: str = "IOS"
    postprocess_match_threshold: float = 0.5
    postprocess_class_agnostic: bool = False

    def resolve(self, width: int, height: int) -> "SliceConfig":
        """The auto rule picks a slice size and overlap from the image resolution (LabelDesk rule, not SAHI's table)."""
        if not self.auto:
            return self
        longest = max(width, height)
        size = 640 if longest <= 1600 else 800 if longest <= 3200 else 1024 if longest <= 6400 else 1280
        overlap = 0.2 if longest <= 3200 else 0.25
        return replace(self, slice_width=size, slice_height=size, overlap_width_ratio=overlap,
                       overlap_height_ratio=overlap)

    def boxes(self, width: int, height: int) -> list[tuple[int, int, int, int]]:
        sw, sh = min(self.slice_width, width), min(self.slice_height, height)
        grid = [(x, y, x + sw, y + sh)
                for y in _starts(height, sh, self.overlap_height_ratio)
                for x in _starts(width, sw, self.overlap_width_ratio)]
        if len(grid) > MAX_SLICES:
            raise ValueError(f"this setting makes {len(grid)} slices (max {MAX_SLICES}); use bigger slices or less overlap")
        return grid


_FIELDS = {"slice_width": int, "slice_height": int, "overlap_width_ratio": float, "overlap_height_ratio": float,
           "auto_slice": bool, "perform_standard_pred": bool, "min_area_ratio": float,
           "postprocess_type": str, "postprocess_match_metric": str, "postprocess_match_threshold": float,
           "postprocess_class_agnostic": bool}


def parse_options(raw: dict) -> SliceConfig | None:
    """None when no slicing option is set; otherwise a validated config. Unknown keys are refused."""
    raw = {k: v for k, v in (raw or {}).items() if v is not None}
    if not raw:
        return None
    unknown = set(raw) - set(_FIELDS)
    if unknown:
        raise ValueError(f"unknown slice option: {', '.join(sorted(unknown))}")
    kw = {("auto" if k == "auto_slice" else k): _FIELDS[k](v) for k, v in raw.items()}
    for key in ("slice_width", "slice_height"):
        if key in kw and not MIN_SLICE <= kw[key] <= MAX_SLICE:
            raise ValueError(f"{key} must be {MIN_SLICE}-{MAX_SLICE}")
    for key in ("overlap_width_ratio", "overlap_height_ratio"):
        if key in kw and not 0 <= kw[key] <= MAX_OVERLAP:
            raise ValueError(f"{key} must be 0-{MAX_OVERLAP}")
    for key in ("min_area_ratio", "postprocess_match_threshold"):
        if key in kw and not 0 <= kw[key] <= 1:
            raise ValueError(f"{key} must be 0-1")
    if kw.get("postprocess_type", "NMS").upper() not in POSTPROCESS:
        raise ValueError(f"postprocess_type must be one of {', '.join(POSTPROCESS)}")
    if kw.get("postprocess_match_metric", "IOU").upper() not in METRICS:
        raise ValueError(f"postprocess_match_metric must be one of {', '.join(METRICS)}")
    for key in ("postprocess_type", "postprocess_match_metric"):
        if key in kw:
            kw[key] = kw[key].upper()
    return SliceConfig(**kw)


# --- inference-time options (Ultralytics models) ---------------------------------------------------

_MODEL_INTS = {"imgsz": (32, 4096), "max_det": (1, 3000)}
_MODEL_FLAGS = ("agnostic_nms", "augment", "half", "retina_masks")


def parse_model_options(raw: dict) -> dict:
    """Validated inference-time options: image size, max detections, agnostic NMS, TTA (augment),
    half precision, retina masks and a class-id filter. Empty when none were given."""
    out: dict = {}
    for key, (lo, hi) in _MODEL_INTS.items():
        if raw.get(key) is not None:
            value = int(raw[key])
            if not lo <= value <= hi:
                raise ValueError(f"{key} must be {lo}-{hi}")
            out[key] = value
    for key in _MODEL_FLAGS:
        if raw.get(key) is not None:
            out[key] = bool(raw[key])
    if raw.get("class_ids") not in (None, ""):
        try:
            out["class_ids"] = [int(x) for x in str(raw["class_ids"]).split(",") if x.strip()]
        except ValueError as e:
            raise ValueError("class_ids must be comma-separated numbers") from e
    return out


# --- running it -----------------------------------------------------------------------------------

def _shift(pred: dict, ox: int, oy: int, width: int, height: int, min_area_ratio: float) -> dict | None:
    """Move a slice-local box into image coordinates, clip it, and drop it when too little of it is left."""
    x1, y1 = pred["x"] - pred["width"] / 2 + ox, pred["y"] - pred["height"] / 2 + oy
    x2, y2 = pred["x"] + pred["width"] / 2 + ox, pred["y"] + pred["height"] / 2 + oy
    full = max(1e-9, (x2 - x1) * (y2 - y1))
    cx1, cy1, cx2, cy2 = max(0.0, x1), max(0.0, y1), min(float(width), x2), min(float(height), y2)
    if cx2 - cx1 < 1 or cy2 - cy1 < 1 or ((cx2 - cx1) * (cy2 - cy1)) / full < min_area_ratio:
        return None
    out = dict(pred)
    out.update(x=round((cx1 + cx2) / 2, 1), y=round((cy1 + cy2) / 2, 1),
               width=round(cx2 - cx1, 1), height=round(cy2 - cy1, 1))
    if out.get("points"):
        out["points"] = [{"x": round(min(width, max(0.0, q["x"] + ox)), 1),
                          "y": round(min(height, max(0.0, q["y"] + oy)), 1)} for q in out["points"]]
    return out


def sahi_predict(model, im: PImage.Image, cfg: SliceConfig, **kw) -> dict:
    """Slice, predict every slice (plus the whole image when asked), shift back, post-process."""
    if model.adapter.family in ("sam3", "vlm") or not (
            {"detect", "segment"} & set(model.adapter.capabilities(getattr(model, "variant", "")))):
        raise ValueError("slice inference needs a detection or segmentation model")
    t0 = time.perf_counter()
    cfg = cfg.resolve(im.width, im.height)
    pieces: list[dict] = []
    for box in cfg.boxes(im.width, im.height):
        out = model.predict(im.crop(box), **kw)
        if "top" in out:
            raise ValueError("slice inference needs a detection or segmentation model")
        for p in out.get("predictions", []):
            shifted = _shift(p, box[0], box[1], im.width, im.height, cfg.min_area_ratio)
            if shifted is not None:
                pieces.append(shifted)
    if cfg.perform_standard_pred:
        pieces += model.predict(im, **kw).get("predictions", [])
    kept = postprocess(pieces, kind=cfg.postprocess_type, metric=cfg.postprocess_match_metric,
                       threshold=cfg.postprocess_match_threshold, class_agnostic=cfg.postprocess_class_agnostic)
    return {"predictions": kept, "time": round(time.perf_counter() - t0, 4),
            "image": {"width": im.width, "height": im.height}, "model": getattr(model, "ref", ""),
            "slices": len(cfg.boxes(im.width, im.height)) + (1 if cfg.perform_standard_pred else 0)}
