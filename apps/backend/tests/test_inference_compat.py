"""T-1003: an engine says compatible, warning or blocked before a button exists.

Every rule answers with the host's own numbers, in the card's order, and returns on the first
blocking rule while collecting every warning. A host that reports a partial payload gets a reason,
never a 500. The route refuses an unknown or foreign host, a non-admin, a missing host id and a
workspace whose hub flag is off.
"""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Worker, Workspace, WorkspaceFlag
from app.services import flags, inference_catalog, inference_compat
from conftest import login, login_as

WS = "labeldesk-demo"
ENGINES = f"/api/ws/{WS}/inference/engines"


def _host(**over) -> dict:
    """A report shaped like the worker's inventory: one 4090 on a driver that fits every pin."""
    inv = {"os": "Linux", "arch": "x86_64", "python": "3.11.9",
           "gpus": [{"name": "NVIDIA GeForce RTX 4090", "vram_mb": 24564,
                     "driver": "575.51", "cuda": "12.9"}],
           "cuda": "12.9", "docker": True,
           "disk": {"models_free_gb": 812.5, "models_total_gb": 1863.0},
           "engines": []}
    inv.update(over)
    return inv


# ---------- the rules ---------------------------------------------------------

def test_absent_inventory_blocks_every_engine():
    for row in inference_catalog.ENGINES:
        out = inference_compat.evaluate(None, row, "uv", free_gb=100.0)
        assert out["status"] == "blocked", row["id"]
        assert out["reasons"] == ["This host has not reported hardware yet."], row["id"]

    partial = inference_compat.evaluate({}, inference_catalog.engine("vllm"), "uv", free_gb=100.0)
    assert partial["status"] == "blocked" and partial["reasons"]       # a reason, never a 500


def test_cpu_host_blocks_gpu_engines_and_keeps_llamacpp():
    host = _host(gpus=[], cuda=None)
    for engine_id, runtime in (("vllm", "uv"), ("tensorrtllm", "docker")):
        out = inference_compat.evaluate(host, inference_catalog.engine(engine_id), runtime, free_gb=812.5)
        assert out["status"] == "blocked", engine_id
        assert out["reasons"] == ["Needs an NVIDIA GPU; this host reports CPU only."], engine_id

    out = inference_compat.evaluate(host, inference_catalog.engine("llamacpp"), "uv", free_gb=812.5)
    assert out["status"] == "ok"
    assert out["reasons"] == [] and out["installed"] is False


def test_old_driver_and_cuda_block_with_the_reported_values():
    host = _host(gpus=[{"name": "NVIDIA GeForce GTX 1080", "vram_mb": 8192, "driver": "470.0"}],
                 cuda="11.8")
    out = inference_compat.evaluate(host, inference_catalog.engine("vllm"), "uv", free_gb=812.5)
    assert out["status"] == "blocked"
    text = " ".join(out["reasons"])
    assert "470" in text and "11.8" in text


def test_low_disk_blocks_with_the_shortfall():
    row = inference_catalog.engine("vllm")
    need = round(row["disk_mb"] / 1024, 1)
    out = inference_compat.evaluate(_host(), row, "uv", free_gb=2.1)
    assert out["status"] == "blocked"
    assert out["reasons"] == [f"Needs {need:.1f} GB free; the host has 2.1 GB."]


def test_docker_runtime_without_docker_blocks():
    host = _host(docker=False)
    out = inference_compat.evaluate(host, inference_catalog.engine("vllm"), "docker", free_gb=812.5)
    assert out["status"] == "blocked"
    assert out["reasons"] == ["Docker is not available on this host."]
    assert inference_compat.evaluate(host, inference_catalog.engine("vllm"), "uv",
                                     free_gb=812.5)["status"] == "ok"


def test_untested_driver_is_a_warning_not_a_block():
    row = {**inference_catalog.engine("vllm"), "min_driver": "550", "cuda_min": None}
    host = _host(gpus=[{"name": "NVIDIA GeForce RTX 4090", "vram_mb": 24564, "driver": "551.20"}])
    out = inference_compat.evaluate(host, row, "uv", free_gb=812.5)
    assert out["status"] == "warn" and out["reasons"] == []
    assert "551.20" in out["warnings"][0] and "550" in out["warnings"][0]


def test_installed_engine_reads_ok_and_installed():
    row = inference_catalog.engine("vllm")
    host = _host(engines=[{"id": "vllm", "version": row["version"], "ok": True}])
    out = inference_compat.evaluate(host, row, "uv", free_gb=812.5)
    assert out["status"] == "ok" and out["installed"] is True


# ---------- the route ---------------------------------------------------------

def app_client() -> TestClient:
    return TestClient(app)


def _ws_id() -> str:
    with SessionLocal() as db:
        return db.scalar(select(Workspace.id).where(Workspace.slug == WS))


@pytest.fixture(scope="module")
def c():
    client = app_client()
    client.headers.update(login(client))
    yield client


@pytest.fixture(autouse=True)
def flag_on():
    with SessionLocal() as db:
        flags.set_flag(db, _ws_id(), "task_inference", True)
        db.commit()
    yield


@pytest.fixture(autouse=True)
def _clean_hosts():
    with SessionLocal() as db:
        before = set(db.scalars(select(Worker.id)))
    yield
    with SessionLocal() as db:
        for wid in set(db.scalars(select(Worker.id))) - before:
            db.delete(db.get(Worker, wid))
        db.execute(WorkspaceFlag.__table__.delete().where(WorkspaceFlag.key == "task_inference"))
        db.commit()


def _host_row(inventory: dict | None, last_seen: float) -> str:
    wid = f"compat-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        db.add(Worker(id=wid, host=wid, kinds=[], started=0.0, last_seen=last_seen, inventory=inventory))
        db.commit()
    return wid


def test_every_row_carries_compatibility_installed_and_disk_after(c: TestClient):
    row = inference_catalog.engine("vllm")
    wid = _host_row(_host(engines=[{"id": "vllm", "version": row["version"], "ok": True}]), 9e12)
    r = c.get(ENGINES, params={"host": wid})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["host"]["id"] == wid and body["host"]["online"] is True

    rows = {e["id"]: e for e in body["engines"]}
    assert set(rows) == {e["id"] for e in inference_catalog.ENGINES}
    assert rows["vllm"]["compatibility"]["status"] == "ok"
    assert rows["vllm"]["installed"] is True
    assert rows["vllm"]["disk_after_gb"] == round(812.5 - row["disk_mb"] / 1024, 1)
    assert rows["llamacpp"]["installed"] is False
    assert rows["llamacpp"]["compatibility"]["reasons"] == []
    assert "package" not in rows["vllm"] and "container" not in rows["vllm"]


def test_a_stale_host_blocks_installs_and_keeps_its_last_inventory(c: TestClient):
    wid = _host_row(_host(), 0.0)
    r = c.get(ENGINES, params={"host": wid})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["host"]["online"] is False
    assert body["host"]["inventory"]["gpus"][0]["name"] == "NVIDIA GeForce RTX 4090"
    for row in body["engines"]:
        assert row["compatibility"]["status"] == "blocked", row["id"]
        assert "offline" in row["compatibility"]["reasons"][0], row["id"]


def test_foreign_or_unknown_host_is_404(c: TestClient):
    assert c.get(ENGINES, params={"host": "no-such-host-anywhere"}).status_code == 404
    assert c.get(ENGINES).status_code == 422                    # host is required, never defaulted

    member = app_client()
    member.headers.update(login_as(member, "labeler@labeldesk.dev"))
    assert member.get(ENGINES, params={"host": "x"}).status_code == 403

    with SessionLocal() as db:
        flags.set_flag(db, _ws_id(), "task_inference", False)
        db.commit()
    assert c.get(ENGINES, params={"host": "x"}).status_code == 404
