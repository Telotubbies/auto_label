"""No-code workflows: block validation, versioned saves and restore, tenant isolation, flag gate."""

import os
import tempfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-workflows-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import delete, select

from app.config import DATA_DIR
from app.db import SessionLocal
from app.main import app
from app.models import Image, Member, Project, User, Workflow, WorkflowVersion, Workspace
from app.security import issue_access
from app.services import workflow_runner

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/ws/{WS}/projects/{PR}/workflows"

BLOCKS = [
    {"type": "model", "model_ref": "trained:abc", "conf": 0.4, "classes": []},
    {"type": "sink", "kind": "response"},
]


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
        c.headers["Authorization"] = f"Bearer {issue_access(user.id)}"
        yield c


@pytest.fixture(scope="module")
def labeler_client():
    with TestClient(app) as c:
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == "labeler@labeldesk.dev"))
        c.headers["Authorization"] = f"Bearer {issue_access(user.id)}"
        yield c


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setenv("LD_FLAGS_ON", "task_31")
    with SessionLocal() as db:
        db.execute(delete(WorkflowVersion))
        db.execute(delete(Workflow))
        db.commit()
    yield
    with SessionLocal() as db:
        db.execute(delete(WorkflowVersion))
        db.execute(delete(Workflow))
        db.commit()


def _create(client, name="Inspect line", blocks=None):
    r = client.post(BASE, json={"name": name, "blocks": blocks or BLOCKS})
    assert r.status_code == 200, r.text
    return r.json()


def test_flag_off_hides_every_workflow_route(client, monkeypatch):
    wid = _create(client)["id"]
    monkeypatch.delenv("LD_FLAGS_ON")
    assert client.get(BASE).status_code == 404
    assert client.post(BASE, json={"name": "x", "blocks": BLOCKS}).status_code == 404
    assert client.get(f"{BASE}/{wid}").status_code == 404
    assert client.put(f"{BASE}/{wid}", json={"name": "x"}).status_code == 404
    assert client.get(f"{BASE}/{wid}/versions").status_code == 404
    assert client.post(f"{BASE}/{wid}/restore", json={"version": 1}).status_code == 404
    assert client.post(f"{BASE}/{wid}/run", json={"image_id": "missing"}).status_code == 404


def test_create_defaults_to_version_one_and_lists(client):
    w = _create(client)
    assert w["version"] == 1 and w["name"] == "Inspect line" and w["blocks"] == BLOCKS
    rows = client.get(BASE).json()
    assert [r["id"] for r in rows] == [w["id"]]
    with SessionLocal() as db:
        snap = db.scalar(select(WorkflowVersion).where(WorkflowVersion.workflow_id == w["id"]))
        assert snap.number == 1 and snap.blocks == BLOCKS


@pytest.mark.parametrize("blocks,message", [
    ([], "at least one block"),
    ([{"type": "teleport"}], "unknown block type"),
    ([{"type": "model", "model_ref": ""}, {"type": "sink", "kind": "response"}], "model_ref"),
    ([{"type": "model", "model_ref": "trained:a"}, {"type": "sink", "kind": "response"},
      {"type": "sink", "kind": "response"}], "exactly one sink"),
    ([{"type": "sink", "kind": "response"}, {"type": "model", "model_ref": "trained:a"}], "sink block must be last"),
    ([{"type": "filter", "classes": []}, {"type": "sink", "kind": "response"}], "model or OCR block"),
])
def test_block_validation(client, blocks, message):
    r = client.post(BASE, json={"name": "bad", "blocks": blocks})
    assert r.status_code == 400, r.text
    assert message in r.json()["detail"]


def test_saving_blocks_creates_a_version_and_name_only_does_not(client):
    w = _create(client)
    changed = [*BLOCKS[:-1], {"type": "sink", "kind": "annotations"}]
    r = client.put(f"{BASE}/{w['id']}", json={"blocks": changed})
    assert r.status_code == 200, r.text
    assert r.json()["version"] == 2
    r = client.put(f"{BASE}/{w['id']}", json={"name": "Renamed"})
    assert r.json()["version"] == 2 and r.json()["name"] == "Renamed"
    versions = client.get(f"{BASE}/{w['id']}/versions").json()
    assert [v["number"] for v in versions] == [2, 1]
    assert versions[0]["blocks"] == changed and versions[1]["blocks"] == BLOCKS


def test_restore_copies_an_old_snapshot_into_a_new_version(client):
    w = _create(client)
    changed = [*BLOCKS[:-1], {"type": "sink", "kind": "annotations"}]
    assert client.put(f"{BASE}/{w['id']}", json={"blocks": changed}).status_code == 200
    r = client.post(f"{BASE}/{w['id']}/restore", json={"version": 1})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["version"] == 3 and body["blocks"] == BLOCKS
    versions = client.get(f"{BASE}/{w['id']}/versions").json()
    assert versions[0]["number"] == 3 and versions[0]["note"] == "restored from v1"


def test_restore_unknown_version_is_400(client):
    w = _create(client)
    r = client.post(f"{BASE}/{w['id']}/restore", json={"version": 9})
    assert r.status_code == 400


def test_duplicate_name_is_409(client):
    _create(client)
    r = client.post(BASE, json={"name": "Inspect line", "blocks": BLOCKS})
    assert r.status_code == 409


def test_a_labeler_can_read_but_not_write_workflows(client, labeler_client):
    w = _create(client)
    assert labeler_client.get(BASE).status_code == 200
    assert labeler_client.get(f"{BASE}/{w['id']}").status_code == 200
    assert labeler_client.post(BASE, json={"name": "nope", "blocks": BLOCKS}).status_code == 403
    assert labeler_client.put(f"{BASE}/{w['id']}", json={"name": "nope"}).status_code == 403
    assert labeler_client.post(f"{BASE}/{w['id']}/restore", json={"version": 1}).status_code == 403


def test_workflow_is_invisible_from_another_workspace(client):
    w = _create(client)
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
        other = Workspace(slug="workflow-other", name="Other", owner_id=owner.id)
        db.add(other)
        db.flush()
        p = Project(workspace_id=other.id, slug="other", name="Other", type="object-detection",
                    annotation_group="x", settings={})
        db.add(p)
        db.add(Member(workspace_id=other.id, user_id=owner.id, role="owner"))
        db.commit()
        other_id, other_pid = other.id, p.id
    try:
        base = "/api/ws/workflow-other/projects/other/workflows"
        assert client.get(base).json() == []
        assert client.get(f"{base}/{w['id']}").status_code == 404
        assert client.put(f"{base}/{w['id']}", json={"name": "pwn"}).status_code == 404
        assert client.post(f"{base}/{w['id']}/restore", json={"version": 1}).status_code == 404
        assert client.post(f"{base}/{w['id']}/run", json={"image_id": "missing"}).status_code == 404
    finally:
        with SessionLocal() as db:
            db.execute(delete(WorkflowVersion).where(WorkflowVersion.workflow_id == w["id"]))
            db.execute(delete(Workflow))
            db.execute(delete(Project).where(Project.id == other_pid))
            db.execute(delete(Member).where(Member.workspace_id == other_id))
            db.execute(delete(Workspace).where(Workspace.id == other_id))
            db.commit()


def _image_row() -> str:
    rel = "workflow-api/frame.jpg"
    path = DATA_DIR / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    PImage.new("RGB", (80, 60)).save(path, "JPEG")
    with SessionLocal() as db:
        project = db.scalar(select(Project).where(Project.slug == PR))
        row = Image(project_id=project.id, name="frame.jpg", sha256="1" * 64, width=80, height=60,
                    path=rel, thumb=rel, size=10)
        db.add(row)
        db.commit()
        return row.id


def test_run_executes_the_pipeline_on_a_project_image(client, monkeypatch):
    wid = _create(client)["id"]
    image_id = _image_row()

    class Fake:
        def predict(self, im, **kw):
            return {"model": "trained:abc", "time": 0, "image": {"width": im.width, "height": im.height},
                    "predictions": [{"class": "person", "class_id": 0, "confidence": 0.91,
                                     "x": im.width / 2, "y": im.height / 2,
                                     "width": im.width / 4, "height": im.height / 4}]}

    monkeypatch.setattr(workflow_runner, "resolve", lambda ref, db, *, workspace_id=None: Fake())
    try:
        r = client.post(f"{BASE}/{wid}/run", json={"image_id": image_id})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["workflow"] == wid and body["version"] == 1
        assert [d["class"] for d in body["detections"]] == ["person"]
        assert body["detections"][0]["x"] == pytest.approx(0.375)
    finally:
        with SessionLocal() as db:
            db.execute(delete(Image).where(Image.id == image_id))
            db.commit()


def test_run_rejects_an_image_from_another_project(client):
    wid = _create(client)["id"]
    r = client.post(f"{BASE}/{wid}/run", json={"image_id": "missing"})
    assert r.status_code == 404


def test_run_maps_a_bad_model_ref_to_400(client):
    w = _create(client, blocks=[{"type": "model", "model_ref": "trained:missing"},
                                {"type": "sink", "kind": "response"}])
    image_id = _image_row()
    try:
        r = client.post(f"{BASE}/{w['id']}/run", json={"image_id": image_id})
        assert r.status_code == 400
        assert "unknown trained model" in r.json()["detail"]
    finally:
        with SessionLocal() as db:
            db.execute(delete(Image).where(Image.id == image_id))
            db.commit()


def test_run_maps_an_unreachable_model_to_503(client, monkeypatch):
    wid = _create(client)["id"]
    image_id = _image_row()

    def boom(ref, db, *, workspace_id=None):
        raise RuntimeError("vLLM not reachable")

    monkeypatch.setattr(workflow_runner, "resolve", boom)
    try:
        r = client.post(f"{BASE}/{wid}/run", json={"image_id": image_id})
        assert r.status_code == 503
        assert r.json()["detail"] == "model unavailable"
    finally:
        with SessionLocal() as db:
            db.execute(delete(Image).where(Image.id == image_id))
            db.commit()
