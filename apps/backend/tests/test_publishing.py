"""T-033 — publishing a project: a licence, an explicit content check, and a way back.

This is the switch that puts media on the internet, so every refusal has its own sentence and
every call leaves exactly one audit row. Publishing and unpublishing never touch images, classes
or annotations; unpublishing just stops deriving a public address.
"""
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.db import SessionLocal
from app.main import app
from app.models import Audit, Image, Project, Workspace, WorkspaceFlag, set_annotations
from conftest import login

WS = "labeldesk-demo"
FLAG = "task_a1_publish"


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        client.headers.update(login(client))
        yield client


@pytest.fixture(scope="module", autouse=True)
def _own_plan_headroom():
    """The demo workspace's Free plan holds three projects, so this module gets its own seat and
    trashes what it created on the way out."""
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        before = ws.plan
        ws.plan = "pro"
        db.commit()
    yield
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        ws.plan = before
        db.execute(delete(WorkspaceFlag).where(WorkspaceFlag.key == FLAG))
        for p in db.scalars(select(Project).where(Project.workspace_id == ws.id,
                                                  Project.slug.like("publish-%"),
                                                  Project.deleted_at.is_(None))):
            p.deleted_at = time.time()
        db.commit()


def _set_flag(c: TestClient, enabled: bool) -> None:
    r = c.put(f"/api/ws/{WS}/flags/{FLAG}", json={"enabled": enabled})
    assert r.status_code == 200, r.text


@pytest.fixture(autouse=True)
def _flag_on(c):
    """The surface is behind `task_a1_publish`; the flag-off test flips it for one request."""
    _set_flag(c, True)
    yield
    _set_flag(c, True)


def _project(c: TestClient) -> dict:
    r = c.post(f"/api/ws/{WS}/projects", json={"name": f"Publish Check {uuid.uuid4().hex[:8]}"})
    assert r.status_code == 200, r.text
    return r.json()


def _get(c: TestClient, slug: str) -> dict:
    r = c.get(f"/api/ws/{WS}/projects/{slug}")
    assert r.status_code == 200, r.text
    return r.json()


def _publish(c: TestClient, slug: str, **body):
    return c.post(f"/api/ws/{WS}/projects/{slug}/publish", json=body)


def _audits(action: str, target: str) -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count(Audit.id)).where(Audit.action == action, Audit.target == target))


def _dataset(pid: str) -> tuple[int, int]:
    """(live images, annotations on them) — what publishing must never touch."""
    with SessionLocal() as db:
        imgs = db.scalars(select(Image).where(Image.project_id == pid, Image.deleted_at.is_(None))).all()
        return len(imgs), sum(len(i.annotations or []) for i in imgs)


def test_publish_sets_visibility_and_path(c):
    p = _project(c)

    r = _publish(c, p["slug"], license="CC BY 4.0", pii_ack=True)

    assert r.status_code == 200, r.text
    assert r.json() == {"visibility": "public", "license": "CC BY 4.0",
                        "publicPath": f"/d/{WS}/{p['slug']}"}
    assert _get(c, p["slug"])["publicPath"] == f"/d/{WS}/{p['slug']}"
    assert _audits("project.publish", p["name"]) == 1


def test_publish_without_ack_is_422(c):
    p = _project(c)

    r = _publish(c, p["slug"], license="CC BY 4.0")

    assert r.status_code == 422, r.text
    assert r.json()["detail"] == "Confirm the content check before publishing."
    # An explicit `false` is the same refusal as an absent field: the box has to be ticked.
    assert _publish(c, p["slug"], license="CC BY 4.0", pii_ack=False).status_code == 422
    assert _get(c, p["slug"])["visibility"] == "private"
    assert _audits("project.publish", p["name"]) == 0


def test_proprietary_licence_is_refused(c):
    p = _project(c)

    r = _publish(c, p["slug"], license="Proprietary", pii_ack=True)

    assert r.status_code == 422, r.text
    assert r.json()["detail"] == "Proprietary datasets cannot be published."
    assert _get(c, p["slug"])["visibility"] == "private"
    # Anything else outside the offered set — including an empty choice — gets its own sentence.
    for licence in ("All Rights Reserved", ""):
        r = _publish(c, p["slug"], license=licence, pii_ack=True)
        assert r.status_code == 422, r.text
        assert r.json()["detail"] == "Choose a licence for published data."


def test_unpublish_reverses_and_keeps_data(c):
    p = _project(c)
    with SessionLocal() as db:
        img = Image(project_id=p["id"], name="keep.jpg", sha256="0" * 64, width=64, height=48,
                    path="keep.jpg", thumb="keep.jpg", status="annotated")
        db.add(img)
        db.flush()
        set_annotations(db, img, [{"classId": "c1", "x": 1, "y": 2, "w": 3, "h": 4}])
        db.commit()
    before = _dataset(p["id"])
    assert before == (1, 1)

    assert _publish(c, p["slug"], license="CC0 1.0", pii_ack=True).status_code == 200
    assert _dataset(p["id"]) == before, "publishing changes no image and no annotation"

    r = c.post(f"/api/ws/{WS}/projects/{p['slug']}/unpublish")

    assert r.status_code == 200, r.text
    assert r.json() == {"visibility": "private", "license": "CC0 1.0", "publicPath": None}
    got = _get(c, p["slug"])
    assert (got["visibility"], got["publicPath"]) == ("private", None), "the address is gone at once"
    assert _dataset(p["id"]) == before, "unpublishing deletes nothing"
    assert _audits("project.unpublish", p["name"]) == 1


def test_labeler_cannot_publish(c):
    p = _project(c)
    labeler = TestClient(app)
    labeler.headers.update(login(labeler, "labeler@labeldesk.dev"))

    r = labeler.post(f"/api/ws/{WS}/projects/{p['slug']}/publish",
                     json={"license": "CC BY 4.0", "pii_ack": True})

    assert r.status_code == 403, r.text
    assert _get(c, p["slug"])["visibility"] == "private"
    assert _audits("project.publish", p["name"]) == 0


def test_foreign_project_is_404(c):
    """A foreign slug under our workspace is a 404 — and nothing is written anywhere."""
    other = TestClient(app)
    signup = other.post("/api/auth/signup", json={
        "name": "Publish Outsider",
        "email": f"publish-{uuid.uuid4().hex[:8]}@x.io",
        "password": "longenough1",
    }).json()
    headers = {"Authorization": f"Bearer {signup['token']}"}
    ws2 = other.get("/api/me", headers=headers).json()["workspaces"][0]["slug"]
    foreign = other.post(f"/api/ws/{ws2}/projects", json={"name": f"Foreign {uuid.uuid4().hex[:6]}"},
                         headers=headers).json()

    r = _publish(c, foreign["slug"], license="CC BY 4.0", pii_ack=True)

    assert r.status_code == 404, r.text
    assert _audits("project.publish", foreign["name"]) == 0
    theirs = other.get(f"/api/ws/{ws2}/projects/{foreign['slug']}", headers=headers).json()
    assert theirs["visibility"] == "private", "the other workspace's row is untouched"


def test_workspace_policy_blocks_publishing(c, monkeypatch):
    """7-F7.60 owns `workspaces.allow_public_projects`; until that card adds the column, the
    service reads it defensively, so the policy is simulated on the model class here."""
    p = _project(c)
    monkeypatch.setattr(Workspace, "allow_public_projects", False, raising=False)

    r = _publish(c, p["slug"], license="CC BY 4.0", pii_ack=True)

    assert r.status_code == 403, r.text
    assert r.json()["detail"] == "This workspace does not allow public projects."
    assert _get(c, p["slug"])["visibility"] == "private"
    assert _audits("project.publish", p["name"]) == 0


def test_flag_off_has_no_publish_route(c):
    p = _project(c)
    _set_flag(c, False)

    assert _publish(c, p["slug"], license="CC BY 4.0", pii_ack=True).status_code == 404
    assert c.post(f"/api/ws/{WS}/projects/{p['slug']}/unpublish").status_code == 404
    assert _get(c, p["slug"])["visibility"] == "private"
