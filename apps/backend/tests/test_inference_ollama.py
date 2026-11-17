"""T-1023: Ollama is the default engine, its tags are catalogue rows, and a pull is catalogue-only.

PLAN §12 makes Ollama the first and default engine and lists its tags beside the Hugging Face
rows. The tests below pin the three rules that keep that safe: the argv comes from the catalogue
(never from the request), a tag the catalogue does not list is a 422, and a host that already holds
one model refuses a second with the "remove the current model first" sentence. No real Ollama runs
here: the pull is a queued engine job, and the worker's HTTP fake lives in the worker test.
"""
import os
import tempfile
import uuid

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-inference-ollama-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Job, Worker, Workspace
from app.services import flags, inference_catalog, inference_estimate, inference_models, inference_plan
from conftest import login, login_as

WS = "labeldesk-demo"
FLAG = "task_inference"
PULL_URL = f"/api/ws/{WS}/inference/models/ollama/pull"
TAGS = {"qwen3:4b", "qwen3:8b", "gemma3:4b", "llama3.2:3b"}


def _ws_id() -> str:
    with SessionLocal() as db:
        return db.scalar(select(Workspace.id).where(Workspace.slug == WS))


def _inventory(models: list | None = None, free_gb: float = 812.5) -> dict:
    return {"os": "Linux", "arch": "x86_64",
            "gpus": [{"name": "NVIDIA GeForce RTX 4090", "vram_mb": 24564}],
            "cuda": "12.9", "docker": True,
            "disk": {"models_free_gb": free_gb, "models_total_gb": 1863.0},
            "hf_token": False, "models": models or [], "engines": []}


def _host(inventory: dict | None = None) -> str:
    wid = f"ollama-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        db.add(Worker(id=wid, host=wid, kinds=[], started=0.0, last_seen=9e12,
                      inventory=inventory or _inventory()))
        db.commit()
    return wid


def _host_row(inventory: dict | None = None) -> dict:
    return {"id": "h", "online": True, "inventory": inventory or _inventory()}


@pytest.fixture(scope="module", autouse=True)
def _started():
    with TestClient(app):
        yield


@pytest.fixture(autouse=True)
def _flag_on():
    with SessionLocal() as db:
        flags.set_flag(db, _ws_id(), FLAG, True)
        db.commit()
    yield


@pytest.fixture()
def admin() -> TestClient:
    c = TestClient(app)
    c.headers.update(login(c, "demo@labeldesk.dev"))
    return c


@pytest.fixture()
def labeler() -> TestClient:
    c = TestClient(app)
    c.headers.update(login_as(c, "labeler@labeldesk.dev"))
    return c


@pytest.fixture()
def host() -> str:
    wid = _host()
    yield wid
    with SessionLocal() as db:
        for job in db.scalars(select(Job).where(Job.kind == "engine_apply")).all():
            if (job.params or {}).get("host") == wid:
                db.delete(job)
        db.query(Worker).filter(Worker.id == wid).delete()
        db.commit()


# ---------- the engine row -----------------------------------------------------

def test_engines_list_starts_with_ollama_and_it_is_the_default():
    engines = inference_catalog.public_catalog()["engines"]
    assert engines[0]["id"] == "ollama"
    assert engines[0]["default"] is True
    assert [row["id"] for row in engines if row.get("default")] == ["ollama"]


def test_an_install_plan_is_built_only_from_the_catalogue():
    pin = inference_catalog.engine("ollama")
    plan = inference_plan.build(
        {"id": "h", "online": True},
        [{"id": "ollama", "version": pin["version"], "runtime": "docker"}],
        _inventory())
    assert plan["steps"][0]["argv"] == [["docker", "pull", pin["container"]]]

    with pytest.raises(inference_plan.InvalidSelection):
        inference_plan.build(
            {"id": "h", "online": True},
            [{"id": "ollama", "version": "latest; rm -rf /", "runtime": "docker"}],
            _inventory())


def test_the_health_check_is_loopback_only_and_not_public():
    assert inference_catalog.OLLAMA_HEALTH_URL == "http://127.0.0.1:11434/api/version"
    public = inference_catalog.public_catalog()["engines"][0]
    assert "health_url" not in public
    assert "11434" not in repr(public)


# ---------- the tags -----------------------------------------------------------

def test_every_ollama_tag_maps_to_q4_k_m_and_uses_the_estimator():
    rows = {row["tag"]: row for row in inference_models.OLLAMA_TAGS}
    assert TAGS <= set(rows)
    assert all(row["quant"] == "Q4_K_M" for row in rows.values())

    body = inference_models.public_models(_host_row())
    for tag in TAGS:
        row = rows[tag]
        model = next(item for item in body["models"] if item["id"] == row["id"])
        assert model["ollama_tag"] == tag
        assert model["engine"] == ["ollama"]
        variant = model["variants"][0]
        assert variant["format"] == "tag"
        assert variant["quant"] == "Q4_K_M"
        assert variant["bytes"] == row["bytes"] > 0
        expected = inference_estimate.fit(
            row["params_b"], "gguf_q4_k_m", "ollama", row["layers"], row["kv_heads"],
            row["head_dim"], inference_models.FIT_CONTEXT, 24.0)
        assert variant["vram_gb"] == expected["total_gb"]


def test_the_public_rows_still_hide_file_paths():
    body = repr(inference_models.public_models(_host_row()))
    assert "files" not in body
    assert ".safetensors" not in body and ".gguf" not in body


# ---------- the pull boundary --------------------------------------------------

def test_a_tag_outside_the_catalogue_is_refused_with_422(admin, host):
    r = admin.post(PULL_URL, json={"host": host, "tag": "evil:latest", "confirm": True})
    assert r.status_code == 422, r.text
    assert "catalogue" in r.json()["detail"].lower()


def test_a_tag_is_matched_exactly_not_normalised(admin, host):
    r = admin.post(PULL_URL, json={"host": host, "tag": "Qwen3:4B", "confirm": True})
    assert r.status_code == 422, r.text


def test_a_pull_needs_a_confirmation(admin, host):
    r = admin.post(PULL_URL, json={"host": host, "tag": "qwen3:4b", "confirm": False})
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["plan"]["argv"] == ["ollama", "pull", "qwen3:4b"]


def test_a_second_model_on_a_host_is_refused_with_the_remove_message(admin, host):
    with SessionLocal() as db:
        db.get(Worker, host).inventory = _inventory(models=[{"id": "llama3.2-3b", "bytes": 2000}])
        db.commit()
    r = admin.post(PULL_URL, json={"host": host, "tag": "gemma3:4b", "confirm": True})
    assert r.status_code == 409, r.text
    error = r.json()["detail"]["error"]
    assert "remove the current model first" in error
    assert "llama3.2-3b" in error


def test_a_pull_queues_the_catalogue_argv_for_the_worker(admin, host):
    r = admin.post(PULL_URL, json={"host": host, "tag": "qwen3:4b", "confirm": True})
    assert r.status_code == 200, r.text
    with SessionLocal() as db:
        job = db.get(Job, r.json()["job"]["id"])
        assert job.kind == "engine_apply" and job.status == "queued"
        assert job.params["action"] == "pull" and job.params["host"] == host
        step = job.params["engines"][0]
        assert step["argv"] == [["ollama", "pull", "qwen3:4b"]]
        assert step["tag"] == "qwen3:4b"
        assert step["runtime"] == "ollama"


def test_a_busy_host_is_refused_with_the_running_job(admin, host):
    first = admin.post(PULL_URL, json={"host": host, "tag": "qwen3:4b", "confirm": True})
    assert first.status_code == 200, first.text
    second = admin.post(PULL_URL, json={"host": host, "tag": "qwen3:8b", "confirm": True})
    assert second.status_code == 409, second.text
    detail = second.json()["detail"]
    assert "already running" in detail["error"]
    assert detail["job_id"] == first.json()["job"]["id"]


def test_an_already_installed_tag_is_refused(admin, host):
    with SessionLocal() as db:
        db.get(Worker, host).inventory = _inventory(models=[{"id": "qwen3-4b", "bytes": 1}])
        db.commit()
    r = admin.post(PULL_URL, json={"host": host, "tag": "qwen3:4b", "confirm": True})
    assert r.status_code == 409, r.text
    assert "already installed" in r.json()["detail"]["error"]


def test_a_member_is_403_and_flag_off_is_404(admin, labeler, host):
    body = {"host": host, "tag": "qwen3:4b", "confirm": True}
    assert labeler.post(PULL_URL, json=body).status_code == 403
    with SessionLocal() as db:
        flags.set_flag(db, _ws_id(), FLAG, False)
        db.commit()
    assert admin.post(PULL_URL, json=body).status_code == 404


def test_a_foreign_host_is_404(admin):
    r = admin.post(PULL_URL, json={"host": "not-this-deployment", "tag": "qwen3:4b",
                                   "confirm": True})
    assert r.status_code == 404
