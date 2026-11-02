"""Adapter contract shared by every model family (ultralytics, sam3, vlm, ...)."""
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from PIL import Image as PImage

log = logging.getLogger("labeldesk.adapters")


@dataclass
class Availability:
    ok: bool
    reason: str = ""
    vram_mb: int = 0


@dataclass
class TrainResult:
    weights: str
    run_dir: str
    history: list[dict] = field(default_factory=list)


class Adapter(Protocol):
    """Optional members: train(variant, dataset_dir: Path, task, opts, on_epoch, should_stop) -> TrainResult,
    export(weights: str, fmt: str) -> Path, runtime_key(variant, weights) -> str | None (the GPU
    scheduler lease key for this variant, or None for a remote family like vLLM)."""
    family: str

    def probe(self) -> Availability: ...
    def capabilities(self, variant: str) -> set[str]: ...
    def predict(self, variant: str, im: PImage.Image, *, classes: list[str] | None = None,
                prompt: str | None = None, weights: str | None = None, conf: float = 0.4,
                iou: float = 0.5) -> dict: ...


class Cancelled(RuntimeError):
    """A job stopped on purpose before it produced anything registrable (worker maps it to `cancelled`)."""


ADAPTERS: dict[str, Adapter] = {}


def register(adapter: Adapter) -> Adapter:
    ADAPTERS[adapter.family] = adapter
    return adapter


def parse_ref(ref: str) -> tuple[str, str]:
    """'<family>:<variant>' or 'trained:<id>' -> (family, variant)."""
    fam, sep, rest = ref.partition(":")
    if not sep or not fam or not rest:
        raise ValueError(f"bad model ref {ref!r}; expected '<family>:<variant>' or 'trained:<id>'")
    return fam, rest


@dataclass
class Resolved:
    """A model_ref bound to its adapter. weights (DATA_DIR-relative) is set for trained models only.

    conf is the model's own default threshold (the evaluator's best-F1 confidence); None keeps the
    adapter default. Callers that pass conf= explicitly always win."""
    adapter: Adapter
    variant: str
    weights: str | None
    ref: str
    conf: float | None = None
    fallback: "Resolved | None" = None      # the .pt runtime, retried when a TensorRT engine fails to load

    def predict(self, im: PImage.Image, **kw) -> dict:
        if self.conf is not None and "conf" not in kw:
            kw["conf"] = self.conf
        try:
            out = self.adapter.predict(self.variant, im, weights=self.weights, **kw)
        except (RuntimeError, ValueError, OSError, ImportError) as e:
            from ..gpu import GpuBusy
            if isinstance(e, (GpuBusy, Cancelled)) or self.fallback is None:
                raise
            if self.adapter.family == "tensorrt" and self.weights:
                from .catalog import mark_engine_failed
                mark_engine_failed(self.weights)          # a dead engine must not be retried per image
            log.warning("model %s failed on the %s runtime (%s); falling back to %s",
                        self.ref, self.adapter.family, e, self.fallback.adapter.family)
            out = self.fallback.adapter.predict(self.variant, im, weights=self.fallback.weights, **kw)
        out["model"] = self.ref
        return out


_PRED_KEYS = ("class", "class_id", "confidence", "x", "y", "width", "height")


def validate_prediction(d: dict) -> None:
    """Raise ValueError unless d follows the shared prediction schema."""
    if not isinstance(d, dict):
        raise ValueError("prediction must be a dict")
    if not isinstance(d.get("model"), str):
        raise ValueError("model: str required")
    im = d.get("image")
    if not (isinstance(im, dict) and isinstance(im.get("width"), int) and isinstance(im.get("height"), int)):
        raise ValueError("image: {width:int, height:int} required")
    if not isinstance(d.get("time"), (int, float)):
        raise ValueError("time: float required")
    preds = d.get("predictions")
    if not isinstance(preds, list):
        raise ValueError("predictions: list required")
    keys = _PRED_KEYS[:3] if "top" in d else _PRED_KEYS     # classification results carry no box
    for p in preds:
        missing = [k for k in keys if not isinstance(p, dict) or k not in p]
        if missing:
            raise ValueError(f"prediction missing {missing}")
    if "text" in d and not isinstance(d["text"], str):
        raise ValueError("text must be str")
