"""I21/I22/I23: drift job status, cancellation and per-model sample scoping."""
import os
import uuid

os.environ.setdefault("LD_WORKER_TOKEN", "test-worker-token-0123456789abcdef")

import pytest
from sqlalchemy import select

from app import worker
from app.db import Base, SessionLocal, engine
from app.models import DriftRun, DriftSample, Image, Job, Project, TrainedModel, User, Version, Workspace


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


def test_run_health_honours_cancellation_between_images(monkeypatch):
    """I22: run_health must pass the job's predicate into the per-image inference loop."""
    from PIL import Image as PImage

    from app import jobs
    from app.services import health_scan

    ws_id, p_id, v_id = _project()
    with SessionLocal() as db:
        db.add(TrainedModel(workspace_id=ws_id, project_id=p_id, version_id=v_id, name="scan", arch="yolo26n",
                            variant="yolo26n", task="detect", status="ready", family="ultralytics", classes=[]))
        for i in range(4):
            db.add(Image(id=f"hi{uuid.uuid4().hex[:8]}", project_id=p_id, name=f"{i}.jpg", sha256=f"h{i}",
                         width=4, height=4, size=1, path=f"projects/{p_id}/images/{i}.jpg", thumb="",
                         annotations=[], n_annotations=0))
        j = Job(workspace_id=ws_id, project_id=p_id, kind="health", params={})
        db.add(j); db.commit()
        jid = j.id

    calls = {"n": 0}
    predictions: list[int] = []

    def cancel_after_a_few(_jid):
        calls["n"] += 1
        return calls["n"] > 5                      # the job is cancelled after the first inference

    class Fake:
        def predict(self, _im, **_kw):
            predictions.append(1)
            return {"predictions": []}

    monkeypatch.setattr(jobs, "is_cancelled", cancel_after_a_few)
    monkeypatch.setattr(health_scan, "resolve", lambda *a, **kw: Fake())
    monkeypatch.setattr(health_scan, "_leakage_pairs", lambda *a, **kw: 0)
    monkeypatch.setattr(health_scan.imaging, "load", lambda _path: PImage.new("RGB", (4, 4)))

    worker.run_one(jid)

    with SessionLocal() as db:
        assert db.get(Job, jid).status == "cancelled"
    assert 0 < len(predictions) < 4                 # stopped before scanning every image


def test_run_insights_scans_receive_the_cancellation_predicate(monkeypatch):
    from app import jobs
    from app.services import insights_jobs

    ws_id, p_id, _ = _project()
    with SessionLocal() as db:
        j = Job(workspace_id=ws_id, project_id=p_id, kind="insights_images", params={})
        db.add(j); db.commit()
        job = db.get(Job, j.id)
        db.expunge(job)
    monkeypatch.setattr(jobs, "is_cancelled", lambda _jid: False)
    seen = {}
    monkeypatch.setattr(insights_jobs, "scan_images",
                        lambda db, project, should_stop=None: seen.update(ok=callable(should_stop)) or {})
    worker.run_insights_images(job)
    assert seen["ok"] is True


def test_insights_scan_services_stop_on_cancellation():
    from app.adapters.base import Cancelled
    from app.services import insights_embedding, insights_jobs

    ws_id, p_id, _ = _project()
    with SessionLocal() as db:
        project = db.get(Project, p_id)
        with pytest.raises(Cancelled):
            insights_jobs.scan_images(db, project, should_stop=lambda: True)
        with pytest.raises(Cancelled):
            insights_jobs.scan_leakage(db, project, should_stop=lambda: True)
        with pytest.raises(Cancelled):
            insights_embedding.scan_embedding(db, project, should_stop=lambda: True)
