"""Adapter contract shared by every model family (ultralytics, sam3, vlm, ...)."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from PIL import Image as PImage


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
    export(weights: str, fmt: str) -> Path."""
    family: str

    def probe(self) -> Availability: ...
    def capabilities(self, variant: str) -> set[str]: ...
    def predict(self, variant: str, im: PImage.Image, *, classes: list[str] | None = None,
                prompt: str | None = None, conf: float = 0.4, iou: float = 0.5) -> dict: ...


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
    for p in preds:
        missing = [k for k in _PRED_KEYS if not isinstance(p, dict) or k not in p]
        if missing:
            raise ValueError(f"prediction missing {missing}")
    if "text" in d and not isinstance(d["text"], str):
        raise ValueError("text must be str")
