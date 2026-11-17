"""Worker loop: the daily ops scheduler must run even while the worker is busy with a job."""

import os
import threading

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

from app import worker
from app.services import heartbeat


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


class _Stop(BaseException):
    """Ends loop() in the test: BaseException so the loop's own failure handling cannot swallow it."""


def test_loop_survives_a_failed_iteration_and_backs_off(monkeypatch):
    """B1: one transient DB error must not end the only executor, and retries must not spin."""
    pauses: list[float] = []

    def claim():
        raise RuntimeError("database is locked")

    def sleep(pause: float) -> None:
        pauses.append(pause)
        if len(pauses) == 3:
            raise _Stop

    monkeypatch.setattr(worker, "recover", lambda: None)
    monkeypatch.setattr(worker, "_schedule_ops", lambda: None)
    monkeypatch.setattr(worker, "POLL", 0.05)
    monkeypatch.setattr(worker, "BACKOFF_MAX_S", 0.2)
    monkeypatch.setattr(worker, "_claim", claim)
    monkeypatch.setattr(worker.time, "sleep", sleep)   # injected clock: no wall-clock assertion
    with pytest.raises(_Stop):
        worker.loop()                                  # stop=None, so only the injected clock exits
    assert pauses == [0.05, 0.1, 0.2], "a repeated failure must idle longer, up to the cap"


def test_a_failed_iteration_still_beats_the_heartbeat(monkeypatch):
    """m-4: a failed run must not leave its job id (or a stale last_seen) as the worker's last word."""
    beats: list[dict] = []
    stop = threading.Event()

    def claim():
        stop.set()
        raise RuntimeError("database is locked")

    monkeypatch.setattr(worker, "recover", lambda: None)
    monkeypatch.setattr(worker, "_schedule_ops", lambda: None)
    monkeypatch.setattr(worker, "POLL", 0.01)
    monkeypatch.setattr(worker, "BACKOFF_MAX_S", 0.01)
    monkeypatch.setattr(worker, "_claim", claim)
    monkeypatch.setattr(heartbeat, "beat", lambda kinds=None, current_job=None, force=False:
                        beats.append({"job": current_job, "force": force}))
    worker.loop(stop)
    assert len(beats) == 2, f"the failure path must beat too: {beats}"
    assert beats[1] == {"job": None, "force": True}, "a throttled beat would leave the stale state in place"


def test_backoff_is_bounded(monkeypatch):
    monkeypatch.setattr(worker, "POLL", 1.5)
    monkeypatch.setattr(worker, "BACKOFF_MAX_S", 30.0)
    assert worker._backoff(1) == 1.5
    assert worker._backoff(2) == 3.0
    assert worker._backoff(10_000) == 30.0


def test_over_budget_helper():
    """I1: a run aborts once the lease outlives the GPU allowance it started with."""
    assert worker._over_budget(100.0, 30.0, 131.0) is True
    assert worker._over_budget(100.0, 30.0, 130.0) is False
