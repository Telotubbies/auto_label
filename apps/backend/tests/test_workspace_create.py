"""T-010: a person names the workspace and sees its address before submit.

The slug check is bearer-only and answers with availability plus one suggestion; it never
returns another workspace's name or id. The address is derived with the same rule the browser
mirrors in `apps/frontend/src/lib/slug.ts`.
"""
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from conftest import login

FLAG = "task_a1_workspace_create"


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
    """The surface is process-wide: signup has no workspace to hold a per-workspace override."""
    keys = [k for k in os.environ.get("LD_FLAGS_ON", "").split(",") if k]
    if FLAG not in keys:
        keys.append(FLAG)
    monkeypatch.setenv("LD_FLAGS_ON", ",".join(keys))


def test_slug_is_derived_unique_and_lowercase(c, flag_on):
    first = c.post("/api/workspaces", json={"name": "Acme Labs"})
    assert first.status_code == 200
    assert first.json()["slug"] == "acme-labs"

    second = c.post("/api/workspaces", json={"name": "Acme Labs"})
    assert second.status_code == 200
    assert second.json()["slug"] == "acme-labs-2"


def test_slug_check_reports_taken_with_one_suggestion(c, flag_on):
    r = c.get("/api/workspaces/slug", params={"name": "LabelDesk Demo"})
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == "labeldesk-demo"
    assert body["available"] is False
    assert body["suggestion"] == "labeldesk-demo-2"
    # Availability only: no workspace name, id, owner or plan.
    assert set(body) == {"slug", "available", "suggestion"}


def test_reserved_and_malformed_slug_are_refused(c, flag_on):
    reserved = c.post("/api/workspaces", json={"name": "Settings Co", "slug": "settings"})
    assert reserved.status_code == 422

    too_short = c.post("/api/workspaces", json={"name": "A Co", "slug": "a"})
    assert too_short.status_code == 422

    # The same rule guards the preview: a one-letter name has no valid address.
    assert c.get("/api/workspaces/slug", params={"name": "A"}).status_code == 422


def test_slug_check_requires_a_session(flag_on):
    with TestClient(app) as anon:
        assert anon.get("/api/workspaces/slug", params={"name": "acme"}).status_code == 401


def test_flag_off_keeps_derived_name(c, monkeypatch):
    monkeypatch.delenv("LD_FLAGS_ON", raising=False)
    assert c.get("/api/workspaces/slug", params={"name": "acme"}).status_code == 404

    name = f"Quiet Lane {uuid.uuid4().hex[:8]}"
    created = c.post("/api/workspaces", json={"name": name, "slug": "chosen-address"})
    assert created.status_code == 200
    assert created.json()["slug"] != "chosen-address"
    assert created.json()["slug"].startswith("quiet-lane-")
