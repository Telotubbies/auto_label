"""Super-admin console: access control, overview counters, plans, queue health, workers, status page."""
import os
import secrets
import tempfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-admin-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"
os.environ.pop("LD_SUPERADMINS", None)          # every test opts in explicitly

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.config import PLANS, WORKER_STALE_S
from app.db import SessionLocal
from app.main import app
from app.models import Audit, Job, Worker, Workspace, now
from app.services import heartbeat

DEMO = "demo@labeldesk.dev"
PW = "demo1234"


def login(email: str = DEMO) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return c


@pytest.fixture(scope="module")
def admin():
    with TestClient(app):
        yield login()


@pytest.fixture
def superadmin(monkeypatch):
    monkeypatch.setenv("LD_SUPERADMINS", DEMO)


def demo_ws() -> Workspace:
    with SessionLocal() as db:
        return db.scalar(select(Workspace).where(Workspace.slug == "labeldesk-demo"))


def test_non_superadmin_is_refused(admin):
    c = login("labeler@labeldesk.dev")
    r = c.get("/api/admin/overview")
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == "super-admin only"


def test_me_reports_superadmin_flag(admin, superadmin):
    assert admin.get("/api/me").json()["superadmin"] is True
    assert login("labeler@labeldesk.dev").get("/api/me").json()["superadmin"] is False


def test_overview_reports_platform_counters(admin, superadmin):
    r = admin.get("/api/admin/overview")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["version"] == "1.0.0"
    for key in ("workspaces", "users", "projects", "images"):
        assert isinstance(body[key], int) and body[key] >= 1
    assert set(body["jobs"]) == {"queued", "running", "done", "failed", "cancelled"}
    assert all(isinstance(n, int) for n in body["jobs"].values())
    assert {"used_mb", "budget_mb", "holder", "leases"} <= set(body["gpu"])
    assert isinstance(body["workers_online"], int)
    assert isinstance(body["vllm"]["configured"], bool)
    assert body["vllm"]["sleeping"] in (True, False, None)
    assert isinstance(body["generated"], float)


def test_workspace_rows_carry_usage_and_plan(admin, superadmin):
    r = admin.get("/api/admin/workspaces", params={"q": "labeldesk"})
    assert r.status_code == 200, r.text
    rows = r.json()
    assert rows and rows[0]["slug"] == "labeldesk-demo"
    row = rows[0]
    assert set(row) == {"id", "slug", "name", "plan", "plan_label", "region", "owner_email", "created", "members",
                        "projects", "images", "credits_used", "credits_limit"}
    assert row["owner_email"] == DEMO
    assert row["plan"] in PLANS and row["plan_label"] == PLANS[row["plan"]]["label"]
    assert row["members"] >= 1 and row["projects"] >= 1


def test_plan_change_updates_workspace_and_is_audited(admin, superadmin):
    ws = demo_ws()
    target = "pro" if ws.plan != "pro" else "free"
    try:
        r = admin.patch(f"/api/admin/workspaces/{ws.id}", json={"plan": target})
        assert r.status_code == 200, r.text
        assert r.json()["plan"] == target
        with SessionLocal() as db:
            assert db.get(Workspace, ws.id).plan == target
            row = db.scalar(select(Audit).where(Audit.action == "admin.plan", Audit.target == ws.name)
                            .order_by(Audit.created.desc()))
            assert row is not None
            assert row.meta["plan"] == target
            assert row.meta["by"] == DEMO
    finally:
        admin.patch(f"/api/admin/workspaces/{ws.id}", json={"plan": ws.plan})


def test_unknown_plan_is_rejected(admin, superadmin):
    ws = demo_ws()
    r = admin.patch(f"/api/admin/workspaces/{ws.id}", json={"plan": "platinum"})
    assert r.status_code == 400
    assert "unknown plan" in r.json()["detail"]


def test_jobs_counts_and_oldest_queued(admin, superadmin):
    ws = demo_ws()
    jid = f"adminjob{secrets.token_hex(4)}"
    with SessionLocal() as db:
        # "evaluate" is not in LOCAL_JOB_KINDS, so the embedded worker never claims this row.
        db.add(Job(id=jid, workspace_id=ws.id, kind="evaluate", status="queued"))
        db.commit()
    try:
        r = admin.get("/api/admin/jobs", params={"status": "queued", "kind": "evaluate", "limit": 10})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["counts"]["queued"] >= 1
        assert set(body["counts"]) == {"queued", "running", "done", "failed", "cancelled"}
        assert body["oldest_queued_s"] is not None and body["oldest_queued_s"] >= 0
        assert [i["id"] for i in body["items"]] == [jid]
        item = body["items"][0]
        assert item["workspace"] == "labeldesk-demo"
        assert item["kind"] == "evaluate" and item["status"] == "queued"
        assert isinstance(item["age_s"], float)
    finally:
        with SessionLocal() as db:
            db.execute(delete(Job).where(Job.id == jid))
            db.commit()


def test_workers_show_heartbeat_online_and_stale_offline(admin, superadmin):
    heartbeat.beat(force=True)
    stale_id = f"stale-{secrets.token_hex(4)}"
    with SessionLocal() as db:
        db.add(Worker(id=stale_id, host="old-box", kinds=["export"], last_seen=now() - 3600))
        db.commit()
    try:
        r = admin.get("/api/admin/workers")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["stale_after"] == WORKER_STALE_S
        by_id = {w["id"]: w for w in body["workers"]}
        assert by_id[heartbeat.worker_id()]["online"] is True
        assert by_id[stale_id]["online"] is False
    finally:
        with SessionLocal() as db:
            db.execute(delete(Worker).where(Worker.id == stale_id))
            db.commit()


def test_status_page_reports_known_components(admin, superadmin):
    r = admin.get("/api/admin/status")
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body["checked"], float)
    allowed = {"operational", "degraded", "unknown"}
    names = {c["name"]: c for c in body["components"]}
    assert {"api", "database", "worker", "gpu", "vllm", "queue"} <= set(names)
    for comp in body["components"]:
        assert comp["status"] in allowed, comp
        assert isinstance(comp["detail"], str)
    assert names["database"]["status"] == "operational"
