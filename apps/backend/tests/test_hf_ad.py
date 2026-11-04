"""HuggingFace detection family: D-FINE and RT-DETRv2."""
import json
import os
from pathlib import Path

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
import torch
from PIL import Image as PImage

from app.adapters import hf_ad, validate_prediction
from app.adapters.hf_ad import CocoDetection, HfAdapter
from app.config import DATA_DIR

DFINE = "ustc-community/dfine-nano"


# --- probe --------------------------------------------------------------------------

def test_probe_reports_missing_transformers(monkeypatch):
    monkeypatch.setattr(hf_ad.importlib.util, "find_spec",
                        lambda name: None if name == "transformers" else object())
    assert HfAdapter().probe().reason == "transformers not installed"


def test_probe_reports_missing_torch(monkeypatch):
    monkeypatch.setattr(hf_ad.importlib.util, "find_spec",
                        lambda name: None if name == "torch" else object())
    av = HfAdapter().probe()
    assert (av.ok, av.reason) == (False, "torch not installed")


def test_probe_available(monkeypatch):
    monkeypatch.setattr(hf_ad.importlib.util, "find_spec", lambda name: object())
    av = HfAdapter().probe()
    assert (av.ok, av.reason) == (True, "")
    assert HfAdapter().capabilities(DFINE) == {"detect"}


# --- predict ------------------------------------------------------------------------

class _FakeProcessor:
    def __init__(self):
        self.target_sizes = None

    def __call__(self, images=None, return_tensors=None):
        return {"pixel_values": torch.zeros(1, 3, 8, 8)}

    def post_process_object_detection(self, outputs, threshold=None, target_sizes=None):
        self.target_sizes = target_sizes
        return [{"scores": torch.tensor([0.91, 0.52]),
                 "labels": torch.tensor([0, 1]),
                 "boxes": torch.tensor([[0.0, 0.0, 10.0, 10.0], [5.0, 5.0, 15.0, 20.0]])}]


class _FakeModel:
    class config:
        id2label = {0: "helmet", 1: "vest"}

    def __call__(self, **kw):
        return object()


def test_predict_maps_schema_and_filters_classes(monkeypatch):
    calls, proc = [], _FakeProcessor()
    monkeypatch.setattr(hf_ad, "_load", lambda variant, weights: calls.append((variant, weights)) or (proc, _FakeModel()))
    im = PImage.new("RGB", (100, 50))
    out = HfAdapter().predict(DFINE, im, classes=["helmet"], weights="models/helmet")

    validate_prediction(out)
    assert calls == [(DFINE, "models/helmet")]
    assert out["model"] == f"hf:{DFINE}"
    assert out["image"] == {"width": 100, "height": 50}
    assert out["predictions"] == [{"class": "helmet", "class_id": 0, "confidence": 0.91,
                                   "x": 5.0, "y": 5.0, "width": 10.0, "height": 10.0}]
    assert proc.target_sizes.tolist() == [[50, 100]]


def test_predict_without_weights_uses_variant_and_keeps_all_classes(monkeypatch):
    calls = []
    monkeypatch.setattr(hf_ad, "_load", lambda variant, weights: calls.append((variant, weights)) or (_FakeProcessor(), _FakeModel()))
    out = HfAdapter().predict(DFINE, PImage.new("RGB", (100, 50)), conf=0.4)
    assert calls == [(DFINE, None)]
    assert [p["class"] for p in out["predictions"]] == ["helmet", "vest"]


def test_load_resolves_trained_weights_under_data_dir(monkeypatch):
    seen = {}
    monkeypatch.setattr("app.gpu.scheduler.lease",
                        lambda key, vram_mb, loader, unloader: seen.update(key=key) or "sentinel")
    assert hf_ad._load(DFINE, "models/abc") == "sentinel"
    assert seen["key"] == f"hf|{DATA_DIR / 'models/abc'}"


# --- dataset + collator -------------------------------------------------------------

def _write_coco_split(root: Path):
    root.mkdir(parents=True)
    PImage.new("RGB", (100, 50)).save(root / "a.jpg")
    (root / "_annotations.coco.json").write_text(json.dumps({
        "images": [{"id": 0, "file_name": "a.jpg", "width": 100, "height": 50}],
        "annotations": [{"id": 0, "image_id": 0, "category_id": 0, "bbox": [10, 10, 20, 10]},
                        {"id": 1, "image_id": 0, "category_id": 1, "bbox": [50, 20, 10, 20]}],
        "categories": [{"id": 0, "name": "helmet"}, {"id": 1, "name": "vest"}]}))


def test_coco_dataset_converts_to_normalized_cxcywh(tmp_path):
    _write_coco_split(tmp_path / "train")
    ds = CocoDetection(tmp_path / "train")
    assert ds.classes == ["helmet", "vest"]
    im, target = ds[0]
    assert im.size == (100, 50)
    assert target["class_labels"].tolist() == [0, 1]
    assert torch.allclose(target["boxes"], torch.tensor([[0.20, 0.30, 0.20, 0.20],
                                                         [0.55, 0.60, 0.10, 0.40]]))


def test_collator_batches_pixel_values_and_labels(tmp_path):
    _write_coco_split(tmp_path / "train")
    ds = CocoDetection(tmp_path / "train")
    collate = hf_ad._collate(_FakeProcessor())
    batch = collate([ds[0], ds[0]])
    assert set(batch) >= {"pixel_values", "labels"}
    assert batch["pixel_values"].shape == (1, 3, 8, 8)
    assert set(batch["labels"][0]) == {"class_labels", "boxes"}
    assert batch["labels"][0]["class_labels"].tolist() == [0, 1]


# --- epoch reporting ----------------------------------------------------------------

class _State:
    def __init__(self, epoch=0, log_history=None):
        self.epoch = epoch
        self.log_history = log_history or []


class _Control:
    should_training_stop = False


def _report(monkeypatch, stop=False):
    seen = []
    history = []
    monkeypatch.setattr(hf_ad, "_validate", lambda *a: {"val/map50": 0.4, "val/map5095": 0.3,
                                                        "val/precision": 0.6, "val/recall": 0.5})
    cb = hf_ad._EpochReport(lambda ep, total, m: seen.append((ep, total, m)), lambda: stop,
                            history, 5, "model", "processor", Path("valid"))
    return cb, seen, history


def test_epoch_report_emits_common_keys(monkeypatch):
    cb, seen, history = _report(monkeypatch)
    # Trainer logs the epoch loss after on_epoch_end; the report lands on the following on_log.
    cb.on_epoch_end(None, _State(1, [{"loss": 9.9}]), _Control())
    assert seen == []
    cb.on_log(None, _State(1), _Control(), logs={"loss": 1.25})
    epoch, total, metrics = seen[0]
    assert (epoch, total) == (1, 5)
    assert metrics == {"train/loss": 1.25, "val/map50": 0.4, "val/map5095": 0.3,
                       "val/precision": 0.6, "val/recall": 0.5}
    assert history == [{"epoch": 1, **metrics}]
    cb.on_log(None, _State(1), _Control(), logs={"loss": 1.2})     # same epoch is reported once
    assert len(seen) == 1


def test_epoch_report_stops_on_request(monkeypatch):
    cb, seen, _ = _report(monkeypatch, stop=True)
    control = _Control()
    cb.on_epoch_end(None, _State(2, []), control)
    assert control.should_training_stop is True
    cb.on_log(None, _State(2), control, logs={"loss": 0.5})
    assert seen[0][0] == 2


def test_epoch_report_stops_at_max_minutes(monkeypatch):
    cb, _, _ = _report(monkeypatch)
    cb.deadline = 0.0
    control = _Control()
    cb.on_epoch_end(None, _State(1, []), control)
    assert control.should_training_stop is True


def test_epoch_report_survives_validation_error(monkeypatch):
    cb, seen, _ = _report(monkeypatch)
    monkeypatch.setattr(hf_ad, "_validate", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    cb.on_epoch_end(None, _State(1, []), _Control())
    cb.on_log(None, _State(1), _Control(), logs={"loss": 0.7})
    assert seen[0][2] == {"train/loss": 0.7}


def test_report_class_is_a_trainer_callback(monkeypatch):
    import sys
    from types import ModuleType

    class _Base:
        def on_init_end(self, *a, **kw):
            pass

    mod = ModuleType("transformers")
    mod.TrainerCallback = _Base
    monkeypatch.setitem(sys.modules, "transformers", mod)
    cls = hf_ad._report_class()
    assert issubclass(cls, _Base) and issubclass(cls, hf_ad._EpochReport)
    assert hasattr(cls(None, lambda: False, [], 1, None, None, Path("v")), "on_init_end")


# --- validation scoring -------------------------------------------------------------

class _ValProcessor(_FakeProcessor):
    def post_process_object_detection(self, outputs, threshold=None, target_sizes=None):
        return [{"scores": torch.tensor([0.9]), "labels": torch.tensor([0]),
                 "boxes": torch.tensor([[10.0, 10.0, 30.0, 20.0]])}]


class _ValModel:
    class config:
        id2label = {0: "helmet"}

    def eval(self):
        return self

    def train(self):
        return self

    def __call__(self, **kw):
        return object()


def test_validate_scores_a_perfect_prediction(tmp_path):
    root = tmp_path / "valid"
    root.mkdir()
    PImage.new("RGB", (100, 50)).save(root / "a.jpg")
    (root / "_annotations.coco.json").write_text(json.dumps({
        "images": [{"id": 0, "file_name": "a.jpg", "width": 100, "height": 50}],
        "annotations": [{"id": 0, "image_id": 0, "category_id": 0, "bbox": [10, 10, 20, 10],
                         "area": 200, "iscrowd": 0}],
        "categories": [{"id": 0, "name": "helmet"}]}))
    assert hf_ad._validate(_ValModel(), _ValProcessor(), root) == {
        "val/map50": 1.0, "val/map5095": 1.0, "val/precision": 1.0, "val/recall": 1.0}
    assert hf_ad._validate(_ValModel(), _ValProcessor(), tmp_path / "missing") == {}


def test_public_coco_epoch_metrics_contract(tmp_path):
    """The HF adapter scores epochs through this public entry point, never private helpers."""
    from app.services.evaluate import coco_epoch_metrics

    root = tmp_path / "split"
    root.mkdir()
    PImage.new("RGB", (100, 50)).save(root / "a.jpg")
    (root / "_annotations.coco.json").write_text(json.dumps({
        "images": [{"id": 0, "file_name": "a.jpg", "width": 100, "height": 50}],
        "annotations": [{"id": 0, "image_id": 0, "category_id": 0, "bbox": [10, 10, 20, 10],
                         "area": 200, "iscrowd": 0}],
        "categories": [{"id": 0, "name": "helmet"}]}))
    detections = [{"image_id": 0, "category_id": 0, "bbox": [10, 10, 20, 10], "score": 0.9}]

    metrics = coco_epoch_metrics(root / "_annotations.coco.json", detections, conf=0.5)
    assert set(metrics) == {"map50", "map5095", "precision", "recall"}
    assert metrics == {"map50": 1.0, "map5095": 1.0, "precision": 1.0, "recall": 1.0}
    assert coco_epoch_metrics(tmp_path / "missing" / "_annotations.coco.json", detections) == {}


# --- train wiring -------------------------------------------------------------------

class _Saver:
    def __init__(self):
        self.saved = None
        self.config = type("Config", (), {"id2label": {}, "label2id": {}})()

    def save_pretrained(self, path):
        self.saved = Path(path)
        Path(path).mkdir(parents=True, exist_ok=True)
        (Path(path) / "config.json").write_text("{}")


def _version_dir(tmp_path: Path) -> Path:
    v = tmp_path / "version"
    (v / "train").mkdir(parents=True)
    (v / "valid").mkdir(parents=True)
    PImage.new("RGB", (100, 50)).save(v / "train" / "a.jpg")
    PImage.new("RGB", (100, 50)).save(v / "valid" / "b.jpg")
    box = {"kind": "bbox", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}
    (v / "manifest.json").write_text(json.dumps({
        "classes": ["helmet", "vest"], "type": "object-detection",
        "items": [{"file": "train/a.jpg", "split": "train", "width": 100, "height": 50,
                   "anns": [{"cls": 0, "shape": box}]},
                  {"file": "valid/b.jpg", "split": "valid", "width": 100, "height": 50,
                   "anns": [{"cls": 1, "shape": box}]}]}))
    return v


def test_train_wires_build_and_saves_model(tmp_path, monkeypatch):
    monkeypatch.setattr(hf_ad, "_validate", lambda *a: {"val/map50": 0.4})
    seen, calls = {}, []

    class _FakeTrainer:
        def train(self):
            cb = [c for c in seen["callbacks"]][0]
            cb.on_epoch_end(None, _State(1, []), _Control())
            cb.on_log(None, _State(1), _Control(), logs={"loss": 0.7})

    model = _Saver()
    processor = _Saver()

    def fake_build(**kw):
        seen.update(kw)
        seen["callbacks"] = [hf_ad._EpochReport(kw["on_epoch"], kw["should_stop"], kw["history"],
                                                int(kw["opts"]["epochs"]), model, processor,
                                                kw["valid_root"])]
        return processor, model, _FakeTrainer()

    monkeypatch.setattr(hf_ad, "_build", fake_build)
    version = _version_dir(tmp_path)
    res = HfAdapter().train(DFINE, version, "detect", {"model_id": "m1", "epochs": 2, "batch": 4},
                            lambda ep, total, m: calls.append((ep, total, m)), lambda: False)

    assert calls == [(1, 2, {"train/loss": 0.7, "val/map50": 0.4})]
    assert res.history == [{"epoch": 1, "train/loss": 0.7, "val/map50": 0.4}]
    assert res.weights == "models/m1" and model.saved == DATA_DIR / "models" / "m1"
    assert processor.saved == model.saved and Path(DATA_DIR / res.weights).is_dir()
    assert res.run_dir == str(DATA_DIR / "runs" / "m1")
    assert model.config.id2label == {0: "helmet", 1: "vest"}   # saved config keeps the dataset names
    assert model.config.label2id == {"helmet": 0, "vest": 1}
    assert seen["train_ds"].root == version / "exports" / "coco" / "train"
    assert seen["classes"] == ["helmet", "vest"] and seen["source"] == DFINE


def test_train_rejects_unsupported_variant(tmp_path):
    with pytest.raises(ValueError, match="unsupported hf detector 'yolo26n'"):
        HfAdapter().train("yolo26n", tmp_path, "detect", {"model_id": "x"}, lambda *a: None, lambda: False)


def test_train_resumes_from_saved_model_dir(tmp_path, monkeypatch):
    seen = {}
    model, processor = _Saver(), _Saver()

    def fake_build(**kw):
        seen.update(kw)

        class _Noop:
            def train(self):
                pass

        return processor, model, _Noop()

    monkeypatch.setattr(hf_ad, "_build", fake_build)
    prev = DATA_DIR / "models" / "prev1"
    prev.mkdir(parents=True, exist_ok=True)
    HfAdapter().train(DFINE, _version_dir(tmp_path), "detect",
                      {"model_id": "m2", "epochs": 1, "resume_from": "prev1"}, lambda *a: None, lambda: False)
    assert seen["source"] == str(prev)
