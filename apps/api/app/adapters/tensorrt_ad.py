"""TensorRT family: an engine exported from an Ultralytics checkpoint, loaded through YOLO()."""
import importlib.util
import logging
from pathlib import Path

from PIL import Image as PImage

from ..config import DATA_DIR
from .base import Availability, register
from .ultralytics_ad import VRAM_MB, _load, _run, caps_for, lease_key

log = logging.getLogger("labeldesk.tensorrt")


class TensorrtAdapter:
    family = "tensorrt"

    def probe(self) -> Availability:
        if importlib.util.find_spec("ultralytics") is None:
            return Availability(False, "ultralytics not installed")
        if importlib.util.find_spec("tensorrt") is None:      # engines need the TensorRT runtime
            return Availability(False, "tensorrt not installed")
        return Availability(True, vram_mb=VRAM_MB)

    def capabilities(self, variant: str) -> set[str]:
        return caps_for(variant)

    def runtime_key(self, variant: str, weights: str | None) -> str | None:
        return lease_key(variant, weights) if weights else None

    def predict(self, variant, im: PImage.Image, *, classes=None, prompt=None, weights=None,
                conf=0.4, iou=0.5) -> dict:
        """An engine is always bound to a trained model, so weights is the DATA_DIR-relative .engine."""
        if not weights:
            raise ValueError("tensorrt models run an exported engine; weights is required")
        path = DATA_DIR / weights
        if not Path(path).exists():
            log.warning("TensorRT engine missing: %s", path)
            raise ValueError("the TensorRT engine for this model is missing; re-export it")
        return _run(_load(str(path)), im, conf, iou)


register(TensorrtAdapter())
