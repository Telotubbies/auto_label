"""T-1006: a dry-run install plan, then one confirmed job per host.

The plan is the contract: it names the exact argv, the bytes and the disk after, and it writes
nothing — no job, no audit, no file. Install and uninstall only enqueue a queued ``engine_apply``
row after confirmation, refuse a plan that no longer describes the host, and keep one engine job
per host. No request string can become an argument: ids, catalogue versions and enums only.
"""
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import DATA_DIR
from app.db import SessionLocal
from app.main import app
from app.models import Audit, Job, Worker, Workspace, WorkspaceFlag
from app.services import flags, inference_catalog
from conftest import login, login_as

WS = "labeldesk-demo"
PLAN = f"/api/ws/{WS}/inference/engines/plan"
INSTALL = f"/api/ws/{WS}/inference/engines/install"
UNINSTALL = f"/api/ws/{WS}/inference/engines/uninstall"
VLLM = inference_catalog.engine("vllm")
OLLAMA = inference_catalog.engine("ollama")


def _ws_id() -> str:
    with SessionLocal() as db:
        return db.scalar(select(Workspace.id).where(Workspace.slug == WS))


def _host(inventory: dict | None, last_seen: float = 9e12) -> str:
    """A host row the plan can read; a huge last_seen keeps it online for the whole test."""
    wid = f"plan-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        db.add(Worker(id=wid, host=wid, kinds=[], started=0.0, last_seen=last_seen, inventory=inventory))
        db.commit()
    return wid


def _inventory(engines: list | None = None, free_gb: float = 812.5) -> dict:
    """A report shaped like the worker's inventory, on a host that fits every pin."""
    return {"os": "Linux", "arch": "x86_64", "python": "3.11.9",
            "gpus": [{"name": "NVIDIA GeForce RTX 4090", "vram_mb": 24564,
                      "driver": "575.51", "cuda": "12.9"}],
            "cuda": "12.9", "docker": True,
            "disk": {"models_free_gb": free_gb, "models_total_gb": 1863.0},
            "engines": engines or []}


def _choice(engine: dict = VLLM, runtime: str = "uv", version: str | None = None) -> dict:
    return {"id": engine["id"], "version": version or engine["version"], "runtime": runtime}


def _engine_jobs() -> list[Job]:
    with SessionLocal() as db:
        return list(db.scalars(select(Job).where(Job.kind == "engine_apply")))


def _set_inventory(wid: str, inventory: dict) -> None:
    with SessionLocal() as db:
        db.get(Worker, wid).inventory = inventory
        db.commit()


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
    """No host, job or flag of this module survives into another one."""
    with SessionLocal() as db:
        before = set(db.scalars(select(Worker.id)))
    yield
    with SessionLocal() as db:
        for wid in set(db.scalars(select(Worker.id))) - before:
            db.delete(db.get(Worker, wid))
        db.execute(Job.__table__.delete().where(Job.kind == "engine_apply"))
        db.execute(WorkspaceFlag.__table__.delete().where(WorkspaceFlag.key == "task_inference"))
        db.commit()


def test_plan_is_side_effect_free(c: TestClient):
    wid = _host(_inventory())
    before_jobs, before_files = len(_engine_jobs()), set(DATA_DIR.rglob("*"))
    with SessionLocal() as db:
        before_audits = len(db.scalars(select(Audit.id).where(Audit.target == wid)).all())

    r = c.post(PLAN, json={"host": wid, "engines": [_choice()]})
    assert r.status_code == 200, r.text

    assert len(_engine_jobs()) == before_jobs
    assert set(DATA_DIR.rglob("*")) == before_files
    with SessionLocal() as db:
        assert len(db.scalars(select(Audit.id).where(Audit.target == wid)).all()) == before_audits


def test_uv_plan_has_exactly_two_steps_per_engine(c: TestClient):
    wid = _host(_inventory())
    r = c.post(PLAN, json={"host": wid, "engines": [_choice(OLLAMA, "docker"), _choice()]})
    assert r.status_code == 200, r.text
    plan = r.json()

    assert plan["host"] == wid
    assert plan["disk_free_gb"] == 812.5
    assert plan["noop"] is False and plan["blocked"] == []
    vllm = next(step for step in plan["steps"] if step["id"] == "vllm")
    target = f"vllm-{VLLM['version']}"
    assert vllm["status"] == "install" and vllm["disk_mb"] == VLLM["disk_mb"]
    assert vllm["argv"] == [
        ["uv", "venv", target],
        ["uv", "pip", "install", "--python", f"{target}/bin/python", f"vllm=={VLLM['version']}"],
    ]

    assert plan["total_disk_mb"] == VLLM["disk_mb"] + OLLAMA["disk_mb"]
    assert plan["disk_after_gb"] == round(812.5 - plan["total_disk_mb"] / 1024, 1)
    for step in plan["steps"]:
        for argv in step["argv"]:
            for part in argv:
                assert not any(token in part for token in (";", "|", "&&", "$(")), part


def test_pip_and_docker_argv_are_the_same_fixed_shape(c: TestClient):
    wid = _host(_inventory())
    r = c.post(PLAN, json={"host": wid,
                           "engines": [_choice(VLLM, "pip"), _choice(OLLAMA, "docker")]})
    assert r.status_code == 200, r.text
    steps = {step["id"]: step for step in r.json()["steps"]}

    target = f"vllm-{VLLM['version']}"
    assert steps["vllm"]["argv"] == [
        ["python", "-m", "venv", target],
        [f"{target}/bin/python", "-m", "pip", "install", "--no-input", VLLM["package"]],
    ]
    assert steps["ollama"]["argv"] == [["docker", "pull", OLLAMA["container"]]]


def test_an_installed_engine_is_a_noop_step(c: TestClient):
    installed = [{"id": "vllm", "version": VLLM["version"], "runtime": "uv", "ok": True}]
    wid = _host(_inventory(engines=installed))

    plan = c.post(PLAN, json={"host": wid, "engines": [_choice()]}).json()
    assert plan["noop"] is True
    assert plan["steps"][0]["status"] == "installed"
    assert plan["steps"][0]["argv"] == []
    assert plan["total_disk_mb"] == 0
    assert plan["disk_after_gb"] == 812.5

    r = c.post(INSTALL, json={"host": wid, "engines": [_choice()],
                              "plan_id": plan["plan_id"], "confirm": True})
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "Nothing to install."
    assert _engine_jobs() == []


def test_unknown_engine_or_runtime_is_422(c: TestClient):
    wid = _host(_inventory())
    for choice in (_choice(VLLM, "binary"), _choice(OLLAMA, "uv"),
                   {"id": "nope", "version": "1.0.0", "runtime": "uv"},
                   _choice(VLLM, "uv", version="0.33.0")):
        r = c.post(PLAN, json={"host": wid, "engines": [choice]})
        assert r.status_code == 422, (choice, r.text)
        r = c.post(INSTALL, json={"host": wid, "engines": [choice],
                                  "plan_id": "0" * 16, "confirm": True})
        assert r.status_code == 422, (choice, r.text)
    assert _engine_jobs() == []


def test_install_requires_confirm(c: TestClient):
    wid = _host(_inventory())
    plan = c.post(PLAN, json={"host": wid, "engines": [_choice()]}).json()

    r = c.post(INSTALL, json={"host": wid, "engines": [_choice()],
                              "plan_id": plan["plan_id"], "confirm": False})
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["plan"]["plan_id"] == plan["plan_id"]
    assert _engine_jobs() == []


def test_a_stale_plan_id_is_409(c: TestClient):
    wid = _host(_inventory())
    plan = c.post(PLAN, json={"host": wid, "engines": [_choice()]}).json()
    _set_inventory(wid, _inventory(engines=[{"id": "llamacpp", "version": "1.0.0",
                                             "runtime": "uv", "ok": True}]))

    r = c.post(INSTALL, json={"host": wid, "engines": [_choice()],
                              "plan_id": plan["plan_id"], "confirm": True})
    assert r.status_code == 409, r.text
    assert "stale" in r.json()["detail"]["error"].lower()
    assert r.json()["detail"]["plan"]["plan_id"] != plan["plan_id"]
    assert _engine_jobs() == []


def test_one_job_per_host(c: TestClient):
    a, b = _host(_inventory()), _host(_inventory())
    for wid in (a, b):
        plan = c.post(PLAN, json={"host": wid, "engines": [_choice()]}).json()
        r = c.post(INSTALL, json={"host": wid, "engines": [_choice()],
                                  "plan_id": plan["plan_id"], "confirm": True})
        assert r.status_code == 200, r.text
        job = r.json()["job"]
        assert job["kind"] == "engine_apply" and job["status"] == "queued"

    # the second host installed while the first host's job was still queued
    first = c.post(PLAN, json={"host": a, "engines": [_choice()]}).json()
    r = c.post(INSTALL, json={"host": a, "engines": [_choice()],
                              "plan_id": first["plan_id"], "confirm": True})
    assert r.status_code == 409, r.text
    busy = r.json()["detail"]
    assert busy["error"] == "An engine job is already running on this host."
    assert busy["job_id"] in r.text and busy["job_id"]


def test_uninstall_requires_the_engine_to_be_installed(c: TestClient):
    empty = _host(_inventory())
    r = c.post(UNINSTALL, json={"host": empty, "id": "vllm", "confirm": True})
    assert r.status_code == 404, r.text
    assert _engine_jobs() == []

    installed = _host(_inventory(engines=[{"id": "vllm", "version": VLLM["version"],
                                          "runtime": "uv", "ok": True}]))
    r = c.post(UNINSTALL, json={"host": installed, "id": "vllm", "confirm": True})
    assert r.status_code == 200, r.text
    job = r.json()["job"]
    assert job["params"]["action"] == "uninstall"
    assert job["params"]["engines"][0]["argv"] == [["rm", "-rf", f"vllm-{VLLM['version']}"]]

    containerised = _host(_inventory(engines=[{"id": "ollama", "version": OLLAMA["version"],
                                               "runtime": "docker", "ok": True}]))
    r = c.post(UNINSTALL, json={"host": containerised, "id": "ollama", "confirm": True})
    assert r.status_code == 200, r.text
    assert r.json()["job"]["params"]["engines"][0]["argv"] == [["docker", "rmi", OLLAMA["container"]]]


def test_audit_rows_name_host_engine_and_job_and_no_secret(c: TestClient):
    install_host = _host(_inventory())
    plan = c.post(PLAN, json={"host": install_host, "engines": [_choice()]}).json()
    job = c.post(INSTALL, json={"host": install_host, "engines": [_choice()],
                                "plan_id": plan["plan_id"], "confirm": True}).json()["job"]

    uninstall_host = _host(_inventory(engines=[{"id": "vllm", "version": VLLM["version"],
                                                "runtime": "uv", "ok": True}]))
    removed = c.post(UNINSTALL, json={"host": uninstall_host, "id": "vllm",
                                      "confirm": True}).json()["job"]

    with SessionLocal() as db:
        rows = list(db.scalars(select(Audit).where(Audit.target.in_([install_host, uninstall_host]))
                               .order_by(Audit.created)))
    assert [row.action for row in rows] == ["inference.engine_install", "inference.engine_uninstall"]
    assert [row.target for row in rows] == [install_host, uninstall_host]
    assert rows[0].meta["engines"] == ["vllm"] and rows[0].meta["plan_id"] == plan["plan_id"]
    assert rows[0].meta["job_id"] == job["id"]
    assert rows[1].meta["job_id"] == removed["id"]
    dumped = json.dumps([row.meta for row in rows])
    assert "hf_" not in dumped
    assert "/" not in dumped and "\\" not in dumped          # no absolute path in the audit


def test_member_is_403_foreign_host_is_404_flag_off_is_404(c: TestClient):
    wid = _host(_inventory())
    body = {"host": wid, "engines": [_choice()]}

    member = TestClient(app)
    member.headers.update(login_as(member, "labeler@labeldesk.dev"))
    assert member.post(PLAN, json=body).status_code == 403
    assert member.post(UNINSTALL, json={"host": wid, "id": "vllm", "confirm": True}).status_code == 403

    assert c.post(PLAN, json={**body, "host": "no-such-host-anywhere"}).status_code == 404
    assert c.post(UNINSTALL, json={"host": "no-such-host-anywhere", "id": "vllm",
                                   "confirm": True}).status_code == 404

    with SessionLocal() as db:
        flags.set_flag(db, _ws_id(), "task_inference", False)
        db.commit()
    assert c.post(PLAN, json=body).status_code == 404
    assert c.post(INSTALL, json={**body, "plan_id": "x", "confirm": True}).status_code == 404
