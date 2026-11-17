"""T-1104 V1/V2 — a project name is not a unique key in a workspace.

The dialog shows the address a name will take, so the browser's slug rule and this one must agree.
A duplicate is refused in place with the taken address and a free one; nothing is stored under
`<slug>-2` behind the buyer's back.
"""
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Project, Workspace
from app.routers.projects import slugify
from conftest import login

WS = "labeldesk-demo"

# Mirrors apps/frontend/tests/slug.test.mjs: both sides assert this table, so the two rules cannot
# drift apart without a red test.
SLUG_CASES = [
    ("Hardhat Detection", "hardhat-detection"),
    ("PPE — ตรวจสอบ หมวกกันน็อค!", "ppe"),
    ("ซอย 5 (ทดสอบ)", "5"),
    ("  Lots   of   SPACE  ", "lots-of-space"),
    ("Settings", "settings-project"),
]


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        client.headers.update(login(client))
        yield client


@pytest.fixture(scope="module", autouse=True)
def _own_project_headroom():
    """The demo workspace's Free plan holds three projects, so it cannot fit this module's own.
    The plan goes back and the projects this module created are trashed on the way out, so the
    modules that follow still have the seats they expect."""
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
                                                  Project.slug.like("address-%"),
                                                  Project.deleted_at.is_(None))):
            p.deleted_at = time.time()
        db.commit()


@pytest.mark.parametrize("name,expected", SLUG_CASES)
def test_the_dialog_preview_table_is_the_server_slug_rule(name, expected):
    assert slugify(name) == expected


def test_duplicate_name_is_refused_with_the_taken_address_and_a_free_one(c):
    name = f"Address Check {uuid.uuid4().hex[:8]}"
    first = c.post(f"/api/ws/{WS}/projects", json={"name": name, "type": "object-detection"})
    assert first.status_code == 200, first.text
    slug = first.json()["slug"]
    before = len(c.get(f"/api/ws/{WS}/projects").json())

    again = c.post(f"/api/ws/{WS}/projects", json={"name": name, "type": "object-detection"})

    assert again.status_code == 409, again.text
    body = again.json()["detail"]
    assert body["taken"] == f"/{WS}/p/{slug}"
    assert body["suggestion"] == f"/{WS}/p/{slug}-2"
    # No second project, and the suggested address is genuinely free.
    assert len(c.get(f"/api/ws/{WS}/projects").json()) == before
    assert c.get(f"/api/ws/{WS}/projects/{slug}-2").status_code == 404


def test_the_refusal_survives_a_trashed_project(c):
    """A soft-deleted project still owns its address, so the refusal cannot be skipped by deleting."""
    name = f"Address Trashed {uuid.uuid4().hex[:8]}"
    first = c.post(f"/api/ws/{WS}/projects", json={"name": name, "type": "object-detection"})
    assert first.status_code == 200, first.text
    slug = first.json()["slug"]
    assert c.delete(f"/api/ws/{WS}/projects/{slug}").status_code == 200

    again = c.post(f"/api/ws/{WS}/projects", json={"name": name, "type": "object-detection"})

    assert again.status_code == 409, again.text
    assert again.json()["detail"]["taken"] == f"/{WS}/p/{slug}"


def test_the_same_name_is_free_in_another_workspace(c):
    """The refusal is scoped to the workspace, like every other project lookup."""
    name = f"Address Isolation {uuid.uuid4().hex[:8]}"
    assert c.post(f"/api/ws/{WS}/projects", json={"name": name}).status_code == 200

    other = TestClient(app)
    signup = other.post("/api/auth/signup", json={
        "name": "Address Outsider",
        "email": f"addr-{uuid.uuid4().hex[:8]}@x.io",
        "password": "longenough1",
    }).json()
    headers = {"Authorization": f"Bearer {signup['token']}"}
    ws2 = other.get("/api/me", headers=headers).json()["workspaces"][0]["slug"]

    created = other.post(f"/api/ws/{ws2}/projects", json={"name": name}, headers=headers)

    assert created.status_code == 200, created.text
    assert created.json()["slug"] == slugify(name)
