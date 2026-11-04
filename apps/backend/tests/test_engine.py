"""TensorRT export: endpoint -> export_engine job -> runtime_refs.engine -> tensorrt adapter."""
import os
import shutil
import sys
import logging
import importlib
import uuid
from pathlib import Path
from types import SimpleNamespace

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import func, select

from app import config, worker
from app.adapters import ADAPTERS, resolve
from app.adapters.base import Availability
from app.config import DATA_DIR, LOCAL_JOB_KINDS, REMOTE_JOB_KINDS
from app.db import SessionLocal
from app.gpu import GpuScheduler
from app.main import app
from app.models import Job, Member, Project, TrainedModel, User, Version, Workspace
from app.routers import training as training_router
from app.security import issue_access

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/ws/{WS}/projects/{PR}"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
        c.headers["Authorization"] = f"Bearer {issue_access(user.id)}"
        yield c


@pytest.fixture(autouse=True)
def _tensorrt_available(monkeypatch):
    """The dev/CI box has no TensorRT runtime; endpoint tests assume a GPU worker that does."""
    monkeypatch.setattr(ADAPTERS["tensorrt"], "probe", lambda: Availability(True))


def _demo(db):
    ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
    p = db.scalar(select(Project).where(Project.workspace_id == ws.id, Project.slug == PR))
    return ws, p


def _new_version(db, p) -> Version:
    n = (db.scalar(select(func.max(Version.number)).where(Version.project_id == p.id)) or 0) + 1
    v = Version(project_id=p.id, number=n, name=f"engine-{n}", status="ready", stats={"class_names": ["person"]})
    db.add(v)
    db.flush()
    return v


def _new_model(db, ws, p, v, *, status="ready", weights="models/x/best.pt", variant="yolo26n",
               family="ultralytics", runtime_refs=None) -> TrainedModel:
    m = TrainedModel(workspace_id=ws.id, project_id=p.id, version_id=v.id, name=f"engine-{v.number}",
                     arch=variant, family=family, variant=variant, task="detect", status=status,
                     classes=["person"], weights=weights, runtime_refs=runtime_refs or {})
    db.add(m)
    db.flush()
    return m


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
    for mid in model_ids:
        (DATA_DIR / "engines" / f"{mid}.engine").unlink(missing_ok=True)
        shutil.rmtree(DATA_DIR / "models" / mid, ignore_errors=True)
    for vid in version_ids:
        shutil.rmtree(DATA_DIR / "versions" / vid, ignore_errors=True)


def _cancel(jid: str):
    """Keep the embedded worker from claiming a job a test queued for inspection."""
    with SessionLocal() as db:
        row = db.get(Job, jid)
        if row and row.status == "queued":
            row.status = "cancelled"
            db.commit()


def test_export_engine_is_a_local_job_kind():
    assert "export_engine" in LOCAL_JOB_KINDS
    assert "export_engine" not in REMOTE_JOB_KINDS       # the engine build needs the local GPU


def test_export_endpoint_queues_export_engine_job(client):
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v)
        mid, vid = m.id, v.id
        db.commit()
    jid = None
    try:
        r = client.post(f"{BASE}/models/{mid}/export", json={"format": "engine"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["kind"] == "export_engine" and body["status"] == "queued"
        jid = body["id"]
        with SessionLocal() as db:
            job = db.get(Job, jid)
            assert job.params == {"model_id": mid, "format": "engine"}
            assert job.created_by
    finally:
        if jid:
            _cancel(jid)
        _drop(model_ids=[mid], version_ids=[vid], job_ids=[jid] if jid else [])


def test_export_endpoint_returns_the_running_job_instead_of_queueing_again(client):
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v)
        mid, vid = m.id, v.id
        db.commit()
    jid = None
    try:
        first = client.post(f"{BASE}/models/{mid}/export", json={"format": "engine"}).json()
        jid = first["id"]
        second = client.post(f"{BASE}/models/{mid}/export", json={"format": "engine"}).json()
        assert second["id"] == first["id"]
        with SessionLocal() as db:
            rows = db.scalars(select(Job).where(Job.kind == "export_engine")).all()
        assert sum(1 for j in rows if j.params.get("model_id") == mid) == 1
    finally:
        if jid:
            _cancel(jid)
        _drop(model_ids=[mid], version_ids=[vid], job_ids=[jid] if jid else [])


def test_export_endpoint_rejects_unknown_format(client):
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v)
        mid, vid = m.id, v.id
        db.commit()
    try:
        r = client.post(f"{BASE}/models/{mid}/export", json={"format": "onnx"})
        assert r.status_code == 400
    finally:
        _drop(model_ids=[mid], version_ids=[vid])


def test_export_endpoint_requires_a_ready_model(client):
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v, status="training")
        mid, vid = m.id, v.id
        db.commit()
    try:
        r = client.post(f"{BASE}/models/{mid}/export", json={"format": "engine"})
        assert r.status_code == 409
    finally:
        _drop(model_ids=[mid], version_ids=[vid])


def test_export_endpoint_rejects_open_vocabulary_models(client):
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v, variant="yolov8s-worldv2")
        mid, vid = m.id, v.id
        db.commit()
    try:
        r = client.post(f"{BASE}/models/{mid}/export", json={"format": "engine"})
        assert r.status_code == 400 and "open-vocabulary" in r.json()["detail"]
    finally:
        _drop(model_ids=[mid], version_ids=[vid])


def test_export_endpoint_reports_when_tensorrt_is_unavailable(client, monkeypatch):
    monkeypatch.setattr(ADAPTERS["tensorrt"], "probe", lambda: Availability(False, "tensorrt not installed"))
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v)
        mid, vid = m.id, v.id
        db.commit()
    try:
        r = client.post(f"{BASE}/models/{mid}/export", json={"format": "engine"})
        assert r.status_code == 503 and "TensorRT" in r.json()["detail"]
    finally:
        _drop(model_ids=[mid], version_ids=[vid])


def test_export_endpoint_reports_when_no_local_worker_builds_engines(client, monkeypatch):
    monkeypatch.setattr(training_router, "LOCAL_JOB_KINDS", ["version", "export", "train", "autolabel"])
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v)
        mid, vid = m.id, v.id
        db.commit()
    try:
        r = client.post(f"{BASE}/models/{mid}/export", json={"format": "engine"})
        assert r.status_code == 503
    finally:
        _drop(model_ids=[mid], version_ids=[vid])


def test_export_endpoint_requires_admin(client):
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v)
        user = User(email=f"engine-annotator-{suffix}@test.dev", name="Annotator")
        db.add(user)
        db.flush()
        db.add(Member(workspace_id=ws.id, user_id=user.id, role="annotator"))
        mid, vid, uid = m.id, v.id, user.id
        db.commit()
    try:
        r = client.post(f"{BASE}/models/{mid}/export", json={"format": "engine"},
                        headers={"Authorization": f"Bearer {issue_access(uid)}"})
        assert r.status_code == 403
    finally:
        _drop(model_ids=[mid], version_ids=[vid])
        with SessionLocal() as db:
            db.query(Member).filter(Member.user_id == uid).delete()
            db.query(User).filter(User.id == uid).delete()
            db.commit()


def test_export_endpoint_hides_models_of_other_projects(client):
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        ws, _ = _demo(db)
        other = Project(workspace_id=ws.id, slug=f"engine-other-{suffix}", name="Other", type="object-detection")
        db.add(other)
        db.flush()
        v = _new_version(db, other)
        m = _new_model(db, ws, other, v)
        mid, vid, pid = m.id, v.id, other.id
        db.commit()
    try:
        r = client.post(f"{BASE}/models/{mid}/export", json={"format": "engine"})
        assert r.status_code == 404
    finally:
        _drop(model_ids=[mid], version_ids=[vid])
        with SessionLocal() as db:
            db.query(Project).filter(Project.id == pid).delete()
            db.commit()


class FakeEngineAdapter:
    """Stands in for ultralytics: writes a stand-in engine where the worker asks for it."""

    family = "ultralytics"
    calls: list[dict] = []

    def export(self, weights, fmt, *, half=True, dest=None) -> Path:
        FakeEngineAdapter.calls.append({"weights": weights, "fmt": fmt, "half": half})
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"FAKE-ENGINE")
        return dest


def test_export_job_stores_engine_runtime_ref(client, monkeypatch):
    FakeEngineAdapter.calls.clear()
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v)
        m.weights = f"models/{m.id}/best.pt"
        job = Job(workspace_id=ws.id, project_id=p.id, kind="export_engine", status="running",
                  params={"model_id": m.id, "format": "engine"})
        db.add(job)
        db.flush()
        mid, vid, jid = m.id, v.id, job.id
        db.commit()

    src = DATA_DIR / "models" / mid / "best.pt"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"PT")

    sched = GpuScheduler(4500, None)
    holders: list[str | None] = []

    class RecordingAdapter(FakeEngineAdapter):
        def export(self, weights, fmt, *, half=True, dest=None):
            holders.append(sched.state()["holder"])       # engine builds own the card
            return super().export(weights, fmt, half=half, dest=dest)

    monkeypatch.setattr(worker, "ADAPTERS", {"ultralytics": RecordingAdapter()})
    monkeypatch.setattr(worker, "scheduler", sched)
    try:
        with SessionLocal() as db:
            job = db.get(Job, jid)
        out = worker.run_export_engine(job)

        assert out["engine"] == f"engines/{mid}.engine"
        assert (DATA_DIR / out["engine"]).read_bytes() == b"FAKE-ENGINE"
        assert holders == ["engine export yolo26n"]
        assert FakeEngineAdapter.calls[0]["fmt"] == "engine" and FakeEngineAdapter.calls[0]["half"] is True
        assert FakeEngineAdapter.calls[0]["weights"] == str(src)
        with SessionLocal() as db:
            m = db.get(TrainedModel, mid)
            assert m.runtime_refs["engine"] == out["engine"]
            assert m.runtime_refs["pt"] == f"models/{mid}/best.pt"
    finally:
        _drop(model_ids=[mid], version_ids=[vid], job_ids=[jid])


def test_export_job_fails_when_the_weights_are_missing(client):
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v)
        job = Job(workspace_id=ws.id, project_id=p.id, kind="export_engine", status="running",
                  params={"model_id": m.id, "format": "engine"})
        db.add(job)
        db.flush()
        mid, vid, jid = m.id, v.id, job.id
        db.commit()
    try:
        with SessionLocal() as db:
            job = db.get(Job, jid)
        with pytest.raises(RuntimeError, match="weights are missing"):
            worker.run_export_engine(job)
    finally:
        _drop(model_ids=[mid], version_ids=[vid], job_ids=[jid])


def test_failed_export_marks_the_job_failed_and_keeps_old_runtime_ref(client, monkeypatch):
    class Boom:
        family = "ultralytics"

        def export(self, *a, **kw):
            raise RuntimeError("TensorRT is not installed")

    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v, runtime_refs={"pt": "models/x/best.pt"})
        m.weights = f"models/{m.id}/best.pt"
        job = Job(workspace_id=ws.id, project_id=p.id, kind="export_engine", status="queued",
                  params={"model_id": m.id, "format": "engine"})
        db.add(job)
        db.flush()
        mid, vid, jid = m.id, v.id, job.id
        db.commit()

    src = DATA_DIR / "models" / mid / "best.pt"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"PT")

    monkeypatch.setattr(worker, "ADAPTERS", {"ultralytics": Boom()})
    monkeypatch.setattr(worker, "scheduler", GpuScheduler(4500, None))
    try:
        worker.run_one(jid)
        with SessionLocal() as db:
            job = db.get(Job, jid)
            assert job.status == "failed" and "TensorRT" in job.error
            assert db.get(TrainedModel, mid).runtime_refs == {"pt": "models/x/best.pt"}
    finally:
        _drop(model_ids=[mid], version_ids=[vid], job_ids=[jid])


def test_model_detail_exposes_only_a_live_engine_ref(client):
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v, runtime_refs={"pt": "models/x/best.pt", "engine": "engines/live.engine"})
        mid, vid = m.id, v.id
        db.commit()

    engine = DATA_DIR / "engines" / "live.engine"
    engine.parent.mkdir(parents=True, exist_ok=True)
    engine.write_bytes(b"ENGINE")
    try:
        body = client.get(f"{BASE}/models/{mid}").json()
        assert body["runtimeRefs"] == {"engine": "engines/live.engine"}
        engine.unlink()
        body = client.get(f"{BASE}/models/{mid}").json()
        assert body["runtimeRefs"] == {}
    finally:
        engine.unlink(missing_ok=True)
        _drop(model_ids=[mid], version_ids=[vid])


def test_delete_model_removes_its_cached_engine(client):
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v, runtime_refs={"engine": "engines/gone.engine"})
        mid, vid = m.id, v.id
        db.commit()
    engine = DATA_DIR / "engines" / "gone.engine"
    engine.parent.mkdir(parents=True, exist_ok=True)
    engine.write_bytes(b"ENGINE")
    try:
        assert client.delete(f"{BASE}/models/{mid}").status_code == 200
        assert not engine.exists()
    finally:
        _drop(model_ids=[mid], version_ids=[vid])


def test_resolve_prefers_the_engine_runtime_when_it_exists(client, monkeypatch):
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v, runtime_refs={"pt": "models/x/best.pt", "engine": "engines/pending.engine"})
        mid, vid = m.id, v.id
        db.commit()

    monkeypatch.setattr(ADAPTERS["tensorrt"], "probe", lambda: Availability(True))
    engine = DATA_DIR / "engines" / "pending.engine"
    engine.parent.mkdir(parents=True, exist_ok=True)
    engine.write_bytes(b"ENGINE")
    try:
        with SessionLocal() as db:
            r = resolve(f"trained:{mid}", db, workspace_id=ws.id)
            assert r.adapter.family == "tensorrt"
            assert r.weights == "engines/pending.engine"
            assert r.ref == f"trained:{mid}" and r.variant == "yolo26n"
    finally:
        engine.unlink(missing_ok=True)
        _drop(model_ids=[mid], version_ids=[vid])


def test_resolve_keeps_pt_when_tensorrt_is_not_installed(client, monkeypatch):
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v, runtime_refs={"pt": "models/x/best.pt", "engine": "engines/pending.engine"})
        mid, vid = m.id, v.id
        db.commit()

    monkeypatch.setattr(ADAPTERS["tensorrt"], "probe", lambda: Availability(False, "tensorrt not installed"))
    engine = DATA_DIR / "engines" / "pending.engine"
    engine.parent.mkdir(parents=True, exist_ok=True)
    engine.write_bytes(b"ENGINE")
    try:
        with SessionLocal() as db:
            r = resolve(f"trained:{mid}", db, workspace_id=ws.id)
            assert r.adapter.family == "ultralytics"
            assert r.weights == "models/x/best.pt"
    finally:
        engine.unlink(missing_ok=True)
        _drop(model_ids=[mid], version_ids=[vid])


def test_resolve_ignores_an_engine_for_open_vocabulary_models(client, monkeypatch):
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v, variant="yolov8s-worldv2",
                       runtime_refs={"pt": "models/x/best.pt", "engine": "engines/world.engine"})
        mid, vid = m.id, v.id
        db.commit()

    monkeypatch.setattr(ADAPTERS["tensorrt"], "probe", lambda: Availability(True))
    engine = DATA_DIR / "engines" / "world.engine"
    engine.parent.mkdir(parents=True, exist_ok=True)
    engine.write_bytes(b"ENGINE")
    try:
        with SessionLocal() as db:
            r = resolve(f"trained:{mid}", db, workspace_id=ws.id)
            assert r.adapter.family == "ultralytics"
            assert r.weights == "models/x/best.pt"
    finally:
        engine.unlink(missing_ok=True)
        _drop(model_ids=[mid], version_ids=[vid])


def test_resolve_falls_back_to_pt_when_the_engine_fails_to_load(client, monkeypatch, caplog):
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v, runtime_refs={"pt": "models/x/best.pt", "engine": "engines/broken.engine"})
        m.metrics = {"eval": {"f1_best": {"conf": 0.62}}}
        mid, vid = m.id, v.id
        db.commit()

    monkeypatch.setattr(importlib.import_module("app.adapters.catalog"), "_failed_engines", {})
    monkeypatch.setattr(ADAPTERS["tensorrt"], "probe", lambda: Availability(True))
    engine = DATA_DIR / "engines" / "broken.engine"
    engine.parent.mkdir(parents=True, exist_ok=True)
    engine.write_bytes(b"NOT-AN-ENGINE")

    def boom(*_a, **_kw):
        raise RuntimeError("engine deserialize failed")

    seen: dict = {}

    def fake_pt(variant, im, *, classes=None, prompt=None, weights=None, conf=0.4, iou=0.5):
        seen.update(variant=variant, weights=weights, conf=conf)
        return {"predictions": [], "time": 0.0, "image": {"width": im.width, "height": im.height}}

    monkeypatch.setattr(ADAPTERS["tensorrt"], "predict", boom)
    monkeypatch.setattr(ADAPTERS["ultralytics"], "predict", fake_pt)
    try:
        with SessionLocal() as db:
            r = resolve(f"trained:{mid}", db, workspace_id=ws.id)
        with caplog.at_level(logging.WARNING):
            out = r.predict(PImage.new("RGB", (10, 10)))
        assert out["model"] == f"trained:{mid}"
        assert seen["variant"] == "yolo26n" and seen["weights"] == "models/x/best.pt"
        assert seen["conf"] == 0.62                       # the model's best-F1 threshold survives the fallback
        assert "falling back" in caplog.text
        with SessionLocal() as db:
            again = resolve(f"trained:{mid}", db, workspace_id=ws.id)
        assert again.adapter.family == "ultralytics"      # the dead engine is not retried every image
    finally:
        engine.unlink(missing_ok=True)
        _drop(model_ids=[mid], version_ids=[vid])


def test_resolve_falls_back_to_pt_when_the_engine_file_is_gone(client):
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v, runtime_refs={"pt": "models/x/best.pt", "engine": "engines/missing.engine"})
        mid, vid = m.id, v.id
        db.commit()
    try:
        with SessionLocal() as db:
            r = resolve(f"trained:{mid}", db, workspace_id=ws.id)
            assert r.adapter.family == "ultralytics"
            assert r.weights == "models/x/best.pt"
    finally:
        _drop(model_ids=[mid], version_ids=[vid])


def test_export_caches_the_engine_atomically(monkeypatch, tmp_path):
    from app.adapters import ultralytics_ad

    calls: list[dict] = []

    class FakeYOLO:
        def __init__(self, path):
            self.path = Path(path)

        def export(self, **kw):
            calls.append(kw)
            self.path.with_suffix(".onnx").write_bytes(b"ONNX")     # ultralytics leaves this behind
            out = self.path.with_suffix(".engine")
            out.write_bytes(b"ENGINE-" + str(len(calls)).encode())
            return str(out)

    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=FakeYOLO))
    monkeypatch.setattr(ultralytics_ad, "TRAIN_DEVICE", "")
    src = tmp_path / "best.pt"
    src.write_bytes(b"PT")
    dest = tmp_path / "engines" / "m.engine"

    out = ultralytics_ad.UltralyticsAdapter().export(str(src), "engine", half=True, dest=dest)
    assert out == dest and dest.read_bytes() == b"ENGINE-1"
    assert calls[0] == {"format": "engine", "half": True}
    assert not src.with_suffix(".onnx").exists()                    # intermediate ONNX is cleaned up
    assert not dest.with_name(dest.name + ".tmp").exists()

    ultralytics_ad.UltralyticsAdapter().export(str(src), "engine", half=True, dest=dest)   # rebuild overwrites
    assert dest.read_bytes() == b"ENGINE-2"

    def boom(_src, _dst):
        raise OSError("disk full")

    monkeypatch.setattr(ultralytics_ad.os, "replace", boom)
    with pytest.raises(OSError, match="disk full"):
        ultralytics_ad.UltralyticsAdapter().export(str(src), "engine", half=True, dest=dest)
    assert dest.read_bytes() == b"ENGINE-2"                     # the previous engine survives a failed rebuild
    assert not dest.with_name(dest.name + ".tmp").exists()


def test_export_passes_train_device(monkeypatch, tmp_path):
    from app.adapters import ultralytics_ad

    seen: dict = {}

    class FakeYOLO:
        def __init__(self, path):
            self.path = Path(path)

        def export(self, **kw):
            seen.update(kw)
            out = self.path.with_suffix(".engine")
            out.write_bytes(b"ENGINE")
            return str(out)

    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=FakeYOLO))
    monkeypatch.setattr(ultralytics_ad, "TRAIN_DEVICE", "0")
    src = tmp_path / "best.pt"
    src.write_bytes(b"PT")

    ultralytics_ad.UltralyticsAdapter().export(str(src), "engine", half=True, dest=tmp_path / "engines" / "m.engine")
    assert seen == {"format": "engine", "half": True, "device": "0"}


def test_failed_export_removes_the_intermediate_onnx(monkeypatch, tmp_path):
    from app.adapters import ultralytics_ad

    class FakeYOLO:
        def __init__(self, path):
            self.path = Path(path)

        def export(self, **_kw):
            self.path.with_suffix(".onnx").write_bytes(b"ONNX")
            raise RuntimeError("engine build failed")

    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=FakeYOLO))
    src = tmp_path / "best.pt"
    src.write_bytes(b"PT")
    with pytest.raises(RuntimeError, match="engine build failed"):
        ultralytics_ad.UltralyticsAdapter().export(str(src), "engine", half=True, dest=tmp_path / "m.engine")
    assert not src.with_suffix(".onnx").exists()


def test_export_job_rejects_a_family_without_export(client, monkeypatch):
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v, family="rfdetr", variant="nano")
        m.weights = f"models/{m.id}/best.pt"
        job = Job(workspace_id=ws.id, project_id=p.id, kind="export_engine", status="running",
                  params={"model_id": m.id, "format": "engine"})
        db.add(job)
        db.flush()
        mid, vid, jid = m.id, v.id, job.id
        db.commit()
    src = DATA_DIR / "models" / mid / "best.pt"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"PT")
    monkeypatch.setattr(worker, "ADAPTERS", {"rfdetr": object()})
    monkeypatch.setattr(worker, "scheduler", GpuScheduler(4500, None))
    try:
        with SessionLocal() as db:
            job = db.get(Job, jid)
        with pytest.raises(RuntimeError, match="cannot be exported"):
            worker.run_export_engine(job)
    finally:
        _drop(model_ids=[mid], version_ids=[vid], job_ids=[jid])


def test_remote_autolabel_accepts_an_engine_backed_trained_model(client, monkeypatch):
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v, runtime_refs={"pt": "models/x/best.pt", "engine": "engines/remote.engine"})
        mid, vid = m.id, v.id
        db.commit()
    engine = DATA_DIR / "engines" / "remote.engine"
    engine.parent.mkdir(parents=True, exist_ok=True)
    engine.write_bytes(b"ENGINE")
    monkeypatch.setattr(training_router, "LOCAL_JOB_KINDS",
                        [k for k in LOCAL_JOB_KINDS if k != "autolabel"])
    monkeypatch.setattr(config, "TRAIN_WORKER", "remote")     # the pip worker is the executor here
    jid = None
    try:
        r = client.post(f"{BASE}/autolabel", json={"method": "model", "model_ref": f"trained:{mid}"})
        assert r.status_code == 200, r.text
        jid = r.json()["id"]
    finally:
        if jid:
            _cancel(jid)
        engine.unlink(missing_ok=True)
        _drop(model_ids=[mid], version_ids=[vid], job_ids=[jid] if jid else [])


class _FakeYolo:
    def __init__(self):
        self.seen: dict = {}

    def predict(self, im, conf, iou, verbose):
        self.seen.update(size=(im.width, im.height), conf=conf, iou=iou)
        return [SimpleNamespace(names={0: "person"}, boxes=[], probs=None, masks=None)]


def test_tensorrt_adapter_loads_the_engine_through_yolo(monkeypatch):
    from app.adapters import tensorrt_ad

    model = _FakeYolo()
    loaded: dict = {}

    def fake_load(path, cls="YOLO"):
        loaded.update(path=path, cls=cls)
        return model

    monkeypatch.setattr(tensorrt_ad, "_load", fake_load)
    engine = DATA_DIR / "engines" / "m.engine"
    engine.parent.mkdir(parents=True, exist_ok=True)
    engine.write_bytes(b"ENGINE")
    im = PImage.new("RGB", (64, 48))
    try:
        out = tensorrt_ad.TensorrtAdapter().predict("yolo26n", im, weights="engines/m.engine", conf=0.3, iou=0.6)
    finally:
        engine.unlink(missing_ok=True)

    assert loaded == {"path": str(DATA_DIR / "engines" / "m.engine"), "cls": "YOLO"}
    assert out["predictions"] == [] and out["image"] == {"width": 64, "height": 48}
    assert model.seen == {"size": (64, 48), "conf": 0.3, "iou": 0.6}


def test_tensorrt_adapter_requires_an_exported_engine():
    from app.adapters import tensorrt_ad

    with pytest.raises(ValueError, match="engine"):
        tensorrt_ad.TensorrtAdapter().predict("yolo26n", PImage.new("RGB", (8, 8)))


def test_tensorrt_adapter_reports_a_missing_engine_without_leaking_the_path():
    from app.adapters import tensorrt_ad

    with pytest.raises(ValueError, match="missing") as e:
        tensorrt_ad.TensorrtAdapter().predict("yolo26n", PImage.new("RGB", (8, 8)), weights="engines/none.engine")
    assert "engines/none.engine" not in str(e.value)


def test_tensorrt_adapter_is_registered():
    assert ADAPTERS["tensorrt"].family == "tensorrt"


def test_tensorrt_capabilities_match_ultralytics():
    from app.adapters import tensorrt_ad, ultralytics_ad

    trt, ultra = tensorrt_ad.TensorrtAdapter(), ultralytics_ad.UltralyticsAdapter()
    for variant in ("yolo26n", "yolo26n-seg", "yolov8s-worldv2"):
        assert trt.capabilities(variant) == ultra.capabilities(variant)


def _iou(a: dict, b: dict) -> float:
    ax1, ay1 = a["x"] - a["width"] / 2, a["y"] - a["height"] / 2
    ax2, ay2 = a["x"] + a["width"] / 2, a["y"] + a["height"] / 2
    bx1, by1 = b["x"] - b["width"] / 2, b["y"] - b["height"] / 2
    bx2, by2 = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
    inter = max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))
    union = a["width"] * a["height"] + b["width"] * b["height"] - inter
    return inter / union if union > 0 else 0.0


@pytest.mark.gpu
@pytest.mark.skipif(os.environ.get("LD_GPU_TESTS") != "1", reason="GPU-only: set LD_GPU_TESTS=1")
def test_engine_predict_matches_pt_within_tolerance():
    """Same top-1 class and box IoU >= 0.9 between the .pt and its TensorRT engine (shipped adapter path)."""
    from app.adapters.tensorrt_ad import TensorrtAdapter
    from app.adapters.ultralytics_ad import UltralyticsAdapter
    from app.config import PRETRAINED_DIR, REPO_ROOT

    weights = next((p for p in (PRETRAINED_DIR / "yolo26n.pt", PRETRAINED_DIR / "yolo26s.pt") if p.exists()), None)
    image = os.environ.get("LD_ENGINE_TEST_IMAGE")
    if image is None:                                  # the demo dataset ships with the repo
        shots = sorted((REPO_ROOT / "data" / "raw" / "blurred").glob("*.jpg"))
        image = str(shots[0]) if shots else None
    if weights is None or not image or not Path(image).exists():
        pytest.skip("needs a local yolo26 checkpoint and a test photo (LD_ENGINE_TEST_IMAGE)")

    rel = f"engines/test-{uuid.uuid4().hex}.engine"
    dest = DATA_DIR / rel
    try:
        im = PImage.open(image).convert("RGB")
        pt = UltralyticsAdapter().predict("yolo26n", im, weights=str(weights), conf=0.25)
        UltralyticsAdapter().export(str(weights), "engine", half=True, dest=dest)
        trt = TensorrtAdapter().predict("yolo26n", im, weights=rel, conf=0.25)

        assert pt["predictions"] and trt["predictions"]
        a = max(pt["predictions"], key=lambda p: p["confidence"])
        b = max(trt["predictions"], key=lambda p: p["confidence"])
        assert a["class"] == b["class"]
        assert _iou(a, b) >= 0.9
    finally:
        dest.unlink(missing_ok=True)
