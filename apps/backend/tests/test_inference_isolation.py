"""T-1018: another workspace's ids are 404, the flag gates every route, and no secret or path leaks.

The hub belongs to one deployment workspace (`LD_INFERENCE_WORKSPACE`): a second workspace, its
admin and its member all get 404 — never 403, which would confirm the id exists — and neither
workspace changes. The flag is checked on the router's own route table, so a route a later card
appends is covered without editing this file. The token checks seed a token-shaped value where a
host could echo one and then read every surface an admin can reach.
"""
import json
import re
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Audit, Job, Member, Project, User, Worker, Workspace, WorkspaceFlag
from app.routers import inference
from app.services import flags, inference_catalog
from conftest import login

WS = "labeldesk-demo"
BASE = f"/api/ws/{WS}/inference"
WORKER_AUTH = {"X-Worker-Token": "test-worker-token-0123456789abcdef"}
# A token-shaped value that is not a credential: long enough for every redaction pattern in the app.
SECRET = "hf_" + "S3CRETVALUE" * 3
TOKENISH = re.compile(r"hf_[A-Za-z0-9_-]{12,}")
ENGINE = {"id": "vllm", "version": inference_catalog.engine("vllm")["version"], "runtime": "uv"}


def _ws_id(slug: str = WS) -> str:
    with SessionLocal() as db:
        return db.scalar(select(Workspace.id).where(Workspace.slug == slug))


def _inventory(**over) -> dict:
    """A report shaped like apps/worker/labeldesk_worker/inventory.py:collect()."""
    inv = {"os": "Linux", "arch": "x86_64", "cuda": "12.9", "hf_token": True,
           "gpus": [{"name": "NVIDIA GeForce RTX 4090", "vram_mb": 24564,
                     "driver": "575.51", "cuda": "12.9"}],
           "disk": {"models_free_gb": 812.5, "models_total_gb": 1863.0},
           "engines": [], "models": []}
    inv.update(over)
    return inv


def _host(inventory: dict | None = None) -> str:
    wid = f"gpu-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        db.add(Worker(id=wid, host=wid, kinds=["engine_apply"], started=0.0, last_seen=9e12,
                      inventory=_inventory() if inventory is None else inventory))
        db.commit()
    return wid


def _plan(c: TestClient, host: str) -> dict:
    r = c.post(f"{BASE}/engines/plan", json={"host": host, "engines": [ENGINE]})
    assert r.status_code == 200, r.text
    return r.json()


def _install(c: TestClient, host: str) -> dict:
    plan = _plan(c, host)
    r = c.post(f"{BASE}/engines/install", json={"host": host, "engines": [ENGINE],
                                                "plan_id": plan["plan_id"], "confirm": True})
    assert r.status_code == 200, r.text
    return r.json()["job"]


def _snapshot(host: str) -> dict:
    """Everything a cross-workspace request must leave alone, as comparable data."""
    with SessionLocal() as db:
        jobs = sorted((row.id, row.status) for row in db.scalars(select(Job)).all())
        audits = len(db.scalars(select(Audit)).all())
        worker = db.get(Worker, host)
        project = db.scalar(select(Project).where(Project.slug == "ppe-detection"))
        return {"jobs": jobs, "audits": audits,
                "inventory": None if worker is None else worker.inventory,
                "project": None if project is None else (project.id, project.updated)}


def _cross_requests(slug: str, host: str, job_id: str) -> list[tuple]:
    """Every read and write the hub offers, aimed at workspace A's ids from workspace B."""
    base = f"/api/ws/{slug}/inference"
    model = {"id": "qwen2.5-vl-7b", "variant": "bf16"}
    return [
        ("GET", f"{base}/hosts", {}),
        ("GET", f"{base}/catalog", {}),
        ("GET", f"{base}/engines", {"params": {"host": host}}),
        ("GET", f"{base}/models", {"params": {"host": host}}),
        ("GET", f"{base}/segmentation", {"params": {"host": host, "project": "ppe-detection"}}),
        ("GET", f"{base}/jobs", {}),
        ("GET", f"{base}/jobs/{job_id}", {}),
        ("POST", f"{base}/jobs/{job_id}/cancel", {}),
        ("POST", f"{base}/models/plan", {"json": {"host": host, **model}}),
        ("POST", f"{base}/models/download", {"json": {"host": host, **model, "confirm": True}}),
        ("DELETE", f"{base}/models/{model['id']}",
         {"params": {"host": host, "variant": "bf16", "confirm": True}}),
        ("POST", f"{base}/engines/plan", {"json": {"host": host, "engines": [ENGINE]}}),
        ("POST", f"{base}/engines/install",
         {"json": {"host": host, "engines": [ENGINE], "plan_id": "x" * 16, "confirm": True}}),
        ("POST", f"{base}/engines/uninstall",
         {"json": {"host": host, "id": "vllm", "confirm": True}}),
        ("POST", f"{base}/models/ollama/pull",
         {"json": {"host": host, "tag": "qwen3:4b", "confirm": True}}),
        ("POST", f"{base}/estimate", {"json": {
            "model": {"params_b": 7.6, "layers": 28, "kv_heads": 4, "head_dim": 128},
            "quant": "bf16", "context": 8192, "batch": 4, "users": 1,
            "gpu": {"preset": "rtx4090"}, "engine": "vllm"}}),
    ]


@pytest.fixture(scope="module")
def c():
    client = TestClient(app)
    client.headers.update(login(client))
    yield client


@pytest.fixture(scope="module")
def other():
    """A second workspace the same account belongs to, with the hub flag on."""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
        ws = Workspace(slug=f"other-{uuid.uuid4().hex[:8]}", name="Other", owner_id=user.id)
        db.add(ws)
        db.flush()
        db.add(Member(workspace_id=ws.id, user_id=user.id, role="admin"))
        flags.set_flag(db, ws.id, "task_inference", True)
        db.commit()
        out = {"id": ws.id, "slug": ws.slug}
    yield out
    with SessionLocal() as db:
        db.execute(WorkspaceFlag.__table__.delete().where(WorkspaceFlag.workspace_id == out["id"]))
        db.execute(Member.__table__.delete().where(Member.workspace_id == out["id"]))
        db.execute(Workspace.__table__.delete().where(Workspace.id == out["id"]))
        db.commit()


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
        db.execute(Job.__table__.delete().where(Job.kind.in_(("engine_apply", "model_pull"))))
        db.execute(WorkspaceFlag.__table__.delete().where(WorkspaceFlag.key == "task_inference"))
        db.commit()


def test_cross_workspace_host_job_and_project_are_404(c: TestClient, other, monkeypatch):
    """16 requests carrying workspace A's ids from workspace B: 404 each, and nothing changes."""
    host = _host()
    job = _install(c, host)
    monkeypatch.setenv("LD_INFERENCE_WORKSPACE", _ws_id())      # the hub belongs to A
    before = _snapshot(host)

    requests = _cross_requests(other["slug"], host, job["id"])
    assert len(requests) >= 10, "the card names ten ids; keep the table complete"
    for method, url, kw in requests:
        r = c.request(method, url, **kw)
        assert r.status_code == 404, f"{method} {url} answered {r.status_code}, not 404"
        assert "forbidden" not in r.text.lower() and "requires" not in r.text.lower()

    assert _snapshot(host) == before
    with SessionLocal() as db:
        assert not db.scalars(select(Job).where(Job.workspace_id == other["id"])).all()
        assert not db.scalars(select(Audit).where(Audit.workspace_id == other["id"])).all()


ROUTES = sorted({(sorted(route.methods)[0], route.path) for route in inference.router.routes})


@pytest.mark.parametrize("method,path", ROUTES, ids=[f"{m} {p}" for m, p in ROUTES])
def test_flag_off_is_404_on_every_route(c: TestClient, method, path):
    """Every route the router carries answers 404 when `task_inference` is off for the workspace."""
    assert len(ROUTES) >= 16, "the route table is the coverage: a filtered-out route would pass"
    with SessionLocal() as db:
        flags.set_flag(db, _ws_id(), "task_inference", False)
        db.commit()

    url = (path.replace("{ws}", WS).replace("{jid}", "unknown-job")
           .replace("{mid}", "unknown-model"))
    kw = {"params": {"host": "unknown-host"}} if method in ("GET", "DELETE") else {"json": {}}
    r = c.request(method, url, **kw)

    assert r.status_code == 404, f"{method} {path} answered {r.status_code} with the flag off"


def test_token_never_appears_in_any_response(c: TestClient, monkeypatch):
    """A token in the worker's log or environment reaches no response, and no stored row."""
    monkeypatch.setenv("HF_TOKEN", SECRET)
    host = _host(_inventory(hf_token=True))
    job = _install(c, host)
    posted = TestClient(app).post(f"/api/worker/jobs/{job['id']}/progress", headers=WORKER_AUTH,
                                  json={"progress": 40, "phase": "installing vllm",
                                        "log": [f"pip using {SECRET}",
                                                f"cache /home/alice/{SECRET}"]})
    assert posted.status_code == 200, posted.text

    # Every read, plus the read-only POSTs; the write POSTs return the same job view as /jobs/{id}.
    reads = [(method, url, kw) for method, url, kw in _cross_requests(WS, host, job["id"])
             if method == "GET"]
    reads += [("POST", f"{BASE}/estimate", {"json": {
        "model": {"params_b": 7.6, "layers": 28, "kv_heads": 4, "head_dim": 128},
        "quant": "bf16", "context": 8192, "batch": 4, "users": 1,
        "gpu": {"preset": "rtx4090"}, "engine": "vllm"}}),
        ("POST", f"{BASE}/engines/plan", {"json": {"host": host, "engines": [ENGINE]}}),
              ("POST", f"{BASE}/models/plan",
               {"json": {"host": host, "id": "qwen2.5-vl-7b", "variant": "bf16"}})]
    for method, url, kw in reads:
        r = c.request(method, url, **kw)
        assert r.status_code == 200, f"{method} {url} answered {r.status_code}"
        assert SECRET not in r.text, f"{method} {url} echoed the token"
        assert not TOKENISH.search(r.text), f"{method} {url} carries a token-shaped value"

    with SessionLocal() as db:
        stored = json.dumps(db.get(Job, job["id"]).result)
        assert SECRET not in stored and not TOKENISH.search(stored)


def test_audit_carries_no_argv_and_no_path(c: TestClient):
    """The audit row names host, engine and job — never the argv, a machine path or a token."""
    host = _host()
    job = _install(c, host)

    with SessionLocal() as db:
        rows = db.scalars(select(Audit).where(Audit.workspace_id == _ws_id())).all()
        assert rows, "an install writes one audit row"
        installs = [row for row in rows if row.action == "inference.engine_install"]
        assert installs, "the install is the action this test reads"
        assert installs[-1].meta.get("job_id") == job["id"]
        assert "vllm" in installs[-1].meta.get("engines", [])

        for row in rows:
            text = json.dumps({"action": row.action, "target": row.target, "meta": row.meta})
            assert "argv" not in text, f"{row.action} carries an argv"
            assert "/home/" not in text and "C:\\Users\\" not in text
            assert not TOKENISH.search(text), f"{row.action} carries a token"
