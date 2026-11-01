"""RF-DETR adapter: probe, prediction mapping, epoch polling and checkpoint selection.

`rfdetr` is not installed here, so the package, the model and the Lightning CSV are faked.
"""
import os
import tempfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-test-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import importlib.util
import json
import sys
import time
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType

import pytest
from PIL import Image as PImage

from app.adapters import rfdetr_ad as rf
from app.adapters.base import Availability, validate_prediction
from app.config import DATA_DIR

VARIANTS = ("RFDETRNano", "RFDETRSmall", "RFDETRMedium", "RFDETRLarge")


# --- fakes ------------------------------------------------------------------------

class _Detections:
    """Just enough of supervision.Detections for the adapter's mapping."""
    xyxy = [[10.0, 20.0, 30.0, 60.0], [5.0, 5.0, 9.0, 9.0]]
    confidence = [0.9123, 0.71]
    class_id = [0, 1]
    data = {"class_name": ["helmet", "person"]}


class _FakeModel:
    def __init__(self):
        self.kw = None

    def predict(self, im, threshold=0.5, **kw):
        self.kw = {"threshold": threshold, **kw}
        return _Detections()


class _FakeRFDetr:
    """Stand-in for RFDETRNano/Small/Medium/Large: writes Lightning's CSV and a checkpoint."""
    made: list = []

    def __init__(self, **kw):
        self.init_kw = kw
        self.train_kw: dict = {}
        _FakeRFDetr.made.append(self)

    def train(self, **kw):
        self.train_kw = kw
        out = Path(kw["output_dir"])
        out.mkdir(parents=True, exist_ok=True)
        csv = out / "metrics.csv"
        csv.write_text("epoch,train/loss,val/mAP_50,val/mAP_50_95,val/precision,val/recall\n"
                       "0,1.5,0.61,0.41,0.70,0.66\n")
        time.sleep(0.03)                        # the poller sees the first row mid-run
        with open(csv, "a", encoding="utf-8") as f:
            f.write("1,0.90,0.72,0.52,0.75,nan\n")
        (out / "checkpoint_best_total.pth").write_bytes(b"rfdetr-weights")


def _install_fake(monkeypatch):
    """A fake `rfdetr` module with a real spec, so find_spec('rfdetr') succeeds."""
    mod = ModuleType("rfdetr")
    mod.__spec__ = ModuleSpec("rfdetr", None)
    for name in VARIANTS:
        setattr(mod, name, _FakeRFDetr)
    monkeypatch.setitem(sys.modules, "rfdetr", mod)
    _FakeRFDetr.made.clear()


@pytest.fixture
def installed(monkeypatch):
    _install_fake(monkeypatch)


@pytest.fixture
def version_dir(tmp_path):
    """A version dir with one image per split and a manifest.json (cached_export's input)."""
    root = tmp_path / "versions" / "v1"
    items = []
    for i, split in enumerate(("train", "valid", "test")):
        (root / split).mkdir(parents=True, exist_ok=True)
        PImage.new("RGB", (40, 30)).save(root / split / f"img{i}.jpg")
        items.append({"file": f"{split}/img{i}.jpg", "split": split, "width": 40, "height": 30,
                      "anns": [{"cls": 0, "shape": {"kind": "bbox", "x": .1, "y": .1, "w": .3, "h": .3}}]})
    (root / "manifest.json").write_text(json.dumps(
        {"classes": ["helmet"], "type": "object-detection", "items": items}))
    return root


@pytest.fixture
def loaded(monkeypatch):
    """Monkeypatch the _load seam; returns (recorded (variant, weights) calls, fake model)."""
    calls, model = [], _FakeModel()

    def fake_load(variant, weights):
        calls.append((variant, weights))
        return model

    monkeypatch.setattr(rf, "_load", fake_load)
    return calls, model


def _train(version_dir, tmp_path, **opts):
    model_id = f"rfdetr-{tmp_path.name}"
    events = []
    res = rf.RFDetrAdapter().train(
        "nano", version_dir, "detect",
        {"model_id": model_id, "epochs": 2, "batch": 4, **opts},
        lambda ep, total, metrics: events.append((ep, total, metrics)), lambda: False)
    return model_id, events, res


# --- probe ------------------------------------------------------------------------

def test_probe_reports_missing_package(monkeypatch):
    monkeypatch.setattr(importlib.util, "find_spec", lambda *a, **kw: None)
    assert rf.RFDetrAdapter().probe() == Availability(False, "rfdetr not installed")


def test_probe_ok_when_package_present(installed):
    assert rf.RFDetrAdapter().probe().ok


# --- predict ----------------------------------------------------------------------

def test_predict_maps_detections_to_the_shared_schema(installed, loaded):
    calls, model = loaded
    out = rf.RFDetrAdapter().predict("nano", PImage.new("RGB", (64, 48)), conf=0.3)
    validate_prediction(out)
    assert out["model"] == "rfdetr:nano"
    assert out["image"] == {"width": 64, "height": 48}
    assert out["predictions"] == [
        {"class": "helmet", "class_id": 0, "confidence": 0.9123,
         "x": 20.0, "y": 40.0, "width": 20.0, "height": 40.0},
        {"class": "person", "class_id": 1, "confidence": 0.71,
         "x": 7.0, "y": 7.0, "width": 4.0, "height": 4.0},
    ]
    assert model.kw["threshold"] == 0.3           # conf reaches RF-DETR's own threshold
    assert calls == [("nano", None)]              # no weights: the variant's pretrained checkpoint


def test_predict_filters_to_classes_and_resolves_trained_weights(installed, loaded):
    calls, _ = loaded
    ad = rf.RFDetrAdapter()
    out = ad.predict("nano", PImage.new("RGB", (64, 48)), classes=["person"])
    assert [p["class"] for p in out["predictions"]] == ["person"]
    out = ad.predict("nano", PImage.new("RGB", (64, 48)), weights="models/m1/best.pth")
    validate_prediction(out)
    assert calls[-1] == ("nano", str(DATA_DIR / "models" / "m1" / "best.pth"))


# --- train ------------------------------------------------------------------------

def test_train_reports_every_epoch_and_copies_the_checkpoint(installed, version_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(rf, "_POLL_S", 0.01)
    model_id, events, res = _train(version_dir, tmp_path, lr=2e-4)

    # one callback per CSV row, epochs counted from 1 for the UI; NaN boxes are dropped
    assert [e[0] for e in events] == [1, 2]
    assert all(e[1] == 2 for e in events)
    assert events[0][2] == {"train/loss": 1.5, "val/map50": 0.61, "val/map5095": 0.41,
                            "val/precision": 0.7, "val/recall": 0.66}
    assert events[1][2] == {"train/loss": 0.9, "val/map50": 0.72, "val/map5095": 0.52,
                            "val/precision": 0.75}
    assert res.history == [{"epoch": ep, **m} for ep, _, m in events]
    assert res.run_dir == str(DATA_DIR / "runs" / model_id)
    assert res.weights == f"models/{model_id}/best.pth"
    assert (DATA_DIR / res.weights).read_bytes() == b"rfdetr-weights"

    kw = _FakeRFDetr.made[-1].train_kw
    assert kw["dataset_dir"] == str(version_dir / "exports" / "coco")
    assert (version_dir / "exports" / "coco" / "train" / "_annotations.coco.json").exists()
    assert (kw["epochs"], kw["batch_size"], kw["lr"]) == (2, 4, 2e-4)
    assert kw["output_dir"] == str(DATA_DIR / "runs" / model_id)
    assert kw["early_stopping"] is True and kw["early_stopping_patience"] == 50
    assert kw["tensorboard"] is False
    assert "device" not in kw                     # no device requested: let rfdetr pick


def test_train_resumes_and_passes_an_explicit_device(installed, version_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(rf, "_POLL_S", 0.01)
    prev = DATA_DIR / "models" / f"previous-{tmp_path.name}"
    prev.mkdir(parents=True)
    (prev / "checkpoint.pth").write_bytes(b"older")

    _train(version_dir, tmp_path, resume_from=prev.name, device="cuda:0")

    model = _FakeRFDetr.made[-1]
    assert model.init_kw == {"pretrain_weights": str(prev / "checkpoint.pth")}
    assert model.train_kw["device"] == "cuda:0"


def test_train_mirrors_train_as_valid_when_the_version_has_none(installed, tmp_path, monkeypatch):
    monkeypatch.setattr(rf, "_POLL_S", 0.01)
    version = tmp_path / "versions" / "v2"
    (version / "train").mkdir(parents=True)
    PImage.new("RGB", (40, 30)).save(version / "train" / "only.jpg")
    (version / "manifest.json").write_text(json.dumps({
        "classes": ["helmet"], "type": "object-detection",
        "items": [{"file": "train/only.jpg", "split": "train", "width": 40, "height": 30,
                   "anns": [{"cls": 0, "shape": {"kind": "bbox", "x": .1, "y": .1, "w": .3, "h": .3}}]}]}))

    _train(version, tmp_path)

    root = Path(_FakeRFDetr.made[-1].train_kw["dataset_dir"])
    assert root != version / "exports" / "coco"        # the cached export is left untouched
    valid = json.loads((root / "valid" / "_annotations.coco.json").read_text())
    assert (root / "valid" / valid["images"][0]["file_name"]).resolve().exists()
    assert not (version / "exports" / "coco" / "valid").exists()


def test_train_normalizes_a_bare_device_index(installed, version_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(rf, "_POLL_S", 0.01)
    _train(version_dir, tmp_path, device="0")
    assert _FakeRFDetr.made[-1].train_kw["device"] == "cuda:0"


def test_train_without_a_checkpoint_fails(installed, version_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(rf, "_POLL_S", 0.01)
    monkeypatch.setattr(_FakeRFDetr, "train", lambda self, **kw: Path(kw["output_dir"]).mkdir(parents=True, exist_ok=True))
    with pytest.raises(RuntimeError, match="training produced no checkpoint"):
        _train(version_dir, tmp_path)


# --- missing package --------------------------------------------------------------

def test_operations_need_the_package(monkeypatch, version_dir):
    monkeypatch.setattr(importlib.util, "find_spec", lambda *a, **kw: None)
    ad = rf.RFDetrAdapter()
    with pytest.raises(RuntimeError, match="rfdetr not installed"):
        ad.predict("nano", PImage.new("RGB", (8, 8)))
    with pytest.raises(RuntimeError, match="rfdetr not installed"):
        ad.train("nano", version_dir, "detect", {"model_id": "x", "epochs": 1, "batch": 1},
                 lambda *a: None, lambda: False)
