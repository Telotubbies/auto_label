"""Click/text-prompted segmentation.

Smart Polygon uses SAM 3.1 (box prompt around the clicks) when the model is
loadable, else OpenCV GrabCut seeded by the clicks — CPU-only, ~100 ms.
Auto Label uses SAM 3.1 text prompts (one per class name); it has no fallback.
"""
import logging
import math
import sys
import threading
from collections import OrderedDict

import cv2
import numpy as np
from PIL import Image as PImage

from ..config import SAM_ENABLED, SAM_ROOT

log = logging.getLogger("labeldesk.segment")
_sam = {"proc": None, "err": None}
_sam_lock = threading.Lock()

SAM_VRAM_MB = 3000      # spec 3.6 says 3-4 GB; 4 GB could never coexist with a detector in the 4.5 GB budget

DEFAULT_EPS = 0.004     # approxPolyDP tolerance as a fraction of the contour perimeter
EPS_MIN = 0.0005
EPS_MAX = 0.02


def clamp_epsilon(value: float) -> float:
    """Keep the Smart Polygon tolerance inside the range the editor slider offers."""
    eps = float(value)
    if not math.isfinite(eps):
        raise ValueError("epsilon must be a finite number")
    return min(EPS_MAX, max(EPS_MIN, eps))


# --- geometry helpers ---------------------------------------------------------

def mask_to_polygon(mask: np.ndarray, seed: tuple[int, int] | None = None, eps: float = DEFAULT_EPS) -> list[float] | None:
    """Largest (or seed-containing) outer contour -> normalized flat polygon."""
    h, w = mask.shape
    m = (mask > 0).astype("uint8")
    contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    pick = None
    if seed:
        pick = next((c for c in contours if cv2.pointPolygonTest(c, seed, False) >= 0), None)
    c = pick if pick is not None else max(contours, key=cv2.contourArea)
    c = cv2.approxPolyDP(c, eps * cv2.arcLength(c, True), True)
    if len(c) < 3:
        return None
    return [round(float(v), 5) for pt in c[:, 0, :] for v in (pt[0] / w, pt[1] / h)]


# --- GrabCut fallback -----------------------------------------------------------

def _grabcut_mask(im: PImage.Image, points: list[list[float]], negatives: list[list[float]] | None = None
                  ) -> tuple[np.ndarray, tuple[int, int]] | None:
    """GrabCut foreground mask plus the positive click that seeds the contour pick."""
    scale = min(1.0, 800 / max(im.size))
    small = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))))
    arr = cv2.cvtColor(np.asarray(small), cv2.COLOR_RGB2BGR)
    H, W = arr.shape[:2]
    px = [(int(x * W), int(y * H)) for x, y in points]
    xs, ys = [p[0] for p in px], [p[1] for p in px]
    if len(px) == 1:
        rw, rh = int(W * 0.18), int(H * 0.18)
        x1, y1, x2, y2 = xs[0] - rw, ys[0] - rh, xs[0] + rw, ys[0] + rh
    else:
        dx, dy = max(12, int((max(xs) - min(xs)) * 0.25)), max(12, int((max(ys) - min(ys)) * 0.25))
        x1, y1, x2, y2 = min(xs) - dx, min(ys) - dy, max(xs) + dx, max(ys) + dy
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(W - 1, x2), min(H - 1, y2)
    if x2 - x1 < 4 or y2 - y1 < 4:
        return None
    mask = np.full((H, W), cv2.GC_BGD, np.uint8)
    mask[y1:y2, x1:x2] = cv2.GC_PR_FGD
    r = max(3, int(min(W, H) * 0.012))
    for p in px:
        cv2.circle(mask, p, r, cv2.GC_FGD, -1)
    for x, y in negatives or []:
        cv2.circle(mask, (int(x * W), int(y * H)), r, cv2.GC_BGD, -1)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(arr, mask, None, bgd, fgd, 5, cv2.GC_INIT_WITH_MASK)
    fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 1, 0).astype("uint8")
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    return fg, px[0]


def grabcut(im: PImage.Image, points: list[list[float]], negatives: list[list[float]] | None = None,
            eps: float = DEFAULT_EPS) -> list[float] | None:
    found = _grabcut_mask(im, points, negatives)
    if found is None:
        return None
    mask, seed = found
    return mask_to_polygon(mask, seed=seed, eps=eps)


# --- SAM 3.1 ----------------------------------------------------------------------

def _load_sam():
    if _sam["proc"] is not None or _sam["err"] is not None:
        return _sam["proc"]
    with _sam_lock:
        if _sam["proc"] is not None or _sam["err"] is not None:
            return _sam["proc"]
        if SAM_ENABLED == "0":
            _sam["err"] = "disabled by LD_SAM_ENABLED=0"
            return None
        try:
            for p in (SAM_ROOT / "src", SAM_ROOT / "sam3"):
                if str(p) not in sys.path:
                    sys.path.insert(0, str(p))
            if not (SAM_ROOT / "checkpoints" / "sam3.1_multiplex.pt").exists():
                raise FileNotFoundError(f"SAM checkpoint missing under {SAM_ROOT / 'checkpoints'}")
            from config import Config                      # sam3_auto_label/src/config.py
            from inference import build_model
            _sam["proc"] = build_model(Config(base_dir=str(SAM_ROOT)))
            log.info("SAM 3.1 loaded")
        except Exception as e:  # torch/sam3 missing, no checkpoint, OOM …
            _sam["err"] = f"{type(e).__name__}: {e}"
            log.warning("SAM unavailable — %s", _sam["err"])
    return _sam["proc"]


def sam_status() -> dict:
    return {"loaded": _sam["proc"] is not None, "error": _sam["err"]}


def _require_sam():
    proc = _load_sam()
    if proc is None:
        raise RuntimeError(f"SAM 3.1 is not available on this worker ({_sam['err']})")
    return proc


def lease_sam():
    """Account for SAM in the GPU VRAM ledger (every caller loads through here)."""
    from ..gpu import scheduler                  # imported lazily: app.gpu imports the adapters package
    return scheduler.lease("sam3", SAM_VRAM_MB, _require_sam, lambda _proc: unload_sam())


def _try_lease_sam():
    if SAM_ENABLED == "0":
        return None
    try:
        return lease_sam()
    except RuntimeError:
        return None


def unload_sam() -> None:
    """Drop the cached model so the GPU scheduler can reclaim its VRAM (training is exclusive)."""
    with _sam_lock:
        if _sam["proc"] is not None:
            _sam["proc"] = None
            _sam["err"] = None
    import gc
    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:                      # CPU-only installs have nothing to free
        pass


def _masks(output) -> list[tuple[np.ndarray, float]]:
    masks, scores = output.get("masks"), output.get("scores")
    if masks is None or len(masks) == 0:
        return []
    m = masks.float().cpu().numpy()
    s = scores.float().cpu().numpy() if scores is not None else np.ones(len(m))
    return [(mi.squeeze() > 0.5, float(si)) for mi, si in zip(m, s)]


def _sam_mask(im: PImage.Image, points: list[list[float]], negatives: list[list[float]] | None
              ) -> tuple[np.ndarray, tuple[int, int]] | None:
    """Box-prompted SAM mask around the clicks, negatives carved out; None when SAM is unavailable."""
    proc = _try_lease_sam()
    if proc is None or not points:
        return None
    try:
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        pad = 0.08
        x1, y1 = max(0, min(xs) - pad), max(0, min(ys) - pad)
        x2, y2 = min(1, max(xs) + pad), min(1, max(ys) + pad)
        state = proc.set_image(im)
        out = proc.add_geometric_prompt([(x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1], True, state)
        cands = _masks(out)
        sx, sy = int(points[0][0] * im.width), int(points[0][1] * im.height)
        hit = [c for c in cands if c[0].shape == (im.height, im.width) and c[0][sy, sx]]
        best = max(hit or cands, key=lambda c: c[1], default=None)
        if best is not None:
            mask = best[0].astype("uint8").copy()
            if negatives:               # negative clicks carve the same way GrabCut's background seeds do
                r = max(3, int(min(im.height, im.width) * 0.012))
                for x, y in negatives:
                    cv2.circle(mask, (int(x * im.width), int(y * im.height)), r, 0, -1)
            return mask, (sx, sy)
    except Exception as e:
        log.warning("SAM smart polygon failed, using GrabCut: %s", e)
    return None


def _segment_mask(im: PImage.Image, points: list[list[float]], negatives: list[list[float]] | None
                  ) -> tuple[np.ndarray, tuple[int, int] | None, str] | None:
    """SAM first, GrabCut when SAM is unavailable or produced no usable contour."""
    found = _sam_mask(im, points, negatives)
    if found is not None and mask_to_polygon(found[0], seed=found[1]) is not None:
        return found[0], found[1], "sam3.1"
    fallback = _grabcut_mask(im, points, negatives)
    if fallback is None:
        return None
    return fallback[0], fallback[1], "grabcut"


# Moving the simplification slider sends the same clicks again; keep the last few masks so only the
# Douglas-Peucker pass re-runs instead of SAM or GrabCut.
_MASKS: OrderedDict[tuple, tuple[np.ndarray, tuple[int, int] | None, str]] = OrderedDict()
_MASKS_MAX = 4
_masks_lock = threading.Lock()


def _mask_get(key: tuple) -> tuple[np.ndarray, tuple[int, int] | None, str] | None:
    with _masks_lock:
        hit = _MASKS.get(key)
        if hit is not None:
            _MASKS.move_to_end(key)
        return hit


def _mask_put(key: tuple, value: tuple[np.ndarray, tuple[int, int] | None, str]) -> None:
    with _masks_lock:
        _MASKS[key] = value
        while len(_MASKS) > _MASKS_MAX:
            _MASKS.popitem(last=False)


def smart_polygon(im: PImage.Image, points: list[list[float]], negatives=None, eps: float = DEFAULT_EPS,
                  cache_key: str | None = None) -> tuple[list[float] | None, str]:
    """Clicks -> (simplified polygon, source). `eps` re-simplifies a cached mask without re-segmenting."""
    eps = clamp_epsilon(eps)
    key = None
    if cache_key:
        key = (cache_key, tuple((p[0], p[1]) for p in points), tuple((p[0], p[1]) for p in negatives or []))
    hit = _mask_get(key) if key else None
    if hit is None:
        hit = _segment_mask(im, points, negatives)
        if hit is None:
            return None, "grabcut"
        if key:
            _mask_put(key, hit)
    mask, seed, source = hit
    return mask_to_polygon(mask, seed=seed, eps=eps), source


def sam_text(im: PImage.Image, prompts: list[str], threshold: float = 0.4) -> list[tuple[int, list[float], float]]:
    """-> [(prompt index, normalized polygon, score)]; raises if SAM can't load."""
    proc = lease_sam()
    if proc is None:
        raise RuntimeError(f"SAM 3.1 is not available on this worker ({_sam['err']})")
    state = proc.set_image(im)
    out = []
    for i, prompt in enumerate(prompts):
        proc.reset_all_prompts(state)
        for mask, score in _masks(proc.set_text_prompt(state=state, prompt=prompt)):
            if score >= threshold:
                poly = mask_to_polygon(mask.astype("uint8"))
                if poly:
                    out.append((i, poly, score))
    return out


def sam_box(im: PImage.Image, box_xyxy_px: tuple[float, float, float, float]) -> tuple[list[float] | None, float]:
    """Box prompt -> (normalized flat polygon, score); (None, 0.0) when SAM is unavailable or finds nothing."""
    proc = _try_lease_sam()
    if proc is None:
        return None, 0.0
    try:
        x1, y1, x2, y2 = box_xyxy_px
        W, H = im.width, im.height
        state = proc.set_image(im)
        out = proc.add_geometric_prompt([(x1 + x2) / 2 / W, (y1 + y2) / 2 / H, (x2 - x1) / W, (y2 - y1) / H], True, state)
        best = max(_masks(out), key=lambda c: c[1], default=None)
        if best is not None:
            poly = mask_to_polygon(best[0].astype("uint8"))
            if poly:
                return poly, best[1]
    except Exception as e:
        log.warning("SAM box prompt failed: %s", e)
    return None, 0.0
