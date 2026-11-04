"""I19: the remote GPU path meters usage and emits eval/model.ready/job.done."""
import contextlib
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import Base, SessionLocal, engine, get_db
from app.main import app
from app.models import Job, Project, TrainedModel, UsageEvent, User, Version, Webhook, WebhookDelivery, Workspace
from app.models import now
from app.services import finalize

TOKEN = {"X-Worker-Token": os.environ["LD_WORKER_TOKEN"]}


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)


@pytest.fixture(autouse=True)
def _no_embedded_worker(monkeypatch):
    """Another module may have imported `app` with the embedded worker on; keep the real worker out."""
    from app import main
    monkeypatch.setattr(main, "EMBEDDED_WORKER", False)


def _train_job():
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        u = User(id="u" + suffix, email=f"rm-{suffix}@x.io", name="R", pw_hash="x")
        db.add(u); db.flush()
        ws = Workspace(id="w" + suffix, slug=f"rm-{suffix}", name="R", owner_id=u.id)
        db.add(ws); db.flush()
        p = Project(workspace_id=ws.id, slug=f"rmp-{suffix}", name="Remote")
        db.add(p); db.flush()
        v = Version(project_id=p.id, number=1, status="ready", stats={})
        db.add(v); db.flush()
        m = TrainedModel(workspace_id=ws.id, project_id=p.id, version_id=v.id, name="remote", arch="yolo26n",
                         variant="yolo26n", task="detect", status="training", family="ultralytics", classes=[])
        db.add(m); db.flush()
        j = Job(workspace_id=ws.id, project_id=p.id, kind="train", status="running", started=now(),
                params={"model_id": m.id, "options": {}})
        db.add(j); db.flush()
        w = Webhook(workspace_id=ws.id, url="https://example.com/hook", secret="s", events=["model.ready", "job.done"])
        db.add(w)
        db.commit()
        return {"job": j.id, "model": m.id, "ws": ws.id, "project": p.id}


def test_remote_train_complete_meters_and_notifies():
    ids = _train_job()
    with TestClient(app) as c:
        r = c.post(f"/api/worker/jobs/{ids['job']}/complete", headers=TOKEN,
                   data={"result": '{"history": [{"epoch": 1, "mAP50": 0.5}]}'},
                   files={"weights": ("best.pt", b"not-a-real-checkpoint")})
    assert r.status_code == 200, r.text
    with SessionLocal() as db:
        metrics = db.get(TrainedModel, ids["model"]).metrics
        assert "eval" in metrics or "eval_error" in metrics
        gpu = db.scalar(select(UsageEvent).where(UsageEvent.workspace_id == ids["ws"],
                                                 UsageEvent.metric == "gpu_seconds"))
        assert gpu is not None
        events = {d.event for d in db.scalars(select(WebhookDelivery).where(
            WebhookDelivery.workspace_id == ids["ws"]))}
        assert "model.ready" in events and "job.done" in events


def test_remote_autolabel_annotation_meters_an_ai_call():
    ids = _train_job()
    with SessionLocal() as db:
        from app.models import Image
        img = Image(id="i" + uuid.uuid4().hex[:8], project_id=ids["project"], name="a.jpg", sha256="x", width=2,
                    height=2, size=1, path="x", thumb="y", annotations=[], n_annotations=0)
        db.add(img); db.commit()
        img_id = img.id
        j = Job(workspace_id=ids["ws"], project_id=ids["project"], kind="autolabel", status="running",
                params={"model_id": ids["model"]})
        db.add(j); db.commit()
        jid = j.id
    with TestClient(app) as c:
        r = c.post(f"/api/worker/jobs/{jid}/annotations", headers=TOKEN,
                   json={"image_id": img_id, "annotations": []})
    assert r.status_code == 200, r.text
    with SessionLocal() as db:
        calls = db.scalar(select(func.count()).select_from(UsageEvent).where(
            UsageEvent.workspace_id == ids["ws"], UsageEvent.metric == "ai_calls"))
    assert calls == 1


def test_remote_fail_notifies_and_meters_the_failed_run():
    """I19: a failed GPU run still consumed the card and integrations wait on job.done."""
    ids = _train_job()
    with SessionLocal() as db:
        j = db.get(Job, ids["job"])
        j.started = now() - 40                      # a run that held the GPU before it failed
        db.commit()
    with TestClient(app) as c:
        r = c.post(f"/api/worker/jobs/{ids['job']}/fail", headers=TOKEN, json={"error": "CUDA out of memory"})
    assert r.status_code == 200, r.text
    with SessionLocal() as db:
        job = db.get(Job, ids["job"])
        assert job.status == "failed"
        assert db.get(TrainedModel, ids["model"]).status == "failed"
        gpu = db.scalar(select(UsageEvent).where(
            UsageEvent.workspace_id == ids["ws"], UsageEvent.metric == "gpu_seconds",
            UsageEvent.meta["job_id"].as_string() == ids["job"]))
        assert gpu is not None and gpu.quantity > 0
        events = {d.event for d in db.scalars(select(WebhookDelivery).where(
            WebhookDelivery.workspace_id == ids["ws"]))}
        assert "job.done" in events


def test_remote_autolabel_complete_meters_elapsed_gpu_time():
    """I19: autolabel uploads no weights, but it still occupied the GPU and must be metered."""
    ids = _train_job()
    with SessionLocal() as db:
        j = Job(workspace_id=ids["ws"], project_id=ids["project"], kind="autolabel", status="running",
                started=now() - 30, params={"model_id": ids["model"]})
        db.add(j); db.commit()
        jid = j.id
    with TestClient(app) as c:
        r = c.post(f"/api/worker/jobs/{jid}/complete", headers=TOKEN, data={"result": "{}"})
    assert r.status_code == 200, r.text
    with SessionLocal() as db:
        gpu = db.scalar(select(UsageEvent).where(UsageEvent.workspace_id == ids["ws"],
                                                 UsageEvent.metric == "gpu_seconds"))
        assert gpu is not None and gpu.quantity > 0
        assert db.get(Job, jid).status == "done"


def _gpu_usage(workspace_id):
    with SessionLocal() as db:
        count = db.scalar(select(func.count()).select_from(UsageEvent).where(
            UsageEvent.workspace_id == workspace_id, UsageEvent.metric == "gpu_seconds"))
        total = db.scalar(select(func.coalesce(func.sum(UsageEvent.quantity), 0.0)).where(
            UsageEvent.workspace_id == workspace_id, UsageEvent.metric == "gpu_seconds"))
    return count, float(total)


def _event_count(workspace_id, event):
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(WebhookDelivery).where(
            WebhookDelivery.workspace_id == workspace_id, WebhookDelivery.event == event))


def test_remote_complete_is_idempotent_and_fail_cannot_overwrite_done(monkeypatch):
    """I19: a retried complete (or a late /fail) must not re-meter, re-evaluate or re-emit job.done."""
    ids = _train_job()
    calls = []

    def fake_evaluate(*args, **kwargs):
        calls.append(1)
        if len(calls) > 1:
            raise AssertionError("evaluation must run at most once")
        return {"AP": 0.5}

    monkeypatch.setattr(finalize, "evaluate", fake_evaluate)
    upload = {"weights": ("best.pt", b"not-a-real-checkpoint")}
    data = {"result": '{"history": [{"epoch": 1, "mAP50": 0.5}]}'}

    with TestClient(app) as c:
        r = c.post(f"/api/worker/jobs/{ids['job']}/complete", headers=TOKEN, data=data, files=upload)
        assert r.status_code == 200, r.text
        gpu_after_first = _gpu_usage(ids["ws"])
        done_after_first = _event_count(ids["ws"], "job.done")
        assert gpu_after_first[0] == 1 and done_after_first == 1

        r = c.post(f"/api/worker/jobs/{ids['job']}/complete", headers=TOKEN, data=data, files=upload)
        assert r.status_code == 200, r.text
        r = c.post(f"/api/worker/jobs/{ids['job']}/fail", headers=TOKEN, json={"error": "late timeout"})
        assert r.status_code == 200, r.text

    assert calls == [1]
    assert _gpu_usage(ids["ws"]) == gpu_after_first
    assert _event_count(ids["ws"], "job.done") == done_after_first
    with SessionLocal() as db:
        job = db.get(Job, ids["job"])
        assert job.status == "done"
        assert job.result["model_id"] == ids["model"]
        assert db.get(TrainedModel, ids["model"]).status == "ready"


def test_remote_complete_finalizes_in_background_under_a_training_lease(monkeypatch):
    """I19: eval must run off the request path, on its own session, under `scheduler.training_scope`."""
    ids = _train_job()
    order, scopes, seen = [], [], {}

    @contextlib.contextmanager
    def spy_scope():
        scopes.append("enter")
        try:
            yield
        finally:
            scopes.append("exit")

    real_job_done = finalize.job_done

    def tracking_job_done(db, job, status, error=""):
        order.append("job_done")
        return real_job_done(db, job, status, error)

    def fake_evaluate(model_ref, version_dir, task, db=None, workspace_id=None):
        order.append("evaluate")
        seen["db"] = db
        seen["in_scope"] = scopes == ["enter"]
        return {"AP": 0.5}

    monkeypatch.setattr(finalize, "evaluate", fake_evaluate)
    monkeypatch.setattr(finalize, "job_done", tracking_job_done)
    monkeypatch.setattr("app.gpu.scheduler.training_scope", spy_scope)

    request_sessions = []

    def tracking_get_db():
        session = SessionLocal()
        request_sessions.append(session)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = tracking_get_db
    try:
        with TestClient(app) as c:
            r = c.post(f"/api/worker/jobs/{ids['job']}/complete", headers=TOKEN,
                       data={"result": '{"history": [{"epoch": 1, "mAP50": 0.5}]}'},
                       files={"weights": ("best.pt", b"not-a-real-checkpoint")})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200, r.text
    # TestClient runs background tasks before returning, so the evaluator has already run.
    assert order == ["job_done", "evaluate"], order
    assert scopes == ["enter", "exit"], scopes
    assert seen["in_scope"] is True
    assert len(request_sessions) == 1
    assert seen["db"] is not request_sessions[0]
    with SessionLocal() as db:
        assert db.get(Job, ids["job"]).status == "done"
        metrics = db.get(TrainedModel, ids["model"]).metrics
        assert metrics["eval"] == {"AP": 0.5}
