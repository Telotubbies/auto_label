"""Task 12: demo seed v2 — ready version, evaluated YOLO26n model and the gate stream.

The seed runs from bootstrap on a fresh demo DB; these tests pin the demo content it must leave
behind and its idempotency. No GPU and no network: the model's weights and metrics come from the
repo's recorded PPE training run, not from live inference.
"""

import os
import tempfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-test-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import seed_v2
from app.config import DATA_DIR
from app.db import SessionLocal
from app.main import app
from app.models import Project, Stream, TrainedModel, Version, Workspace


@pytest.fixture(scope="module", autouse=True)
def _booted():
    """Run the app lifespan once so bootstrap creates the schema and the v2 demo seed."""
    with TestClient(app):
        yield


def _demo(db):
    ws = db.scalar(select(Workspace).where(Workspace.slug == seed_v2.WS_SLUG))
    assert ws is not None, "bootstrap must create the demo workspace"
    p = db.scalar(select(Project).where(Project.workspace_id == ws.id, Project.slug == seed_v2.PROJECT_SLUG))
    assert p is not None, "bootstrap must create the PPE demo project"
    return ws, p


def _model(db, p):
    return db.scalar(
        select(TrainedModel).where(TrainedModel.project_id == p.id, TrainedModel.name == seed_v2.MODEL_NAME)
    )


def _stream(db, p):
    return db.scalar(select(Stream).where(Stream.project_id == p.id, Stream.name == seed_v2.STREAM_NAME))


def test_seed_leaves_a_ready_version():
    with SessionLocal() as db:
        _, p = _demo(db)
        v = db.scalars(select(Version).where(Version.project_id == p.id).order_by(Version.number)).first()
        assert v is not None and v.status == "ready", "the demo needs a generated version to train on"
        assert v.stats.get("images", 0) > 0 and v.stats.get("splits", {}).get("train", 0) > 0
        assert "person" in v.stats.get("class_names", [])
        assert (DATA_DIR / "versions" / v.id / "manifest.json").is_file()


def test_seed_leaves_a_ready_yolo26n_model_with_recorded_evaluation():
    with SessionLocal() as db:
        _, p = _demo(db)
        m = _model(db, p)
        assert m is not None and m.status == "ready"
        assert (m.arch, m.variant, m.family, m.task) == (
            "yolo26n",
            "yolo26n",
            "ultralytics",
            "detect",
        )
        assert 0 < m.metrics["map50"] < 1 and 0 < m.metrics["map5095"] < m.metrics["map50"]
        # Honest provenance: the aggregate numbers are the recorded run, the deep COCO panel is not re-run here.
        assert "not evaluated" in m.metrics["eval"]["note"]
        assert m.weights and (DATA_DIR / m.weights).is_file(), "a ready model needs local weights"
        assert m.classes, "the model card shows its classes"
        assert m.version_id and db.get(Version, m.version_id).status == "ready"


def test_seed_leaves_a_stopped_gate_camera_with_zone_and_rules():
    with SessionLocal() as db:
        _, p = _demo(db)
        m = _model(db, p)
        s = _stream(db, p)
        assert s is not None and s.status == "stopped", "streams always start stopped"
        assert s.source == "file:videos/demo.mp4"
        assert s.model_ref == f"trained:{m.id}"
        assert s.zones and s.zones[0]["id"] == "gate" and len(s.zones[0]["points"]) >= 6
        assert [r["kind"] for r in s.rules] == ["line", "count"]
        assert s.rules[0]["class"] == "person" and s.rules[1]["class"] == "person"
        assert (DATA_DIR / "videos" / "demo.mp4").is_file(), "the demo stream needs a looping clip"


def test_seed_is_idempotent():
    first = seed_v2.seed_demo_v2()
    second = seed_v2.seed_demo_v2()
    assert first == second and first, "a restart must reuse the same demo rows"
    with SessionLocal() as db:
        _, p = _demo(db)
        assert db.scalar(select(func.count(Version.id)).where(Version.project_id == p.id)) == 1
        assert (
            db.scalar(
                select(func.count(TrainedModel.id)).where(
                    TrainedModel.project_id == p.id,
                    TrainedModel.name == seed_v2.MODEL_NAME,
                )
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count(Stream.id)).where(Stream.project_id == p.id, Stream.name == seed_v2.STREAM_NAME)
            )
            == 1
        )


def test_seed_skips_a_project_that_does_not_exist(monkeypatch):
    monkeypatch.setattr(seed_v2, "PROJECT_SLUG", "no-such-project")
    assert seed_v2.seed_demo_v2() == {}
