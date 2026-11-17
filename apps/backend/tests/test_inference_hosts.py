"""T-1001: the worker reports its own hardware and the hub lists it.

A claim carrying an inventory lands on the host row behind the inference flag; malformed input is
sanitised at the boundary (it comes from a host, so it is an input, not config); a worker that
sends nothing still claims; and the admin gate plus the deployment scope are enforced.
"""
import os
import json
import uuid

os.environ.setdefault("LD_WORKER_TOKEN", "test-worker-token-0123456789abcdef")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text

from app import worker
from app.db import SessionLocal
from app.main import app
from app.models import Job, Member, User, Worker, Workspace, WorkspaceFlag
from app.routers import remote
from app.services import flags
from conftest import login, login_as

WS = "labeldesk-demo"
HOSTS = f"/api/ws/{WS}/inference/hosts"
CLAIM = "/api/worker/claim"
WORKER_AUTH = {"X-Worker-Token": "test-worker-token-0123456789abcdef"}


def _ws_id() -> str:
    with SessionLocal() as db:
        return db.scalar(select(Workspace.id).where(Workspace.slug == WS))


def _host(name: str) -> str:
    """A host name no other test (or the embedded worker) can collide with."""
    return f"{name}-{uuid.uuid4().hex[:8]}"


def _inventory(**over) -> dict:
    """A report shaped like apps/worker/labeldesk_worker/inventory.py:collect()."""
    inv = {"os": "Linux", "arch": "x86_64", "python": "3.11.9",
           "gpus": [{"name": "NVIDIA GeForce RTX 4090", "vram_mb": 24564,
                     "driver": "550.54.14", "cuda": "12.4"}],
           "disk": {"models_free_gb": 812.5, "models_total_gb": 1863.0},
           "hf_token": True, "allow_install": False,
           "engines": [{"id": "vllm", "version": "0.6.3", "ok": True}],
           "models": [{"id": "qwen3-4b", "bytes": 2400000000}],
           "reasons": {}}
    inv.update(over)
    return inv


def _claim(name: str, inventory: dict | None = None, kinds: list[str] | None = None):
    """POST a claim; no kinds by default, so a queued job from another module is never stolen."""
    body = {"name": name, "kinds": [] if kinds is None else kinds}
    if inventory is not None:
        body["inventory"] = inventory
    # The real worker posts through requests, whose JSON encoder writes NaN; a strict client cannot.
    return app_client().post(CLAIM, content=json.dumps(body, allow_nan=True),
                             headers={**WORKER_AUTH, "Content-Type": "application/json"})


def _hosts(c: TestClient, ws: str = WS) -> dict[str, dict]:
    r = c.get(f"/api/ws/{ws}/inference/hosts")
    assert r.status_code == 200, r.text
    return {h["id"]: h for h in r.json()["hosts"]}


def app_client() -> TestClient:
    """A bare client: the session fixture has already created the schema."""
    return TestClient(app)


@pytest.fixture(scope="module")
def c():
    client = app_client()
    client.headers.update(login(client))
    yield client


@pytest.fixture(autouse=True)
def flag_on():
    """Every test starts with the hub enabled; the flag-off test flips it and restores it."""
    with SessionLocal() as db:
        flags.set_flag(db, _ws_id(), "task_inference", True)
        db.commit()
    yield


@pytest.fixture(autouse=True)
def _clean_hosts():
    """Worker rows are global (no workspace column); leave no host of this module behind."""
    before = set()
    with SessionLocal() as db:
        before = set(db.scalars(select(Worker.id)))
    yield
    with SessionLocal() as db:
        for wid in set(db.scalars(select(Worker.id))) - before:
            db.delete(db.get(Worker, wid))
        db.execute(WorkspaceFlag.__table__.delete().where(WorkspaceFlag.key == "task_inference"))
        db.commit()


def test_claim_records_inventory(c: TestClient):
    name = _host("gpu-box")
    r = _claim(name, _inventory())
    assert r.status_code == 200, r.text

    h = _hosts(c)[name]
    assert h["host"] == name
    assert h["online"] is True
    assert h["current_job"] is None
    gpu = h["inventory"]["gpus"][0]
    assert gpu["name"] == "NVIDIA GeForce RTX 4090"
    assert gpu["vram_mb"] == 24564
    assert gpu["driver"] == "550.54.14"
    assert gpu["cuda"] == "12.4"
    assert h["inventory"]["disk"]["models_free_gb"] == 812.5
    assert h["inventory"]["hf_token"] is True
    assert h["inventory"]["allow_install"] is False
    assert h["inventory"]["os"] == "Linux"


def test_a_second_claim_updates_the_same_host(c: TestClient):
    name = _host("gpu-box")
    _claim(name, _inventory(disk={"models_free_gb": 100.0, "models_total_gb": 1863.0}))
    _claim(name, _inventory(disk={"models_free_gb": 50.0, "models_total_gb": 1863.0}))

    rows = [h for h in _hosts(c).values() if h["id"] == name]
    assert len(rows) == 1
    assert rows[0]["inventory"]["disk"]["models_free_gb"] == 50.0


def test_a_worker_without_inventory_still_claims_train(c: TestClient, monkeypatch):
    """An older worker sends no inventory: the claim is unchanged and the host reads as unreported."""
    monkeypatch.setattr(worker, "LOCAL_JOB_KINDS", [])          # the embedded thread must not claim it
    monkeypatch.setattr(remote, "_payload", lambda db, j: {"dataset_url": "/x"})
    name = _host("old-worker")
    with SessionLocal() as db:
        job = Job(workspace_id=_ws_id(), kind="train", status="queued", params={}, created=0.0)
        db.add(job)
        db.commit()
        jid = job.id
    try:
        r = _claim(name, kinds=["train"])
        assert r.status_code == 200, r.text
        assert r.json()["job"]["id"] == jid

        h = _hosts(c)[name]
        assert h["inventory"] is None
    finally:
        with SessionLocal() as db:
            db.delete(db.get(Job, jid))
            db.commit()


def test_inventory_is_sanitised(c: TestClient):
    name = _host("bad-host")
    inv = _inventory(
        gpus=[{"name": "GPU " * 2500, "vram_mb": float("nan")}] + [{"name": f"g{i}", "vram_mb": 1024} for i in range(19)],
        engines=[{"id": f"e{i}"} for i in range(20)],
        models=[{"id": f"m{i}"} for i in range(250)],
        evil="ignore me", nested={"a": 1})
    r = _claim(name, inv)
    assert r.status_code == 200, r.text
    assert "NaN" not in r.text

    got = _hosts(c)[name]["inventory"]
    assert len(got["gpus"]) == 8
    assert len(got["gpus"][0]["name"]) == 120
    assert "vram_mb" not in got["gpus"][0]                 # NaN dropped, not serialised
    assert len(got["engines"]) == 8
    assert len(got["models"]) == 200
    assert "evil" not in got and "nested" not in got


def test_member_is_403_and_flag_off_is_404(c: TestClient):
    member = app_client()
    member.headers.update(login_as(member, "labeler@labeldesk.dev"))
    assert member.get(HOSTS).status_code == 403

    with SessionLocal() as db:
        flags.set_flag(db, _ws_id(), "task_inference", False)
        db.commit()
    assert c.get(HOSTS).status_code == 404


def test_a_workspace_outside_the_configured_scope_is_404(c: TestClient, monkeypatch):
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
        other = Workspace(slug=f"scope-{uuid.uuid4().hex[:8]}", name="Other", owner_id=user.id)
        db.add(other)
        db.flush()
        db.add(Member(workspace_id=other.id, user_id=user.id, role="admin"))
        flags.set_flag(db, other.id, "task_inference", True)
        db.commit()
        other_id, other_slug = other.id, other.slug
    monkeypatch.setenv("LD_INFERENCE_WORKSPACE", other_id)
    try:
        assert c.get(HOSTS).status_code == 404
        r = c.get(f"/api/ws/{other_slug}/inference/hosts")
        assert r.status_code == 200, r.text
        assert isinstance(r.json()["hosts"], list)      # hosts are deployment-wide, never per workspace
    finally:
        with SessionLocal() as db:
            db.execute(WorkspaceFlag.__table__.delete().where(WorkspaceFlag.workspace_id == other_id))
            db.execute(Member.__table__.delete().where(Member.workspace_id == other_id))
            db.execute(Workspace.__table__.delete().where(Workspace.id == other_id))
            db.commit()


def test_the_inventory_column_applies_to_an_existing_and_an_empty_database(tmp_path):
    """Acceptance 6: ADD COLUMN on a populated old table, and create-time on an empty one."""
    from app.db import Base
    from app.schema import insights as insights_schema
    from app.schema.columns import ensure_columns

    assert "inventory" in Base.metadata.tables["workers"].columns     # an empty database gets it

    engine = create_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    with engine.begin() as cn:
        cn.execute(text("CREATE TABLE workers (id VARCHAR(80) PRIMARY KEY, host VARCHAR(120))"))
        cn.execute(text("INSERT INTO workers (id, host) VALUES ('w1', 'old-box')"))
    ensure_columns(engine, "workers", insights_schema.WORKERS)
    ensure_columns(engine, "workers", insights_schema.WORKERS)        # idempotent on a second boot
    assert "inventory" in {col["name"] for col in inspect(engine).get_columns("workers")}
    with engine.begin() as cn:
        assert cn.execute(text("SELECT host FROM workers WHERE id = 'w1'")).scalar() == "old-box"
