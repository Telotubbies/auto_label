"""T-052: `drift.production_model` asks the alias service once, in its real 3-arg form.

The old body probed `(db, project)` first and swallowed the `TypeError` on every call, because the
2-argument signature has not existed since the alias service landed. These tests pin the contract
the caller actually gets: the `production` alias when it resolves to a ready model, and the newest
ready model otherwise — including when the alias service is not importable at all.
"""
import dataclasses
import os
import sys
import uuid
from unittest.mock import Mock, call

os.environ.setdefault("LD_WORKER_TOKEN", "test-worker-token-0123456789abcdef")

import app.services
from app.adapters.base import Availability
from app.db import SessionLocal
from app.models import Project, TrainedModel, User, Version, Workspace
from app.services import deployments, drift


def _project():
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        u = User(id="u" + suffix, email=f"ds-{suffix}@x.io", name="D", pw_hash="x")
        db.add(u); db.flush()
        ws = Workspace(id="w" + suffix, slug=f"ds-{suffix}", name="D", owner_id=u.id)
        db.add(ws); db.flush()
        p = Project(workspace_id=ws.id, slug=f"dsp-{suffix}", name="Drift status")
        db.add(p); db.flush()
        v = Version(project_id=p.id, number=1, status="ready", stats={})
        db.add(v); db.flush()
        db.commit()
        return ws.id, p.id, v.id


def _model(ws_id, p_id, v_id, name, created):
    with SessionLocal() as db:
        m = TrainedModel(workspace_id=ws_id, project_id=p_id, version_id=v_id, name=name, arch="yolo26n",
                         variant="yolo26n", task="detect", status="ready", family="ultralytics",
                         classes=[], created=created)
        db.add(m); db.commit()
        return m.id


def test_production_model_prefers_the_alias(monkeypatch):
    ws_id, p_id, v_id = _project()
    alias_id = _model(ws_id, p_id, v_id, "alias", created=1.0)
    _model(ws_id, p_id, v_id, "newest", created=2.0)

    def alias_model(db, project, alias):        # the service's real 3-argument signature
        return db.get(TrainedModel, alias_id)

    spy = Mock(wraps=alias_model)
    monkeypatch.setattr(deployments, "alias_model", spy)
    with SessionLocal() as db:
        project = db.get(Project, p_id)
        got = drift.production_model(db, project)
        assert got.id == alias_id
        assert spy.call_args_list == [call(db, project, "production")]


def test_production_model_falls_back_to_newest_ready(monkeypatch):
    ws_id, p_id, v_id = _project()
    _model(ws_id, p_id, v_id, "older", created=1.0)
    newest_id = _model(ws_id, p_id, v_id, "newest", created=2.0)

    monkeypatch.setattr(deployments, "alias_model", lambda db, project, alias: None)
    with SessionLocal() as db:
        assert drift.production_model(db, db.get(Project, p_id)).id == newest_id


def test_production_model_survives_a_missing_alias_service(monkeypatch):
    ws_id, p_id, v_id = _project()
    ready_id = _model(ws_id, p_id, v_id, "only-one", created=1.0)

    # Make `from . import deployments` in drift raise: no module and no package attribute.
    monkeypatch.setitem(sys.modules, "app.services.deployments", None)
    monkeypatch.delattr(app.services, "deployments", raising=False)
    with SessionLocal() as db:
        assert drift.production_model(db, db.get(Project, p_id)).id == ready_id


def test_availability_has_no_vram_field():
    """`catalog()` never read `Availability.vram_mb`, so the probe must not advertise it."""
    assert "vram_mb" not in {f.name for f in dataclasses.fields(Availability)}
