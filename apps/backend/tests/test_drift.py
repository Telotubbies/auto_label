"""Drift monitor: MMD statistic, permutation test, sample retention, synthetic-shift alerts."""

import io
import os
import secrets
import tempfile
import time
from types import SimpleNamespace

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-drift-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import func, select

from app.bootstrap import init_db
from app.config import DATA_DIR
from app.db import SessionLocal
from app.main import app
from app.models import Audit, DriftRun, DriftSample, Image, Job, Project, TrainedModel, User, Version, Workspace
from app.routers import ops
from app.security import issue_access
from app.services import drift

WS = "labeldesk-demo"


@pytest.fixture(scope="module", autouse=True)
def _database():
    init_db()
    yield


@pytest.fixture(scope="module")
def api():
    """A minimal app wiring only the ops routers: main.py is owned by the lead."""
    with TestClient(app):
        pass
    mini = FastAPI()
    mini.include_router(ops.router)
    mini.include_router(ops.ws_router)
    client = TestClient(mini)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
    client.headers["Authorization"] = f"Bearer {issue_access(user.id)}"
    return client


@pytest.fixture()
def project():
    slug = f"drift-qa-{secrets.token_hex(3)}"
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        p = Project(workspace_id=ws.id, slug=slug, name=f"Drift QA {slug}", settings={})
        db.add(p)
        db.commit()
        pid = p.id
    yield p
    with SessionLocal() as db:  # the shared demo workspace stays under the project limit
        row = db.get(Project, pid)
        if row is not None:
            db.delete(row)
            db.commit()


def _noise(seed: int, size: int = 32) -> PImage.Image:
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 256, (size, size, 3), dtype=np.uint8)
    return PImage.fromarray(arr)


def _jpeg(colour: tuple[int, int, int], size: int = 32) -> bytes:
    b = io.BytesIO()
    PImage.new("RGB", (size, size), colour).save(b, "JPEG")
    return b.getvalue()


def _add_reference(pid: str, n: int, seed_base: int = 0) -> None:
    with SessionLocal() as db:
        for i in range(n):
            im = _noise(seed_base + i)
            rel = f"drift-test/{pid}/{i}.jpg"
            dest = DATA_DIR / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            im.save(dest, "JPEG", quality=90)
            db.add(
                Image(
                    project_id=pid,
                    name=f"ref{i}.jpg",
                    sha256=f"{pid}-{i}",
                    width=32,
                    height=32,
                    path=rel,
                    thumb=rel,
                    status="done",
                )
            )
        db.commit()


def _add_samples(project: Project, n: int, shift: float, seed_base: int = 100) -> None:
    with SessionLocal() as db:
        for i in range(n):
            base = np.asarray(drift.features(_noise(seed_base + i)))
            db.add(
                DriftSample(
                    workspace_id=project.workspace_id,
                    project_id=project.id,
                    sha256=f"{project.id}-sample-{i}",
                    path="",
                    features=(base + shift).tolist(),
                    width=32,
                    height=32,
                    created=time.time(),
                )
            )
        db.commit()


def test_mmd2_zero_for_identical_and_positive_for_shift():
    rng = np.random.default_rng(1)
    x = rng.normal(0, 1, (40, 6))
    y = rng.normal(0, 1, (40, 6))
    z = x + 3.0
    assert drift.mmd2(x, x) == 0.0
    assert drift.mmd2(x, z) > drift.mmd2(x, y)
    assert drift.mmd2(x, z) > 0.05


def test_permutation_p_low_for_shift_high_for_same():
    rng = np.random.default_rng(2)
    x = rng.normal(0, 1, (60, 8))
    y = rng.normal(0, 1, (60, 8))
    z = x + 3.0
    assert drift.permutation_p(x, z, permutations=100, seed=3) < 0.05
    assert drift.permutation_p(x, y, permutations=100, seed=3) > 0.05


def test_analyse_alerts_on_synthetic_shift(project):
    _add_reference(project.id, 24)
    _add_samples(project, 24, shift=12.0, seed_base=500)
    with SessionLocal() as db:
        p = db.get(Project, project.id)
        run = drift.analyse(db, p)
        assert run.status == "done"
        assert run.n_reference >= drift.DRIFT_MIN_SAMPLES
        assert run.n_current >= drift.DRIFT_MIN_SAMPLES
        assert run.statistic > 0
        assert run.p_value < drift.DRIFT_P
        assert run.alert is True
        audit = db.scalar(
            select(Audit).where(
                Audit.workspace_id == project.workspace_id,
                Audit.action == "drift.alert",
                Audit.target == p.name,
            )
        )
        assert audit is not None
        assert audit.meta.get("run_id") == run.id
        latest = drift.latest(db, p)
        assert latest is not None and latest["id"] == run.id and latest["alert"] is True
        assert drift.runs(db, p)[0]["id"] == run.id


def test_analyse_marks_insufficient_below_min_samples(project):
    _add_reference(project.id, 3, seed_base=700)
    _add_samples(project, 3, shift=0.0, seed_base=800)
    with SessionLocal() as db:
        p = db.get(Project, project.id)
        run = drift.analyse(db, p)
        assert run.status == "insufficient"
        assert run.alert is False
        assert run.p_value == 1.0
        assert run.n_reference == 3
        assert run.n_current == 3


def test_analyse_skips_reference_features_when_inputs_are_short(project, monkeypatch):
    """C2: a short sample window must not decode up to MAX_REFERENCE training images."""

    def boom(*args, **kwargs):
        raise AssertionError("reference features must not be read")

    monkeypatch.setattr(drift, "_reference_features", boom)
    _add_reference(project.id, 20)
    _add_samples(project, 2, shift=0.0, seed_base=900)
    with SessionLocal() as db:
        p = db.get(Project, project.id)
        run = drift.analyse(db, p)
        assert run.status == "insufficient"
        assert run.n_current == 2
        assert run.n_reference == 20


@pytest.mark.parametrize("status", ["insufficient", "failed"])
def test_any_attempt_throttles_the_daily_scheduler(project, status):
    """C2: the newest run throttles the next enqueue whatever its status."""
    with SessionLocal() as db:
        p = db.get(Project, project.id)
        v = Version(project_id=p.id, number=1, status="ready")
        db.add(v)
        db.flush()
        db.add(
            TrainedModel(
                workspace_id=p.workspace_id,
                project_id=p.id,
                version_id=v.id,
                name="Throttle model",
                arch="yolo26n",
                task="detect",
                status="ready",
                classes=["person"],
            )
        )
        db.add(
            DriftRun(
                workspace_id=p.workspace_id,
                project_id=p.id,
                status=status,
                created=time.time(),
                finished=time.time(),
            )
        )
        db.commit()
        before = db.scalar(select(func.count(Job.id)).where(Job.project_id == p.id, Job.kind == "drift"))
        drift.schedule_daily(db)
        after = db.scalar(select(func.count(Job.id)).where(Job.project_id == p.id, Job.kind == "drift"))
        assert after == before


def test_stride_caps_reference_ids_deterministically():
    """I7: a manifest with far more images than SQLite allows bind variables must be thinned."""
    ids = [f"img-{i}" for i in range(5000)]
    out = drift._stride_ids(ids)
    assert len(out) == drift.MAX_REFERENCE
    assert out[0] == "img-0"
    assert out == drift._stride_ids(ids)
    assert len(set(out)) == len(out)
    assert set(out) <= set(ids)
    assert drift._stride_ids(["a", "b"]) == ["a", "b"]
    assert drift._stride_ids(["a"], 0) == []


def test_feature_source_and_vector_size_follow_the_embedder(monkeypatch):
    """I6: one embeddings seam decides both the label and the vector size."""
    assert drift.feature_source() in ("clip", "colour/layout map")
    monkeypatch.setattr(drift.embeddings, "available", lambda: True)
    monkeypatch.setattr(drift.embeddings, "embed_image", lambda im, sha=None: [0.25] * 8)
    assert drift.feature_source() == "clip"
    assert len(drift.features(_noise(3))) == 8


def test_run_labels_the_fallback_that_was_actually_used(project, monkeypatch):
    """N3: an importable-but-unusable encoder must not make the run claim `clip`."""
    monkeypatch.setattr(drift.embeddings, "available", lambda: True)

    def unavailable(*args, **kwargs):
        raise RuntimeError("CLIP embeddings are not available")

    monkeypatch.setattr(drift.embeddings, "embed_image", unavailable)
    _add_reference(project.id, 20, seed_base=1400)
    _add_samples(project, 20, shift=2.0, seed_base=1500)
    with SessionLocal() as db:
        run = drift.analyse(db, db.get(Project, project.id))
    assert run.status == "done"
    assert run.feature_source == "colour/layout map"


def test_run_labels_clip_when_clip_vectors_were_used(project, monkeypatch):
    """N3: the label follows the vectors, not the module list."""
    monkeypatch.setattr(drift.embeddings, "available", lambda: True)
    monkeypatch.setattr(drift.embeddings, "embed_image", lambda im, sha=None: [0.25] * 8)
    _add_reference(project.id, 20, seed_base=1600)
    _add_samples(project, 20, shift=1.0, seed_base=1700)
    with SessionLocal() as db:
        run = drift.analyse(db, db.get(Project, project.id))
    assert run.status == "done"
    assert run.feature_source == "clip"


def test_a_run_without_vectors_does_not_claim_a_feature_source(project):
    """N3: an insufficient run never computed features, so it must not advertise one."""
    _add_samples(project, 2, shift=0.0, seed_base=1800)
    with SessionLocal() as db:
        run = drift.analyse(db, db.get(Project, project.id))
    assert run.status == "insufficient"
    assert run.feature_source == "unknown"


def test_drift_job_releases_the_embedding_backend(project, monkeypatch):
    """N2: the CLIP model must not outlive the job that loaded it."""
    released = []
    monkeypatch.setattr(drift.embeddings, "release", lambda: released.append("release"))

    def boom(db, p):
        raise RuntimeError("analysis exploded")

    monkeypatch.setattr(drift, "analyse", boom)
    out = drift.run_job(SimpleNamespace(id="job-drift", project_id=project.id))
    assert out["status"] == "failed"
    assert released == ["release"]


def test_record_sample_caps_and_dedupes(project, monkeypatch):
    monkeypatch.setattr(drift, "DRIFT_MAX_SAMPLES", 2)
    with SessionLocal() as db:
        p = db.get(Project, project.id)
        first = drift.record_sample(db, project.workspace_id, p, None, _jpeg((10, 20, 30)))
        db.commit()
        first_created, first_path = first.created, DATA_DIR / first.path
        assert first.path.startswith(f"workspaces/{project.workspace_id}/drift/{project.id}/")
        assert first_path.exists()

        time.sleep(0.01)
        again = drift.record_sample(db, project.workspace_id, p, None, _jpeg((10, 20, 30)))
        db.commit()
        assert again.id == first.id
        assert drift.sample_count(db, p) == 1
        assert again.created > first_created

        # make the deduped row unambiguously the oldest, then push past the cap
        again.created = time.time() - 100
        db.commit()
        second = drift.record_sample(db, project.workspace_id, p, None, _jpeg((200, 10, 10)))
        db.commit()
        third = drift.record_sample(db, project.workspace_id, p, None, _jpeg((10, 200, 10)))
        db.commit()
        assert drift.sample_count(db, p) == 2
        assert not first_path.exists()
        assert {second.id, third.id} == {
            row.id for row in db.scalars(select(DriftSample).where(DriftSample.project_id == p.id))
        }


def test_record_sample_corrupt_image_returns_none(project):
    with SessionLocal() as db:
        p = db.get(Project, project.id)
        assert drift.record_sample(db, project.workspace_id, p, None, b"not an image") is None
        assert drift.sample_count(db, p) == 0


def test_record_sample_swallows_a_storage_failure(project, monkeypatch):
    """I4: a full or read-only data volume must never escape as an inference error."""
    data = _jpeg((1, 2, 3))

    def boom(*args, **kwargs):
        raise OSError("data volume is full")

    monkeypatch.setattr(PImage.Image, "save", boom)
    with SessionLocal() as db:
        p = db.get(Project, project.id)
        assert drift.record_sample(db, project.workspace_id, p, None, data) is None
        assert drift.sample_count(db, p) == 0


def test_schedule_daily_is_idempotent(project):
    with SessionLocal() as db:
        p = db.get(Project, project.id)
        v = Version(project_id=p.id, number=1, status="ready")
        db.add(v)
        db.flush()
        db.add(
            TrainedModel(
                workspace_id=p.workspace_id,
                project_id=p.id,
                version_id=v.id,
                name="Drift model",
                arch="yolo26n",
                task="detect",
                status="ready",
                classes=["person"],
            )
        )
        db.commit()
        assert drift.schedule_daily(db) >= 1
        job = db.scalar(select(Job).where(Job.project_id == p.id, Job.kind == "drift", Job.status == "queued"))
        assert job is not None and job.params["model_id"]
        assert drift.schedule_daily(db) == 0


def test_drift_endpoints(api, project):
    base = f"/api/ws/{WS}/projects/{project.slug}"
    body = api.get(f"{base}/drift").json()
    assert body["samples"] == 0
    assert body["latest"] is None
    assert body["config"]["min_samples"] == drift.DRIFT_MIN_SAMPLES
    assert body["source"] == drift.feature_source()

    # no ready model yet -> state conflict
    assert api.post(f"{base}/drift/scan").status_code == 409
    assert api.post(f"{base}/drift/nope/send-to-labeling").status_code == 404

    rows = api.get(f"/api/ws/{WS}/drift").json()
    assert any(row["project_id"] == project.id and row["slug"] == project.slug for row in rows)
