"""I19: the remote GPU path meters usage and emits eval/model.ready/job.done."""
import os
import uuid

os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import Job, Project, TrainedModel, UsageEvent, User, Version, Webhook, WebhookDelivery, Workspace
from app.models import now

TOKEN = {"X-Worker-Token": os.environ["LD_WORKER_TOKEN"]}


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)


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
