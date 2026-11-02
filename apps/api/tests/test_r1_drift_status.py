"""I21/I22/I23: drift job status, cancellation and per-model sample scoping."""
import os
import uuid

os.environ.setdefault("LD_WORKER_TOKEN", "test-worker-token-0123456789abcdef")

import pytest
from sqlalchemy import select

from app import worker
from app.db import Base, SessionLocal, engine
from app.models import DriftRun, DriftSample, Job, Project, TrainedModel, User, Version, Workspace


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)


def _project():
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        u = User(id="u" + suffix, email=f"dr-{suffix}@x.io", name="D", pw_hash="x")
        db.add(u); db.flush()
        ws = Workspace(id="w" + suffix, slug=f"dr-{suffix}", name="D", owner_id=u.id)
        db.add(ws); db.flush()
        p = Project(workspace_id=ws.id, slug=f"drp-{suffix}", name="Drift project")
        db.add(p); db.flush()
        v = Version(project_id=p.id, number=1, status="ready", stats={})
        db.add(v); db.flush()
        db.commit()
        return ws.id, p.id, v.id


def test_failed_drift_result_marks_the_job_failed():
    ws_id, p_id, _ = _project()
    with SessionLocal() as db:
        j = Job(workspace_id=ws_id, project_id=None, kind="drift", params={})
        db.add(j); db.commit()
        jid = j.id
    worker.run_one(jid)
    with SessionLocal() as db:
        assert db.get(Job, jid).status == "failed"


def test_cancelled_drift_job_is_not_run():
    ws_id, p_id, _ = _project()
    with SessionLocal() as db:
        j = Job(workspace_id=ws_id, project_id=p_id, kind="drift", params={}, status="cancelling")
        db.add(j); db.commit()
        jid = j.id
    worker.run_one(jid)
    with SessionLocal() as db:
        assert db.get(Job, jid).status == "cancelled"
        assert db.scalar(select(DriftRun).where(DriftRun.project_id == p_id)) is None


def test_current_features_are_scoped_to_the_served_model():
    ws_id, p_id, v_id = _project()
    with SessionLocal() as db:
        prod = TrainedModel(workspace_id=ws_id, project_id=p_id, version_id=v_id, name="prod", arch="yolo26n",
                            variant="yolo26n", task="detect", status="ready", family="ultralytics", classes=[])
        staging = TrainedModel(workspace_id=ws_id, project_id=p_id, version_id=v_id, name="staging", arch="yolo26n",
                               variant="yolo26n", task="detect", status="ready", family="ultralytics", classes=[])
        db.add_all([prod, staging]); db.flush()
        db.add_all([
            DriftSample(workspace_id=ws_id, project_id=p_id, model_id=prod.id, sha256="a", features=[0.1, 0.2]),
            DriftSample(workspace_id=ws_id, project_id=p_id, model_id=staging.id, sha256="b", features=[9.0, 9.0]),
        ])
        db.commit()
        from app.services import drift
        prod_features = drift._current_features(db, db.get(Project, p_id), 2, model_id=prod.id)
        all_features = drift._current_features(db, db.get(Project, p_id), 2)
    assert prod_features == [[0.1, 0.2]]
    assert len(all_features) == 2


def test_health_scan_stops_when_the_job_is_cancelled():
    """I22: cancellation is honoured inside the scan, not only before the job starts."""
    ws_id, p_id, _ = _project()
    from app.adapters.base import Cancelled
    from app.services import health_scan

    with SessionLocal() as db:
        project = db.get(Project, p_id)
        with pytest.raises(Cancelled):
            health_scan.scan_health(db, project, should_stop=lambda: True)
