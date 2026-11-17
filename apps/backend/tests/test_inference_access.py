"""T-1017: three locks on one inference action — role, deployment scope and a minute's budget.

Every hub route answers 404 with the flag off and 404 outside the deployment's scope; every route
but the calculator answers 403 to a member or a labeler; every write needs ``confirm``; a fifth
request in a minute is 429 with a retry hint; and each enqueue leaves exactly one audit row that
names the host, the catalogue id, the version or variant and the job, with no token and no absolute
path. A host id this deployment does not list is 404, so a guessed id from another deployment never
reaches a worker. Worker text is an input boundary: the redaction T-1008 shipped is asserted here on
the failure path as well as the log tail.
"""
import json
import os
import time
import uuid

os.environ.setdefault("LD_WORKER_TOKEN", "test-worker-token-0123456789abcdef")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.bootstrap import DEMO_PW
from app.db import SessionLocal
from app.main import app
from app.models import Audit, Job, Member, User, Worker, Workspace, WorkspaceFlag
from app.routers import inference
from app.security import hash_password
from app.services import flags, inference_catalog, inference_access
from conftest import login

WS = "labeldesk-demo"
BASE = f"/api/ws/{WS}/inference"
AUTH = {"X-Worker-Token": "test-worker-token-0123456789abcdef"}
MODEL, VARIANT = "qwen2.5-vl-7b", "bf16"
VLLM = inference_catalog.engine("vllm")
START = time.time()

# The PLAN §2.3 worked example: the one body the estimator always accepts.
ESTIMATE = {"model": {"params_b": 7.6, "layers": 28, "kv_heads": 4, "head_dim": 128},
            "quant": "bf16", "context": 8192, "batch": 4, "users": 1,
            "gpu": {"preset": "rtx4090"}, "gpu_count": 1, "tensor_parallel": 1,
            "engine": "vllm", "usable": 0.9}


def _ws_id() -> str:
    with SessionLocal() as db:
        return db.scalar(select(Workspace.id).where(Workspace.slug == WS))


def _owner_id() -> str:
    """The demo owner's id: the account every route call in this module belongs to."""
    with SessionLocal() as db:
        return db.scalar(select(Workspace.owner_id).where(Workspace.slug == WS))


def _finish(job_id: str) -> None:
    """A queued job is the busy host; a completed one lets the next action on that host through."""
    with SessionLocal() as db:
        row = db.get(Job, job_id)
        row.status, row.finished = "done", time.time()
        db.commit()


def _inventory(engines: list | None = None, models: list | None = None,
               hf_token: bool = True) -> dict:
    """A report shaped like the worker's inventory, on a host that fits every pin."""
    return {"os": "Linux", "arch": "x86_64", "python": "3.11.9",
            "gpus": [{"name": "NVIDIA GeForce RTX 4090", "vram_mb": 24564,
                      "driver": "575.51", "cuda": "12.9"}],
            "cuda": "12.9", "docker": True, "hf_token": hf_token,
            "disk": {"models_free_gb": 812.5, "models_total_gb": 1863.0},
            "engines": engines or [], "models": models or []}


def _host(engines: list | None = None, models: list | None = None) -> str:
    """A host row the hub can read; a huge last_seen keeps it online for the whole test."""
    wid = f"acc-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        db.add(Worker(id=wid, host=wid, kinds=["engine_apply"], started=0.0, last_seen=9e12,
                      inventory=_inventory(engines, models)))
        db.commit()
    return wid


def _installed_engine() -> list:
    return [{"id": "vllm", "version": VLLM["version"], "runtime": "uv", "ok": True}]


def _installed_model() -> list:
    return [{"id": MODEL, "variant": VARIANT, "bytes": 1000}]


def _table(host: str) -> dict[str, tuple[str, str, str, dict]]:
    """Every hub route: name -> (method, router template, path to call, request kwargs)."""
    install = {"host": host, "engines": [{"id": "vllm", "version": VLLM["version"],
                                          "runtime": "uv"}]}
    download = {"host": host, "id": MODEL, "variant": VARIANT, "confirm": True}
    return {
        "list_hosts": ("GET", "/hosts", "/hosts", {}),
        "catalog": ("GET", "/catalog", "/catalog", {}),
        "engines": ("GET", "/engines", "/engines", {"params": {"host": host}}),
        "models": ("GET", "/models", "/models", {"params": {"host": host}}),
        "segmentation": ("GET", "/segmentation", "/segmentation", {"params": {"host": host}}),
        "jobs": ("GET", "/jobs", "/jobs", {}),
        "job": ("GET", "/jobs/{jid}", "/jobs/no-such-job", {}),
        "cancel": ("POST", "/jobs/{jid}/cancel", "/jobs/no-such-job/cancel", {}),
        "estimate": ("POST", "/estimate", "/estimate", {"json": ESTIMATE}),
        "plan_engines": ("POST", "/engines/plan", "/engines/plan", {"json": install}),
        "install": ("POST", "/engines/install", "/engines/install",
                    {"json": {**install, "plan_id": "0" * 16, "confirm": True}}),
        "uninstall": ("POST", "/engines/uninstall", "/engines/uninstall",
                      {"json": {"host": host, "id": "vllm", "confirm": True}}),
        "plan_model": ("POST", "/models/plan", "/models/plan",
                       {"json": {"host": host, "id": MODEL, "variant": VARIANT}}),
        "download": ("POST", "/models/download", "/models/download", {"json": download}),
        "pull": ("POST", "/models/ollama/pull", "/models/ollama/pull",
                 {"json": {"host": host, "tag": "qwen3:4b", "confirm": True}}),
        "remove": ("DELETE", "/models/{mid}", f"/models/{MODEL}",
                   {"params": {"host": host, "variant": VARIANT, "confirm": "true"}}),
    }


ROUTE_NAMES = tuple(_table("no-such-host"))
ADMIN_ROUTES = tuple(name for name in ROUTE_NAMES if name != "estimate")   # PLAN §12.5


def _call(client: TestClient, entry: tuple[str, str, str, dict]):
    method, _, path, kwargs = entry
    return client.request(method, BASE + path, **kwargs)


def _jobs() -> list[Job]:
    with SessionLocal() as db:
        return list(db.scalars(select(Job).where(Job.kind.in_(("engine_apply", "model_pull")))))


@pytest.fixture(scope="module")
def c():
    client = TestClient(app)
    client.headers.update(login(client))
    yield client


@pytest.fixture(scope="module")
def accounts():
    """The two accounts the seed does not provide: a plain member and a second, non-owner admin."""
    made = {}
    with SessionLocal() as db:
        ws_id = db.scalar(select(Workspace.id).where(Workspace.slug == WS))
        for role, email in (("member", "member-t1017@example.test"),
                            ("admin", "admin-t1017@example.test")):
            user = User(email=email, name=role, pw_hash=hash_password(DEMO_PW),
                        email_verified=time.time())
            db.add(user)
            db.flush()
            db.add(Member(workspace_id=ws_id, user_id=user.id, role=role))
            made[role] = (user.id, email)
        db.commit()
    yield made
    with SessionLocal() as db:
        for user_id, _ in made.values():
            db.execute(Member.__table__.delete().where(Member.user_id == user_id))
            db.delete(db.get(User, user_id))
        db.commit()


def _client_for(email: str) -> TestClient:
    client = TestClient(app)
    client.headers.update(login(client, email))
    return client


@pytest.fixture(scope="module")
def as_member(accounts):
    yield _client_for(accounts["member"][1])


@pytest.fixture(scope="module")
def as_admin(accounts):
    yield _client_for(accounts["admin"][1])


@pytest.fixture(scope="module")
def as_labeler():
    yield _client_for("labeler@labeldesk.dev")


@pytest.fixture(autouse=True)
def flag_on():
    with SessionLocal() as db:
        flags.set_flag(db, _ws_id(), "task_inference", True)
        db.commit()
    yield


@pytest.fixture(autouse=True)
def _clean():
    """No host, job, audit or flag of this module survives into another one."""
    with SessionLocal() as db:
        before = set(db.scalars(select(Worker.id)))
    yield
    with SessionLocal() as db:
        for wid in set(db.scalars(select(Worker.id))) - before:
            db.delete(db.get(Worker, wid))
        db.execute(Job.__table__.delete().where(Job.kind.in_(("engine_apply", "model_pull")),
                                                Job.created >= START))
        db.execute(Audit.__table__.delete().where(Audit.action.like("inference.%"),
                                                  Audit.created >= START))
        db.execute(WorkspaceFlag.__table__.delete().where(WorkspaceFlag.key == "task_inference"))
        db.commit()


# --- the locks --------------------------------------------------------------------------------
@pytest.mark.parametrize("name", ADMIN_ROUTES)
def test_every_inference_route_refuses_a_member(name, as_member, as_labeler, c, as_admin):
    """Every hub route but the calculator is workspace-admin work: no member, no labeler, no half."""
    entry = _table("no-such-host")[name]

    assert _call(as_member, entry).status_code == 403
    assert _call(as_labeler, entry).status_code == 403
    assert _call(c, entry).status_code != 403                 # owner
    assert _call(as_admin, entry).status_code != 403           # a non-owner admin


def test_the_calculator_stays_open_to_members(as_member, c):
    """PLAN §12.5: a member reads the estimate; it reads no host, no catalogue row and stores nothing."""
    r = _call(as_member, _table("no-such-host")["estimate"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["fits"] is True
    assert "hosts" not in body and "inventory" not in json.dumps(body)


def test_every_route_is_404_outside_the_configured_scope(c, monkeypatch, as_member):
    """One deployment serves one hub: pinned elsewhere, every route is a 404 — never a 403."""
    monkeypatch.setenv("LD_INFERENCE_WORKSPACE", f"scope-{uuid.uuid4().hex[:8]}")
    for name in ROUTE_NAMES:
        assert _call(c, _table("no-such-host")[name]).status_code == 404, name
    assert _call(as_member, _table("no-such-host")["estimate"]).status_code == 404


def test_the_configured_workspace_reaches_the_same_hosts(c, monkeypatch):
    """The pinned workspace reads the deployment's hosts and installs into its own job list."""
    host = _host()
    with SessionLocal() as db:
        owner_id = db.get(Workspace, _ws_id()).owner_id
        other = Workspace(slug=f"acc-{uuid.uuid4().hex[:8]}", name="Other", owner_id=owner_id)
        db.add(other)
        db.flush()
        db.add(Member(workspace_id=other.id, user_id=owner_id, role="admin"))
        flags.set_flag(db, other.id, "task_inference", True)
        db.commit()
        other_id, other_slug = other.id, other.slug
    monkeypatch.setenv("LD_INFERENCE_WORKSPACE", other_id)
    try:
        other_base = f"/api/ws/{other_slug}/inference"
        assert c.get(f"{BASE}/hosts").status_code == 404       # A is not the hub's workspace
        hosts = c.get(f"{other_base}/hosts")
        assert hosts.status_code == 200, hosts.text
        assert host in {row["id"] for row in hosts.json()["hosts"]}

        plan = c.post(f"{other_base}/engines/plan",
                      json={"host": host, "engines": [{"id": "vllm", "runtime": "uv",
                                                       "version": VLLM["version"]}]})
        assert plan.status_code == 200, plan.text
        r = c.post(f"{other_base}/engines/install",
                   json={"host": host, "engines": [{"id": "vllm", "runtime": "uv",
                                                    "version": VLLM["version"]}],
                         "plan_id": plan.json()["plan_id"], "confirm": True})
        assert r.status_code == 200, r.text
        with SessionLocal() as db:
            assert db.get(Job, r.json()["job"]["id"]).workspace_id == other_id
    finally:
        with SessionLocal() as db:
            db.execute(Job.__table__.delete().where(Job.workspace_id == other_id))
            db.execute(WorkspaceFlag.__table__.delete().where(WorkspaceFlag.workspace_id == other_id))
            db.execute(Member.__table__.delete().where(Member.workspace_id == other_id))
            db.execute(Workspace.__table__.delete().where(Workspace.id == other_id))
            db.commit()


@pytest.mark.parametrize("name", ROUTE_NAMES)
def test_flag_off_is_404_for_every_route(name, c, as_member):
    """The rollback is one flag: no route answers, for an admin or for a member."""
    with SessionLocal() as db:
        flags.set_flag(db, _ws_id(), "task_inference", False)
        db.commit()
    entry = _table("no-such-host")[name]
    assert _call(c, entry).status_code == 404
    assert _call(as_member, entry).status_code == 404


def test_a_guessed_host_id_is_404(c):
    """A host id this deployment does not list reaches no route, and queues nothing."""
    before = len(_jobs())
    guessed = f"guessed-{uuid.uuid4().hex[:8]}"
    for name in ("engines", "models", "segmentation", "plan_engines", "install", "uninstall",
                 "plan_model", "download", "remove"):
        assert _call(c, _table(guessed)[name]).status_code == 404, name
    assert len(_jobs()) == before


# --- writes need a confirmation ----------------------------------------------------------------
def test_every_write_route_refuses_missing_confirm(c):
    """Install, uninstall, download and remove all refuse without an explicit confirmation."""
    installed = _host(_installed_engine(), _installed_model())
    install = {"host": installed, "engines": [{"id": "vllm", "version": VLLM["version"],
                                               "runtime": "uv"}]}
    before = len(_jobs())

    r = c.post(f"{BASE}/engines/install",
               json={**install, "plan_id": "0" * 16, "confirm": False})
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["plan"]["plan_id"]              # the plan is returned, not a job
    assert c.post(f"{BASE}/engines/uninstall",
                  json={"host": installed, "id": "vllm", "confirm": False}).status_code == 400
    assert c.post(f"{BASE}/models/download",
                  json={"host": installed, "id": MODEL, "variant": VARIANT,
                        "confirm": False}).status_code == 400
    assert c.delete(f"{BASE}/models/{MODEL}",
                    params={"host": installed, "variant": VARIANT}).status_code == 400

    assert len(_jobs()) == before                                # not one queued row


# --- the minute's budget -----------------------------------------------------------------------
def test_fifth_action_in_a_minute_is_429(c, as_admin):
    """Four enqueues, then a 429 with a retry hint; another admin still has their own minute."""
    installs = []
    for index in range(5):
        host = _host()
        plan = c.post(f"{BASE}/engines/plan",
                      json={"host": host, "engines": [{"id": "vllm", "runtime": "uv",
                                                       "version": VLLM["version"]}]}).json()
        r = c.post(f"{BASE}/engines/install",
                   json={"host": host, "engines": [{"id": "vllm", "runtime": "uv",
                                                    "version": VLLM["version"]}],
                         "plan_id": plan["plan_id"], "confirm": True})
        installs.append(r)
        if index < 4:
            assert r.status_code == 200, r.text

    fifth = installs[-1]
    assert fifth.status_code == 429, fifth.text
    assert fifth.json()["detail"] == "too many inference actions; wait a minute"
    assert fifth.headers["Retry-After"] == "60"

    with SessionLocal() as db:
        assert inference_access.recent_actions(db, _ws_id(), _owner_id()) == 4
        assert inference_access.recent_actions(db, _ws_id(), _owner_id(), "install") == 4
        assert inference_access.recent_actions(db, _ws_id(), _owner_id(), "download") == 0

    # The limit is per user: the other admin is not punished for this admin's minute.
    host = _host()
    plan = as_admin.post(f"{BASE}/engines/plan",
                         json={"host": host, "engines": [{"id": "vllm", "runtime": "uv",
                                                          "version": VLLM["version"]}]}).json()
    other = as_admin.post(f"{BASE}/engines/install",
                          json={"host": host, "engines": [{"id": "vllm", "runtime": "uv",
                                                           "version": VLLM["version"]}],
                                "plan_id": plan["plan_id"], "confirm": True})
    assert other.status_code == 200, other.text


# --- the audit trail ---------------------------------------------------------------------------
def test_audit_rows_carry_host_engine_and_job_and_no_secret(c, monkeypatch):
    """One row per action, naming host, catalogue id, version or variant and job — never a secret."""
    token = f"hf_{uuid.uuid4().hex}"                             # a seeded secret must not leak
    monkeypatch.setenv("HF_TOKEN", token)
    engine_host = _host()
    model_host = _host()
    plan = c.post(f"{BASE}/engines/plan",
                  json={"host": engine_host, "engines": [{"id": "vllm", "runtime": "uv",
                                                          "version": VLLM["version"]}]}).json()
    installed = c.post(f"{BASE}/engines/install",
                       json={"host": engine_host, "engines": [{"id": "vllm", "runtime": "uv",
                                                               "version": VLLM["version"]}],
                             "plan_id": plan["plan_id"], "confirm": True})
    assert installed.status_code == 200, installed.text
    downloaded = c.post(f"{BASE}/models/download",
                        json={"host": model_host, "id": MODEL, "variant": VARIANT,
                              "confirm": True})
    assert downloaded.status_code == 200, downloaded.text

    # A queued job is the busy host, so each host is let go before its second action.
    _finish(installed.json()["job"]["id"])
    _finish(downloaded.json()["job"]["id"])
    with SessionLocal() as db:
        db.get(Worker, engine_host).inventory = _inventory(_installed_engine())
        db.get(Worker, model_host).inventory = _inventory(models=_installed_model())
        db.commit()

    removed = c.post(f"{BASE}/engines/uninstall",
                     json={"host": engine_host, "id": "vllm", "confirm": True})
    assert removed.status_code == 200, removed.text
    dropped = c.delete(f"{BASE}/models/{MODEL}",
                       params={"host": model_host, "variant": VARIANT, "confirm": "true"})
    assert dropped.status_code == 200, dropped.text

    with SessionLocal() as db:
        rows = list(db.scalars(select(Audit).where(Audit.target.in_([engine_host, model_host]))
                               .order_by(Audit.created)))
    assert [row.action for row in rows] == ["inference.engine_install", "inference.model_download",
                                            "inference.engine_uninstall", "inference.model_remove"]
    assert [row.target for row in rows] == [engine_host, model_host, engine_host, model_host]
    assert all(row.user_id == _owner_id() for row in rows)
    assert rows[0].meta["host"] == engine_host
    assert rows[0].meta["engines"] == ["vllm"]
    assert rows[0].meta["versions"] == {"vllm": VLLM["version"]}
    assert rows[0].meta["job_id"] == installed.json()["job"]["id"]
    assert rows[1].meta["model"] == MODEL and rows[1].meta["variant"] == VARIANT
    assert rows[1].meta["job_id"] == downloaded.json()["job"]["id"]
    assert rows[2].meta["job_id"] == removed.json()["job"]["id"]
    assert rows[3].meta["job_id"] == dropped.json()["job"]["id"]

    dumped = json.dumps([{"target": row.target, "meta": row.meta} for row in rows])
    assert token not in dumped and "hf_" not in dumped
    assert "/home/" not in dumped and "/root/" not in dumped and ":/" not in dumped
    assert "argv" not in dumped
    assert rows[0].meta["versions"]["vllm"] == VLLM["version"]   # a pin, never a path


# --- worker text is an input boundary ----------------------------------------------------------
def test_worker_error_text_is_scrubbed_before_it_reaches_the_job(c):
    """A failure that names a token and an absolute path is stored and returned redacted."""
    host = _host()
    with SessionLocal() as db:
        job = Job(workspace_id=_ws_id(), kind="engine_apply", status="running",
                  params={"host": host, "action": "install",
                          "engines": [{"id": "vllm", "version": VLLM["version"], "runtime": "uv"}]},
                  result={}, created=time.time())
        db.add(job)
        db.commit()
        jid = job.id

    r = TestClient(app).post(f"/api/worker/jobs/{jid}/fail", headers=AUTH,
                             json={"error": "pull failed: hf_AbCdEf0123456789 denied at "
                                            "/root/.labeldesk/models"})
    assert r.status_code == 200, r.text

    with SessionLocal() as db:
        stored = db.get(Job, jid).error
    assert stored                                                   # a sentence, not an empty field
    assert "hf_" not in stored and "/root/" not in stored

    view = c.get(f"{BASE}/jobs/{jid}")
    assert view.status_code == 200, view.text
    assert "hf_" not in json.dumps(view.json()) and "/root/" not in json.dumps(view.json())

    # The log tail takes the same trip: the sentence survives, the credential does not.
    TestClient(app).post(f"/api/worker/jobs/{jid}/progress", headers=AUTH,
                         json={"progress": 10, "log": ["using hf_abc123token to pull"],
                               "phase": "pulling"})
    with SessionLocal() as db:
        job = db.get(Job, jid)
        assert job.result["log"] == ["using hf_*** to pull"]
        assert "hf_abc123token" not in json.dumps(job.result)


# --- the guard that keeps the table honest -----------------------------------------------------
def test_the_route_table_matches_the_router():
    """A new hub route must be added to the table above, or the three locks go untested on it."""
    shipped = {(method, route.path.removeprefix(inference.router.prefix))
               for route in inference.router.routes for method in route.methods
               if method in ("GET", "POST", "PUT", "PATCH", "DELETE")}
    assert shipped == {(method, template) for method, template, _, _ in _table("x").values()}
