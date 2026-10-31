"""Click/text-prompted segmentation.

Smart Polygon uses SAM 3.1 (box prompt around the clicks) when the model is
loadable, else OpenCV GrabCut seeded by the clicks — CPU-only, ~100 ms.
Auto Label uses SAM 3.1 text prompts (one per class name); it has no fallback.
"""
import logging
import sys
import threading

import cv2
import numpy as np
from PIL import Image as PImage

from ..config import SAM_ENABLED, SAM_ROOT

log = logging.getLogger("labeldesk.segment")
_sam = {"proc": None, "err": None}
_sam_lock = threading.Lock()

SAM_VRAM_MB = 3000      # spec 3.6 says 3-4 GB; 4 GB could never coexist with a detector in the 4.5 GB budget


# --- geometry helpers ---------------------------------------------------------

def mask_to_polygon(mask: np.ndarray, seed: tuple[int, int] | None = None, eps: float = 0.004) -> list[float] | None:
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

def grabcut(im: PImage.Image, points: list[list[float]], negatives: list[list[float]] | None = None) -> list[float] | None:
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
    return mask_to_polygon(fg, seed=px[0])


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


def smart_polygon(im: PImage.Image, points: list[list[float]], negatives=None) -> tuple[list[float] | None, str]:
    proc = _try_lease_sam()
    if proc is not None and len(points) >= 1:
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
                poly = mask_to_polygon(best[0].astype("uint8"), seed=(sx, sy))
                if poly:
                    return poly, "sam3.1"
        except Exception as e:
            log.warning("SAM smart polygon failed, using GrabCut: %s", e)
    return grabcut(im, points, negatives), "grabcut"


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
