"""Developer API actions: start auto-label, build a version, list deployments, infer by image id.

The routes are thin delegations, so these tests prove the delegated paths answer for a key-built
`Ctx` (no user), keep the key's scope checks and stay inside the key's workspace.
"""
import io
import os
import time
import uuid

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import select

from app.adapters import ADAPTERS, Availability
from app.db import SessionLocal
from app.main import app
from app.models import Image, Job, Member, Project, TrainedModel, User, Version, Workspace
from app.security import issue_access
from conftest import login

WS = "labeldesk-demo"


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        client.headers.update(login(client))
        yield client


def anon() -> TestClient:
    return TestClient(app)


def _usage(c) -> float:
    return c.get(f"/api/ws/{WS}/usage").json()["credits_used"]


def jpeg(color=(90, 120, 150)) -> bytes:
    b = io.BytesIO()
    PImage.new("RGB", (96, 96), color).save(b, "JPEG")
    return b.getvalue()


@pytest.fixture(scope="module", autouse=True)
def fresh_credits():
    """Start at zero and put the demo counter back, so this module neither needs nor spends the
    allowance earlier modules earned. The 402 case sets its own value and restores it."""
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        saved = ws.credits_used
        ws.credits_used = 0.0
        db.commit()
    yield
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        ws.credits_used = saved
        db.commit()


# --- fakes ---------------------------------------------------------------------------------

class FakeDetector:
    """The auto-label/predict adapter double from test_autolabel_v2.py: one person box."""

    family = "ultralytics"

    def probe(self):
        return Availability(True)

    def capabilities(self, variant):
        return {"detect"}

    def predict(self, variant, im, *, classes=None, prompt=None, weights=None, conf=0.4, iou=0.5):
        return {"predictions": [{"class": "person", "class_id": 0, "confidence": 0.9, "x": 48.0,
                                 "y": 48.0, "width": 24.0, "height": 24.0}],
                "time": 0.0, "image": {"width": im.width, "height": im.height}}


# --- fixtures ------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def scratch(c):
    """A throwaway project with three unannotated images and one ready model."""
    name = f"devapi-actions-{uuid.uuid4().hex[:8]}"
    p = c.post(f"/api/ws/{WS}/projects", json={"name": name, "type": "object-detection",
                                               "classes": ["person"]}).json()
    base = f"/api/ws/{WS}/projects/{p['slug']}"
    up = c.post(f"{base}/upload", files=[("files", (f"act-{i}.jpg", jpeg((10 + i * 40, 60, 90))))
                                         for i in range(3)],
                data={"split": "train", "batch_name": "devapi actions"})
    assert up.status_code == 200 and up.json()["uploaded"] == 3, up.text
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        v = Version(project_id=p["id"], number=1, name="actions")
        db.add(v)
        db.flush()
        m = TrainedModel(workspace_id=ws.id, project_id=p["id"], version_id=v.id, name="actions model",
                         arch="yolo26n", task="detect", status="ready", family="ultralytics",
                         variant="yolo26n")
        db.add(m)
        db.commit()
        mid, vid = m.id, v.id
    yield {"id": p["id"], "slug": p["slug"], "base": base, "model_id": mid, "version_id": vid,
           "images": [x["id"] for x in up.json()["images"]]}
    c.delete(base)
    with SessionLocal() as db:
        db.delete(db.get(TrainedModel, mid))
        db.delete(db.get(Version, vid))
        db.commit()


def make_key(c, name: str, scopes: list[str]) -> dict:
    r = c.post(f"/api/ws/{WS}/keys", json={"name": name, "scopes": scopes})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['key']}"}


@pytest.fixture(scope="module")
def keys(c):
    read = make_key(c, "actions-read", ["read"])
    write = make_key(c, "actions-write", ["read", "write"])
    infer = make_key(c, "actions-infer", ["infer"])
    yield {"read": read, "write": write, "infer": infer}
    for kid in c.get(f"/api/ws/{WS}/keys").json():
        if kid["name"].startswith("actions-"):
            c.delete(f"/api/ws/{WS}/keys/{kid['id']}")


@pytest.fixture(scope="module")
def other():
    """Workspace B: one project, one image and one job whose ids must never cross over."""
    tag = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        u = User(email=f"devapi-b-{tag}@test.local", name="B", pw_hash="", email_verified=time.time())
        db.add(u)
        db.flush()
        ws = Workspace(slug=f"devapi-b-{tag}", name="B", owner_id=u.id)
        db.add(ws)
        db.flush()
        db.add(Member(workspace_id=ws.id, user_id=u.id, role="admin"))
        p = Project(workspace_id=ws.id, slug="foreign", name="Foreign", settings={})
        db.add(p)
        db.flush()
        img = Image(project_id=p.id, name="x.jpg", sha256=uuid.uuid4().hex * 2, width=10, height=10,
                    path="x.jpg", thumb="x.jpg")
        j = Job(workspace_id=ws.id, project_id=p.id, kind="version", params={})
        db.add_all([img, j])
        db.commit()
        uid, ws_id, ws_slug, pid, img_id, job_id = u.id, ws.id, ws.slug, p.id, img.id, j.id
    headers = {"Authorization": f"Bearer {issue_access(uid)}"}
    r = anon().post(f"/api/ws/{ws_slug}/keys", headers=headers, json={"name": "b-read", "scopes": ["read"]})
    assert r.status_code == 200, r.text
    yield {"ws_id": ws_id, "ws_slug": ws_slug, "image_id": img_id, "job_id": job_id,
           "key": {"Authorization": f"Bearer {r.json()['key']}"}}
    with SessionLocal() as db:
        db.query(Job).filter(Job.workspace_id == ws_id).delete()
        db.query(Image).filter(Image.project_id == pid).delete()
        db.query(Project).filter(Project.id == pid).delete()
        db.query(Member).filter(Member.workspace_id == ws_id).delete()
        db.query(Workspace).filter(Workspace.id == ws_id).delete()
        db.query(User).filter(User.id == uid).delete()
        db.commit()


def wait_api_job(headers: dict, jid: str, timeout: float = 90) -> dict:
    t = time.time()
    while time.time() - t < timeout:
        j = anon().get(f"/api/v1/jobs/{jid}", headers=headers)
        assert j.status_code == 200, j.text
        body = j.json()
        if body["status"] in ("done", "failed", "cancelled"):
            return body
        time.sleep(0.25)
    raise TimeoutError(jid)


# --- create a version ----------------------------------------------------------------------

def test_create_version_queues_a_job_and_charges_half_a_credit(c, scratch, keys):
    before = _usage(c)
    r = anon().post(f"/api/v1/projects/{scratch['slug']}/versions", headers=keys["write"],
                    json={"name": "agent build"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] in ("queued", "generating"), body
    assert body["job"] and body["job"]["id"], body
    assert _usage(c) - before == pytest.approx(0.5)
    with SessionLocal() as db:
        v = db.get(Version, body["id"])
        assert v is not None and v.created_by is None, "a key-built Ctx has no user, not a crash"


def test_create_version_is_402_when_the_credits_are_gone(c, scratch, keys):
    from app.config import PLANS

    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        saved, saved_period = ws.credits_used, ws.credits_period
        ws.credits_used = PLANS[ws.plan]["credits"]
        ws.credits_period = time.strftime("%Y-%m")
        db.commit()
    try:
        r = anon().post(f"/api/v1/projects/{scratch['slug']}/versions", headers=keys["write"],
                        json={"name": "too much"})
        assert r.status_code == 402, r.text
        assert PLANS["free"]["label"] in r.json()["detail"]
    finally:
        with SessionLocal() as db:
            ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
            ws.credits_used, ws.credits_period = saved, saved_period
            db.commit()


# --- auto-label ----------------------------------------------------------------------------

def test_autolabel_needs_a_model_or_a_prompt(scratch, keys):
    r = anon().post(f"/api/v1/projects/{scratch['slug']}/autolabel", headers=keys["write"], json={})
    assert r.status_code == 400
    assert "choose a trained model" in r.json()["detail"]


def test_autolabel_queues_a_job_and_completes_with_the_fake_detector(c, scratch, keys, monkeypatch):
    monkeypatch.setitem(ADAPTERS, "ultralytics", FakeDetector())
    ids = scratch["images"][:2]
    r = anon().post(f"/api/v1/projects/{scratch['slug']}/autolabel", headers=keys["write"],
                    json={"method": "model", "model_ref": f"trained:{scratch['model_id']}",
                          "image_ids": ids})
    assert r.status_code == 200, r.text
    job = wait_api_job(keys["write"], r.json()["id"])
    assert job["status"] == "done", job
    for image_id in ids:
        got = c.get(f"/api/images/{image_id}").json()
        assert got["annotations"], got
        assert all(a["source"] == f"trained:{scratch['model_id']}" for a in got["annotations"]), got


def test_autolabel_requires_the_write_scope(c, scratch, keys):
    limited = make_key(c, "actions-read-train", ["read", "train"])
    r = anon().post(f"/api/v1/projects/{scratch['slug']}/autolabel", headers=limited, json={})
    assert r.status_code == 403
    assert "'write'" in r.json()["detail"]


# --- infer by stored image -----------------------------------------------------------------

def test_predict_accepts_a_stored_image_id(c, scratch, keys, monkeypatch):
    monkeypatch.setitem(ADAPTERS, "ultralytics", FakeDetector())
    before = _usage(c)
    r = anon().post(f"/api/v1/models/{scratch['model_id']}/predict", headers=keys["infer"],
                    params={"image_id": scratch["images"][0]})
    assert r.status_code == 200, r.text
    assert r.json()["predictions"], r.json()
    assert _usage(c) - before == pytest.approx(0.001)


def test_predict_refuses_a_foreign_image_id(c, scratch, keys, other):
    before = _usage(c)
    r = anon().post(f"/api/v1/models/{scratch['model_id']}/predict", headers=keys["infer"],
                    params={"image_id": other["image_id"]})
    assert r.status_code == 404
    assert r.json()["detail"] == "image not found"
    assert _usage(c) == before, "a refused image must not be billed"


# --- deployments and jobs ------------------------------------------------------------------

def test_list_deployments_is_scoped_to_the_key_workspace(c, scratch, keys, other):
    up = c.put(f"{scratch['base']}/deployments/production", json={"model_id": scratch["model_id"]})
    assert up.status_code == 200, up.text

    mine = anon().get("/api/v1/deployments", headers=keys["read"])
    assert mine.status_code == 200
    project = next(p for p in mine.json()["projects"] if p["slug"] == scratch["slug"])
    alias = project["aliases"][0]
    assert alias["alias"] == "production" and alias["model_id"] == scratch["model_id"]
    assert "weights" not in project["ready_models"][0]

    theirs = anon().get("/api/v1/deployments", headers=other["key"])
    assert theirs.status_code == 200
    assert scratch["slug"] not in {p["slug"] for p in theirs.json()["projects"]}


def test_get_job_of_another_workspace_is_404(keys, other):
    r = anon().get(f"/api/v1/jobs/{other['job_id']}", headers=keys["read"])
    assert r.status_code == 404
    assert r.json()["detail"] == "job not found"
