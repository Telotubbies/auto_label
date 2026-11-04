"""Quotas: the real job size is reserved up front and long jobs clamp at the allowance."""

import io
import os
import secrets
import shutil
import tempfile
from contextlib import contextmanager, nullcontext
from types import SimpleNamespace

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-quota-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import select

from app import worker
from app.config import DATA_DIR
from app.db import SessionLocal
from app.main import app
from app.models import Image, Job, Project, TrainedModel, Version, Workspace

WS = "labeldesk-demo"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        tok = c.post("/api/auth/login", json={"email": "demo@labeldesk.dev", "password": "demo1234"}).json()["token"]
        c.headers["Authorization"] = f"Bearer {tok}"
        yield c


@pytest.fixture()
def scratch():
    """A project with a ready version, a ready model and three unlabelled images."""
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        p = Project(
            workspace_id=ws.id,
            slug=f"quota-{secrets.token_hex(3)}",
            name="Quota QA",
            type="object-detection",
            settings={},
        )
        db.add(p)
        db.flush()
        v = Version(
            project_id=p.id,
            number=1,
            name="quota-v1",
            status="ready",
            stats={"class_names": ["person"], "splits": {"train": 100, "valid": 10}},
        )
        db.add(v)
        db.flush()
        m = TrainedModel(
            workspace_id=ws.id,
            project_id=p.id,
            version_id=v.id,
            name="quota-model",
            arch="yolo26n",
            family="ultralytics",
            variant="yolo26n",
            task="detect",
            status="ready",
            classes=["person"],
        )
        db.add(m)
        db.flush()
        ids = []
        for i in range(3):
            rel = f"quota-test/{p.id}/{i}.jpg"
            dest = DATA_DIR / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            b = io.BytesIO()
            PImage.new("RGB", (16, 16), (i * 10 + 1, 20, 30)).save(b, "JPEG")
            dest.write_bytes(b.getvalue())
            img = Image(
                project_id=p.id,
                name=f"q{i}.jpg",
                sha256=f"{p.id}-{i}",
                width=16,
                height=16,
                path=rel,
                thumb="",
                size=len(b.getvalue()),
                n_annotations=0,
            )
            db.add(img)
            db.flush()
            ids.append(img.id)
        db.commit()
        data = {
            "ws_id": ws.id,
            "project_id": p.id,
            "slug": p.slug,
            "version_id": v.id,
            "model_id": m.id,
            "image_ids": ids,
        }
    yield data
    with SessionLocal() as db:
        row = db.get(Project, data["project_id"])
        if row is not None:
            db.delete(row)
            db.commit()
    shutil.rmtree(DATA_DIR / "quota-test" / data["project_id"], ignore_errors=True)


def _used(ws_id: str, metric: str) -> float:
    from app.services import metering

    with SessionLocal() as db:
        ws = db.get(Workspace, ws_id)
        since = None if metric == "storage_bytes" else metering.month_start()
        return metering.used(db, ws, metric, since=since)


@contextmanager
def _allowance(ws_id: str, **values):
    """Set per-workspace allowances for the block, then restore the original quotas."""
    with SessionLocal() as db:
        ws = db.get(Workspace, ws_id)
        old = dict(ws.quotas or {})
        ws.quotas = {**old, **values}
        db.commit()
    try:
        yield
    finally:
        with SessionLocal() as db:
            ws = db.get(Workspace, ws_id)
            ws.quotas = old or None
            db.commit()


def test_train_reserves_its_gpu_estimate(client, scratch):
    """I1: 100 images × 10 epochs estimates ~100 s; a 30 s allowance must block up front."""
    used = _used(scratch["ws_id"], "gpu_seconds")
    with _allowance(scratch["ws_id"], gpu_seconds=used + 30):
        r = client.post(
            f"/api/ws/{WS}/projects/{scratch['slug']}/train",
            json={"version_id": scratch["version_id"], "epochs": 10, "imgsz": 640},
        )
        assert r.status_code == 402, r.text
        assert "GPU time quota" in r.json()["detail"]


def test_autolabel_reserves_the_selected_image_count(client, scratch):
    """I1: three selected images need three AI calls, not one."""
    used = _used(scratch["ws_id"], "ai_calls")
    with _allowance(scratch["ws_id"], ai_calls=used + 1):
        r = client.post(
            f"/api/ws/{WS}/projects/{scratch['slug']}/autolabel",
            json={"model_ref": f"trained:{scratch['model_id']}", "image_ids": scratch["image_ids"]},
        )
        assert r.status_code == 402, r.text
        assert "AI calls quota" in r.json()["detail"]


def _autolabel_job(scratch) -> Job:
    """A running autolabel job over the scratch project's three unlabelled images."""
    with SessionLocal() as db:
        j = Job(
            workspace_id=scratch["ws_id"],
            project_id=scratch["project_id"],
            kind="autolabel",
            status="running",
            params={"image_ids": scratch["image_ids"], "only_unannotated": True},
        )
        db.add(j)
        db.commit()
        job = db.get(Job, j.id)
        db.expunge(job)
        return job


def _no_annotations(monkeypatch):
    monkeypatch.setattr(worker, "label_image", lambda *args, **kwargs: [])
    monkeypatch.setattr(worker.imaging, "load", lambda path: None)


def test_autolabel_clamps_at_the_call_allowance(scratch, monkeypatch):
    """I1: a job enqueued earlier stops before it overruns an almost exhausted allowance."""
    used = _used(scratch["ws_id"], "ai_calls")
    with _allowance(scratch["ws_id"], ai_calls=used + 1):
        job = _autolabel_job(scratch)
        _no_annotations(monkeypatch)
        out = worker.run_autolabel(job)
        assert out["images"] == 1  # only the image the allowance could pay for was processed
        assert out["selected"] == 3
        assert out["quota_clamped"] is True
    assert _used(scratch["ws_id"], "ai_calls") == pytest.approx(used + 1)


def test_autolabel_reports_processed_not_selected_images(scratch, monkeypatch):
    """R3-3: a run that is not clamped counts every processed image, not just the selection."""
    used = _used(scratch["ws_id"], "ai_calls")
    with _allowance(scratch["ws_id"], ai_calls=used + 10):
        job = _autolabel_job(scratch)
        _no_annotations(monkeypatch)
        out = worker.run_autolabel(job)
    assert out == {"images": 3, "selected": 3, "labeled": 0, "annotations": 0, "quota_clamped": False}


def test_autolabel_processes_nothing_when_the_allowance_is_already_spent(scratch, monkeypatch):
    """R3-3: an exhausted allowance must not claim three images were processed."""
    used = _used(scratch["ws_id"], "ai_calls")
    with _allowance(scratch["ws_id"], ai_calls=used):
        job = _autolabel_job(scratch)
        _no_annotations(monkeypatch)
        out = worker.run_autolabel(job)
    assert out["images"] == 0
    assert out["selected"] == 3
    assert out["quota_clamped"] is True


# --- N1: a budget-truncated training run must never look finished -------------------


def _train_job(scratch, epochs: int = 10, status: str = "queued", weights: str | None = None) -> tuple[str, str]:
    """A queued training job on its own model row, as /train creates it."""
    with SessionLocal() as db:
        m = TrainedModel(
            workspace_id=scratch["ws_id"],
            project_id=scratch["project_id"],
            version_id=scratch["version_id"],
            name="quota-train",
            arch="yolo26n",
            family="ultralytics",
            variant="yolo26n",
            task="detect",
            status=status,
            weights=weights,
            classes=["person"],
        )
        db.add(m)
        db.flush()
        j = Job(
            workspace_id=scratch["ws_id"],
            project_id=scratch["project_id"],
            kind="train",
            status="running",
            params={"model_id": m.id, "version_id": scratch["version_id"], "options": {"epochs": epochs}},
        )
        db.add(j)
        db.commit()
        return m.id, j.id


def _train_stubs(monkeypatch, train):
    """Neutralise the dataset export, weight lookup and exclusive lease around the fake adapter."""
    monkeypatch.setattr(worker.versioning, "cached_export", lambda *args, **kwargs: None)
    monkeypatch.setattr(worker, "_start_weights", lambda *args, **kwargs: "yolo26n.pt")
    monkeypatch.setattr(worker.scheduler, "exclusive", lambda reason: nullcontext())
    monkeypatch.setitem(worker.ADAPTERS, "ultralytics", SimpleNamespace(train=train))


def _job_and_model(job_id: str, model_id: str) -> tuple[Job, TrainedModel]:
    with SessionLocal() as db:
        return db.get(Job, job_id), db.get(TrainedModel, model_id)


def test_train_refuses_to_start_without_a_minimal_gpu_allowance(scratch, monkeypatch):
    """N1: when the allowance cannot fund one minimal run, do not train at all."""
    mid, jid = _train_job(scratch)
    monkeypatch.setattr(worker.metering, "remaining", lambda db, ws, metric: 5.0)
    trained = []
    _train_stubs(monkeypatch, lambda *args, **kwargs: trained.append("train"))

    worker.run_one(jid)

    job, model = _job_and_model(jid, mid)
    assert job.status == "failed"
    assert "GPU time allowance" in job.error
    assert model.status == "failed"
    assert not model.weights
    assert trained == []


@pytest.mark.parametrize("epochs_done", [0, 1])
def test_train_budget_stop_fails_the_job_instead_of_registering_the_model(scratch, monkeypatch, epochs_done):
    """N1: zero or partial epochs under a clamp is a failure, not a ready model."""
    mid, jid = _train_job(scratch)
    monkeypatch.setattr(worker.metering, "remaining", lambda db, ws, metric: 10_000.0)
    monkeypatch.setattr(worker, "_over_budget", lambda *args: True)  # the lease outlives the allowance

    def fake_train(variant, data_dir, task, opts, on_epoch, should_stop):
        for ep in range(1, epochs_done + 1):
            on_epoch(ep, 10, {})
        assert should_stop() is True
        return SimpleNamespace(weights="models/partial/best.pt")

    _train_stubs(monkeypatch, fake_train)

    worker.run_one(jid)

    job, model = _job_and_model(jid, mid)
    assert job.status == "failed"
    assert "GPU time allowance" in job.error
    assert f"{epochs_done} of 10 epochs" in job.error
    assert model.status == "failed"
    assert not model.weights  # the truncated checkpoint is never registered
    assert model.status != "ready"


def test_a_clamped_retrain_keeps_the_previous_checkpoint_and_status(scratch, monkeypatch):
    """N1: a run that would replace a good model must leave the old one deployable."""
    mid, jid = _train_job(scratch, status="ready", weights="models/prev/best.pt")
    monkeypatch.setattr(worker.metering, "remaining", lambda db, ws, metric: 10_000.0)
    monkeypatch.setattr(worker, "_over_budget", lambda *args: True)

    def fake_train(variant, data_dir, task, opts, on_epoch, should_stop):
        on_epoch(1, 10, {})
        assert should_stop() is True
        return SimpleNamespace(weights="models/partial/best.pt")

    _train_stubs(monkeypatch, fake_train)

    worker.run_one(jid)

    job, model = _job_and_model(jid, mid)
    assert job.status == "failed"
    assert "GPU time allowance" in job.error
    assert model.status == "ready"
    assert model.weights == "models/prev/best.pt"
