"""Parity guard, area 6: deploy threshold, workflow blocks and zone geometry.

Pins the shipped behaviour behind the HAVE rows of `docs/research/roboflow-parity/backlog/T-006.md`:
6-F6.9 (the deploy form's confidence travels to the model and an omission keeps the model's own
threshold), 6-F6.22 (every block type saves with the fields its panel edits, and a bad value is
refused with its block number) and 6-F6.35 (the block catalogue keeps `rule` and `sink` kinds).

Already pinned elsewhere, so this guard does not repeat them: the alias switch/rollback/no-op
(`test_deployments.py`), the hosted alias route (`test_task25_integration.py`), the block validation
matrix and flag-off 404 (`test_workflows.py::test_block_validation`,
`::test_flag_off_hides_every_workflow_route`), versioned saves/restore (`test_workflows.py`), the
runner's rule/sink behaviour (`test_workflow_runner.py`) and the stream zone/line validation plus the
crossing (`test_streams.py`).

Nothing here starts a stream, runs a workflow model or queues training: rows are inserted directly and
the one predict test stands a recorder in for the resolved adapter.
"""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import select

from app.adapters import model_conf
from app.db import SessionLocal
from app.main import app
from app.models import Member, Project, TrainedModel, User, Version, Workspace
from app.routers import training
from app.security import issue_access
from app.services import workflows

WS = "parity-guard-area6"
DETECT = "deploy-guard"
BEST_F1 = 0.62


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def _user(db, email: str) -> User:
    u = User(email=email, name=email.split("@")[0], pw_hash="")
    db.add(u)
    return u


@pytest.fixture(scope="module")
def users(c):
    with SessionLocal() as db:
        admin = _user(db, "area6-admin@test.local")
        db.flush()
        ws = Workspace(slug=WS, name="Area 6 Guard", owner_id=admin.id)
        db.add(ws)
        db.flush()
        db.add(Member(workspace_id=ws.id, user_id=admin.id, role="admin"))
        db.commit()
        return {"admin": admin.id}


def _headers(uid: str) -> dict:
    return {"Authorization": f"Bearer {issue_access(uid)}"}


def _project(slug: str = DETECT) -> str:
    """Get-or-create the guard project, so a single-test selection still has its workspace row."""
    with SessionLocal() as db:
        workspace = db.scalar(select(Workspace).where(Workspace.slug == WS))
        existing = db.scalar(select(Project).where(Project.workspace_id == workspace.id,
                                                  Project.slug == slug))
        if existing is not None:
            return existing.id
        p = Project(workspace_id=workspace.id, slug=slug, name=slug, type="object-detection",
                    settings={})
        db.add(p)
        db.flush()
        pid = p.id
        db.commit()
    return pid


def _version(project_id: str, number: int = 1) -> str:
    with SessionLocal() as db:
        v = Version(project_id=project_id, number=number, name=f"guard-{number}", status="ready",
                    stats={"class_names": ["person"], "splits": {"train": 12, "valid": 3}})
        db.add(v)
        db.flush()
        vid = v.id
        db.commit()
    return vid


def _model(project_id: str, version_id: str, name: str, *, conf: float | None = BEST_F1) -> str:
    """One ready training row. `conf` is the evaluator's best-F1 threshold the deploy form can omit."""
    with SessionLocal() as db:
        p = db.get(Project, project_id)
        metrics = {"eval": {"f1_best": {"conf": conf, "f1": 0.8}}} if conf is not None else {}
        m = TrainedModel(workspace_id=p.workspace_id, project_id=p.id, version_id=version_id, name=name,
                         arch="yolo26n", family="ultralytics", variant="yolo26n", task="detect",
                         status="ready", license="AGPL-3.0", history=[], classes=["person"],
                         metrics=metrics)
        db.add(m)
        db.flush()
        mid = m.id
        db.commit()
    return mid


def _image_bytes() -> bytes:
    buf = io.BytesIO()
    PImage.new("RGB", (32, 24)).save(buf, "JPEG")
    return buf.getvalue()


class _Recorder:
    """Stands in for the resolved adapter so the guard sees the exact kwargs the route sends."""

    def __init__(self, seen: list[dict]):
        self.seen = seen

    def predict(self, im, **kw):
        self.seen.append(kw)
        return {"model": "trained:guard", "time": 0.0,
                "image": {"width": im.width, "height": im.height}, "predictions": []}


# --- 6-F6.9: the slider value reaches the model, an omission keeps the stored threshold ---------

def test_predict_forwards_the_slider_confidence_and_omits_it_by_default(c, users, monkeypatch):
    """6-F6.9: the Deploy & Test form field is forwarded only when the labeler moved the slider."""
    pid = _project()
    mid = _model(pid, _version(pid), "deploy-guard-model")
    seen: list[dict] = []
    monkeypatch.setattr(training, "resolve",
                        lambda ref, db, *, workspace_id=None: _Recorder(seen))
    url = f"/api/ws/{WS}/projects/{DETECT}/models/{mid}/predict"
    files = {"file": ("frame.jpg", _image_bytes(), "image/jpeg")}

    moved = c.post(url, headers=_headers(users["admin"]), files=files, data={"confidence": "0.7"})
    assert moved.status_code == 200, moved.text
    assert seen[0]["conf"] == pytest.approx(0.7), \
        "6-F6.9: the slider value is the confidence the model runs at"

    moved = c.post(url, headers=_headers(users["admin"]), files=files)
    assert moved.status_code == 200, moved.text
    assert "conf" not in seen[1], \
        "6-F6.9: an untouched slider sends no confidence, so the model's own threshold is used"
    with SessionLocal() as db:
        assert model_conf(db.get(TrainedModel, mid)) == pytest.approx(BEST_F1), \
            "6-F6.9: the threshold the omission falls back to is the evaluated best-F1 one"


# --- 6-F6.22: every block type saves its documented fields --------------------------------------

def test_every_block_type_saves_with_its_documented_fields(c, users, monkeypatch):
    """6-F6.22: the canvas vocabulary saves as-is, and a bad value names the block it sits in."""
    _project()
    base = f"/api/ws/{WS}/projects/{DETECT}/workflows"
    headers = _headers(users["admin"])

    monkeypatch.delenv("LD_FLAGS_ON", raising=False)
    assert c.get(base, headers=headers).status_code == 404, \
        "6-F6.22: with task_31 off the workflow surface does not exist"
    monkeypatch.setenv("LD_FLAGS_ON", "task_31")

    blocks = [
        {"type": "model", "model_ref": "ultralytics:yolo26n", "conf": 0.4, "classes": []},
        {"type": "filter", "classes": ["person"], "min_conf": 0.3},
        {"type": "crop", "expand": 0.1},
        {"type": "rule", "kind": "count", "class": "person", "k": 2, "op": ">=", "for_s": 0},
        {"type": "sink", "kind": "response"},
    ]
    r = c.post(base, headers=headers, json={"name": "Guard line", "blocks": blocks})
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved["version"] == 1, "6-F6.22: the first save is version 1"
    assert saved["blocks"] == blocks, "6-F6.22: every block keeps the fields its panel edits"

    for name, bad, message in [
        ("bad crop", [{"type": "model", "model_ref": "ultralytics:yolo26n"},
                      {"type": "filter"}, {"type": "crop", "expand": 2},
                      {"type": "sink", "kind": "response"}],
         "block 3: expand must be between 0 and 1"),
        ("bad count", [{"type": "model", "model_ref": "ultralytics:yolo26n"},
                       {"type": "rule", "kind": "count", "class": "person", "k": -1},
                       {"type": "sink", "kind": "response"}],
         "block 2: k must be an integer between 0 and 100000"),
        ("sink not last", [{"type": "model", "model_ref": "ultralytics:yolo26n"},
                           {"type": "sink", "kind": "response"}, {"type": "filter"}],
         "the sink block must be last"),
    ]:
        r = c.post(base, headers=headers, json={"name": name, "blocks": bad})
        assert r.status_code == 400, (name, r.text)
        assert message in r.json()["detail"], (name, r.json()["detail"])


# --- 6-F6.35: the catalogue keeps the rule and sink kinds ---------------------------------------

def test_the_block_catalogue_keeps_rule_and_sink_kinds():
    """6-F6.35: the detect → count chain needs `rule`/`sink`; a draw type appends, never replaces."""
    assert workflows.BLOCK_TYPES[:6] == ("model", "filter", "crop", "ocr", "rule", "sink"), \
        "6-F6.35: the six shipped block types keep their order and names"
    assert {"count", "zone"} <= set(workflows.RULE_KINDS), \
        "6-F6.35: a rule can still count and check a zone"
    assert {"response", "annotations"} <= set(workflows.SINK_KINDS), \
        "6-F6.35: the sink can still answer and write annotations"
    assert workflows.MAX_BLOCKS == 12, "6-F6.35: the canvas cap is still twelve blocks"
