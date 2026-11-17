"""T-011: the plan is offered on the creation form and stored on the workspace row.

The choice is creation-time only: `POST /api/workspaces` (and signup) honour it while
`task_a1_plan_choice` is on, and ignore it otherwise. The catalogue route carries the limits
the picker prints — no tenant data, no price, because no price has been set.
"""
import os
import re
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from conftest import login

FLAG = "task_a1_plan_choice"


@pytest.fixture(scope="module", autouse=True)
def _started():
    with TestClient(app):
        yield


@pytest.fixture
def c():
    with TestClient(app) as client:
        client.headers.update(login(client))
        yield client


@pytest.fixture
def flag_on(monkeypatch):
    """Creation-time surfaces are process-wide: no workspace exists yet to hold a row."""
    keys = [k for k in os.environ.get("LD_FLAGS_ON", "").split(",") if k]
    if FLAG not in keys:
        keys.append(FLAG)
    monkeypatch.setenv("LD_FLAGS_ON", ",".join(keys))


def _name(prefix: str) -> str:
    return f"{prefix} {uuid.uuid4().hex[:8]}"


def test_plan_is_stored_when_flag_on(c, flag_on):
    created = c.post("/api/workspaces", json={"name": _name("Pro Shop"), "plan": "pro"})
    assert created.status_code == 200
    slug = created.json()["slug"]

    usage = c.get(f"/api/ws/{slug}").json()["usage"]
    assert usage["plan"] == "pro"
    assert usage["plan_label"] == "Pro"
    assert usage["credits_left"] == 500          # the Pro allowance, not the free 30


def test_unknown_plan_is_refused(c, flag_on):
    name = _name("No Plan")
    refused = c.post("/api/workspaces", json={"name": name, "plan": "unlimited"})
    assert refused.status_code == 422
    assert "unknown plan" in refused.json()["detail"]

    # Nothing was created behind the refusal.
    assert c.get(f"/api/ws/{name.lower().replace(' ', '-')}").status_code == 404


def test_flag_off_ignores_the_plan(c, monkeypatch):
    monkeypatch.delenv("LD_FLAGS_ON", raising=False)
    created = c.post("/api/workspaces", json={"name": _name("Quiet Shop"), "plan": "pro"})
    assert created.status_code == 200
    assert set(created.json()) == {"slug", "name"}      # the response is unchanged from today

    usage = c.get(f"/api/ws/{created.json()['slug']}").json()["usage"]
    assert usage["plan"] == "free"
    assert usage["credits_left"] == 30


def test_plan_route_is_flag_gated_and_tenant_free(c, flag_on, monkeypatch):
    plans = c.get("/api/workspaces/plans")
    assert plans.status_code == 200
    rows = plans.json()
    assert [row["id"] for row in rows] == ["free", "pro", "enterprise"]
    for row in rows:
        assert set(row) == {"id", "label", "projects", "credits", "seats"}
    assert rows[0]["projects"] == 3 and rows[0]["credits"] == 30

    # A signup page has no session yet, so the catalogue is public like /config; it names no
    # workspace and quotes no money.
    text = plans.text
    assert not re.search(r"[$\u0e3f]", text)
    assert not re.search(r"[0-9a-f]{32}", text)
    with TestClient(app) as anon:
        assert anon.get("/api/workspaces/plans").status_code == 200

    monkeypatch.delenv("LD_FLAGS_ON", raising=False)
    assert c.get("/api/workspaces/plans").status_code == 404


def test_an_admin_cannot_move_the_plan(c):
    """Creation writes the tier; moving it stays a platform-operator action."""
    moved = c.patch("/api/ws/labeldesk-demo", json={"plan": "enterprise"})
    assert moved.status_code == 403
    assert c.get("/api/ws/labeldesk-demo").json()["usage"]["plan"] == "free"

    # A workspace the caller is not in stays a 404, never a 403 that would confirm it exists.
    assert c.patch("/api/ws/not-a-workspace-i-belong-to", json={"plan": "enterprise"}).status_code == 404
