"""I9: a dead remote GPU worker must not strand train/autolabel in running/cancelling forever."""
import os
import uuid

os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_EMBEDDED_WORKER"] = "0"     # the API process runs no jobs; only the reaper acts here

import pytest
from sqlalchemy import select

from app import config
from app.db import Base, SessionLocal, engine
from app.models import Job, Project, TrainedModel, User, Version, Webhook, WebhookDelivery, Workspace, now
from app.services import remote_reaper


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)


def _case(kind="train", status="running", started_age=0.0, result=None, model_status="training",
          executor="remote"):
    """One workspace/project/version/model/webhook plus a job whose worker is gone."""
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        user = User(id="u" + suffix, email=f"reap-{suffix}@x.io", name="Reap", pw_hash="x")
        db.add(user)
        db.flush()
        ws = Workspace(id="w" + suffix, slug=f"reap-{suffix}", name="Reap", owner_id=user.id)
        db.add(ws)
        db.flush()
        project = Project(workspace_id=ws.id, slug=f"reapp-{suffix}", name="Reaper")
        db.add(project)
        db.flush()
        version = Version(project_id=project.id, number=1, status="ready", stats={})
        db.add(version)
        db.flush()
        model = TrainedModel(workspace_id=ws.id, project_id=project.id, version_id=version.id,
                             name="dead-run", arch="yolo26n", variant="yolo26n", task="detect",
                             status=model_status, family="ultralytics", classes=[])
        db.add(model)
        db.flush()
        created = now() - (config.REMOTE_JOB_TIMEOUT_S + 60 if started_age is None else started_age + 1)
        job = Job(workspace_id=ws.id, project_id=project.id, kind=kind, status=status,
                  created=created, executor=executor,
                  started=None if started_age is None else now() - started_age,
                  result=result or {}, params={"model_id": model.id})
        db.add(job)
        db.flush()
        db.add(Webhook(workspace_id=ws.id, url="https://example.com/hook", secret="s",
                       events=["job.done"]))
        db.commit()
        return {"job": job.id, "model": model.id, "ws": ws.id}


def test_dead_remote_train_fails_the_job_the_model_and_notifies():
    ids = _case("train", started_age=config.REMOTE_JOB_TIMEOUT_S + 60)
    with SessionLocal() as db:
        assert remote_reaper.reap(db) == [ids["job"]]

    with SessionLocal() as db:
        job = db.get(Job, ids["job"])
        assert job.status == "failed"
        assert job.finished is not None
        assert job.error                                          # a readable reason reaches the UI
        assert db.get(TrainedModel, ids["model"]).status == "failed"
        events = {d.event for d in db.scalars(select(WebhookDelivery).where(
            WebhookDelivery.workspace_id == ids["ws"]))}
        assert "job.done" in events


def test_running_row_without_a_start_timestamp_is_still_reaped():
    """A migrated row may be `running` with no `started`; aging it from creation avoids a hang."""
    ids = _case("train", started_age=None)
    with SessionLocal() as db:
        assert remote_reaper.reap(db) == [ids["job"]]
    with SessionLocal() as db:
        assert db.get(Job, ids["job"]).status == "failed"


def test_a_recent_progress_report_keeps_a_long_run_alive(monkeypatch):
    """I9: the timeout is a missed-heartbeat clock, not a cap on legitimate training time."""
    from fastapi.testclient import TestClient

    from app import main
    from app.main import app

    monkeypatch.setattr(main, "EMBEDDED_WORKER", False)   # no local reaper thread races this test
    ids = _case("train", started_age=config.REMOTE_JOB_TIMEOUT_S + 600)
    with TestClient(app) as client:
        r = client.post(f"/api/worker/jobs/{ids['job']}/progress", json={"progress": 42},
                        headers={"X-Worker-Token": os.environ["LD_WORKER_TOKEN"]})
    assert r.status_code == 200, r.text
    with SessionLocal() as db:
        job = db.get(Job, ids["job"])
        assert job.result["heartbeat"] > 0
        assert remote_reaper.reap(db) == []                # a 2-hour run with fresh progress survives
        assert job.status == "running"


def test_abandoned_remote_cancel_reaches_cancelled():
    ids = _case("autolabel", status="cancelling", started_age=30,
                result={"worker": "gpu", "cancel_requested": now() - config.REMOTE_CANCEL_GRACE_S - 5})
    with SessionLocal() as db:
        assert remote_reaper.reap(db) == [ids["job"]]
    with SessionLocal() as db:
        job = db.get(Job, ids["job"])
        assert job.status == "cancelled" and job.finished is not None


def test_abandoned_remote_train_cancel_finishes_the_model_too():
    """I9: cancelling a run whose worker is gone must not leave the model non-terminal forever."""
    ids = _case("train", status="cancelling", started_age=30, model_status="queued",
                result={"worker": "gpu", "cancel_requested": now() - config.REMOTE_CANCEL_GRACE_S - 5})
    with SessionLocal() as db:
        assert remote_reaper.reap(db) == [ids["job"]]
    with SessionLocal() as db:
        assert db.get(Job, ids["job"]).status == "cancelled"
        assert db.get(TrainedModel, ids["model"]).status == "failed"


def test_a_live_remote_job_and_a_local_job_are_left_alone():
    live = _case("train", started_age=config.REMOTE_JOB_TIMEOUT_S - 60)
    local = _case("export", started_age=config.REMOTE_JOB_TIMEOUT_S + 600)
    with SessionLocal() as db:
        assert remote_reaper.reap(db) == []
    with SessionLocal() as db:
        assert db.get(Job, live["job"]).status == "running"
        assert db.get(Job, local["job"]).status == "running"     # local recovery owns these kinds


def test_a_local_train_claimed_by_a_local_worker_is_not_reaped():
    """I9 root: the reaper owns remote claims, not every row whose kind is train/autolabel.

    A local `app.worker` never writes `result.heartbeat`, so a kind-only sweep would fail a
    healthy multi-hour CPU training run after 30 minutes.
    """
    ids = _case("train", started_age=config.REMOTE_JOB_TIMEOUT_S + 600, executor="local")
    with SessionLocal() as db:
        assert remote_reaper.reap(db) == []
    with SessionLocal() as db:
        assert db.get(Job, ids["job"]).status == "running"
        assert db.get(TrainedModel, ids["model"]).status == "training"


def test_a_pre_upgrade_remote_claim_is_still_reaped():
    """Rows claimed before the executor column existed carry the claim route's worker marker."""
    ids = _case("train", started_age=config.REMOTE_JOB_TIMEOUT_S + 60, executor="",
                result={"worker": "old-gpu"})
    with SessionLocal() as db:
        assert remote_reaper.reap(db) == [ids["job"]]
    with SessionLocal() as db:
        assert db.get(Job, ids["job"]).status == "failed"


def test_local_recovery_does_not_requeue_a_remote_claim():
    """I9 root: restarting a local worker must not duplicate a job the remote GPU worker owns."""
    from app import worker

    ids = _case("train", executor="remote")
    worker.recover()
    with SessionLocal() as db:
        assert db.get(Job, ids["job"]).status == "running"


def test_the_reaper_runs_on_its_own_thread_independently_of_the_job_loop(monkeypatch):
    """I9 root: a multi-hour local job must not starve the sweep that reaps dead GPU workers."""
    import threading

    from app import worker

    seen = threading.Event()
    monkeypatch.setattr(worker.remote_reaper, "reap", lambda db: seen.set() or [])
    monkeypatch.setattr(worker, "REAP_S", 0.01)
    stop = threading.Event()
    t = threading.Thread(target=worker._reaper_loop, args=(stop,), daemon=True)
    t.start()
    try:
        assert seen.wait(3), "the reaper did not run while the job loop was busy"
    finally:
        stop.set()
        t.join(3)


def test_cancel_stamps_when_the_dead_worker_was_asked(monkeypatch):
    """The reaper can only finish an abandoned cancel if the route records when it was requested."""
    from fastapi.testclient import TestClient

    from app import main
    from app.main import app
    from app.security import issue_access

    monkeypatch.setattr(main, "EMBEDDED_WORKER", False)   # no local worker may claim/cancel the row

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
        ws = db.scalar(select(Workspace).where(Workspace.slug == "labeldesk-demo"))
        project = db.scalar(select(Project).where(Project.workspace_id == ws.id,
                                                  Project.slug == "ppe-detection"))
        job = Job(workspace_id=ws.id, project_id=project.id, kind="train", status="running",
                  started=now(), params={}, result={"worker": "gpu"})
        db.add(job)
        db.commit()
        demo_job = job.id
    headers = {"Authorization": f"Bearer {issue_access(user.id)}"}
    try:
        with TestClient(app) as client:
            r = client.post(f"/api/ws/labeldesk-demo/projects/ppe-detection/jobs/{demo_job}/cancel",
                            headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "cancelling"
        with SessionLocal() as db:
            job = db.get(Job, demo_job)
            assert job.result["cancel_requested"] > 0
    finally:
        with SessionLocal() as db:
            db.delete(db.get(Job, demo_job))
            db.commit()

