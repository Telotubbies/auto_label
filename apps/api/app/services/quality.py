"""Per-image quality signals measured once at ingest: sharpness and mean luminance.

Both come from the image the upload has already decoded and are stored on the `Image` row, so the
dataset filter and the health check read columns instead of decoding pixels again. A row with no
stored score is *unknown* — never quietly counted as good.

Sharpness is the variance of the Laplacian of a grayscale copy downscaled to `SIDE` px, divided by
`SHARPNESS_SCALE` and clamped to 0-1. The scale is chosen so the Encord-style floor of 0.005 is
exactly Laplacian variance 100 on that scale: 100 is also this codebase's own boundary between the
"soft/blurred" and "usable" bins of `insights_jobs.BLUR_BUCKETS`. Smooth gradients and Gaussian-
blurred frames measure 10-20, a focused photo measures thousands. Luminance is the mean of the same
grayscale copy over 255, so 0 is black and 1 is white.
"""

import cv2
import numpy as np
from PIL import Image as PImage
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Image, Project

SIDE = 512  # downscale before measuring: full resolution makes the score depend on camera MP
SHARPNESS_SCALE = 20_000.0  # Laplacian variance that maps to sharpness 1.0
BLUR_FLOOR = 0.005  # Encord's sharpness floor on a 0-1 scale == variance 100 here
DARK_MEAN = 0.1  # mean luminance below 10 % of full scale counts as too dark
SAMPLE = 50  # capped per-class sample of image ids in the health payload
CLASSES = ("blurry", "dark", "ok", "unknown")

_KNOWN = Image.sharpness.is_not(None) & Image.luminance.is_not(None)


def analyze(im: PImage.Image) -> tuple[float, float]:
    """(sharpness, luminance), both in 0-1, for an already-decoded RGB image."""
    gray = im.convert("L")
    gray.thumbnail((SIDE, SIDE))  # in place, keeps the aspect ratio, never upscales
    pixels = np.asarray(gray, dtype=np.float32)
    variance = float(cv2.Laplacian(pixels, cv2.CV_32F).var())
    return min(1.0, variance / SHARPNESS_SCALE), float(pixels.mean()) / 255.0


def classify(sharpness: float | None, luminance: float | None) -> str:
    """Blur first, then darkness; a missing score makes the image unknown on both axes."""
    if sharpness is None or luminance is None:
        return "unknown"
    if sharpness < BLUR_FLOOR:
        return "blurry"
    if luminance < DARK_MEAN:
        return "dark"
    return "ok"


def sql_filter(kind: str):
    """SQL twin of `classify` for the dataset list; the three known classes plus their complement."""
    if kind == "unknown":
        return Image.sharpness.is_(None) | Image.luminance.is_(None)
    if kind == "blurry":
        return _KNOWN & (Image.sharpness < BLUR_FLOOR)
    if kind == "dark":
        return _KNOWN & (Image.sharpness >= BLUR_FLOOR) & (Image.luminance < DARK_MEAN)
    if kind == "ok":
        return _KNOWN & (Image.sharpness >= BLUR_FLOOR) & (Image.luminance >= DARK_MEAN)
    raise ValueError("bad quality")


def summary(db: Session, project: Project, limit: int = SAMPLE) -> dict:
    """Counts per class plus a capped sample of ids, read from the stored columns only."""
    counts = dict.fromkeys(CLASSES, 0)
    samples: dict[str, list[str]] = {"blurry": [], "dark": []}
    rows = db.execute(
        select(Image.id, Image.sharpness, Image.luminance)
        .where(Image.project_id == project.id, Image.deleted_at.is_(None))
        .order_by(Image.created, Image.id)
    ).all()
    for image_id, sharpness, luminance in rows:
        kind = classify(sharpness, luminance)
        counts[kind] += 1
        if kind in samples and len(samples[kind]) < limit:
            samples[kind].append(image_id)
    return {"counts": counts, "samples": samples}
