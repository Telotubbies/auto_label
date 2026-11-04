"""Task 25 integration: alias resolution on the hosted API, metered usage and quota 402s."""

import io
import os
import tempfile
import time

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-t25-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import select

from app.adapters import ADAPTERS
from app.db import SessionLocal
from app.main import app
from app.models import Image, Project, TrainedModel, Version, Workspace

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/ws/{WS}/projects/{PR}"


class FakeDetector:
    family = "ultralytics"

    def probe(self):
        from app.adapters import Availability

        return Availability(True)

    def capabilities(self, variant):
        return {"detect"}

    def predict(self, variant, im, *, classes=None, prompt=None, weights=None, conf=0.4, iou=0.5):
        return {
            "time": 0.01,
            "image": {"width": im.width, "height": im.height},
            "predictions": [
                {"class": "helmet", "class_id": 0, "confidence": 0.91, "x": 4, "y": 4, "width": 20, "height": 20}
            ],
        }


def jpeg(color=(120, 60, 30)) -> bytes:
    b = io.BytesIO()
    PImage.new("RGB", (64, 48), color).save(b, "JPEG")
    return b.getvalue()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        tok = c.post("/api/auth/login", json={"email": "demo@labeldesk.dev", "password": "demo1234"}).json()["token"]
        c.headers["Authorization"] = f"Bearer {tok}"
        yield c


@pytest.fixture(scope="module")
def models(client):
    """Two ready models in the demo project and an infer-scoped key."""
    with SessionLocal() as db:
        project = db.scalar(select(Project).where(Project.slug == PR))
        v = db.scalar(select(Version).where(Version.project_id == project.id).limit(1))
        if v is None:
            v = Version(
                project_id=project.id, number=900, name="t25", status="ready", stats={"class_names": ["helmet"]}
            )
            db.add(v)
            db.flush()
        made = []
        for name in ("t25-det-a", "t25-det-b"):
            m = TrainedModel(
                id=f"t25{name[-1]}{int(time.time() * 1000) % 100000}",
                workspace_id=project.workspace_id,
                project_id=project.id,
                version_id=v.id,
                name=name,
                arch="yolo26n",
                task="detect",
                status="ready",
                classes=["helmet"],
                weights="weights/x.pt",
            )
            db.add(m)
            made.append(m.id)
        db.commit()
    key = client.post(f"/api/ws/{WS}/keys", json={"name": "t25-infer", "scopes": ["infer"]}).json()["key"]
    return {"a": made[0], "b": made[1], "key": key, "project": project.slug}


def test_alias_switch_and_rollback(client, models):
    r = client.put(f"{BASE}/deployments/production", json={"model_id": models["a"]})
    assert r.status_code == 200, r.text
    assert r.json()["model_id"] == models["a"]
    assert r.json()["previous_model_id"] is None

    r = client.put(f"{BASE}/deployments/production", json={"model_id": models["b"]})
    assert r.status_code == 200, r.text
    assert r.json()["previous_model_id"] == models["a"]

    # a failed switch leaves the alias exactly where it was (atomic: no half-update)
    r = client.put(f"{BASE}/deployments/production", json={"model_id": "does-not-exist"})
    assert r.status_code == 400
    state = client.get(f"{BASE}/deployments").json()
    prod = next(a for a in state["aliases"] if a["alias"] == "production")
    assert prod["model_id"] == models["b"]

    r = client.post(f"{BASE}/deployments/production/rollback")
    assert r.status_code == 200, r.text
    assert r.json()["model_id"] == models["a"]
    assert r.json()["previous_model_id"] == models["b"]


def test_hosted_api_resolves_project_alias(client, models, monkeypatch):
    monkeypatch.setitem(ADAPTERS, "ultralytics", FakeDetector())
    client.put(f"{BASE}/deployments/production", json={"model_id": models["a"]})
    h = {"Authorization": f"Bearer {models['key']}"}
    r = client.post(f"/api/v1/models/production@{PR}/predict", headers=h, files={"file": ("frame.jpg", jpeg())})
    assert r.status_code == 200, r.text
    assert r.json()["predictions"][0]["class"] == "helmet"
    # the plain model route also accepts an alias when it is unique in the workspace
    r = client.post("/api/v1/models/production/predict", headers=h, files={"file": ("frame.jpg", jpeg())})
    assert r.status_code == 200, r.text


def test_usage_endpoint_meters_are_present(client):
    u = client.get(f"/api/ws/{WS}/usage").json()
    assert set(u["meters"]) == {"gpu_seconds", "stream_hours", "ai_calls", "storage_bytes"}
    assert u["meters"]["ai_calls"]["used"] >= 2  # two hosted predictions above
    assert len(u["daily_meters"]) == 30
    assert u["daily_meters"][-1]["date"] == time.strftime("%Y-%m-%d")
    assert u["daily_meters"][-1]["ai_calls"] >= 2


def test_quota_blocks_hosted_inference_with_402(client, models, monkeypatch):
    monkeypatch.setitem(ADAPTERS, "ultralytics", FakeDetector())
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        old = dict(ws.quotas or {})
        ws.quotas = {**old, "ai_calls": 0}
        db.commit()
        ws_id = ws.id
    try:
        h = {"Authorization": f"Bearer {models['key']}"}
        r = client.post(f"/api/v1/models/production@{PR}/predict", headers=h, files={"file": ("frame.jpg", jpeg())})
        assert r.status_code == 402
        assert "AI calls quota" in r.json()["detail"]
    finally:
        with SessionLocal() as db:
            ws = db.get(Workspace, ws_id)
            ws.quotas = old or None
            db.commit()


def test_storage_quota_blocks_upload_with_402(client):
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        old = dict(ws.quotas or {})
        ws.quotas = {**old, "storage_bytes": 0}
        db.commit()
        ws_id = ws.id
    try:
        r = client.post(f"{BASE}/upload", files={"files": ("new.jpg", jpeg((5, 5, 5)))}, data={"split": "auto"})
        assert r.status_code == 402
        assert "Storage quota" in r.json()["detail"]
    finally:
        with SessionLocal() as db:
            ws = db.get(Workspace, ws_id)
            ws.quotas = old or None
            db.commit()


def random_jpeg() -> bytes:
    b = io.BytesIO()
    PImage.frombytes("RGB", (16, 16), os.urandom(16 * 16 * 3)).save(b, "JPEG")
    return b.getvalue()


def test_delete_image_releases_storage(client):
    """I2: deleting an image must give its bytes back to the storage meter."""
    before = client.get(f"/api/ws/{WS}/usage").json()["meters"]["storage_bytes"]["used"]
    up = client.post(
        f"{BASE}/upload",
        files={"files": ("meter.jpg", random_jpeg())},
        data={"split": "auto", "batch_name": "t25 meter"},
    )
    assert up.status_code == 200, up.text
    assert up.json()["uploaded"] == 1
    iid = up.json()["images"][0]["id"]
    with SessionLocal() as db:
        size = db.get(Image, iid).size
    after_upload = client.get(f"/api/ws/{WS}/usage").json()["meters"]["storage_bytes"]["used"]
    assert after_upload == pytest.approx(before + size)

    assert client.delete(f"/api/images/{iid}").status_code == 200
    after_delete = client.get(f"/api/ws/{WS}/usage").json()["meters"]["storage_bytes"]["used"]
    assert after_delete == pytest.approx(before)
    meter = client.get(f"/api/ws/{WS}/usage").json()["meters"]["storage_bytes"]
    assert meter["label"] == "Storage" and meter["period"] == "total"


def test_hosted_predict_survives_a_sampling_failure(client, models, monkeypatch):
    """I4: a monitoring side effect must never turn a successful inference into a 500."""
    from app.services import active_learning, drift

    monkeypatch.setitem(ADAPTERS, "ultralytics", FakeDetector())

    def boom(*args, **kwargs):
        raise OSError("data volume is full")

    monkeypatch.setattr(drift, "record_sample", boom)
    monkeypatch.setattr(active_learning, "auto_offer", boom)
    assert client.put(f"{BASE}/deployments/production", json={"model_id": models["a"]}).status_code == 200
    h = {"Authorization": f"Bearer {models['key']}"}
    r = client.post(f"/api/v1/models/production@{PR}/predict", headers=h, files={"file": ("frame.jpg", jpeg())})
    assert r.status_code == 200, r.text
    assert r.json()["predictions"][0]["class"] == "helmet"


def test_ops_endpoints_are_wired(client):
    assert client.get(f"{BASE}/drift").status_code == 200
    al = client.get(f"{BASE}/active-learning").json()
    assert al["cap"] >= 1 and al["remaining"] >= 0
    assert client.get(f"/api/ws/{WS}/deployments").status_code == 200
