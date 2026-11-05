"""Task 34: edge export presets — flags gate, preset catalog, export job, artifacts."""

import json
import os
import shutil
from pathlib import Path

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import worker
from app.adapters.base import Availability
from app.config import DATA_DIR, LOCAL_JOB_KINDS, REMOTE_JOB_KINDS
from app.db import SessionLocal
from app.handlers import versioning as vhandlers
from app.main import app
from app.models import Job, Member, Project, TrainedModel, User, Version, Workspace, WorkspaceFlag
from app.security import issue_access
from app.services import edge

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/ws/{WS}/projects/{PR}"
FLAGS = f"/api/ws/{WS}/flags"
PRESETS = f"{BASE}/models/edge-presets"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
        c.headers["Authorization"] = f"Bearer {issue_access(user.id)}"
        yield c


@pytest.fixture(autouse=True)
def _flag_off_and_cleanup():
    yield
    try:
        with SessionLocal() as db:
            ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
            row = db.get(WorkspaceFlag, (ws.id, "task_34")) if ws else None
            if row and row.enabled:
                row.enabled = False
                db.commit()
    except Exception:  # tests that never opened the app have no database yet
        pass


def _demo(db):
    ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
    p = db.scalar(select(Project).where(Project.workspace_id == ws.id, Project.slug == PR))
    return ws, p


def _enable_flag(client):
    r = client.put(f"{FLAGS}/task_34", json={"enabled": True})
    assert r.status_code == 200, r.text


def _new_version(db, p, *, status="ready", manifest=None) -> Version:
    n = (db.scalar(select(func.max(Version.number)).where(Version.project_id == p.id)) or 0) + 1
    v = Version(project_id=p.id, number=n, name=f"edge-{n}", status=status,
                stats={"class_names": ["person"]})
    db.add(v)
    db.flush()
    if manifest is not None:
        d = DATA_DIR / "versions" / v.id
        d.mkdir(parents=True, exist_ok=True)
        (d / "manifest.json").write_text(json.dumps(manifest))
    return v


def _new_model(db, ws, p, v, *, status="ready", variant="yolo26n", family="ultralytics", task="detect"):
    m = TrainedModel(workspace_id=ws.id, project_id=p.id, version_id=v.id, name=f"edge-{v.number}",
                     arch=variant, family=family, variant=variant, task=task, status=status,
                     classes=["person"], weights="", runtime_refs={})
    db.add(m)
    db.flush()
    m.weights = f"models/{m.id}/best.pt"
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
        shutil.rmtree(DATA_DIR / "models" / mid, ignore_errors=True)
        shutil.rmtree(DATA_DIR / "edge" / mid, ignore_errors=True)
    for vid in version_ids:
        shutil.rmtree(DATA_DIR / "versions" / vid, ignore_errors=True)


def _cancel(jid: str):
    """Keep the embedded worker from claiming a job a test queued for inspection."""
    with SessionLocal() as db:
        row = db.get(Job, jid)
        if row and row.status == "queued":
            row.status = "cancelled"
            db.commit()


# --- flags --------------------------------------------------------------------


def test_edge_presets_are_a_local_job_kind():
    assert "export_preset" in LOCAL_JOB_KINDS
    assert "export_preset" not in REMOTE_JOB_KINDS    # built by the worker that owns the export toolchain


def test_flags_default_off_and_hide_the_presets(client):
    r = client.get(FLAGS)
    assert r.status_code == 200
    assert "task_34" not in r.json()["enabled"]
    assert client.get(PRESETS).status_code == 404


def test_flag_can_be_enabled_by_an_admin(client):
    _enable_flag(client)
    assert "task_34" in client.get(FLAGS).json()["enabled"]
    assert client.get(PRESETS).status_code == 200


def test_flag_overrides_are_workspace_scoped(client):
    """Enabling task_34 for the demo workspace must not leak into another tenant."""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
        other = Workspace(slug=f"edge-other-{user.id}", name="Other", owner_id=user.id)
        db.add(other)
        db.flush()
        db.add(Member(workspace_id=other.id, user_id=user.id, role="owner"))
        db.commit()
        other_slug = other.slug
    try:
        _enable_flag(client)
        assert "task_34" in client.get(FLAGS).json()["enabled"]
        assert "task_34" not in client.get(f"/api/ws/{other_slug}/flags").json()["enabled"]
    finally:
        with SessionLocal() as db:
            ws = db.scalar(select(Workspace).where(Workspace.slug == other_slug))
            if ws:
                db.delete(ws)
                db.commit()


# --- catalog ------------------------------------------------------------------


def test_catalog_lists_the_required_presets_and_every_one_is_unverified(client):
    _enable_flag(client)
    r = client.get(PRESETS)
    assert r.status_code == 200, r.text
    items = {x["id"]: x for x in r.json()}
    assert {"onnx", "onnx-nms-free", "openvino", "tflite-int8", "jetson", "hailo", "deepx"} <= set(items)
    assert all(x["verified"] is False for x in items.values())     # none ran on a real device
    assert all(x["status"] == "UNVERIFIED" for x in items.values())
    assert items["onnx-nms-free"]["requires"] == "yolo26"
    assert items["hailo"]["device"] and items["deepx"]["device"] and items["jetson"]["device"]
    assert items["tflite-int8"]["needs_data"] is True
    assert "options" not in items["onnx"]             # internal export kwargs never reach the UI


# --- export request -----------------------------------------------------------


def test_export_preset_queues_a_job_and_is_idempotent(client):
    _enable_flag(client)
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v)
        mid, vid = m.id, v.id
        db.commit()
    jid = None
    try:
        r = client.post(f"{BASE}/models/{mid}/export", json={"preset": "onnx"})
        assert r.status_code == 200, r.text
        body = r.json()
        jid = body["id"]
        assert body["kind"] == "export_preset"
        assert body["params"] == {"model_id": mid, "preset": "onnx"}
        again = client.post(f"{BASE}/models/{mid}/export", json={"preset": "onnx"})
        assert again.status_code == 200 and again.json()["id"] == jid
    finally:
        if jid:
            _cancel(jid)
        _drop(model_ids=[mid], version_ids=[vid], job_ids=[jid] if jid else [])


def test_export_preset_rejects_unknown_and_invalid_models(client):
    _enable_flag(client)
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        ok = _new_model(db, ws, p, v)
        world = _new_model(db, ws, p, v, variant="yolov8s-worldv2")
        hf = _new_model(db, ws, p, v, family="hf")
        training = _new_model(db, ws, p, v, status="training")
        ids = [ok.id, world.id, hf.id, training.id]
        vid = v.id
        db.commit()
    try:
        assert client.post(f"{BASE}/models/{ok.id}/export", json={"preset": "nope"}).status_code == 400
        assert client.post(f"{BASE}/models/{world.id}/export", json={"preset": "onnx"}).status_code == 400
        assert client.post(f"{BASE}/models/{hf.id}/export", json={"preset": "onnx"}).status_code == 400
        assert client.post(f"{BASE}/models/{training.id}/export", json={"preset": "onnx"}).status_code == 409
    finally:
        _drop(model_ids=ids, version_ids=[vid])


def test_nms_free_preset_requires_yolo26(client):
    _enable_flag(client)
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        old = _new_model(db, ws, p, v, variant="yolo11n")
        new = _new_model(db, ws, p, v, variant="yolo26n")
        ids, vid = [old.id, new.id], v.id
        db.commit()
    jid = None
    try:
        assert client.post(f"{BASE}/models/{old.id}/export", json={"preset": "onnx-nms-free"}).status_code == 400
        r = client.post(f"{BASE}/models/{new.id}/export", json={"preset": "onnx-nms-free"})
        assert r.status_code == 200, r.text
        jid = r.json()["id"]
    finally:
        if jid:
            _cancel(jid)
        _drop(model_ids=ids, version_ids=[vid], job_ids=[jid] if jid else [])


def test_int8_preset_needs_a_ready_version(client):
    _enable_flag(client)
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p, status="generating")
        m = _new_model(db, ws, p, v)
        mid, vid = m.id, v.id
        db.commit()
    try:
        assert client.post(f"{BASE}/models/{mid}/export", json={"preset": "tflite-int8"}).status_code == 409
    finally:
        _drop(model_ids=[mid], version_ids=[vid])


def test_engine_export_is_unchanged_while_the_flag_is_off(client, monkeypatch):
    """The pre-Task-34 TensorRT flow must keep working with task_34 off."""
    from app.adapters import ADAPTERS

    monkeypatch.setattr(ADAPTERS["tensorrt"], "probe", lambda: Availability(True))
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
        assert r.json()["kind"] == "export_engine"
        jid = r.json()["id"]
    finally:
        if jid:
            _cancel(jid)
        _drop(model_ids=[mid], version_ids=[vid], job_ids=[jid] if jid else [])


def test_preset_export_is_a_404_while_the_flag_is_off(client):
    """A preset request must not reveal the feature, and must not queue a job."""
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v)
        mid, vid, pid = m.id, v.id, p.id
        db.commit()
    try:
        r = client.post(f"{BASE}/models/{mid}/export", json={"preset": "onnx"})
        assert r.status_code == 404
        with SessionLocal() as db:
            assert db.scalar(select(func.count(Job.id)).where(
                Job.project_id == pid, Job.kind == "export_preset")) == 0
    finally:
        _drop(model_ids=[mid], version_ids=[vid])


def test_only_managers_can_queue_an_edge_build(client):
    _enable_flag(client)
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v)
        mid, vid = m.id, v.id
        user = db.scalar(select(User).where(User.email == "labeler@labeldesk.dev"))
        db.commit()
    h = {"Authorization": f"Bearer {issue_access(user.id)}"}
    try:
        r = client.post(f"{BASE}/models/{mid}/export", json={"preset": "onnx"}, headers=h)
        assert r.status_code == 403
    finally:
        _drop(model_ids=[mid], version_ids=[vid])


def test_export_plan_uses_litert_on_new_ultralytics(monkeypatch):
    monkeypatch.setattr(edge, "_ultralytics_version", lambda: (8, 4, 146))
    assert edge.export_plan("tflite-int8") == ("litert", {"quantize": 8})
    monkeypatch.setattr(edge, "_ultralytics_version", lambda: (8, 3, 0))
    assert edge.export_plan("tflite-int8") == ("tflite", {"int8": True})
    assert edge.export_plan("onnx-nms-free") == ("onnx", {"nms": False})


# --- worker -------------------------------------------------------------------


class FakePresetAdapter:
    """Writes a single-file artifact for onnx-like presets and a directory for openvino-like ones."""

    family = "ultralytics"
    calls: list[dict] = []

    def __init__(self, *, directory=False):
        self.directory = directory

    def export(self, weights, fmt, *, half=True, dest=None, options=None, data=None):
        FakePresetAdapter.calls.append({"weights": weights, "fmt": fmt, "half": half,
                                        "options": options or {}, "data": data})
        out = Path(weights).with_name(f"best.{fmt}")
        if self.directory:
            out.mkdir(parents=True, exist_ok=True)
            (out / "openvino.xml").write_text("<net/>")
            (out / "openvino.bin").write_bytes(b"BIN")
        else:
            out.write_bytes(b"ONNX")
        return out


def _queued_job(db, ws, p, m, preset) -> Job:
    job = Job(workspace_id=ws.id, project_id=p.id, kind="export_preset", status="running",
              params={"model_id": m.id, "preset": preset})
    db.add(job)
    db.flush()
    return job


def _model_files(mid: str):
    src = DATA_DIR / "models" / mid / "best.pt"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"PT")


def test_preset_job_zips_the_artifact_and_records_an_unverified_export(client, monkeypatch):
    FakePresetAdapter.calls.clear()
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v, variant="yolo26n")
        job = _queued_job(db, ws, p, m, "onnx")
        mid, vid, jid = m.id, v.id, job.id
        db.commit()
    _model_files(mid)
    monkeypatch.setattr(worker, "ADAPTERS", {"ultralytics": FakePresetAdapter()})
    try:
        with SessionLocal() as db:
            out = vhandlers.run_export_preset(db.get(Job, jid))
        rel = f"edge/{mid}/onnx.zip"
        assert out["file"] == rel
        assert (DATA_DIR / rel).is_file()
        assert FakePresetAdapter.calls[0]["fmt"] == "onnx"
        with SessionLocal() as db:
            refs = db.get(TrainedModel, mid).runtime_refs["edge"]["onnx"]
            assert refs["file"] == rel and refs["verified"] is False and refs["bytes"] > 0
            assert "built" in refs
        detail = client.get(f"{BASE}/models/{mid}")
        assert detail.status_code == 200
        entry = detail.json()["edgeExports"]["onnx"]
        assert entry["url"].startswith("/api/files/") and entry["verified"] is False
    finally:
        _drop(model_ids=[mid], version_ids=[vid], job_ids=[jid])


def test_preset_job_zips_a_directory_artifact(client, monkeypatch):
    FakePresetAdapter.calls.clear()
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v)
        job = _queued_job(db, ws, p, m, "openvino")
        mid, vid, jid = m.id, v.id, job.id
        db.commit()
    _model_files(mid)
    monkeypatch.setattr(worker, "ADAPTERS", {"ultralytics": FakePresetAdapter(directory=True)})
    try:
        with SessionLocal() as db:
            vhandlers.run_export_preset(db.get(Job, jid))
        import zipfile

        with zipfile.ZipFile(DATA_DIR / "edge" / mid / "openvino.zip") as z:
            names = z.namelist()
        assert any(n.endswith("openvino.xml") for n in names)
        assert FakePresetAdapter.calls[0]["fmt"] == "openvino"
    finally:
        _drop(model_ids=[mid], version_ids=[vid], job_ids=[jid])


def test_int8_preset_receives_calibration_data(client, monkeypatch):
    FakePresetAdapter.calls.clear()
    manifest = {"classes": ["person"], "type": "object-detection", "items": []}
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p, manifest=manifest)
        m = _new_model(db, ws, p, v)
        job = _queued_job(db, ws, p, m, "tflite-int8")
        mid, vid, jid = m.id, v.id, job.id
        db.commit()
    _model_files(mid)
    monkeypatch.setattr(worker, "ADAPTERS", {"ultralytics": FakePresetAdapter()})
    try:
        with SessionLocal() as db:
            vhandlers.run_export_preset(db.get(Job, jid))
        call = FakePresetAdapter.calls[0]
        assert call["fmt"] == edge.export_plan("tflite-int8")[0]
        assert call["options"] == edge.export_plan("tflite-int8")[1]
        assert call["data"] and call["data"].endswith("data.yaml")
    finally:
        _drop(model_ids=[mid], version_ids=[vid], job_ids=[jid])


def test_classification_calibration_points_at_the_dataset_root():
    """`check_cls_dataset` wants the folder, not a data.yaml (which it cannot parse)."""
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p, manifest={"classes": ["ok", "defect"], "type": "classification", "items": []})
        vid = v.id
        db.commit()
        root = edge.calibration_data(v, "classify")
    try:
        assert Path(root).is_dir() and Path(root).name == "folder"
    finally:
        _drop(version_ids=[vid])


def test_preset_job_requires_the_weights(client):
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v)
        job = _queued_job(db, ws, p, m, "onnx")
        mid, vid, jid = m.id, v.id, job.id
        db.commit()
    try:
        with SessionLocal() as db, pytest.raises(RuntimeError, match="weights are missing"):
            vhandlers.run_export_preset(db.get(Job, jid))
    finally:
        _drop(model_ids=[mid], version_ids=[vid], job_ids=[jid])


def test_delete_model_removes_its_edge_exports(client):
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v)
        mid, vid = m.id, v.id
        db.commit()
    edge_dir = DATA_DIR / "edge" / mid
    edge_dir.mkdir(parents=True, exist_ok=True)
    (edge_dir / "onnx.zip").write_bytes(b"ZIP")
    try:
        r = client.delete(f"{BASE}/models/{mid}")
        assert r.status_code == 200, r.text
        assert not edge_dir.exists()
    finally:
        _drop(model_ids=[mid], version_ids=[vid])
