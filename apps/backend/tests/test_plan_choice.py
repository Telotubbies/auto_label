"""T-011 + T-1111: the plan is offered on the creation form, requested on the workspace row.

A choice is a *request*: every workspace starts on Free (or the trial tier when the plan table
defines one), because no billing provider is wired. The requested tier is recorded for Settings →
Plan, which shows it without applying it. The catalogue route carries the limits the picker
prints — no tenant data, no price, because no price has been set.
"""
import os
import re
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import PLANS
from app.main import app
from app.routers import auth as auth_router
from conftest import login

FLAG = "task_a1_plan_choice"
# What the server may grant at creation: Free, or Trial when the plan table grows one.
START_PLAN = "trial" if "trial" in PLANS else "free"


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


def test_paid_choice_is_recorded_not_granted(c, flag_on):
    created = c.post("/api/workspaces", json={"name": _name("Pro Shop"), "plan": "pro"})
    assert created.status_code == 200
    slug = created.json()["slug"]

    usage = c.get(f"/api/ws/{slug}").json()["usage"]
    assert usage["plan"] == START_PLAN               # the paid tier was not granted
    assert usage["credits_left"] == PLANS[START_PLAN]["credits"]
    assert usage["requested_plan"] == "pro"          # the request was recorded


def test_signup_records_the_paid_choice_without_granting_it(flag_on):
    email = f"plan-{uuid.uuid4().hex[:8]}@labeldesk.dev"
    with TestClient(app) as anon:
        made = anon.post("/api/auth/signup", json={
            "name": "Plan Buyer", "email": email, "password": "longenough1",
            "workspace": _name("Signup Shop"), "plan": "pro",
        })
        assert made.status_code == 200
        anon.headers.update({"Authorization": f"Bearer {made.json()['token']}"})
        ws = anon.get("/api/me").json()["workspaces"][0]
        usage = anon.get(f"/api/ws/{ws['slug']}").json()["usage"]

    assert usage["plan"] == START_PLAN
    assert usage["requested_plan"] == "pro"


def test_every_plan_in_the_table_is_only_a_request(c, flag_on):
    """No tier in PLANS is grantable through creation, whatever its id."""
    for tier in PLANS:
        created = c.post("/api/workspaces", json={"name": _name(tier), "plan": tier})
        assert created.status_code == 200
        usage = c.get(f"/api/ws/{created.json()['slug']}").json()["usage"]
        assert usage["plan"] == START_PLAN
        assert usage["requested_plan"] == tier


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
    assert usage["plan"] == START_PLAN
    assert usage.get("requested_plan") is None          # a flag-off deployment records nothing
    assert usage["credits_left"] == PLANS[START_PLAN]["credits"]


def test_the_router_never_returns_the_chosen_tier_as_the_plan():
    """The T-011 defect: the requested tier became the workspace's granted plan."""
    src = Path(auth_router.__file__).read_text(encoding="utf-8")
    assert "plan=START_PLAN" in src, "creation always grants the start tier"
    assert "requested_plan=requested" in src, "the request is recorded on its own field"
    granted = re.search(r"(?<![\w])plan=(requested|chosen)", src)
    assert granted is None, "a requested tier must never become the granted tier"


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
    """Creation records the request; moving the granted tier stays a platform-operator action."""
    moved = c.patch("/api/ws/labeldesk-demo", json={"plan": "enterprise"})
    assert moved.status_code == 403
    assert c.get("/api/ws/labeldesk-demo").json()["usage"]["plan"] == "free"

    # A workspace the caller is not in stays a 404, never a 403 that would confirm it exists.
    assert c.patch("/api/ws/not-a-workspace-i-belong-to", json={"plan": "enterprise"}).status_code == 404
