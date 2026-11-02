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

from app.db import SessionLocal, engine, get_db
from app.deps import Ctx
from app.main import app
from app.models import Audit, Project, Stream, User, Workspace, WorkspaceFlag, new_id
from app.services import flags

WS = "labeldesk-demo"
FLAG = "task_10b"
SURFACES = {"task_10b", "task_20c", "task_22", "task_23"}


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


@pytest.fixture(scope="module", autouse=True)
def _no_global_force():
    """This module proves the default (off); the shared suite forces the shipped flags on."""
    saved = os.environ.pop("LD_FLAGS_ON", None)
    yield
    if saved is not None:
        os.environ["LD_FLAGS_ON"] = saved


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


def test_registry_names_every_shipped_surface():
    assert SURFACES <= set(flags.FLAGS)


def test_streams_surface_is_gated_until_enabled(admin):
    """I13: the flag has to gate the shipped route, not just appear in the toggle list."""
    path = f"/api/ws/{WS}/projects/ppe-detection/streams"
    assert admin.get(path).status_code == 404
    assert admin.put(f"/api/ws/{WS}/flags/{FLAG}", json={"enabled": True}).status_code == 200
    assert admin.get(path).status_code == 200


SURFACE_ROUTES = [
    f"/api/ws/{WS}/projects/ppe-detection/streams",
    f"/api/ws/{WS}/projects/ppe-detection/videos",
    f"/api/ws/{WS}/projects/ppe-detection/insights/lineage",
    f"/api/ws/{WS}/projects/ppe-detection/dashboards",
    f"/api/ws/{WS}/projects/ppe-detection/labeling/dashboard",
]


@pytest.mark.parametrize("path", SURFACE_ROUTES)
def test_every_shipped_surface_route_is_gated(admin, path):
    """I13: one representative read per registered surface, not only streams."""
    assert admin.get(path).status_code == 404


def _dependency_calls(dependant) -> set:
    calls = {getattr(dependant, "call", None)}
    for sub in dependant.dependencies:
        calls |= _dependency_calls(sub)
    return calls


def _app_routes():
    """FastAPI 0.139 keeps included routers lazy; flatten them for dependency introspection."""
    for route in app.routes:
        included = getattr(route, "original_router", None)
        if included is not None:
            yield from included.routes
        else:
            yield route


@pytest.mark.parametrize("suffix", ["frame", "mjpeg"])
def test_live_view_routes_do_not_pin_a_request_session(suffix):
    """I-1: the MJPEG/JPEG body is endless, so its flag gate must not depend on get_db."""
    path = f"/api/ws/{{ws}}/projects/{{project}}/streams/{{sid}}/{suffix}"
    route = next(r for r in _app_routes() if getattr(r, "path", None) == path)
    assert get_db not in _dependency_calls(route.dependant)


def test_workspace_flag_dependency_closes_its_session(monkeypatch):
    monkeypatch.setenv("LD_FLAGS_ON", FLAG)
    dep = flags.require_workspace_flag(FLAG)
    before = engine.pool.checkedout()
    dep(WS)
    assert engine.pool.checkedout() == before


class _FakeWorker:
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True


def _create_stream() -> str:
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        project = db.scalar(select(Project).where(Project.workspace_id == ws.id, Project.slug == "ppe-detection"))
        stream = Stream(id=new_id(), workspace_id=ws.id, project_id=project.id, name="kill-switch",
                        source="file:videos/kill.mp4", model_ref="ultralytics:yolo26n", status="live")
        db.add(stream)
        db.commit()
        return stream.id


def _drop_stream(sid: str) -> None:
    from app.streams.manager import manager
    manager._workers.pop(sid, None)
    with SessionLocal() as db:
        db.execute(delete(Stream).where(Stream.id == sid))
        db.commit()


def test_disabling_streams_flag_stops_running_cameras(admin):
    """I-2: the kill switch must stop capture, not just hide the API."""
    from app.streams.manager import manager
    sid = _create_stream()
    worker = _FakeWorker()
    manager._workers[sid] = worker
    try:
        assert admin.put(f"/api/ws/{WS}/flags/{FLAG}", json={"enabled": True}).status_code == 200
        r = admin.put(f"/api/ws/{WS}/flags/{FLAG}", json={"enabled": False})
        assert r.status_code == 200 and r.json()["enabled"] is False
        assert worker.stopped is True
        assert sid not in manager._workers
        with SessionLocal() as db:
            assert db.get(Stream, sid).status == "stopped"
    finally:
        _drop_stream(sid)


def test_stop_route_stays_reachable_when_streams_flag_is_off(admin):
    """I-2: turning the flag off must not strand a camera behind a 404 stop control."""
    from app.streams.manager import manager
    sid = _create_stream()
    worker = _FakeWorker()
    manager._workers[sid] = worker
    try:
        r = admin.post(f"/api/ws/{WS}/projects/ppe-detection/streams/{sid}/stop")
        assert r.status_code == 200, r.text
        assert worker.stopped is True
    finally:
        _drop_stream(sid)
