"""T-1009: the job card's three reads — one job, the active list, and a cancel.

A job the browser may see carries the phase and the worker's log tail, and never ``params`` (it
holds the install argv). The active list is this workspace's engine work only, newest first. A
cancel sets ``cancelling`` for a claimed job and is idempotent; a queued job that no worker will ever
claim is cancelled outright. Another workspace's job is 404, a member is 403, and the flag gates all
three.
"""
import json
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Job, Workspace, WorkspaceFlag
from app.services import flags
from conftest import login, login_as

WS = "labeldesk-demo"
JOBS = f"/api/ws/{WS}/inference/jobs"
HOST = "t1009-host"
ARGV = [["uv", "venv", "vllm-0.6.3"],
        ["uv", "pip", "install", "--python", "vllm-0.6.3/bin/python", "vllm==0.6.3"]]

CREATED: list[str] = []          # job ids this module made, so cleanup never touches another module
FOREIGN: list[str] = []          # workspace ids this module made


def _ws_id() -> str:
    with SessionLocal() as db:
        return db.scalar(select(Workspace.id).where(Workspace.slug == WS))


def _job(status: str = "running", result: dict | None = None, ws_id: str | None = None,
         created: float | None = None, kind: str = "engine_apply") -> str:
    """One job row shaped like T-1006/T-1008 write it; params carries the argv the shaper must drop."""
    with SessionLocal() as db:
        job = Job(workspace_id=ws_id or _ws_id(), project_id=None, kind=kind, status=status,
                  params={"host": HOST, "action": "install", "plan_id": "plan-t1009",
                          "engines": [{"id": "vllm", "version": "0.6.3", "runtime": "uv",
                                       "argv": ARGV}]},
                  result=result or {}, created=created or time.time())
        db.add(job)
        db.commit()
        CREATED.append(job.id)
        return job.id


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
    """No job, flag or foreign workspace of this module survives into another one."""
    yield
    with SessionLocal() as db:
        for jid in CREATED:
            row = db.get(Job, jid)
            if row is not None:
                db.delete(row)
        for wid in FOREIGN:
            row = db.get(Workspace, wid)
            if row is not None:
                db.delete(row)
        db.execute(WorkspaceFlag.__table__.delete().where(WorkspaceFlag.key == "task_inference"))
        db.commit()
    CREATED.clear()
    FOREIGN.clear()


def test_job_view_omits_params_and_keeps_the_log(c: TestClient):
    result = {"log": ["resolved vllm 0.6.3", "installing vllm"], "phase": "installing vllm"}
    jid = _job(status="running", result=result)

    r = c.get(f"{JOBS}/{jid}")
    assert r.status_code == 200, r.text
    body = r.json()

    assert "params" not in body
    assert body["log"] == ["resolved vllm 0.6.3", "installing vllm"]
    assert body["phase"] == "installing vllm"
    assert body["kind"] == "engine_apply" and body["status"] == "running"
    assert body["host"] == HOST
    # The argv lives in params and must not reach the browser through any field.
    assert "argv" not in body
    assert "venv" not in json.dumps(body)


def test_active_list_excludes_terminal_jobs(c: TestClient):
    earlier = time.time() - 5
    done = _job(status="done", created=earlier)
    running = _job(status="running", created=earlier + 1)

    r = c.get(JOBS, params={"status": "active"})
    assert r.status_code == 200, r.text
    jobs = r.json()
    ids = [job["id"] for job in jobs]

    assert running in ids
    assert done not in ids
    assert ids.index(running) == 0                      # newest first
    assert all(job["status"] in ("queued", "running", "cancelling") for job in jobs)


def test_cancel_sets_cancelling_and_is_idempotent(c: TestClient):
    running = _job(status="running")
    first = c.post(f"{JOBS}/{running}/cancel")
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "cancelling"

    second = c.post(f"{JOBS}/{running}/cancel")
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "cancelling"      # still waiting for the worker to acknowledge

    done = _job(status="done")
    assert c.post(f"{JOBS}/{done}/cancel").json()["status"] == "done"

    # A queued job has no worker to acknowledge it: cancel it outright instead of stranding it.
    queued = _job(status="queued")
    assert c.post(f"{JOBS}/{queued}/cancel").json()["status"] == "cancelled"


def test_foreign_job_is_404(c: TestClient):
    with SessionLocal() as db:
        owner_id = db.get(Workspace, _ws_id()).owner_id
        other = Workspace(slug=f"t1009-{uuid.uuid4().hex[:8]}", name="Other", owner_id=owner_id)
        db.add(other)
        db.commit()
        FOREIGN.append(other.id)
        other_id = other.id
    jid = _job(status="running", ws_id=other_id)
    local = _job(status="running")                  # the same route reads this workspace's job
    assert c.get(f"{JOBS}/{local}").status_code == 200

    assert c.get(f"{JOBS}/{jid}").status_code == 404
    r = c.post(f"{JOBS}/{jid}/cancel")
    assert r.status_code == 404
    with SessionLocal() as db:
        assert db.get(Job, jid).status == "running"     # a foreign 404 changed nothing


def test_member_is_403_and_flag_off_is_404(c: TestClient):
    jid = _job(status="running")

    member = TestClient(app)
    member.headers.update(login_as(member, "labeler@labeldesk.dev"))
    assert member.get(JOBS).status_code == 403
    assert member.get(f"{JOBS}/{jid}").status_code == 403
    assert member.post(f"{JOBS}/{jid}/cancel").status_code == 403

    with SessionLocal() as db:
        flags.set_flag(db, _ws_id(), "task_inference", False)
        db.commit()
    assert c.get(JOBS).status_code == 404
    assert c.get(f"{JOBS}/{jid}").status_code == 404
    assert c.post(f"{JOBS}/{jid}/cancel").status_code == 404
