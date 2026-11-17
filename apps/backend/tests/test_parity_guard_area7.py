"""Parity guard, area 7: membership removal, usage limits, key lifecycle and first run.

Pins the shipped behaviour behind the HAVE rows of `docs/research/roboflow-parity/backlog/T-007.md`:
7-F7.7 (self-leave removes the member and keeps the workspace), 7-F7.15 (one usage read carrying the
plan, the plan ladder, projects, seats, credits and the four meters), 7-F7.26 (a key is revealed once
and the row keeps its prefix and last-used stamp), 7-F7.34 (a publishable key is inference-only) and
7-F7.57 (signup creates one admin workspace on the free plan).

Removal/leave revoking project roles (`test_rbac.py::test_removal_and_leaving_revoke_project_roles`),
scope sets, publishable enforcement and revocation (`test_api_keys_scopes.py`), the usage meters and
their daily series (`test_task25_integration.py::test_usage_endpoint_meters_are_present`), the slow
signup training path (`test_e2e.py::test_signup_creates_workspace`) and audit export
(`test_audit_log.py`) are already pinned, so this module does not repeat them.

Every key this module mints is revoked in the test that created it; no value is logged or written.
"""

import secrets
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.config import PLANS
from app.db import SessionLocal
from app.main import app
from app.models import API_SCOPES, Audit, Member, Project, RefreshToken, User, Workspace
from app.security import issue_access
from app.services import metering

WS = "parity-guard-area7"
FOREIGN_WS = "parity-guard-area7-foreign"
METERS = {"gpu_seconds", "stream_hours", "ai_calls", "storage_bytes"}


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def _user(db, email: str) -> User:
    u = User(email=email, name=email.split("@")[0], pw_hash="")
    db.add(u)
    return u


@pytest.fixture(scope="module")
def users(c):
    """One workspace to read, plus a second one whose rows must stay invisible."""
    with SessionLocal() as db:
        owner = _user(db, "area7-owner@test.local")
        outsider = _user(db, "area7-outsider@test.local")
        db.flush()
        ws = Workspace(slug=WS, name="Area 7 Guard", owner_id=owner.id)
        foreign = Workspace(slug=FOREIGN_WS, name="Area 7 Foreign", owner_id=outsider.id)
        db.add_all([ws, foreign])
        db.flush()
        db.add_all([
            Member(workspace_id=ws.id, user_id=owner.id, role="admin"),
            Member(workspace_id=foreign.id, user_id=outsider.id, role="admin"),
        ])
        db.commit()
        return {"owner": owner.id, "outsider": outsider.id}


def _headers(uid: str) -> dict:
    return {"Authorization": f"Bearer {issue_access(uid)}"}


def _ws_id(slug: str) -> str:
    with SessionLocal() as db:
        return db.scalar(select(Workspace.id).where(Workspace.slug == slug))


def _project(ws_slug: str, slug: str, *, deleted: bool = False) -> str:
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == ws_slug))
        p = Project(workspace_id=ws.id, slug=slug, name=slug, type="object-detection", settings={},
                    deleted_at=time.time() if deleted else None)
        db.add(p)
        db.flush()
        pid = p.id
        db.commit()
    return pid


# --- 7-F7.7: leaving on your own removes the member, not the workspace -------------------------

def test_a_self_leave_removes_the_member_and_keeps_the_workspace(c, users):
    """7-F7.7: DELETE on your own row answers 200, the membership goes, the workspace stays."""
    wid = _ws_id(WS)
    with SessionLocal() as db:
        leaver = _user(db, "area7-leaver@test.local")
        db.flush()
        db.add(Member(workspace_id=wid, user_id=leaver.id, role="member"))
        db.commit()
        uid = leaver.id

    member = _headers(uid)
    assert c.get(f"/api/ws/{WS}", headers=member).status_code == 200

    r = c.delete(f"/api/ws/{WS}/members/{uid}", headers=member)
    assert r.status_code == 200, r.text
    with SessionLocal() as db:
        assert db.get(Member, (wid, uid)) is None, "7-F7.7: the member row is gone"

    assert c.get(f"/api/ws/{WS}", headers=member).status_code == 403, \
        "7-F7.7: the leaver is no longer a member"
    assert c.get(f"/api/ws/{WS}", headers=_headers(users["owner"])).status_code == 200, \
        "7-F7.7: the workspace still answers for its owner"
    assert c.get(f"/api/ws/{WS}/home", headers=_headers(users["owner"])).status_code == 200


# --- 7-F7.15: one read carries the plan ladder, the counts and the meters ----------------------

def test_usage_reports_the_plan_limits_projects_seats_credits_and_meters(c, users):
    """7-F7.15: a fresh workspace reports zeros, its plan ladder and all four meters."""
    wid = _ws_id(WS)
    _project(WS, "usage-live-a")
    _project(WS, "usage-live-b")
    _project(WS, "usage-trashed", deleted=True)
    with SessionLocal() as db:
        seat = db.scalar(select(User).where(User.email == "area7-seat@test.local"))
        if seat is None:
            seat = _user(db, "area7-seat@test.local")
            db.flush()
            db.add(Member(workspace_id=wid, user_id=seat.id, role="member"))
        db.commit()
        projects = db.scalar(select(func.count()).select_from(Project)
                             .where(Project.workspace_id == wid, Project.deleted_at.is_(None)))
        seats = db.scalar(select(func.count()).select_from(Member).where(Member.workspace_id == wid))

    r = c.get(f"/api/ws/{WS}/usage", headers=_headers(users["owner"]))
    assert r.status_code == 200, r.text
    u = r.json()

    for key in ("plan", "plan_label", "limits", "credits_used", "credits_left", "projects", "seats",
                "meters", "daily_meters"):
        assert key in u, f"7-F7.15: the usage read carries {key}"

    assert u["plan"] == "free" and u["plan_label"] == PLANS["free"]["label"]
    assert u["limits"] == PLANS["free"], "7-F7.15: the limits are the plan ladder itself"
    assert u["projects"] == projects == 2, "7-F7.15: projects counts live rows only"
    assert u["seats"] == seats, "7-F7.15: seats counts Member rows"
    assert u["credits_used"] == 0 and u["credits_left"] == PLANS["free"]["credits"], \
        "7-F7.15: a fresh workspace shows zeros, not an error"

    assert set(u["meters"]) == METERS, "7-F7.15: all four meters are present"
    for key in METERS:
        meter = u["meters"][key]
        assert {"used", "quota", "period", "label"} <= set(meter), (key, meter)
        assert meter["quota"] == PLANS["free"][key], f"7-F7.15: {key} reads its plan allowance"
        assert meter["used"] == 0, f"7-F7.15: {key} is zero on a fresh workspace"
    assert isinstance(u["daily_meters"], list) and u["daily_meters"], "7-F7.15: the daily series is present"
    assert all("date" in day and METERS <= set(day) for day in u["daily_meters"])


def test_usage_is_workspace_scoped(c, users):
    """7-F7.15: a second workspace never includes the first one's projects, seats or meters."""
    with SessionLocal() as db:
        metering.record(db, _ws_id(WS), "ai_calls", 7)
        metering.record(db, _ws_id(WS), "storage_bytes", 4096)
        db.commit()

    u = c.get(f"/api/ws/{FOREIGN_WS}/usage", headers=_headers(users["outsider"])).json()
    assert u["projects"] == 0, "7-F7.15: another workspace's projects are not counted"
    assert u["seats"] == 1, "7-F7.15: seats count this workspace's members only"
    for key in METERS:
        assert u["meters"][key]["used"] == 0, f"7-F7.15: {key} does not leak across workspaces"


def test_another_workspace_is_unreachable_through_usage_members_and_keys(c, users):
    """Cross-workspace: a non-member gets 403 on every surface, a missing slug 404."""
    for path in ("usage", "members", "keys"):
        r = c.get(f"/api/ws/{FOREIGN_WS}/{path}", headers=_headers(users["owner"]))
        assert r.status_code == 403, (path, r.text)

    missing = c.get("/api/ws/no-such-workspace-area7/usage", headers=_headers(users["owner"]))
    assert missing.status_code == 404, "7-F7.57: a missing workspace is not found"


# --- 7-F7.26: the secret exists once, the row keeps prefix and last use ------------------------

def test_a_key_is_revealed_once_and_the_row_keeps_prefix_and_last_used(c, users):
    """7-F7.26: POST returns the value, the list keeps prefix/scopes/last_used and never the key."""
    admin = _headers(users["owner"])
    r = c.post(f"/api/ws/{WS}/keys", headers=admin, json={"name": "guard-once"})
    assert r.status_code == 200, r.text
    created = r.json()

    try:
        assert created["key"] and created["prefix"], "7-F7.26: creation reveals the value with its prefix"
        assert created["key"].startswith(created["prefix"]) and len(created["prefix"]) < len(created["key"])
        assert created["scopes"] == list(API_SCOPES), "7-F7.26: an omitted scope set means all scopes"

        row = next(x for x in c.get(f"/api/ws/{WS}/keys", headers=admin).json() if x["id"] == created["id"])
        assert row["prefix"] == created["prefix"], "7-F7.26: the row is identified by its prefix"
        assert row["scopes"] == created["scopes"] and row["publishable"] is False
        assert row["created"], "7-F7.26: the row carries when it was created"
        assert row["last_used"] is None, "7-F7.26: an unused key says so of itself"
        assert "key" not in row and "hash" not in row, "7-F7.26: the value is never listed again"
    finally:
        assert c.delete(f"/api/ws/{WS}/keys/{created['id']}", headers=admin).status_code == 200

    assert all(x["id"] != created["id"] for x in c.get(f"/api/ws/{WS}/keys", headers=admin).json()), \
        "7-F7.26: a revoked key is no longer listed"


# --- 7-F7.34: a publishable key is browser-safe and cannot manage ------------------------------

def test_publishable_key_is_inference_only_and_cannot_manage(c, users):
    """7-F7.34: the browser key is `infer` only, starts ld_pub_ and every management route 403s."""
    admin = _headers(users["owner"])
    r = c.post(f"/api/ws/{WS}/keys", headers=admin, json={"name": "guard-browser", "publishable": True})
    assert r.status_code == 200, r.text
    created = r.json()

    try:
        assert created["scopes"] == ["infer"], "7-F7.34: a publishable key may only infer"
        assert created["key"].startswith("ld_pub_"), "7-F7.34: the value names its weaker kind"
        h = {"Authorization": f"Bearer {created['key']}"}
        assert c.get("/api/v1/projects", headers=h).status_code == 403, \
            "7-F7.34: the browser key cannot list the workspace"
        assert c.get("/api/v1/whoami", headers=h).status_code == 403, \
            "7-F7.34: the browser key cannot read identity"
    finally:
        assert c.delete(f"/api/ws/{WS}/keys/{created['id']}", headers=admin).status_code == 200


# --- 7-F7.57: signup owns exactly one workspace, as its admin, on the free plan ---------------

def test_signup_creates_one_workspace_with_the_caller_as_admin(c):
    """7-F7.57: a fresh account lands as admin of one free workspace whose slug already serves."""
    email = f"area7-signup-{secrets.token_hex(3)}@test.local"
    r = c.post("/api/auth/signup", json={"name": "Area Seven", "email": email, "password": "longpassword1"})
    assert r.status_code == 200, r.text
    h = {"Authorization": f"Bearer {r.json()['token']}"}

    try:
        me = c.get("/api/me", headers=h)
        assert me.status_code == 200, me.text
        workspaces = me.json()["workspaces"]
        assert len(workspaces) == 1, "7-F7.57: signup creates exactly one workspace"
        only = workspaces[0]
        assert only["role"] == "admin", "7-F7.57: the caller owns the workspace as its admin"
        assert only["plan"] == "free", "7-F7.57: first run starts on the free plan"
        home = c.get(f"/api/ws/{only['slug']}/home", headers=h)
        assert home.status_code == 200, "7-F7.57: the new slug is usable straight away"
    finally:
        with SessionLocal() as db:
            u = db.scalar(select(User).where(User.email == email))
            if u is not None:
                for ws in db.scalars(select(Workspace).where(Workspace.owner_id == u.id)).all():
                    db.execute(delete(Audit).where(Audit.workspace_id == ws.id))
                    db.execute(delete(Member).where(Member.workspace_id == ws.id))
                    db.delete(ws)
                db.execute(delete(RefreshToken).where(RefreshToken.user_id == u.id))
                db.execute(delete(Audit).where(Audit.user_id == u.id))
                db.delete(u)
                db.commit()
