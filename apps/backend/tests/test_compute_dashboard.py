"""The Compute page: one honest answer to "is anything using the GPU, and what is waiting?".

The header badge used to read only the API process's own GPU lease, so a pip worker training on another
GPU still showed "GPU idle". The summary reads workers and jobs, never one process's ledger alone.
"""
import os

os.environ.setdefault("LD_WORKER_TOKEN", "test-worker-token-0123456789abcdef")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.compute_state import headline
from conftest import login

WS = "labeldesk-demo"


def _job(kind="train", status="running", progress=40.0, **extra):
    return {"id": "j1", "kind": kind, "status": status, "progress": progress, **extra}


def test_a_running_training_job_makes_the_headline_training_even_when_the_api_gpu_is_idle():
    h = headline(workers_online=1, jobs=[_job()], api_holder=None)

    assert h["state"] == "training"
    assert h["label"] == "Training · 40%"


def test_other_gpu_work_is_working_not_training():
    h = headline(workers_online=1, jobs=[_job(kind="autolabel", progress=12)], api_holder=None)

    assert (h["state"], h["label"]) == ("working", "Auto-label · 12%")


def test_the_api_gpu_holder_counts_as_working_when_no_job_is_running():
    h = headline(workers_online=0, jobs=[], api_holder="sam3")

    assert h["state"] == "working" and "sam3" in h["label"]


def test_idle_when_a_worker_is_online_and_nothing_runs():
    assert headline(workers_online=1, jobs=[], api_holder=None) == {"state": "idle", "label": "Idle"}


def test_queued_work_with_no_worker_says_so_instead_of_idle():
    h = headline(workers_online=0, jobs=[_job(status="queued", progress=0)], api_holder=None)

    assert h["state"] == "offline"
    assert "no worker" in h["label"].lower()


def test_no_worker_and_no_work_is_offline_not_idle():
    assert headline(workers_online=0, jobs=[], api_holder=None)["state"] == "offline"


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        client.headers.update(login(client))
        yield client


def test_the_route_returns_the_dashboard_shape_for_a_workspace_member(c):
    r = c.get(f"/api/ws/{WS}/compute")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] in {"training", "working", "idle", "offline"}
    assert set(body["workers"]) >= {"online", "total", "busy"}
    assert set(body["queue"]) >= {"running", "queued", "oldest_wait_s"}
    assert isinstance(body["jobs"], list) and isinstance(body["gpus"], list)
    assert set(body["api_gpu"]) >= {"used_mb", "budget_mb", "models"}


def test_the_route_never_names_a_worker_host_to_a_workspace(c):
    text = c.get(f"/api/ws/{WS}/compute").text

    assert "host" not in text.lower() or '"host"' not in text


def test_an_unknown_workspace_is_404(c):
    assert c.get("/api/ws/no-such-workspace/compute").status_code in (403, 404)
