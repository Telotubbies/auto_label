"""T-1018: a crafted value in any hub field is refused, and a refused request creates no job.

`PAYLOADS` is the one table of hostile strings the card names, so a new field is a row plus one
parametrisation and a new payload is one line. Every case asserts the status *and* that nothing was
written: a 400 that still enqueued a job is the bug this suite exists for. The service is attacked
directly as well as through the route, because Pydantic on the route is not the only way in.
"""
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Audit, Job, Workspace, WorkspaceFlag, Worker
from app.routers.inference import InstallIn, ModelDownloadIn
from app.services import flags, inference_catalog, inference_models, inference_plan
from conftest import login

WS = "labeldesk-demo"
BASE = f"/api/ws/{WS}/inference"
PLAN = f"{BASE}/engines/plan"
INSTALL = f"{BASE}/engines/install"
MODEL_PLAN = f"{BASE}/models/plan"
DOWNLOAD = f"{BASE}/models/download"
VLLM = inference_catalog.engine("vllm")
ENGINE = {"id": "vllm", "version": VLLM["version"], "runtime": "uv"}

# One table: the shell, command-substitution, traversal, newline and overlong forms the card names.
PAYLOADS = [
    "; rm -rf /",
    "$(id)",
    "`id`",
    "&& curl evil",
    "../x",
    "vllm==1.0\nrm",
    "A" * 200,
]
ENGINE_FIELDS = ("id", "version", "runtime")
MODEL_FIELDS = ("id", "variant")


def _ws_id() -> str:
    with SessionLocal() as db:
        return db.scalar(select(Workspace.id).where(Workspace.slug == WS))


def _host(inventory: dict | None = None) -> str:
    """A host row the plan and the model routes read; a huge last_seen keeps it online."""
    wid = f"gpu-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        db.add(Worker(id=wid, host=wid, kinds=["engine_apply"], started=0.0, last_seen=9e12,
                      inventory=inventory if inventory is not None else _inventory()))
        db.commit()
    return wid


def _inventory() -> dict:
    """A report shaped like apps/worker/labeldesk_worker/inventory.py:collect()."""
    return {"os": "Linux", "arch": "x86_64", "cuda": "12.9", "hf_token": True,
            "gpus": [{"name": "NVIDIA GeForce RTX 4090", "vram_mb": 24564,
                      "driver": "575.51", "cuda": "12.9"}],
            "disk": {"models_free_gb": 812.5, "models_total_gb": 1863.0},
            "engines": [], "models": []}


def _jobs() -> list[Job]:
    with SessionLocal() as db:
        rows = db.scalars(select(Job)).all()
        for row in rows:
            db.expunge(row)
        return rows


def _audits() -> list[Audit]:
    with SessionLocal() as db:
        rows = db.scalars(select(Audit)).all()
        for row in rows:
            db.expunge(row)
        return rows


def _engine_body(field: str, payload: str, host: str) -> dict:
    choice = {"id": ENGINE["id"], "version": ENGINE["version"], "runtime": ENGINE["runtime"]}
    choice[field] = payload
    return {"host": host, "engines": [choice]}


def _model_body(field: str, payload: str, host: str) -> dict:
    body = {"host": host, "id": "qwen2.5-vl-7b", "variant": "bf16"}
    body[field] = payload
    return body


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
    """No host or engine job of this module survives into another one."""
    with SessionLocal() as db:
        before = set(db.scalars(select(Worker.id)))
    yield
    with SessionLocal() as db:
        for wid in set(db.scalars(select(Worker.id))) - before:
            db.delete(db.get(Worker, wid))
        db.execute(Job.__table__.delete().where(Job.kind.in_(("engine_apply", "model_pull"))))
        db.execute(WorkspaceFlag.__table__.delete().where(WorkspaceFlag.key == "task_inference"))
        db.commit()


@pytest.mark.parametrize("field", ENGINE_FIELDS)
@pytest.mark.parametrize("payload", PAYLOADS)
def test_engine_fields_refuse_shell_and_path_payloads(c: TestClient, field, payload):
    """Plan and install both 422 the field, and neither writes a job nor an audit row."""
    host = _host()
    jobs, audits = len(_jobs()), len(_audits())

    plan = _engine_body(field, payload, host)
    for url, body in ((PLAN, plan),
                      (INSTALL, plan | {"plan_id": "x" * 16, "confirm": True})):
        r = c.post(url, json=body)
        assert r.status_code in (400, 422), f"{url} answered {r.status_code} for {payload!r}"

    assert not any(payload in json.dumps({"t": row.target, "m": row.meta}) for row in _audits())
    assert len(_jobs()) == jobs, f"{payload!r} in {field} created a job"
    assert len(_audits()) == audits, f"{payload!r} in {field} reached the audit log"

    # The service, not only the route: a hand-built selection must fail the same way.
    with pytest.raises(inference_plan.InvalidSelection):
        inference_plan.build({"id": host, "online": True}, [{"id": ENGINE["id"],
                              "version": ENGINE["version"], "runtime": "uv", field: payload}],
                             _inventory())


@pytest.mark.parametrize("field", MODEL_FIELDS)
@pytest.mark.parametrize("payload", ["../../x", "https://evil/x", "owner/name/extra", ""])
def test_model_fields_refuse_traversal_and_urls(c: TestClient, field, payload):
    """A model id or variant is a catalogue key: a path, a URL or an empty string is refused."""
    host = _host()
    jobs = len(_jobs())
    body = _model_body(field, payload, host) | {"confirm": True}

    for url, allowed in ((DOWNLOAD, (400, 422)), (MODEL_PLAN, (400, 404, 422))):
        r = c.post(url, json=body)
        assert r.status_code in allowed, f"{url} answered {r.status_code} for {payload!r}"

    assert len(_jobs()) == jobs, f"{payload!r} in {field} created a job"

    # The service, not only the route: the lookup raises instead of building a path or a URL.
    with pytest.raises(KeyError):
        inference_models.model(payload) if field == "id" else inference_models.variant(
            inference_models.model("qwen2.5-vl-7b"), payload)


@pytest.mark.parametrize("host", ["../../etc", "/etc/passwd", "C:\\Windows", "host/../x", "h" * 4096])
def test_host_and_job_ids_are_not_interpolated(c: TestClient, host):
    """A host is a lookup key, never a path: 404/422, never a 500, and nothing is written."""
    real = _host()
    jobs, audits = len(_jobs()), len(_audits())
    big = "j" * 4096

    cases = [
        ("GET", f"{BASE}/models", {"params": {"host": host}}),
        ("GET", f"{BASE}/engines", {"params": {"host": host}}),
        ("GET", f"{BASE}/segmentation", {"params": {"host": host}}),
        ("POST", MODEL_PLAN, {"json": {"host": host, "id": "qwen2.5-vl-7b", "variant": "bf16"}}),
        ("GET", f"{BASE}/jobs/{big}", {}),
        ("POST", f"{BASE}/jobs/{big}/cancel", {}),
        ("DELETE", f"{BASE}/models/{big}", {"params": {"host": real, "variant": "bf16",
                                                       "confirm": True}}),
        ("POST", MODEL_PLAN, {"json": {"host": big, "id": "qwen2.5-vl-7b", "variant": "bf16"}}),
    ]
    for method, url, kw in cases:
        r = c.request(method, url, **kw)
        assert r.status_code in (404, 422), f"{method} {url[:90]} answered {r.status_code}"

    assert len(_jobs()) == jobs and len(_audits()) == audits


def test_oversized_body_is_refused(c: TestClient):
    """A 2 MB body is refused by validation before the plan service runs, and queues nothing."""
    jobs = len(_jobs())
    body = {"host": "h" * 2_000_000, "engines": [ENGINE], "plan_id": "x" * 16, "confirm": True}

    r = c.post(INSTALL, json=body)

    assert r.status_code in (413, 422), f"an oversized body answered {r.status_code}"
    assert len(_jobs()) == jobs
    assert not any(row.action.startswith("inference.") for row in _audits())


@pytest.mark.parametrize("bad", ["true", 1, "1", None, [], "yes"])
def test_confirm_must_be_a_boolean_true(c: TestClient, bad):
    """`confirm` is a gate: a string, a number or null is a 422, never a coerced yes."""
    host = _host()
    jobs = len(_jobs())
    plan = c.post(PLAN, json={"host": host, "engines": [ENGINE]})
    assert plan.status_code == 200, plan.text

    bodies = {
        DOWNLOAD: _model_body("id", "qwen2.5-vl-7b", host) | {"confirm": bad},
        INSTALL: {"host": host, "engines": [ENGINE], "plan_id": plan.json()["plan_id"],
                  "confirm": bad},
    }
    for url, body in bodies.items():
        r = c.post(url, json=body)
        assert r.status_code in (400, 422), f"{url} accepted confirm={bad!r} ({r.status_code})"
    assert len(_jobs()) == jobs, f"confirm={bad!r} still queued a job"

    # The route model itself is strict, so a hand-built body cannot skip the gate either.
    with pytest.raises(ValidationError):
        ModelDownloadIn(host=host, id="qwen2.5-vl-7b", variant="bf16", confirm=bad)
    with pytest.raises(ValidationError):
        InstallIn(host=host, engines=[ENGINE], plan_id="x" * 16, confirm=bad)

    r = c.post(DOWNLOAD, json=_model_body("id", "qwen2.5-vl-7b", host) | {"confirm": True})
    assert r.status_code == 200, r.text
    assert len(_jobs()) == jobs + 1
