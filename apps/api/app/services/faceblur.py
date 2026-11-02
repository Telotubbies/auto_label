"""Face anonymisation for CCTV frames before they enter a dataset (PDPA: faces are personal data).

CPU only: an OpenCV Haar cascade detects frontal faces; PIL blurs a padded square around each face.
The detector is injectable so tests never need the cascade file. Unavailable OpenCV or a missing
cascade degrades to "no faces found" and is logged once — a broken blur must never stop an upload.
"""

import logging
from collections.abc import Callable
from functools import lru_cache

import numpy as np
from PIL import Image, ImageFilter

log = logging.getLogger(__name__)

CASCADE_FILE = "haarcascade_frontalface_default.xml"
MAX_DETECT_PX = 640  # downscale before detection; boxes are scaled back
Detector = Callable[[np.ndarray], list[tuple[int, int, int, int]]]


@lru_cache(maxsize=1)
def _cascade():
    """The Haar classifier, or None (logged once) when OpenCV or the cascade is unavailable."""
    try:
        import cv2

        classifier = cv2.CascadeClassifier(cv2.data.haarcascades + CASCADE_FILE)
        if classifier.empty():
            raise RuntimeError("cascade file could not be loaded")
        return classifier
    except Exception:  # no cv2, no cv2.data, corrupt install — degrade, never raise
        log.warning("face detection unavailable; stream frames will not be blurred")
        return None


def available() -> bool:
    """True when the Haar detector can actually run (fail-closed callers check this)."""
    return _cascade() is not None


def detect_faces(gray: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Frontal faces in a grayscale array as (x, y, w, h) pixels; [] when detection is unavailable."""
    classifier = _cascade()
    if classifier is None or gray is None:
        return []
    arr = np.asarray(gray)
    if arr.ndim == 3:
        arr = arr[..., :3].mean(axis=2)
    if arr.dtype != np.uint8:
        arr = arr.astype(np.uint8)
    try:
        faces = classifier.detectMultiScale(arr, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24))
    except Exception:  # OpenCV assertion on odd shapes must not break ingest
        log.exception("face detection failed")
        return []
    return [(int(x), int(y), int(w), int(h)) for x, y, w, h in faces]


def _region(box: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    """Padded square around a face, clamped to the image."""
    x, y, w, h = box
    cx, cy = x + w / 2, y + h / 2
    half = max(w, h) / 2 + max(w, h) * 0.25
    return (max(0, int(cx - half)), max(0, int(cy - half)), min(width, int(cx + half)), min(height, int(cy + half)))


def blur_faces(im: Image.Image, detector: Detector | None = None) -> tuple[Image.Image, int]:
    """Blur every detected face; return (image, faces_blurred).

    Returns the same image object when nothing was found. The blur radius grows with the face so
    a close-up is not merely softened.
    """
    work = im if im.mode == "RGB" else im.convert("RGB")
    width, height = work.size
    scale = min(1.0, MAX_DETECT_PX / max(width, height))
    small = work if scale >= 1.0 else work.resize((max(1, round(width * scale)), max(1, round(height * scale))))
    boxes = (detector or detect_faces)(np.asarray(small.convert("L")))
    if not boxes:
        return work, 0
    out = work.copy()
    for box in boxes:
        if scale < 1.0:
            box = tuple(round(v / scale) for v in box)
        left, top, right, bottom = _region(box, width, height)
        if right - left < 2 or bottom - top < 2:
            continue
        side = max(box[2], box[3])
        kernel = max(31, 2 * int(side / 3) + 1)
        radius = max(8.0, kernel / 2.0)
        out.paste(out.crop((left, top, right, bottom)).filter(ImageFilter.GaussianBlur(radius)), (left, top))
    return out, len(boxes)
