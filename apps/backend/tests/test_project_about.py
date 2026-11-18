"""T-023 — the project description, and the public address derived from visibility.

One field, one editor: `projects.description`, capped at 600 characters, newlines kept, and a
`publicPath` that exists only while the project is public. The string is visitor-facing text as
soon as a project is public, so it round-trips as data — never as markup.
"""
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Project, Workspace
from conftest import login

WS = "labeldesk-demo"
TWO_PARAGRAPHS = ("Safety gear on a construction site: helmets, vests and gloves.\n\n"
                  "Shot on two sites in Chonburi; 1,284 images, one class per person and per item.")


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        client.headers.update(login(client))
        yield client


@pytest.fixture(scope="module", autouse=True)
def _own_project_headroom():
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
        for p in db.scalars(select(Project).where(Project.workspace_id == ws.id,
                                                  Project.slug.like("about-%"),
                                                  Project.deleted_at.is_(None))):
            p.deleted_at = time.time()
        db.commit()


@pytest.fixture(scope="module")
def project(c):
    name = f"About Check {uuid.uuid4().hex[:8]}"
    r = c.post(f"/api/ws/{WS}/projects", json={"name": name, "type": "object-detection"})
    assert r.status_code == 200, r.text
    return r.json()


def _get(c, slug):
    r = c.get(f"/api/ws/{WS}/projects/{slug}")
    assert r.status_code == 200, r.text
    return r.json()


def test_description_round_trips_with_newlines(c, project):
    r = c.patch(f"/api/ws/{WS}/projects/{project['slug']}", json={"description": TWO_PARAGRAPHS})

    assert r.status_code == 200, r.text
    assert r.json()["description"] == TWO_PARAGRAPHS
    # The paragraphs survive the database round trip, not just the PATCH response.
    assert _get(c, project["slug"])["description"] == TWO_PARAGRAPHS


def test_description_over_600_is_refused(c, project):
    slug = project["slug"]
    assert c.patch(f"/api/ws/{WS}/projects/{slug}", json={"description": "kept"}).status_code == 200

    r = c.patch(f"/api/ws/{WS}/projects/{slug}", json={"description": "x" * 601})

    assert r.status_code == 422, r.text
    assert _get(c, slug)["description"] == "kept"
    # 600 itself is allowed: the cap is a limit, not a fencepost error.
    assert c.patch(f"/api/ws/{WS}/projects/{slug}", json={"description": "y" * 600}).status_code == 200


def test_public_path_only_when_public(c, project):
    slug = project["slug"]
    assert c.patch(f"/api/ws/{WS}/projects/{slug}", json={"visibility": "private"}).status_code == 200
    assert _get(c, slug)["publicPath"] is None

    r = c.patch(f"/api/ws/{WS}/projects/{slug}", json={"visibility": "public"})

    assert r.status_code == 200, r.text
    assert r.json()["publicPath"] == f"/d/{WS}/{slug}"
    assert _get(c, slug)["publicPath"] == f"/d/{WS}/{slug}"

    # Back to private: the derived address disappears with it; nothing was stored in between.
    c.patch(f"/api/ws/{WS}/projects/{slug}", json={"visibility": "private"})
    assert _get(c, slug)["publicPath"] is None


def test_labeler_cannot_edit_the_description(c, project):
    slug = project["slug"]
    assert c.patch(f"/api/ws/{WS}/projects/{slug}", json={"description": "manager wrote this"}).status_code == 200

    labeler = TestClient(app)
    labeler.headers.update(login(labeler, "labeler@labeldesk.dev"))
    r = labeler.patch(f"/api/ws/{WS}/projects/{slug}", json={"description": "labeler rewrote it"})

    assert r.status_code == 403, r.text
    assert _get(c, slug)["description"] == "manager wrote this"


def test_description_from_another_workspace_is_404(c):
    """A foreign slug under our workspace is a 404 — and the other workspace's row is untouched."""
    other = TestClient(app)
    signup = other.post("/api/auth/signup", json={
        "name": "About Outsider",
        "email": f"about-{uuid.uuid4().hex[:8]}@x.io",
        "password": "longenough1",
    }).json()
    headers = {"Authorization": f"Bearer {signup['token']}"}
    ws2 = other.get("/api/me", headers=headers).json()["workspaces"][0]["slug"]
    foreign = other.post(f"/api/ws/{ws2}/projects", json={"name": f"Foreign {uuid.uuid4().hex[:6]}"},
                         headers=headers).json()
    theirs = f"/api/ws/{ws2}/projects/{foreign['slug']}"
    assert other.patch(theirs, json={"description": "theirs"}, headers=headers).status_code == 200

    r = c.patch(f"/api/ws/{WS}/projects/{foreign['slug']}", json={"description": "hijacked"})

    assert r.status_code == 404, r.text
    assert other.get(theirs, headers=headers).json()["description"] == "theirs"


def test_description_is_not_html_rendered(c, project):
    slug = project["slug"]
    markup = "<b>x</b><script>alert(1)</script>"

    r = c.patch(f"/api/ws/{WS}/projects/{slug}", json={"description": markup})

    assert r.status_code == 200, r.text
    assert r.json()["description"] == markup
    got = c.get(f"/api/ws/{WS}/projects/{slug}")
    assert got.json()["description"] == markup, "the string is data, returned unchanged"
    assert got.headers["content-type"].startswith("application/json"), "no HTML content type"
