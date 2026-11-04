"""RF-DETR adapter: probe, prediction mapping, child-process training, cancelling and class names.

`rfdetr` is not installed here, so the package, the training child and the Lightning CSV are faked.
"""
import os

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import importlib.util
import itertools
import json
import sys
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from PIL import Image as PImage

from app.adapters import rfdetr_ad as rf
from app.adapters.base import Availability, Cancelled, validate_prediction
from app.config import DATA_DIR

VARIANTS = ("RFDETRNano", "RFDETRSmall", "RFDETRMedium", "RFDETRLarge")
HEADER = "epoch,train/loss,val/mAP_50,val/mAP_50_95,val/precision,val/recall\n"
ROWS = ["0,1.5,0.61,0.41,0.70,0.66\n", "1,0.90,0.72,0.52,0.75,nan\n"]


# --- fakes ------------------------------------------------------------------------

class _Detections:
    """Just enough of supervision.Detections for the adapter's mapping."""
    xyxy = [[10.0, 20.0, 30.0, 60.0], [5.0, 5.0, 9.0, 9.0]]
    confidence = [0.9123, 0.71]
    class_id = [0, 1]
    data = {"class_name": ["helmet", "person"]}


class _UnnamedDetections(_Detections):
    """A trained RF-DETR checkpoint returns class ids only: no class_name in `data`."""
    data = {}


class _FakeModel:
    def __init__(self, det=None):
        self.det = det or _Detections()
        self.kw = None

    def predict(self, im, threshold=0.5, **kw):
        self.kw = {"threshold": threshold, **kw}
        return self.det


class _FakeRFDetr:
    """Stand-in for RFDETRNano/Small/Medium/Large; the training child is faked below."""
    def __init__(self, **kw):
        self.init_kw = kw
        self.train_kw: dict = {}

    def train(self, **kw):
        self.train_kw = kw


class FakeProc:
    """A spawned training child: `is_alive()` advances the run, writing the CSV and a checkpoint.

    Each poll appends one CSV row, so the parent pumps progress mid-run exactly as it would with
    Lightning writing metrics.csv. `exitcode` is None while the run is alive."""

    def __init__(self, output_dir, *, polls=3, exitcode=0, checkpoint="checkpoint_best_total.pth",
                 rows=ROWS):
        self.out = Path(output_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.polls = polls
        self.finish_code = exitcode
        self.checkpoint = checkpoint
        self.rows = list(rows)
        self.seen = 0
        self.exitcode = None
        self.terminated = 0
        self.killed = 0
        self.joins: list = []

    def is_alive(self):
        if self.terminated or self.killed:
            return False
        self.seen += 1
        if self.seen > self.polls:
            self.exitcode = self.finish_code
            return False
        csv = self.out / "metrics.csv"
        if not csv.exists():
            csv.write_text(HEADER)
        if self.seen <= len(self.rows):
            with open(csv, "a", encoding="utf-8") as f:
                f.write(self.rows[self.seen - 1])
        if self.checkpoint and not (self.out / self.checkpoint).exists():
            (self.out / self.checkpoint).write_bytes(b"rfdetr-weights")
        return True

    def terminate(self):
        self.terminated += 1
        self.exitcode = -15

    def join(self, timeout=None):
        self.joins.append(timeout)

    def kill(self):
        self.killed += 1
        self.exitcode = -9


def _install_fake(monkeypatch):
    """A fake `rfdetr` module with a real spec, so find_spec('rfdetr') succeeds."""
    mod = ModuleType("rfdetr")
    mod.__spec__ = ModuleSpec("rfdetr", None)
    for name in VARIANTS:
        setattr(mod, name, _FakeRFDetr)
    monkeypatch.setitem(sys.modules, "rfdetr", mod)


@pytest.fixture
def installed(monkeypatch):
    _install_fake(monkeypatch)


@pytest.fixture(autouse=True)
def fast_poll(monkeypatch):
    monkeypatch.setattr(rf, "_POLL_S", 0.001)


@pytest.fixture
def spawned(monkeypatch):
    """Monkeypatch the spawn seam; `opts` configures the fake child the next spawn returns."""
    state = SimpleNamespace(calls=[], opts={})

    def fake_spawn(variant, init, kw):
        proc = FakeProc(kw["output_dir"], **state.opts)
        state.calls.append((variant, init, kw, proc))
        return proc

    monkeypatch.setattr(rf, "_spawn", fake_spawn)
    return state


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


def _train(version_dir, tmp_path, *, stop=None, **opts):
    model_id = f"rfdetr-{tmp_path.name}"
    events = []
    res = rf.RFDetrAdapter().train(
        "nano", version_dir, "detect",
        {"model_id": model_id, "epochs": 2, "batch": 4, **opts},
        lambda ep, total, metrics: events.append((ep, total, metrics)), stop or (lambda: False))
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


def test_predict_names_trained_detections_from_the_sibling_classes_json(installed, loaded, tmp_path):
    _, model = loaded
    model.det = _UnnamedDetections()
    weights = DATA_DIR / "models" / f"named-{tmp_path.name}" / "best.pth"
    weights.parent.mkdir(parents=True)
    weights.write_bytes(b"w")
    (weights.parent / "classes.json").write_text(json.dumps(["vest", "worker"]))

    out = rf.RFDetrAdapter().predict("nano", PImage.new("RGB", (64, 48)),
                                     weights=weights.relative_to(DATA_DIR).as_posix())

    assert [p["class"] for p in out["predictions"]] == ["vest", "worker"]
    validate_prediction(out)


def test_predict_falls_back_to_ids_without_classes_json(installed, loaded, tmp_path):
    _, model = loaded
    model.det = _UnnamedDetections()
    weights = DATA_DIR / "models" / f"naked-{tmp_path.name}" / "best.pth"
    weights.parent.mkdir(parents=True)
    weights.write_bytes(b"w")

    out = rf.RFDetrAdapter().predict("nano", PImage.new("RGB", (64, 48)),
                                     weights=weights.relative_to(DATA_DIR).as_posix())

    assert [p["class"] for p in out["predictions"]] == ["0", "1"]


# --- train ------------------------------------------------------------------------

def test_train_reports_every_epoch_and_copies_the_checkpoint(installed, version_dir, tmp_path, spawned):
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

    variant, init, kw, proc = spawned.calls[-1]
    assert (variant, init) == ("nano", {})
    assert proc.joins == [] and proc.terminated == 0
    assert kw["dataset_dir"] == str(version_dir / "exports" / "coco")
    assert (version_dir / "exports" / "coco" / "train" / "_annotations.coco.json").exists()
    assert (kw["epochs"], kw["batch_size"], kw["lr"]) == (2, 4, 2e-4)
    assert kw["output_dir"] == str(DATA_DIR / "runs" / model_id)
    assert kw["early_stopping"] is True and kw["early_stopping_patience"] == 50
    assert kw["tensorboard"] is False
    assert kw["run_test"] is False                # a version without test/ cannot break the fit-end pass
    assert "device" not in kw                     # no device requested: let rfdetr pick

    # the run writes the class names it trained on beside the checkpoint
    classes = json.loads((DATA_DIR / "models" / model_id / "classes.json").read_text())
    assert classes == ["helmet"]


def test_train_writes_classes_ordered_by_category_id(installed, version_dir, tmp_path, spawned):
    _train(version_dir, tmp_path)
    coco = version_dir / "exports" / "coco" / "train" / "_annotations.coco.json"
    data = json.loads(coco.read_text())
    data["categories"] = [{"id": 1, "name": "person"}, {"id": 0, "name": "helmet"}]
    coco.write_text(json.dumps(data))

    model_id, _, _ = _train(version_dir, tmp_path / "again")

    classes = json.loads((DATA_DIR / "models" / model_id / "classes.json").read_text())
    assert classes == ["helmet", "person"]


def test_train_resumes_and_passes_an_explicit_device(installed, version_dir, tmp_path, spawned):
    prev = DATA_DIR / "models" / f"previous-{tmp_path.name}"
    prev.mkdir(parents=True)
    (prev / "checkpoint.pth").write_bytes(b"older")

    _train(version_dir, tmp_path, resume_from=prev.name, device="cuda:0")

    _, init, kw, _ = spawned.calls[-1]
    assert init == {"pretrain_weights": str(prev / "checkpoint.pth")}
    assert kw["device"] == "cuda:0"


def test_train_mirrors_train_as_valid_when_the_version_has_none(installed, tmp_path, spawned):
    version = tmp_path / "versions" / "v2"
    (version / "train").mkdir(parents=True)
    PImage.new("RGB", (40, 30)).save(version / "train" / "only.jpg")
    (version / "manifest.json").write_text(json.dumps({
        "classes": ["helmet"], "type": "object-detection",
        "items": [{"file": "train/only.jpg", "split": "train", "width": 40, "height": 30,
                   "anns": [{"cls": 0, "shape": {"kind": "bbox", "x": .1, "y": .1, "w": .3, "h": .3}}]}]}))

    _train(version, tmp_path)

    _, _, kw, _ = spawned.calls[-1]
    root = Path(kw["dataset_dir"])
    assert root != version / "exports" / "coco"        # the cached export is left untouched
    assert kw["run_test"] is False                     # the fit-end pass never needs test/
    valid = json.loads((root / "valid" / "_annotations.coco.json").read_text())
    assert (root / "valid" / valid["images"][0]["file_name"]).resolve().exists()
    assert not (version / "exports" / "coco" / "valid").exists()


def test_train_normalizes_a_bare_device_index(installed, version_dir, tmp_path, spawned):
    _train(version_dir, tmp_path, device="0")
    assert spawned.calls[-1][2]["device"] == "cuda:0"


def test_train_without_a_checkpoint_fails(installed, version_dir, tmp_path, spawned):
    spawned.opts.update(polls=2, checkpoint=None)
    with pytest.raises(RuntimeError, match="training produced no checkpoint"):
        _train(version_dir, tmp_path)


def test_train_terminates_the_child_when_cancelled(installed, version_dir, tmp_path, spawned):
    spawned.opts.update(polls=50, checkpoint="checkpoint.pth")
    asked = []

    def stop():
        asked.append(1)
        return len(asked) > 2

    model_id, events, res = _train(version_dir, tmp_path, stop=stop)

    proc = spawned.calls[-1][3]
    assert proc.terminated == 1                       # the child is killed at the next poll
    assert proc.joins == [10]
    assert proc.exitcode == -15
    assert [e[0] for e in events] == [1, 2]           # progress seen before the cancel
    assert (DATA_DIR / res.weights).read_bytes() == b"rfdetr-weights"   # last checkpoint kept
    assert res.weights == f"models/{model_id}/best.pth"


def test_train_stops_at_the_max_minutes_deadline(installed, version_dir, tmp_path, spawned, monkeypatch):
    spawned.opts["polls"] = 50
    ticks = itertools.count(step=0.1)
    monkeypatch.setattr(rf, "_now", lambda: round(next(ticks), 2))

    _train(version_dir, tmp_path, max_minutes=0.01)   # 0.6 s on the synthetic clock

    proc = spawned.calls[-1][3]
    assert proc.terminated == 1
    assert proc.exitcode == -15


def test_train_beats_only_when_the_child_writes_progress(installed, version_dir, tmp_path, spawned):
    beats = []
    spawned.opts["polls"] = 4

    _train(version_dir, tmp_path, heartbeat=lambda: beats.append(1))

    # header+row+checkpoint, then row 2: two signature changes, not one per poll
    assert len(beats) == 2


def test_train_raises_when_the_child_fails(installed, version_dir, tmp_path, spawned):
    spawned.opts.update(polls=2, exitcode=3)
    with pytest.raises(RuntimeError, match="exit code 3"):
        _train(version_dir, tmp_path)


def test_train_cancel_before_the_first_checkpoint_is_a_cancel(installed, version_dir, tmp_path, spawned):
    spawned.opts["polls"] = 50
    with pytest.raises(Cancelled, match="cancelled before the first checkpoint"):
        _train(version_dir, tmp_path, stop=lambda: True)


def _lazy_watchdog(limit: float):
    """Build the watchdog at the first poll, after the dataset export (it must not age during setup)."""
    from app import worker

    holder = {}

    def wd():
        if "w" not in holder:
            holder["w"] = worker._Watchdog(first_limit=limit).start()
        return holder["w"]

    return holder, (lambda: wd().stalled), (lambda: wd().beat()), (lambda: wd().stalled)


def test_silent_live_child_still_stalls(installed, version_dir, tmp_path, spawned):
    """A child that never writes metrics/checkpoints must not keep the watchdog alive."""
    spawned.opts.update(polls=10_000, rows=[], checkpoint=None)
    holder, stop, beat, stalled = _lazy_watchdog(0.08)
    try:
        with pytest.raises(RuntimeError, match="no training progress"):
            _train(version_dir, tmp_path, stop=stop, heartbeat=beat, stalled=stalled)
    finally:
        if holder.get("w"):
            holder["w"].stop()
    assert spawned.calls[-1][3].seen > 1
    assert spawned.calls[-1][3].terminated == 1
    assert holder["w"].stalled is True


def test_progressing_child_does_not_stall(installed, version_dir, tmp_path, spawned, monkeypatch):
    """Each new metrics row is a real progress beat: a slow epoch never trips the watchdog."""
    from app import worker

    monkeypatch.setattr(worker, "_stall_limit", lambda _secs: 0.15)
    monkeypatch.setattr(rf, "_POLL_S", 0.02)
    rows = [f"{i},1.0,0.5,0.4,0.6,0.5\n" for i in range(20)]
    spawned.opts.update(polls=20, rows=rows)
    holder, stop, beat, _ = _lazy_watchdog(0.15)
    try:
        _, events, _ = _train(version_dir, tmp_path, stop=stop, heartbeat=beat)
    finally:
        holder["w"].stop()
    assert holder["w"].stalled is False
    assert len(events) == 20


def test_max_minutes_before_the_first_checkpoint_fails(installed, version_dir, tmp_path, spawned):
    spawned.opts.update(polls=10_000, rows=[], checkpoint=None)
    with pytest.raises(RuntimeError, match="max_minutes reached before the first checkpoint"):
        _train(version_dir, tmp_path, max_minutes=0.00001)


# --- inference leases --------------------------------------------------------------

def test_load_leases_per_variant_vram(monkeypatch):
    from app.gpu import scheduler

    calls = []

    def fake_lease(key, vram_mb, loader, unloader):
        calls.append((key, vram_mb))
        return "model"

    monkeypatch.setattr(scheduler, "lease", fake_lease)
    assert rf._load("large", None) == "model"
    assert rf._load("nano", None) == "model"
    assert calls == [("rfdetr|large", 2600), ("rfdetr|nano", 1200)]


# --- missing package --------------------------------------------------------------

def test_operations_need_the_package(monkeypatch, version_dir):
    monkeypatch.setattr(importlib.util, "find_spec", lambda *a, **kw: None)
    ad = rf.RFDetrAdapter()
    with pytest.raises(RuntimeError, match="rfdetr not installed"):
        ad.predict("nano", PImage.new("RGB", (8, 8)))
    with pytest.raises(RuntimeError, match="rfdetr not installed"):
        ad.train("nano", version_dir, "detect", {"model_id": "x", "epochs": 1, "batch": 1},
                 lambda *a: None, lambda: False)
