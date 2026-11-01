"""Image ingest + the preprocessing/augmentation ops used when generating versions.

Annotations are normalized (0..1) so geometric ops only remap coordinates:
  bbox      {"kind":"bbox","x","y","w","h"}   (top-left + size)
  polygon   {"kind":"polygon","points":[x,y,...]}
  class     {"kind":"class"}                   (classification label, no geometry)
  obb       {"kind":"obb","cx","cy","w","h","angle"}  (angle in radians, clockwise in pixel space)
  keypoints {"kind":"keypoints","points":[x,y,v,...]}  (v: 0 absent, 1 occluded, 2 visible)
"""
import copy
import io
import math
import random
from pathlib import Path

from PIL import Image as PImage, ImageFilter, ImageEnhance, ImageOps

from ..config import DATA_DIR

PImage.MAX_IMAGE_PIXELS = 120_000_000      # ~11k×11k; larger raises DecompressionBombError

THUMB = 480
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def open_image(data: bytes) -> PImage.Image:
    im = PImage.open(io.BytesIO(data))
    im = ImageOps.exif_transpose(im)          # auto-orient on ingest, like Roboflow
    return im.convert("RGB")


def store(rel_dir: str, stem: str, im: PImage.Image) -> tuple[str, str]:
    """Write full-res jpg + thumbnail; return paths relative to DATA_DIR."""
    d = DATA_DIR / rel_dir
    (d / "thumbs").mkdir(parents=True, exist_ok=True)
    full, thumb = f"{rel_dir}/{stem}.jpg", f"{rel_dir}/thumbs/{stem}.jpg"
    im.save(DATA_DIR / full, "JPEG", quality=92)
    t = im.copy(); t.thumbnail((THUMB, THUMB))
    t.save(DATA_DIR / thumb, "JPEG", quality=80)
    return full, thumb


def load(rel: str) -> PImage.Image:
    return PImage.open(DATA_DIR / rel).convert("RGB")


# --- annotation geometry ---------------------------------------------------

def obb_corners(s: dict, W: float = 1.0, H: float = 1.0) -> list[tuple[float, float]]:
    """Pixel-space corners of an obb, clockwise from top-left at angle 0."""
    cx, cy = s["cx"] * W, s["cy"] * H
    hw, hh = s["w"] * W / 2, s["h"] * H / 2
    c, sn = math.cos(s["angle"]), math.sin(s["angle"])
    return [(cx + dx * c - dy * sn, cy + dx * sn + dy * c)
            for dx, dy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))]


def _map_points(ann: dict, fn) -> dict:
    """Apply fn(x, y) -> (x, y) to an annotation's geometry; bbox re-fit from corners."""
    a = copy.deepcopy(ann)
    s = a["shape"]
    if s["kind"] == "bbox":
        xs, ys = [], []
        for cx, cy in ((s["x"], s["y"]), (s["x"] + s["w"], s["y"]), (s["x"], s["y"] + s["h"]), (s["x"] + s["w"], s["y"] + s["h"])):
            nx, ny = fn(cx, cy); xs.append(nx); ys.append(ny)
        s.update(x=min(xs), y=min(ys), w=max(xs) - min(xs), h=max(ys) - min(ys))
    elif s["kind"] == "polygon":
        pts = s["points"]; out = []
        for i in range(0, len(pts) - 1, 2):
            out.extend(fn(pts[i], pts[i + 1]))
        s["points"] = out
    elif s["kind"] == "obb":                       # centre follows the transform; shape and angle stay
        s["cx"], s["cy"] = fn(s["cx"], s["cy"])
    elif s["kind"] == "keypoints":
        pts = s["points"]
        out = []
        for i in range(0, len(pts) - 2, 3):
            x, y = fn(pts[i], pts[i + 1])
            out.extend((x, y, pts[i + 2]))
        s["points"] = out
    return a


def _clip(ann: dict) -> dict | None:
    s = ann["shape"]
    if s["kind"] == "bbox":
        x1, y1 = max(0.0, s["x"]), max(0.0, s["y"])
        x2, y2 = min(1.0, s["x"] + s["w"]), min(1.0, s["y"] + s["h"])
        if x2 - x1 < 1e-3 or y2 - y1 < 1e-3:
            return None
        s.update(x=x1, y=y1, w=x2 - x1, h=y2 - y1)
    elif s["kind"] == "polygon":
        s["points"] = [min(1.0, max(0.0, v)) for v in s["points"]]
    elif s["kind"] == "obb":
        if s["w"] <= 0 or s["h"] <= 0:
            return None
        s["cx"], s["cy"] = min(1.0, max(0.0, s["cx"])), min(1.0, max(0.0, s["cy"]))
    elif s["kind"] == "keypoints":
        pts = s["points"]
        for i in range(0, len(pts) - 2, 3):
            if int(pts[i + 2]) != 0:               # absent points keep their placeholder coordinates
                pts[i], pts[i + 1] = min(1.0, max(0.0, pts[i])), min(1.0, max(0.0, pts[i + 1]))
    return ann


def bbox_of(ann: dict, W: float | None = None, H: float | None = None) -> tuple[float, float, float, float] | None:
    """Normalized (x, y, w, h) for bbox, polygon, obb or keypoint annotations."""
    s = ann["shape"]
    if s["kind"] == "bbox":
        return s["x"], s["y"], s["w"], s["h"]
    if s["kind"] == "polygon" and len(s["points"]) >= 6:
        xs, ys = s["points"][0::2], s["points"][1::2]
        return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
    if s["kind"] == "obb":
        # With image size the pixel-space corners are exact; otherwise the normalized shape is used as-is.
        pts = obb_corners(s, W or 1.0, H or 1.0)
        xs = [p[0] / (W or 1.0) for p in pts]
        ys = [p[1] / (H or 1.0) for p in pts]
        return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
    if s["kind"] == "keypoints":
        pts = s["points"]
        xs = [pts[i] for i in range(0, len(pts) - 2, 3) if int(pts[i + 2]) != 0]
        ys = [pts[i + 1] for i in range(0, len(pts) - 2, 3) if int(pts[i + 2]) != 0]
        if xs and ys:
            return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
    return None


# --- preprocessing ------------------------------------------------------------

def preprocess(im: PImage.Image, anns: list[dict], cfg: dict) -> tuple[PImage.Image, list[dict]]:
    rs = cfg.get("resize")
    if rs and rs.get("width") and rs.get("height"):
        W, H = int(rs["width"]), int(rs["height"])
        mode = rs.get("mode", "stretch")
        if mode == "fit":                      # letterbox: keep aspect, pad black
            scale = min(W / im.width, H / im.height)
            nw, nh = round(im.width * scale), round(im.height * scale)
            canvas = PImage.new("RGB", (W, H))
            ox, oy = (W - nw) // 2, (H - nh) // 2
            canvas.paste(im.resize((nw, nh)), (ox, oy))
            fx, fy, bx, by = nw / W, nh / H, ox / W, oy / H
            anns = [_map_points(a, lambda x, y: (bx + x * fx, by + y * fy)) for a in anns]
            im = canvas
        else:                                   # stretch: normalized coords unchanged
            im = im.resize((W, H))
    if cfg.get("grayscale"):
        im = ImageOps.grayscale(im).convert("RGB")
    if cfg.get("contrast"):
        im = ImageOps.autocontrast(im)
    return im, anns


# --- augmentation -------------------------------------------------------------

def augment(im: PImage.Image, anns: list[dict], cfg: dict, rng: random.Random) -> tuple[PImage.Image, list[dict]]:
    if cfg.get("flip_h") and rng.random() < 0.5:
        im = ImageOps.mirror(im)
        anns = [_map_points(a, lambda x, y: (1 - x, y)) for a in anns]
    if cfg.get("flip_v") and rng.random() < 0.5:
        im = ImageOps.flip(im)
        anns = [_map_points(a, lambda x, y: (x, 1 - y)) for a in anns]
    if cfg.get("rotate90") and rng.random() < 0.5:
        if rng.random() < 0.5:              # 90° clockwise
            im = im.transpose(PImage.Transpose.ROTATE_270)
            anns = [_map_points(a, lambda x, y: (1 - y, x)) for a in anns]
        else:                               # 90° counter-clockwise
            im = im.transpose(PImage.Transpose.ROTATE_90)
            anns = [_map_points(a, lambda x, y: (y, 1 - x)) for a in anns]
    deg = float(cfg.get("rotation") or 0)
    if deg:
        d = rng.uniform(-deg, deg)
        W, H = im.size
        im = im.rotate(d, resample=PImage.Resampling.BILINEAR)   # PIL rotates counter-clockwise about centre
        t = math.radians(d)
        c, s_ = math.cos(t), math.sin(t)

        def rot(x, y):
            px, py = x * W - W / 2, y * H - H / 2
            return ((px * c + py * s_) + W / 2) / W, ((-px * s_ + py * c) + H / 2) / H
        anns = [_map_points(a, rot) for a in anns]
    b = float(cfg.get("brightness") or 0)
    if b:
        im = ImageEnhance.Brightness(im).enhance(1 + rng.uniform(-b, b) / 100)
    e = float(cfg.get("exposure") or 0)
    if e:
        im = ImageEnhance.Contrast(im).enhance(1 + rng.uniform(-e, e) / 100)
    sat = float(cfg.get("saturation") or 0)
    if sat:
        im = ImageEnhance.Color(im).enhance(1 + rng.uniform(-sat, sat) / 100)
    g = float(cfg.get("grayscale_pct") or 0)
    if g and rng.random() < g / 100:
        im = ImageOps.grayscale(im).convert("RGB")
    bl = float(cfg.get("blur") or 0)
    if bl:
        im = im.filter(ImageFilter.GaussianBlur(rng.uniform(0, bl)))
    n = float(cfg.get("noise") or 0)
    if n:
        import numpy as np
        arr = np.asarray(im).astype("int16")
        mask = np.random.default_rng(rng.randint(0, 2**31)).random(arr.shape[:2]) < (n / 100)
        arr[mask] = np.random.default_rng(rng.randint(0, 2**31)).integers(0, 256, (int(mask.sum()), 3))
        im = PImage.fromarray(arr.clip(0, 255).astype("uint8"))
    return im, [c for c in (_clip(a) for a in anns) if c]


def ext_ok(name: str) -> bool:
    return Path(name).suffix.lower() in IMAGE_EXT
