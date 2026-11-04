"""Worker loop: the daily ops scheduler must run even while the worker is busy with a job."""

import os
import threading

import pytest

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

from app import worker


@pytest.fixture(scope="module", autouse=True)
def _schema():
    """I8: this module must not depend on another module's TestClient having created the schema."""
    from sqlalchemy import inspect

    from app.db import Base, engine
    Base.metadata.create_all(engine)
    assert "workers" in inspect(engine).get_table_names()


def test_schedule_ops_runs_while_a_job_is_claimed(monkeypatch):
    """I5: a queue of long jobs must not starve the 15-minute drift scheduler."""
    calls: list[str] = []
    stop = threading.Event()
    monkeypatch.setattr(worker, "recover", lambda: None)
    monkeypatch.setattr(worker, "_schedule_ops", lambda: calls.append("schedule"))
    monkeypatch.setattr(worker, "_claim", lambda: "job-1")

    def run_one(jid: str) -> None:
        calls.append(jid)
        stop.set()

    monkeypatch.setattr(worker, "run_one", run_one)
    worker.loop(stop)
    assert calls == ["schedule", "job-1"]


def test_over_budget_helper():
    """I1: a run aborts once the lease outlives the GPU allowance it started with."""
    assert worker._over_budget(100.0, 30.0, 131.0) is True
    assert worker._over_budget(100.0, 30.0, 130.0) is False
