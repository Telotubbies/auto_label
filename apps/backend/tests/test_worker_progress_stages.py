"""A pip GPU worker reports training stages, so the Models page shows real progress rather than an empty stepper."""
import os

os.environ.setdefault("LD_WORKER_TOKEN", "test-worker-token-0123456789abcdef")

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Job
from test_r1_remote_reaper import _case

AUTH = {"X-Worker-Token": os.environ["LD_WORKER_TOKEN"]}


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def _post(c, job, **body):
    return c.post(f"/api/worker/jobs/{job}/progress", json={"progress": 10, **body}, headers=AUTH)


def _result(job):
    with SessionLocal() as db:
        return dict(db.get(Job, job).result)


def test_a_worker_reports_stages_and_the_job_keeps_them_beside_its_other_result_fields(c):
    ids = _case("train", started_age=5, result={"worker": "gpu-1"})

    r = _post(c, ids["job"], stages={"materialise": {"status": "done", "t": 3.2},
                                     "train": {"status": "running", "t": 9.5, "note": "epoch 4"}})

    assert r.status_code == 200, r.text
    result = _result(ids["job"])
    assert result["worker"] == "gpu-1"
    assert result["stages"]["materialise"] == {"status": "done", "t": 3.2}
    assert result["stages"]["train"]["status"] == "running" and result["stages"]["train"]["note"] == "epoch 4"


def test_a_later_report_replaces_a_stage_and_keeps_the_others(c):
    ids = _case("train", started_age=5)
    _post(c, ids["job"], stages={"materialise": {"status": "done", "t": 3.0}, "train": {"status": "running", "t": 4.0}})

    _post(c, ids["job"], stages={"train": {"status": "done", "t": 80.0}})

    stages = _result(ids["job"])["stages"]
    assert stages["materialise"]["status"] == "done"
    assert stages["train"] == {"status": "done", "t": 80.0}


def test_unknown_stage_names_and_bad_values_are_dropped_not_stored(c):
    ids = _case("train", started_age=5)

    r = _post(c, ids["job"], stages={"rm -rf": {"status": "done", "t": 1}, "train": {"status": "weird", "t": 1},
                                     "evaluate": {"status": "done", "t": "soon"}, "register": {"status": "done", "t": 2.0,
                                                                                               "note": "x" * 900}})

    assert r.status_code == 200
    stages = _result(ids["job"]).get("stages", {})
    assert set(stages) == {"register"}
    assert len(stages["register"]["note"]) <= 200


def test_stages_do_not_overwrite_the_liveness_heartbeat(c):
    ids = _case("train", started_age=5)

    _post(c, ids["job"], stages={"train": {"status": "running", "t": 1.0}})

    assert _result(ids["job"])["heartbeat"] > 0
