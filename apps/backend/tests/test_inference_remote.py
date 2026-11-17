"""T-1008: an engine job is claimed by one host, and its progress is a capped, redacted log tail.

The API process never runs an install (its embedded worker does not advertise the kind), a claim
only takes a job whose ``params.host`` is the claiming worker, the payload carries the plan's steps
so the worker can re-derive its id from its own inventory, and the log an admin reads is bounded and
has no credential in it.
"""
import hashlib
import json
import os
import uuid

os.environ.setdefault("LD_WORKER_TOKEN", "test-worker-token-0123456789abcdef")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import config, worker
from app.db import SessionLocal
from app.main import app
from app.models import Job, Worker, Workspace, WorkspaceFlag
from app.services import flags, inference_catalog, inference_plan
from conftest import login

WS = "labeldesk-demo"
CLAIM = "/api/worker/claim"
PLAN = f"/api/ws/{WS}/inference/engines/plan"
INSTALL = f"/api/ws/{WS}/inference/engines/install"
AUTH = {"X-Worker-Token": "test-worker-token-0123456789abcdef"}
VLLM = inference_catalog.engine("vllm")


def _ws_id() -> str:
    with SessionLocal() as db:
        return db.scalar(select(Workspace.id).where(Workspace.slug == WS))


def _inventory(free_gb: float = 812.5) -> dict:
    """A report shaped like apps/worker/labeldesk_worker/inventory.py:collect()."""
    return {"os": "Linux", "arch": "x86_64", "python": "3.11.9",
            "gpus": [{"name": "NVIDIA GeForce RTX 4090", "vram_mb": 24564,
                      "driver": "575.51", "cuda": "12.9"}],
            "cuda": "12.9", "docker": True,
            "disk": {"models_free_gb": free_gb, "models_total_gb": 1863.0},
            "engines": []}


def _host(inventory: dict | None) -> str:
    """A host row the plan reads; a huge last_seen keeps it online for the whole test."""
    wid = f"gpu-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        db.add(Worker(id=wid, host=wid, kinds=["engine_apply"], started=0.0, last_seen=9e12,
                      inventory=inventory))
        db.commit()
    return wid


def _choice() -> dict:
    return {"id": "vllm", "version": VLLM["version"], "runtime": "uv"}


def _install(c: TestClient, wid: str) -> dict:
    """One confirmed install job for ``wid``, through the plan the admin would have reviewed."""
    plan = c.post(PLAN, json={"host": wid, "engines": [_choice()]})
    assert plan.status_code == 200, plan.text
    r = c.post(INSTALL, json={"host": wid, "engines": [_choice()],
                              "plan_id": plan.json()["plan_id"], "confirm": True})
    assert r.status_code == 200, r.text
    return r.json()["job"]


def _claim(name: str, kinds: list[str]) -> dict:
    return TestClient(app).post(CLAIM, json={"name": name, "kinds": kinds}, headers=AUTH)


def _job(jid: str) -> Job:
    with SessionLocal() as db:
        job = db.get(Job, jid)
        db.expunge(job)
        return job


@pytest.fixture(scope="module")
def c():
    client = TestClient(app)
    client.headers.update(login(client))
    yield client


@pytest.fixture(autouse=True)
def flag_on():
    with SessionLocal() as db:
        flags.set_flag(db, _ws_id(), "task_inference", True)
        db.commit()
    yield


@pytest.fixture(autouse=True)
def _clean():
    """No host, engine job or flag of this module survives into another one."""
    with SessionLocal() as db:
        before = set(db.scalars(select(Worker.id)))
    yield
    with SessionLocal() as db:
        for wid in set(db.scalars(select(Worker.id))) - before:
            db.delete(db.get(Worker, wid))
        db.execute(Job.__table__.delete().where(Job.kind.in_(("engine_apply", "model_pull", "ollama"))))
        db.execute(WorkspaceFlag.__table__.delete().where(WorkspaceFlag.key == "task_inference"))
        db.commit()


def test_api_process_never_claims_an_engine_job(c: TestClient):
    """The embedded worker's list is what this process claims; an install is never on it."""
    wid = _host(_inventory())
    job = _install(c, wid)

    assert "engine_apply" in config.REMOTE_JOB_KINDS
    assert "engine_apply" not in config.LOCAL_JOB_KINDS
    assert config.runs_locally("engine_apply") is False

    for _ in range(2):                       # two poll intervals of the embedded loop
        assert worker._claim() != job["id"]
    assert _job(job["id"]).status == "queued"


def test_claim_is_host_targeted(c: TestClient):
    """Host B gets B's job and the payload carries the plan steps its own inventory can hash."""
    inventory = _inventory()
    a, b = _host(inventory), _host(inventory)
    job_a, job_b = _install(c, a), _install(c, b)

    r = _claim(b, ["engine_apply", "train"])
    assert r.status_code == 200, r.text
    got = r.json()["job"]
    assert got["id"] == job_b["id"]
    payload = got["payload"]
    assert payload["host"] == b and payload["action"] == "install"
    assert _job(job_a["id"]).status == "queued"                 # A's job is untouched

    steps = payload["engines"]
    assert [step["id"] for step in steps] == ["vllm"]
    assert steps[0]["status"] == "install" and steps[0]["argv"][0][:2] == ["uv", "venv"]
    body = json.dumps({"host": b, "steps": steps, "inventory": inference_plan._stamp(inventory)},
                      sort_keys=True, separators=(",", ":"))
    assert hashlib.sha256(body.encode()).hexdigest()[:16] == payload["plan_id"]

    assert _claim(a, ["engine_apply"]).json()["job"]["id"] == job_a["id"]


def test_progress_appends_log_and_redacts_a_token(c: TestClient):
    """A host-supplied log is an input boundary: capped at 200 lines of 500 chars, no token."""
    wid = _host(_inventory())
    job = _install(c, wid)

    lines = [f"line {i}" for i in range(247)] + ["y" * 600, "using hf_abc123token", "ok"]
    r = TestClient(app).post(f"/api/worker/jobs/{job['id']}/progress", headers=AUTH,
                             json={"progress": 40, "log": lines, "phase": "installing vllm"})
    assert r.status_code == 200, r.text

    stored = _job(job["id"]).result
    assert stored["phase"] == "installing vllm"
    assert stored["heartbeat"]
    assert len(stored["log"]) == 200
    assert stored["log"][-1] == "ok"
    assert "using hf_***" in stored["log"]
    assert max(len(line) for line in stored["log"]) == 500
    assert "hf_abc123token" not in json.dumps(stored)


def test_unknown_kind_still_refused(c: TestClient):
    """No worker advertises it, so a row of an unknown kind is never claimed."""
    wid = _host(None)
    with SessionLocal() as db:
        job = Job(workspace_id=_ws_id(), kind="ollama", status="queued",
                  params={"host": wid}, created=0.0)
        db.add(job)
        db.commit()
        jid = job.id

    r = _claim(wid, ["ollama", "engine_apply"])
    assert r.status_code == 200, r.text
    assert "ollama" not in config.REMOTE_JOB_KINDS
    assert r.json()["job"] is None or r.json()["job"]["id"] != jid
    assert _job(jid).status == "queued"
