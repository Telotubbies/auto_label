"""SAM calls must run under bf16 autocast (the model is mixed bf16/fp32 — see segment._autocast)."""

import contextlib
import os
import tempfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-test-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import torch
from PIL import Image as PImage

from app.services import segment


@contextlib.contextmanager
def _spy(entered: list[str]):
    entered.append("enter")
    try:
        yield
    finally:
        entered.append("exit")


class _Proc:
    def __init__(self, entered: list[str]) -> None:
        self.entered = entered

    def set_image(self, _im):
        assert self.entered == ["enter"], "set_image must run inside the autocast block"
        return {}

    def reset_all_prompts(self, _state) -> None:
        assert self.entered == ["enter"]

    def set_text_prompt(self, *, state, prompt):
        assert self.entered == ["enter"], "the text prompt must run inside the autocast block"
        masks = torch.zeros(1, 32, 32)
        masks[:, 8:24, 8:24] = 1
        return {"masks": masks, "scores": torch.tensor([0.9])}

    def add_geometric_prompt(self, _box, _positive, _state):
        assert self.entered == ["enter"], "the box prompt must run inside the autocast block"
        masks = torch.zeros(1, 32, 32)
        masks[:, 8:24, 8:24] = 1
        return {"masks": masks, "scores": torch.tensor([0.9])}


def test_sam_text_prompts_run_under_autocast(monkeypatch):
    entered: list[str] = []
    monkeypatch.setattr(segment, "_autocast", lambda: _spy(entered))
    monkeypatch.setattr(segment, "lease_sam", lambda: _Proc(entered))
    out = segment.sam_text(PImage.new("RGB", (32, 32)), ["person"], 0.4)
    assert out and entered == ["enter", "exit"]


def test_sam_box_prompt_runs_under_autocast(monkeypatch):
    entered: list[str] = []
    monkeypatch.setattr(segment, "_autocast", lambda: _spy(entered))
    monkeypatch.setattr(segment, "_try_lease_sam", lambda: _Proc(entered))
    poly, score = segment.sam_box(PImage.new("RGB", (32, 32)), (8, 8, 24, 24))
    assert poly and score > 0 and entered == ["enter", "exit"]


def test_smart_polygon_runs_under_autocast(monkeypatch):
    entered: list[str] = []
    monkeypatch.setattr(segment, "_autocast", lambda: _spy(entered))
    monkeypatch.setattr(segment, "_try_lease_sam", lambda: _Proc(entered))
    poly, label = segment.smart_polygon(PImage.new("RGB", (32, 32)), [[0.5, 0.5]])
    assert entered == ["enter", "exit"]
    assert poly and label == "sam3.1"


def test_autocast_is_cuda_bfloat16_when_cuda_is_available(monkeypatch):
    # A CPU-only torch build refuses to construct a CUDA autocast context, so stub the two
    # capability probes; the context itself is pure bookkeeping until ops run.
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "is_bf16_supported", lambda: True)
    ctx = segment._autocast()
    assert getattr(ctx, "device", None) == "cuda"
    assert getattr(ctx, "fast_dtype", None) == torch.bfloat16
    with ctx:
        assert torch.is_autocast_enabled()
        assert torch.get_autocast_dtype("cuda") == torch.bfloat16


def test_autocast_is_a_noop_without_cuda(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    ctx = segment._autocast()
    assert getattr(ctx, "device", None) is None, "CPU installs must not enter a CUDA autocast"
    with ctx:
        assert not torch.is_autocast_enabled()
