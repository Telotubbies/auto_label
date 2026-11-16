"""Tiled inference is wired into playground, editor assist, auto-label and the hosted API, behind task_30."""
import io
import os
import time
from types import SimpleNamespace

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import delete, select

from app.adapters import refine
from app.db import SessionLocal
from app.main import app
from app.models import Image, Job, LabelClass, Project, TrainedModel, Version, Workspace, WorkspaceFlag
from app.services import health

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/ws/{WS}/projects/{PR}"


def _jpeg(size=(800, 800)) -> bytes:
    buf = io.BytesIO()
    PImage.new("RGB", size, (40, 80, 120)).save(buf, "JPEG")
    return buf.getvalue()


class FakeResolved:
    conf = None
    variant = "yolo26n"
    ref = "trained:fake"
    adapter = SimpleNamespace(family="ultralytics", capabilities=lambda _v: {"detect"})

    def __init__(self):
        self.calls = []

    def predict(self, im, **kw):
        self.calls.append((im.size, kw))
        return {"predictions": [{"x": im.width / 2, "y": im.height / 2, "width": 60, "height": 60,
                                 "confidence": 0.8, "class": "helmet", "class_id": 0}],
                "time": 0.01, "image": {"width": im.width, "height": im.height}, "model": self.ref}


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        r = client.post("/api/auth/login", json={"email": "demo@labeldesk.dev", "password": "demo1234"})
        client.headers["Authorization"] = f"Bearer {r.json()['token']}"
        yield client


@pytest.fixture(autouse=True)
def _flag_off(monkeypatch):
    keys = [k for k in os.environ.get("LD_FLAGS_ON", "").split(",") if k and k != "task_30"]
    monkeypatch.setenv("LD_FLAGS_ON", ",".join(keys))
    _clear()
    yield
    _clear()


def _clear():
    with SessionLocal() as db:
        db.execute(delete(WorkspaceFlag).where(WorkspaceFlag.key == "task_30"))
        db.commit()
        db.execute(delete(TrainedModel).where(TrainedModel.name.like("t30-%")))
        db.execute(delete(Workspace).where(Workspace.slug.like("t30-%")))
        db.commit()


def _enable(on: bool = True):
    with SessionLocal() as db:
        ws = db.scalar(select(Project.workspace_id).where(Project.slug == PR))
        db.merge(WorkspaceFlag(workspace_id=ws, key="task_30", enabled=on))
        db.commit()


def _ready_model(name: str = "t30-model") -> str:
    """A ready model row without weights, enough for the pre-flight and quota paths."""
    mid = f"{name}-{int(time.time() * 1000) % 100000}"
    with SessionLocal() as db:
        project = db.scalar(select(Project).where(Project.slug == PR))
        version = db.scalar(select(Version).where(Version.project_id == project.id).limit(1))
        if version is None:
            version = Version(project_id=project.id, number=931, name="t30", status="ready", stats={})
            db.add(version)
            db.flush()
        db.add(TrainedModel(id=mid, workspace_id=project.workspace_id, project_id=project.id,
                            version_id=version.id, name=f"t30-{name}", arch="yolo26n", task="detect",
                            status="ready", classes=["helmet"], weights="weights/x.pt"))
        db.commit()
    return mid


def _credits() -> float:
    with SessionLocal() as db:
        return db.scalar(select(Workspace.credits_used).where(Workspace.slug == WS))


def _image_id() -> str:
    with SessionLocal() as db:
        pid = db.scalar(select(Project.id).where(Project.slug == PR))
        return db.scalar(select(Image.id).where(Image.project_id == pid, Image.deleted_at.is_(None)).limit(1))


def _foreign_model() -> str:
    """A ready model that belongs to another workspace, sharing only the demo project id."""
    mid = f"t30-foreign-{int(time.time() * 1000) % 100000}"
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        project = db.scalar(select(Project).where(Project.slug == PR))
        version = db.scalar(select(Version).where(Version.project_id == project.id).limit(1))
        other = Workspace(id=f"w{mid[-10:]}", slug=f"t30-{mid[-8:]}", name="T30 other", owner_id=ws.owner_id)
        db.add(other)
        db.flush()
        db.add(TrainedModel(id=mid, workspace_id=other.id, project_id=project.id, version_id=version.id,
                            name="t30-foreign", arch="yolo26n", task="detect", status="ready",
                            classes=["helmet"], weights="weights/x.pt"))
        db.commit()
    return mid


def test_playground_slices_when_the_flag_is_on(c, monkeypatch):
    fake = FakeResolved()
    monkeypatch.setattr("app.routers.playground.resolve", lambda *a, **kw: fake)
    _enable()
    r = c.post(f"/api/ws/{WS}/playground/predict", files={"file": ("big.jpg", _jpeg())},
               data={"model_refs": "trained:fake", "confidence": "0.3", "tile_size": "400", "tile_overlap": "0"})
    assert r.status_code == 200, r.text
    pred = r.json()["results"][0]["prediction"]
    assert pred["image"] == {"width": 800, "height": 800}
    assert len(fake.calls) == 4
    assert {p["x"] for p in pred["predictions"]} == {200.0, 600.0}


def test_playground_tiling_is_hidden_when_the_flag_is_off(c):
    r = c.post(f"/api/ws/{WS}/playground/predict", files={"file": ("big.jpg", _jpeg())},
               data={"model_refs": "trained:fake", "tile_size": "400"})
    assert r.status_code == 404, r.text


def test_playground_rejects_a_bad_tile_size(c):
    _enable()
    r = c.post(f"/api/ws/{WS}/playground/predict", files={"file": ("big.jpg", _jpeg())},
               data={"model_refs": "trained:fake", "tile_size": "16"})
    assert r.status_code == 400, r.text
    assert "tiling" in r.json()["detail"]


def test_playground_rejects_an_overlap_that_leaves_no_stride(c):
    _enable()
    r = c.post(f"/api/ws/{WS}/playground/predict", files={"file": ("big.jpg", _jpeg())},
               data={"model_refs": "trained:fake", "tile_size": "400", "tile_overlap": "0.95"})
    assert r.status_code == 400, r.text
    assert "overlap" in r.json()["detail"]


def test_label_image_uses_global_coordinates(monkeypatch):
    fake = FakeResolved()
    monkeypatch.setattr(refine, "resolve", lambda *a, **kw: fake)
    with SessionLocal() as db:
        pid = db.scalar(select(Project.id).where(Project.slug == PR))
        classes = list(db.scalars(select(LabelClass).where(LabelClass.project_id == pid)).all())
    anns = refine.label_image(
        PImage.new("RGB", (800, 800)), project_type="object-detection",
        params={"model_ref": "trained:fake", "tile_size": 400, "tile_overlap": 0, "class_ids": []},
        classes=classes, db=None, workspace_id=WS, sam_ok=False)
    assert len(fake.calls) == 4
    assert len(anns) == 4
    centres = [a["shape"]["x"] + a["shape"]["w"] / 2 for a in anns]
    assert any(abs(x - 0.25) < 0.01 for x in centres)
    assert any(abs(x - 0.75) < 0.01 for x in centres)


def test_label_image_refuses_a_sam_model(monkeypatch):
    fake = FakeResolved()
    fake.adapter = SimpleNamespace(family="sam3", capabilities=lambda _v: {"segment"})
    monkeypatch.setattr(refine, "resolve", lambda *a, **kw: fake)
    with pytest.raises(ValueError, match="detection"):
        refine.label_image(PImage.new("RGB", (800, 800)), project_type="object-detection",
                           params={"model_ref": "sam3:sam3.1", "tile_size": 400}, classes=[], db=None,
                           workspace_id=WS, sam_ok=False)


def test_health_offers_tiling_only_when_enabled():
    checks = {"imgsz": 640, "size_buckets": {"small": 41, "medium": 30, "large": 29},
              "label_quality": [], "missing_boxes": [], "leakage_pairs": 0}
    plain = next(r for r in health.recommendations(checks) if r["key"] == "imgsz")
    assert plain["suggest"] == {"imgsz": 1024}
    tiled = next(r for r in health.recommendations(checks, tiling=True) if r["key"] == "imgsz")
    assert tiled["suggest"] == {"imgsz": 1024, "tiling": {"tile_size": 1024, "overlap": 0.2}}


def test_autolabel_tiling_is_hidden_when_the_flag_is_off(c):
    r = c.post(f"{BASE}/autolabel/preview", json={"method": "model", "model_id": "missing", "tile_size": 400})
    assert r.status_code == 404, r.text


def test_model_test_predict_is_hidden_before_the_credit_charge(c):
    mid = _ready_model("t30-test")
    before = _credits()
    r = c.post(f"{BASE}/models/{mid}/predict", files={"file": ("big.jpg", _jpeg())}, data={"tile_size": "400"})
    assert r.status_code == 404, r.text
    assert _credits() == before, "a disabled surface must not charge the workspace"


def test_autolabel_carries_tiling_into_the_job_when_enabled(c, monkeypatch):
    mid = _ready_model("t30-auto")
    monkeypatch.setattr("app.routers.training.metering.check", lambda *a, **kw: None)
    _enable()
    r = c.post(f"{BASE}/autolabel", json={"method": "model", "model_id": mid, "tile_size": 512,
                                          "tile_overlap": 0.3})
    assert r.status_code == 200, r.text
    assert r.json()["params"]["tile_size"] == 512
    assert r.json()["params"]["tile_overlap"] == 0.3
    with SessionLocal() as db:          # weights are fake: drop the job instead of letting it fail loudly
        db.execute(delete(Job).where(Job.id == r.json()["id"]))
        db.commit()


def test_autolabel_refuses_tiling_with_sam(c):
    _enable()
    r = c.post(f"{BASE}/autolabel/preview", json={"method": "sam", "tile_size": 512})
    assert r.status_code == 400, r.text
    assert "detection" in r.json()["detail"]


def test_label_assist_refuses_a_model_from_another_workspace(c):
    _enable()
    mid = _foreign_model()
    r = c.post(f"/api/images/{_image_id()}/label-assist", json={"model_id": mid, "tile_size": 512})
    assert r.status_code == 404, r.text


def test_hosted_tiling_answers_404_before_the_quota_check(c):
    """A disabled feature must look missing even when the workspace is over quota."""
    mid = _ready_model("t30-quota")
    with SessionLocal() as db:
        project = db.scalar(select(Project).where(Project.slug == PR))
        ws = db.get(Workspace, project.workspace_id)
        old, ws_id = ws.quotas, ws.id
        ws.quotas = {"ai_calls": 0}
        db.commit()
    try:
        token = c.post(f"/api/ws/{WS}/keys", json={"name": "t30q", "scopes": ["infer"]}).json()["key"]
        r = TestClient(app).post(f"/api/v1/models/{mid}/predict", headers={"x-api-key": token},
                                 params={"tile_size": 400}, files={"file": ("big.jpg", _jpeg())})
        assert r.status_code == 404, r.text
    finally:
        with SessionLocal() as db:
            db.get(Workspace, ws_id).quotas = old
            db.commit()
