"""T-1200 — the e2e entrypoint refuses production, and its fakes are deterministic and offline.

The harness exists so a journey spec is a page of intent: the API runs the real app with fake
workers, so no GPU, model download or network call can happen behind a journey.
"""
import importlib
import io
import sys
import time
from pathlib import Path

import pytest
from PIL import Image as PImage
from sqlalchemy import func, select

from app import worker
from app.adapters.base import validate_prediction
from app.config import DATA_DIR
from app.db import SessionLocal
from app.models import Batch, Image, Job, LabelClass, Project, TrainedModel, Version, Video, Workspace

WS = "labeldesk-demo"
KINDS = ("version", "export", "train", "autolabel", "infer_video", "export_engine",
         "extract_frames", "engine_apply", "model_pull", "health")
ROOT = Path(__file__).resolve().parents[1]          # apps/backend


def _import_entrypoint(monkeypatch, **env):
    """Import `e2e.app` fresh under the given environment, as uvicorn would."""
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    sys.modules.pop("e2e.app", None)
    return importlib.import_module("e2e.app")


def test_the_entrypoint_refuses_production(monkeypatch):
    monkeypatch.setenv("LD_E2E", "1")
    monkeypatch.setenv("LD_ENV", "production")
    sys.modules.pop("e2e.app", None)
    with pytest.raises(RuntimeError, match="production"):
        importlib.import_module("e2e.app")
    assert "e2e.app" not in sys.modules, "a refused entrypoint must not stay imported"


def test_the_entrypoint_refuses_without_the_e2e_env(monkeypatch):
    monkeypatch.delenv("LD_E2E", raising=False)
    monkeypatch.setenv("LD_ENV", "development")
    sys.modules.pop("e2e.app", None)
    with pytest.raises(RuntimeError, match="LD_E2E"):
        importlib.import_module("e2e.app")
    assert "e2e.app" not in sys.modules


@pytest.fixture()
def harness(monkeypatch):
    """The imported entrypoint, with every worker seam put back when the test ends."""
    handlers = dict(worker.HANDLERS)
    adapters = dict(worker.ADAPTERS)
    scheduler, kinds = worker.scheduler, list(worker.LOCAL_JOB_KINDS)
    module = _import_entrypoint(monkeypatch, LD_E2E="1", LD_ENV="development")
    try:
        yield module
    finally:
        worker.HANDLERS.clear()
        worker.HANDLERS.update(handlers)
        worker.ADAPTERS.clear()
        worker.ADAPTERS.update(adapters)
        worker.scheduler = scheduler
        worker.LOCAL_JOB_KINDS[:] = kinds
        sys.modules.pop("e2e.app", None)


@pytest.fixture()
def scratch():
    """A project with a ready version, a ready model, three images and one queued video."""
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        p = Project(workspace_id=ws.id, slug=f"e2e-{time.time_ns()}", name="E2E QA",
                    type="object-detection", settings={})
        db.add(p)
        db.flush()
        classes = [LabelClass(project_id=p.id, name=name, color=color)
                   for name, color in (("person", "#8b5cf6"), ("helmet", "#22c55e"))]
        db.add_all(classes)
        v = Version(project_id=p.id, number=1, name="e2e-v1", status="generating", settings={})
        db.add(v)
        db.flush()
        m = TrainedModel(workspace_id=ws.id, project_id=p.id, version_id=v.id, name="e2e-model",
                         arch="yolo26n", variant="yolo26n", family="ultralytics", task="detect",
                         status="queued", classes=["person", "helmet"])
        db.add(m)
        db.flush()
        rel_dir = f"e2e-test/{p.id}"
        images = []
        for i in range(3):
            rel = f"{rel_dir}/{i}.jpg"
            dest = DATA_DIR / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            buf = io.BytesIO()
            PImage.new("RGB", (320, 180), (20 + i, 40, 60)).save(buf, "JPEG")
            dest.write_bytes(buf.getvalue())
            img = Image(project_id=p.id, name=f"e2e{i}.jpg", sha256=f"{p.id}-{i}", width=320, height=180,
                        path=rel, thumb="", size=len(buf.getvalue()), status="done", split="train")
            db.add(img)
            images.append(img)
        video = Video(project_id=p.id, workspace_id=ws.id, name="line.mp4", path=f"{rel_dir}/line.mp4",
                      width=320, height=180, fps=10.0, frame_count=10, status="queued")
        db.add(video)
        db.commit()
        data = {"ws_id": ws.id, "project_id": p.id, "version_id": v.id, "model_id": m.id,
                "image_ids": [i.id for i in images], "video_id": video.id}
    yield data
    with SessionLocal() as db:
        row = db.get(Project, data["project_id"])
        if row is not None:
            db.delete(row)
            db.commit()
    import shutil
    shutil.rmtree(DATA_DIR / "e2e-test" / data["project_id"], ignore_errors=True)


def _params(kind: str, s: dict) -> dict:
    if kind == "version":
        return {"version_id": s["version_id"]}
    if kind == "export":
        return {"version_id": s["version_id"], "format": "coco"}
    if kind in ("train", "export_engine"):
        return {"model_id": s["model_id"]}
    if kind == "extract_frames":
        return {"video_id": s["video_id"]}
    if kind == "engine_apply":
        return {"host": "e2e-gpu", "action": "install", "engines": [{"id": "engine-a", "version": "1.0"}]}
    if kind == "model_pull":
        return {"host": "e2e-gpu", "model": "qwen2.5-vl-7b", "variant": "awq"}
    return {}


def _queue(s: dict, kind: str) -> str:
    with SessionLocal() as db:
        job = Job(workspace_id=s["ws_id"], project_id=s["project_id"], kind=kind,
                  status="queued", params=_params(kind, s))
        db.add(job)
        db.commit()
        return job.id


def _detached(jid: str) -> Job:
    with SessionLocal() as db:
        job = db.get(Job, jid)
        db.expunge(job)
    return job


def _assert_row(db, kind: str, job: Job, s: dict) -> None:
    """The row the real handler would write, read back after the fake ran."""
    if kind == "version":
        v = db.get(Version, s["version_id"])
        assert v.status == "ready"
        assert v.stats["images"] == 3 and v.stats["splits"]["train"] == 3
    elif kind == "export":
        art = DATA_DIR / job.result["file"]
        assert art.is_file() and art.stat().st_size == job.result["bytes"] > 0
    elif kind == "train":
        m = db.get(TrainedModel, s["model_id"])
        assert m.status == "ready" and (DATA_DIR / m.weights).is_file()
        assert m.metrics["map50"] == 0.874 and m.metrics["map5095"] == 0.612
        assert (DATA_DIR / "models" / m.id / "metrics.json").is_file()
        assert job.result["stages"]["register"]["status"] == "done"
    elif kind == "autolabel":
        assert job.result["labeled"] == 3 and job.result["annotations"] == 6
        labelled = db.scalar(select(func.count(Image.id)).where(Image.project_id == s["project_id"],
                                                              Image.n_annotations > 0))
        assert labelled == 3
    elif kind == "export_engine":
        m = db.get(TrainedModel, s["model_id"])
        assert m.runtime_refs["engine"] == f"engines/{m.id}.engine"
    elif kind == "extract_frames":
        assert db.get(Video, s["video_id"]).status == "ready"
        assert job.result["frames"] == 3
        frames = db.scalar(select(func.count(Image.id)).where(Image.batch_id == job.result["batch_id"]))
        assert frames == 3 and db.get(Batch, job.result["batch_id"]).source == "video"
    elif kind == "health":
        assert job.result["leakage_pairs"] == 0 and job.result["size_buckets"]["small"] >= 0
    elif kind == "infer_video":
        assert job.result["frames"] == 3
    elif kind == "engine_apply":
        assert job.result["installed"] == ["engine-a"]
    elif kind == "model_pull":
        assert job.result["model"] == "qwen2.5-vl-7b" and job.result["bytes"] == 0


@pytest.mark.parametrize("kind", KINDS)
def test_every_fake_job_finishes_and_writes_its_row(harness, scratch, kind):
    jid = _queue(scratch, kind)
    started = time.monotonic()
    worker.run_one(jid)
    took = time.monotonic() - started

    with SessionLocal() as db:
        job = db.get(Job, jid)
        assert job.status == "done", job.error
        assert job.result["phase"] == "done"
        assert len(job.result["log"]) == 3, job.result["log"]
        _assert_row(db, kind, job, scratch)
    # The queue path also pays for SQLite and the webhook row; the fake body is the promise.
    assert took < 0.5, f"{kind} took {took * 1000:.0f} ms; a fake job must never look like real work"

    if kind in ("version", "export", "train", "autolabel"):
        job = _detached(jid)
        started = time.monotonic()
        harness.fakes.HANDLERS[kind](job)
        took = time.monotonic() - started
        assert took < 0.2, f"{kind} took {took * 1000:.0f} ms; the harness promises under 200 ms"


@pytest.mark.parametrize("size", [(320, 180), (640, 480), (1920, 1080)])
def test_the_fake_prediction_is_schema_clean(size):
    from e2e import fakes

    out = fakes.ADAPTER.predict("face-detector", PImage.new("RGB", size))

    validate_prediction(out)
    assert out["image"] == {"width": size[0], "height": size[1]}
    assert len(out["predictions"]) >= 2
    for pred in out["predictions"]:
        assert 0 <= pred["x"] <= pred["x"] + pred["width"] <= size[0]
        assert 0 <= pred["y"] <= pred["y"] + pred["height"] <= size[1]
    assert len(out["predictions"][0]["points"]) >= 8


def test_the_fake_adapter_names_no_network():
    src = (ROOT / "e2e" / "fakes.py").read_text(encoding="utf-8")
    for name in ("requests", "httpx", "urllib", "socket"):
        assert name not in src, f"fakes.py must stay offline, but it names {name}"
