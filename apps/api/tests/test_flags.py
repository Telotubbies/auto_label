"""Feature flags: env forcing, per-workspace overrides, admin toggle and workspace isolation."""
import os
import tempfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-flags-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.deps import Ctx
from app.main import app
from app.models import Audit, User, Workspace, WorkspaceFlag
from app.services import flags

WS = "labeldesk-demo"
FLAG = "task_f1"


def login(email: str = "demo@labeldesk.dev", pw: str = "demo1234") -> TestClient:
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return c


@pytest.fixture(scope="module", autouse=True)
def _started():
    with TestClient(app):
        yield


@pytest.fixture(scope="module")
def admin():
    with TestClient(app):
        yield login()


@pytest.fixture(scope="module")
def labeler():
    with TestClient(app):
        yield login("labeler@labeldesk.dev")


@pytest.fixture(autouse=True)
def _clean_overrides():
    """Every test starts with no stored overrides and no env forcing."""
    def clear():
        with SessionLocal() as db:
            db.execute(delete(WorkspaceFlag))
            db.commit()
    clear()
    yield
    clear()


def ws_id(slug: str = WS) -> str:
    with SessionLocal() as db:
        return db.scalar(select(Workspace.id).where(Workspace.slug == slug))


def test_unknown_and_unset_flags_are_off():
    with SessionLocal() as db:
        assert flags.is_enabled("not_a_real_flag", db, ws_id()) is False
        assert flags.is_enabled(FLAG, db, ws_id()) is False


def test_env_forces_known_flags_on_only(monkeypatch):
    monkeypatch.setenv("LD_FLAGS_ON", f" {FLAG} , not_a_real_flag ")
    with SessionLocal() as db:
        assert flags.is_enabled(FLAG, db, ws_id()) is True
        assert flags.is_enabled("not_a_real_flag", db, ws_id()) is False


def test_get_returns_enabled_keys(admin):
    assert admin.get(f"/api/ws/{WS}/flags").json()["enabled"] == []
    r = admin.put(f"/api/ws/{WS}/flags/{FLAG}", json={"enabled": True})
    assert r.status_code == 200, r.text
    assert admin.get(f"/api/ws/{WS}/flags").json()["enabled"] == [FLAG]


def test_put_is_admin_only(admin, labeler):
    assert labeler.put(f"/api/ws/{WS}/flags/{FLAG}", json={"enabled": True}).status_code == 403
    assert admin.put(f"/api/ws/{WS}/flags/{FLAG}", json={"enabled": True}).status_code == 200


def test_put_is_audited(admin):
    admin.put(f"/api/ws/{WS}/flags/{FLAG}", json={"enabled": True})
    with SessionLocal() as db:
        row = db.scalar(select(Audit).where(Audit.workspace_id == ws_id(), Audit.action == "flag.update",
                                           Audit.target == FLAG))
        assert row is not None and row.meta["enabled"] is True


def test_put_can_turn_a_flag_off(admin):
    admin.put(f"/api/ws/{WS}/flags/{FLAG}", json={"enabled": True})
    assert admin.get(f"/api/ws/{WS}/flags").json()["enabled"] == [FLAG]

    assert admin.put(f"/api/ws/{WS}/flags/{FLAG}", json={"enabled": False}).status_code == 200
    assert admin.get(f"/api/ws/{WS}/flags").json()["enabled"] == []
    with SessionLocal() as db:
        assert flags.is_enabled(FLAG, db, ws_id()) is False


def test_env_force_overrides_a_stored_off(admin, monkeypatch):
    admin.put(f"/api/ws/{WS}/flags/{FLAG}", json={"enabled": False})
    monkeypatch.setenv("LD_FLAGS_ON", FLAG)
    with SessionLocal() as db:
        assert flags.is_enabled(FLAG, db, ws_id()) is True


def test_put_unknown_flag_is_404(admin):
    assert admin.put(f"/api/ws/{WS}/flags/nope", json={"enabled": True}).status_code == 404


def test_overrides_are_isolated_per_workspace(admin, labeler):
    other = admin.post("/api/workspaces", json={"name": "Flags Other"}).json()["slug"]
    admin.put(f"/api/ws/{other}/flags/{FLAG}", json={"enabled": True})

    assert admin.get(f"/api/ws/{other}/flags").json()["enabled"] == [FLAG]
    assert admin.get(f"/api/ws/{WS}/flags").json()["enabled"] == []
    with SessionLocal() as db:
        assert flags.is_enabled(FLAG, db, ws_id(other)) is True
        assert flags.is_enabled(FLAG, db, ws_id()) is False
    # a non-member cannot read another workspace's flags
    assert labeler.get(f"/api/ws/{other}/flags").status_code == 403


def test_require_flag_is_404_until_enabled(admin):
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        user = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
        ctx = Ctx(user=user, ws=ws, role="admin", db=db)
        with pytest.raises(HTTPException) as off:
            flags.require_flag(FLAG)(ctx)
        assert off.value.status_code == 404

        admin.put(f"/api/ws/{WS}/flags/{FLAG}", json={"enabled": True})
        assert flags.require_flag(FLAG)(ctx) is None


def test_require_flag_unknown_key_is_404():
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        user = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
        ctx = Ctx(user=user, ws=ws, role="admin", db=db)
        with pytest.raises(HTTPException) as off:
            flags.require_flag("not_a_real_flag")(ctx)
        assert off.value.status_code == 404
