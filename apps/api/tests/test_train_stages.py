"""Training pipeline: progress stages, watchdog, OOM retry, GPU-busy 503, leaderboard."""
import io
import json
import os
import shutil
import tempfile
import time
from types import SimpleNamespace

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-test-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import func, select

from app import worker
from app.config import DATA_DIR
from app.db import SessionLocal
from app.gpu import GpuBusy, GpuScheduler
from app.main import app
from app.models import Job, Project, TrainedModel, User, Version, Workspace
from app.security import issue_access

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/ws/{WS}/projects/{PR}"
STAGE_ORDER = ["queue", "acquire_gpu", "materialise", "resolve_weights", "build_config",
               "train", "evaluate", "register", "release"]


@pytest.fixture(scope="module")
def client():
    # lifespan seeds the demo workspace; mint the token directly so this module does not
    # spend one of the shared login rate-limit slots the other test modules need.
    with TestClient(app) as c:
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
        c.headers["Authorization"] = f"Bearer {issue_access(user.id)}"
        yield c


def _jpeg(color=(200, 50, 50)) -> bytes:
    b = io.BytesIO()
    PImage.new("RGB", (32, 32), color).save(b, "JPEG")
    return b.getvalue()


def _demo(db):
    ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
    p = db.scalar(select(Project).where(Project.workspace_id == ws.id, Project.slug == PR))
    return ws, p


def _new_version(db, p, with_data: bool = False) -> Version:
    n = (db.scalar(select(func.max(Version.number)).where(Version.project_id == p.id)) or 0) + 1
    v = Version(project_id=p.id, number=n, name=f"test-{n}", status="ready",
                stats={"class_names": ["person"]})
    db.add(v)
    db.flush()
    if with_data:
        d = DATA_DIR / "versions" / v.id
        (d / "train").mkdir(parents=True, exist_ok=True)
        PImage.new("RGB", (32, 32), (10, 20, 30)).save(d / "train" / "a.jpg", "JPEG")
        (d / "manifest.json").write_text(json.dumps({
            "classes": ["person"], "type": "object-detection", "version_hash": "test", "config": {}, "sources": [],
            "items": [{"file": "train/a.jpg", "split": "train", "width": 32, "height": 32, "source": "src1",
                       "anns": [{"cls": 0, "shape": {"kind": "bbox", "x": .1, "y": .1, "w": .2, "h": .2}}]}],
        }))
    return v


def _new_model(db, ws, p, v, *, status="queued", metrics=None) -> TrainedModel:
    m = TrainedModel(workspace_id=ws.id, project_id=p.id, version_id=v.id,
                     name=f"test-{v.number}-yolo26n", arch="yolo26n", family="ultralytics",
                     variant="yolo26n", task="detect", status=status, classes=["person"],
                     metrics=metrics or {})
    db.add(m)
    db.flush()
    return m


def _new_job(db, ws, p, m, v, batch: int = 8) -> Job:
    j = Job(workspace_id=ws.id, project_id=p.id, kind="train", status="running",
            params={"model_id": m.id, "version_id": v.id,
                    "options": {"batch": batch, "epochs": 1, "imgsz": 32, "max_minutes": None,
                                "resume_from": None}})
    db.add(j)
    db.flush()
    m.job_id = j.id
    db.commit()
    return j


def _drop(model_ids=(), version_ids=(), job_ids=()):
    with SessionLocal() as db:
        for jid in job_ids:
            row = db.get(Job, jid)
            if row:
                db.delete(row)
        for mid in model_ids:
            row = db.get(TrainedModel, mid)
            if row:
                db.delete(row)
        for vid in version_ids:
            row = db.get(Version, vid)
            if row:
                db.delete(row)
        db.commit()
    for vid in version_ids:
        shutil.rmtree(DATA_DIR / "versions" / vid, ignore_errors=True)


def _eval_stub(**over) -> dict:
    ev = {
        "split": "valid", "note": "stub",
        "coco": {"AP": 0.5, "AP50": 0.7, "AP75": 0.5, "APs": 0.0, "APm": 0.0, "APl": 0.0,
                 "AR1": 0.1, "AR10": 0.2, "AR100": 0.2, "ARs": 0.0, "ARm": 0.0, "ARl": 0.0},
        "per_class": {}, "f1_best": {"conf": 0.4, "f1": 0.6},
        "confusion": {"labels": [], "matrix": [], "images": []},
        "pr_curve": [], "worst": [], "latency_ms": 3.2, "detections": [],
    }
    ev.update(over)
    return ev


class OutOfMemoryError(RuntimeError):
    """Named like torch.cuda.OutOfMemoryError so the worker's class-name check matches."""


def _run_setup(with_data: bool = True, batch: int = 8):
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p, with_data=with_data)
        m = _new_model(db, ws, p, v)
        j = _new_job(db, ws, p, m, v, batch=batch)
        return m.id, v.id, j.id


def test_oom_retries_with_half_batch(client, monkeypatch):
    batches: list[int] = []
    cleaned: list[str] = []

    class FakeAdapter:
        family = "ultralytics"

        def train(self, variant, dataset_dir, task, opts, on_epoch, should_stop):
            batches.append(opts["batch"])
            if len(batches) == 1:
                raise OutOfMemoryError("CUDA out of memory")
            return SimpleNamespace(weights="models/x/best.pt", run_dir="", history=[])

    import torch
    monkeypatch.setattr(worker.gc, "collect", lambda: cleaned.append("gc"))
    monkeypatch.setattr(torch.cuda, "empty_cache", lambda: cleaned.append("empty_cache"))
    mid, vid, jid = _run_setup(batch=8)
    monkeypatch.setattr(worker, "ADAPTERS", {"ultralytics": FakeAdapter()})
    monkeypatch.setattr(worker, "evaluate", lambda *a, **kw: _eval_stub())
    monkeypatch.setattr(worker, "scheduler", GpuScheduler(4500, None))
    try:
        with SessionLocal() as db:
            job = db.get(Job, jid)
        out = worker.run_train(job)
        assert batches == [8, 4]
        assert "retried with batch=4" in out["stages"]["train"].get("note", "")
        assert cleaned == ["gc", "empty_cache"]          # free the failed attempt before retrying
        with SessionLocal() as db:
            assert db.get(TrainedModel, mid).status == "ready"
    finally:
        _drop(model_ids=[mid], version_ids=[vid], job_ids=[jid])


def test_failed_train_removes_dataset_copy(client, monkeypatch):
    class Boom:
        family = "ultralytics"

        def train(self, *a, **kw):
            raise RuntimeError("boom")

    mid, vid, jid = _run_setup()
    leftover = DATA_DIR / "train_data" / mid
    leftover.mkdir(parents=True, exist_ok=True)
    (leftover / "data.yaml").write_text("names: ['person']\n")
    monkeypatch.setattr(worker, "ADAPTERS", {"ultralytics": Boom()})
    monkeypatch.setattr(worker, "evaluate", lambda *a, **kw: _eval_stub())
    monkeypatch.setattr(worker, "scheduler", GpuScheduler(4500, None))
    try:
        with SessionLocal() as db:
            job = db.get(Job, jid)
        with pytest.raises(RuntimeError, match="boom"):
            worker.run_train(job)
        assert not leftover.exists()
        with SessionLocal() as db:
            assert db.get(TrainedModel, mid).status == "failed"
    finally:
        _drop(model_ids=[mid], version_ids=[vid], job_ids=[jid])


def test_watchdog_fails_stalled_run(client, monkeypatch):
    class StalledAdapter:
        family = "ultralytics"

        def train(self, variant, dataset_dir, task, opts, on_epoch, should_stop):
            started = time.time()
            while not should_stop() and time.time() - started < 5:
                time.sleep(0.01)
            return SimpleNamespace(weights="models/x/best.pt", run_dir="", history=[])

    mid, vid, jid = _run_setup()
    monkeypatch.setattr(worker, "ADAPTERS", {"ultralytics": StalledAdapter()})
    monkeypatch.setattr(worker, "evaluate", lambda *a, **kw: _eval_stub())
    monkeypatch.setattr(worker, "scheduler", GpuScheduler(4500, None))
    monkeypatch.setattr(worker, "_stall_limit", lambda _secs: 0.05)
    monkeypatch.setattr(worker, "_first_limit", lambda *_a: 0.05)
    try:
        with SessionLocal() as db:
            job = db.get(Job, jid)
        with pytest.raises(RuntimeError, match="no training progress"):
            worker.run_train(job)
        with SessionLocal() as db:
            assert db.get(TrainedModel, mid).status == "failed"
    finally:
        _drop(model_ids=[mid], version_ids=[vid], job_ids=[jid])


def test_watchdog_fires_mid_epoch_through_the_real_adapter(client, monkeypatch):
    """The real UltralyticsAdapter only sees should_stop via callbacks; a stalled epoch must
    end the run from a batch callback (not wait for the next epoch boundary) and release the GPU."""
    import sys
    from app.adapters.ultralytics_ad import UltralyticsAdapter

    class FakeYOLO:
        def __init__(self, _weights):
            self.cbs: dict = {}

        def add_callback(self, name, fn):
            self.cbs[name] = fn

        def train(self, **_kw):
            trainer = SimpleNamespace(epoch=0, metrics={}, tloss=None, stop=False)
            for _ in range(2000):                    # a long epoch: no on_fit_epoch_end in sight
                self.cbs["on_train_batch_end"](trainer)
                time.sleep(0.005)
            raise AssertionError("the watchdog never aborted the epoch")

    mid, vid, jid = _run_setup()
    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=FakeYOLO))
    monkeypatch.setattr(worker, "ADAPTERS", {"ultralytics": UltralyticsAdapter()})
    monkeypatch.setattr(worker, "evaluate", lambda *a, **kw: _eval_stub())
    s = GpuScheduler(4500, None)
    monkeypatch.setattr(worker, "scheduler", s)
    monkeypatch.setattr(worker, "_stall_limit", lambda _secs: 0.05)
    monkeypatch.setattr(worker, "_first_limit", lambda *_a: 0.05)
    try:
        with SessionLocal() as db:
            job = db.get(Job, jid)
        with pytest.raises(RuntimeError, match="no training progress"):
            worker.run_train(job)
        assert s.state()["holder"] is None                 # the lease was released
        with SessionLocal() as db:
            assert db.get(TrainedModel, mid).status == "failed"
    finally:
        _drop(model_ids=[mid], version_ids=[vid], job_ids=[jid])


def test_first_epoch_grace_follows_the_train_page_estimate():
    assert worker._first_limit(1, 1, 640) == worker.FIRST_EPOCH_MIN_S
    # 1000 images x 10 epochs / 600 = 16.7 min -> 1000 s estimate -> 2x = 2000 s
    assert worker._first_limit(1000, 10, 640) == pytest.approx(2000)
    # 4x the pixels = 4x the estimate
    assert worker._first_limit(1000, 10, 1280) == pytest.approx(8000)


def test_resolved_predict_uses_the_evaluated_threshold(client, monkeypatch):
    from app.adapters import base as base_mod
    from app.adapters import resolve

    seen: list[float] = []

    class Fake:
        family = "ultralytics"

        def predict(self, variant, im, **kw):
            seen.append(kw.get("conf", 0.4))
            return {"predictions": [], "time": 0.0, "image": {"width": 1, "height": 1}}

    monkeypatch.setitem(base_mod.ADAPTERS, "ultralytics", Fake())
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        tuned = _new_model(db, ws, p, v, status="ready",
                           metrics={"eval": {"f1_best": {"conf": 0.62, "f1": 0.8}}})
        plain = _new_model(db, ws, p, v, status="ready", metrics={})
        db.commit()
        ids, vid = [tuned.id, plain.id], v.id
    try:
        with SessionLocal() as db:
            resolve(f"trained:{tuned.id}", db).predict(object())
            resolve(f"trained:{plain.id}", db).predict(object())
            resolve(f"trained:{tuned.id}", db).predict(object(), conf=0.9)   # explicit always wins
        assert seen == [0.62, 0.4, 0.9]
    finally:
        _drop(model_ids=ids, version_ids=[vid])


def test_eval_failure_keeps_the_model_ready(client, monkeypatch):
    class HappyAdapter:
        family = "ultralytics"

        def train(self, variant, dataset_dir, task, opts, on_epoch, should_stop):
            on_epoch(1, 1, {"metrics/mAP50(B)": 0.5})
            return SimpleNamespace(weights="models/x/best.pt", run_dir="", history=[])

    mid, vid, jid = _run_setup()
    monkeypatch.setattr(worker, "ADAPTERS", {"ultralytics": HappyAdapter()})
    monkeypatch.setattr(worker, "scheduler", GpuScheduler(4500, None))
    monkeypatch.setattr(worker, "_first_limit", lambda *_a: 0.05)

    def boom(*_a, **_kw):
        raise ValueError("bad export")

    monkeypatch.setattr(worker, "evaluate", boom)
    try:
        with SessionLocal() as db:
            job = db.get(Job, jid)
        out = worker.run_train(job)
        assert out["stages"]["evaluate"]["status"] == "failed"
        with SessionLocal() as db:
            tm = db.get(TrainedModel, mid)
            assert tm.status == "ready"                    # weights are still usable
            assert "bad export" in tm.metrics["eval_error"]
            assert "eval" not in tm.metrics
    finally:
        _drop(model_ids=[mid], version_ids=[vid], job_ids=[jid])


def test_stages_recorded_in_order(client, monkeypatch):
    class HappyAdapter:
        family = "ultralytics"

        def train(self, variant, dataset_dir, task, opts, on_epoch, should_stop):
            on_epoch(1, 1, {"metrics/mAP50(B)": 0.5, "metrics/mAP50-95(B)": 0.4})
            return SimpleNamespace(weights="models/x/best.pt", run_dir="", history=[])

    mid, vid, jid = _run_setup()
    monkeypatch.setattr(worker, "ADAPTERS", {"ultralytics": HappyAdapter()})
    monkeypatch.setattr(worker, "evaluate", lambda *a, **kw: _eval_stub())
    monkeypatch.setattr(worker, "scheduler", GpuScheduler(4500, None))
    try:
        with SessionLocal() as db:
            job = db.get(Job, jid)
        out = worker.run_train(job)
        stages = out["stages"]
        assert list(stages) == STAGE_ORDER                  # dict order = first-mark order
        assert all(s["status"] == "done" for s in stages.values())
        assert stages["evaluate"]["status"] == "done"
        assert "eval" in out and "map50" in out
        with SessionLocal() as db:
            tm = db.get(TrainedModel, mid)
            assert tm.metrics["eval"]["coco"]["AP"] == 0.5
    finally:
        _drop(model_ids=[mid], version_ids=[vid], job_ids=[jid])


def test_gpu_busy_maps_to_503(client, monkeypatch):
    from app.routers import training as training_router

    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v, status="ready")
        db.commit()
        mid, vid = m.id, v.id

    def boom(*_a, **_kw):
        raise GpuBusy("GPU busy: training yolo26n")

    monkeypatch.setattr(training_router, "resolve", boom)
    try:
        r = client.post(f"{BASE}/models/{mid}/predict", files={"file": ("f.jpg", _jpeg())})
        assert r.status_code == 503, r.text
        assert r.json()["detail"] == "GPU busy: training yolo26n"
    finally:
        _drop(model_ids=[mid], version_ids=[vid])


def test_playground_maps_gpu_busy_to_503(client, monkeypatch):
    from app.routers import playground

    def boom(*_a, **_kw):
        raise GpuBusy("GPU busy: training yolo26n")

    monkeypatch.setattr(playground, "resolve", boom)
    r = client.post(f"/api/ws/{WS}/playground/predict", files={"file": ("f.jpg", _jpeg())},
                    data={"model_refs": "ultralytics:yolo26n"})
    assert r.status_code == 503, r.text
    assert r.json()["detail"] == "GPU busy: training yolo26n"


def test_lease_refusal_raises_gpu_busy():
    s = GpuScheduler(100, None)
    with s.exclusive("training yolo26n"):
        with pytest.raises(GpuBusy) as info:
            s.lease("model", 10, lambda: object(), lambda _o: None)
    assert isinstance(info.value, RuntimeError)
    assert str(info.value) == "GPU busy: training yolo26n"


def test_training_scope_allows_the_holder_to_lease():
    s = GpuScheduler(4500, None)
    with s.exclusive("training yolo26n"):
        with pytest.raises(GpuBusy):
            s.lease("blocked", 10, lambda: object(), lambda _o: None)
        with s.training_scope():                     # evaluation runs inside the training lease
            assert s.lease("trained:m", 100, lambda: "model", lambda _o: None) == "model"
        with pytest.raises(GpuBusy):                 # the allowance ends with the scope
            s.lease("blocked-again", 10, lambda: object(), lambda _o: None)


def test_get_model_signs_eval_image_urls(client):
    metrics = {"eval": {"split": "valid",
                        "worst": [{"file": "a.jpg"}],
                        "confusion": {"images": [["b.jpg", "c.jpg"]]},
                        "detections": [{"file": "d.jpg"}]}}
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v, status="ready", metrics=metrics)
        plain = _new_model(db, ws, p, v, status="ready", metrics={})
        db.commit()
        mid, plain_id, vid = m.id, plain.id, v.id
    try:
        body = client.get(f"{BASE}/models/{mid}").json()
        assert set(body["evalImages"]) == {"a.jpg", "b.jpg", "c.jpg", "d.jpg"}
        for url in body["evalImages"].values():
            assert url.startswith(f"/api/files/versions/{vid}/valid/")
            assert "exp=" in url and "sig=" in url
        assert client.get(f"{BASE}/models/{plain_id}").json()["evalImages"] == {}
    finally:
        _drop(model_ids=[mid, plain_id], version_ids=[vid])


def test_leaderboard_marks_other_versions_not_comparable(client):
    with SessionLocal() as db:
        ws, p = _demo(db)
        va = _new_version(db, p)
        vb = _new_version(db, p)
        best = _new_model(db, ws, p, vb, status="ready",
                          metrics={"eval": {"coco": {"AP": 0.99}, "latency_ms": 9.5}})
        mid = _new_model(db, ws, p, va, status="ready",
                         metrics={"eval": {"coco": {"AP": 0.5}, "latency_ms": 12.5}})
        none = _new_model(db, ws, p, va, status="ready", metrics={})
        db.commit()
        ids = {best.id: "best", mid.id: "mid", none.id: "none"}
        mids, vids = [best.id, mid.id, none.id], [va.id, vb.id]
    try:
        body = client.get(f"{BASE}/leaderboard").json()
        ours = {r["id"]: r for r in body if r["id"] in ids}
        pos = {r["id"]: i for i, r in enumerate(body)}
        assert pos[best.id] < pos[mid.id] < pos[none.id]
        aps = [r["ap"] for r in body if r["ap"] is not None]
        assert aps == sorted(aps, reverse=True)
        assert ours[best.id]["comparable"] is True
        assert ours[mid.id]["comparable"] is False
        assert ours[none.id]["comparable"] is False
        assert ours[best.id]["ap"] == 0.99
        assert ours[mid.id]["latency_ms"] == 12.5
        assert ours[mid.id]["versionId"] == va.id
    finally:
        _drop(model_ids=mids, version_ids=vids)
