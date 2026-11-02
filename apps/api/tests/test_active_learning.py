"""Active learning: uncertainty band, diversity selection, daily cap, auto-offer."""

import io
import os
import secrets
import tempfile
from types import SimpleNamespace

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-al-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import func, select

from app.bootstrap import init_db
from app.db import SessionLocal
from app.main import app
from app.models import (
    Batch,
    Image,
    Project,
    TrainedModel,
    User,
    Version,
    Workspace,
    now,
)
from app.routers import ops
from app.security import issue_access
from app.services import active_learning as al

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
    slug = f"al-qa-{secrets.token_hex(3)}"
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        p = Project(workspace_id=ws.id, slug=slug, name=f"AL QA {slug}", settings={})
        db.add(p)
        db.commit()
        pid = p.id
    yield p
    with SessionLocal() as db:  # the shared demo workspace stays under the project limit
        row = db.get(Project, pid)
        if row is not None:
            db.delete(row)
            db.commit()


def _jpeg(colour: tuple[int, int, int], size: int = 24) -> bytes:
    b = io.BytesIO()
    PImage.new("RGB", (size, size), colour).save(b, "JPEG")
    return b.getvalue()


def _add_active_image(db, project: Project, name: str, created: float | None = None) -> Image:
    batch = db.scalar(
        select(Batch).where(
            Batch.project_id == project.id,
            Batch.source == "active-learning",
            Batch.name == "seed AL",
        )
    )
    if batch is None:
        batch = Batch(project_id=project.id, name="seed AL", source="active-learning")
        db.add(batch)
        db.flush()
    img = Image(
        project_id=project.id,
        batch_id=batch.id,
        name=name,
        sha256=f"{project.id}-{name}",
        width=8,
        height=8,
        path="",
        thumb="",
        n_annotations=0,
        created=created or now(),
    )
    db.add(img)
    db.flush()
    return img


def test_uncertainty_scores_band_highest():
    assert al.uncertainty([]) == 1.0
    assert al.uncertainty([{"confidence": 0.4}]) == pytest.approx(1.0)
    assert al.uncertainty([{"confidence": 0.2}]) < 1.0
    assert al.uncertainty([{"confidence": 0.95}]) < al.uncertainty([{"confidence": 0.6}]) < 1.0


def test_select_prefers_diverse_candidate_over_near_duplicate():
    candidates = [
        {"id": "a", "uncertainty": 0.9, "features": [1.0, 0.0]},
        {"id": "b", "uncertainty": 0.89, "features": [1.0, 0.01]},  # almost a
        {"id": "c", "uncertainty": 0.5, "features": [0.0, 1.0]},  # distinct
    ]
    assert al.select(candidates, 2) == ["a", "c"]
    assert al.select(candidates, 0) == []
    assert al.select([], 3) == []


def test_daily_cap_counts_and_blocks_endpoint(api, project):
    with SessionLocal() as db:
        p = db.get(Project, project.id)
        _add_active_image(db, p, "one")
        _add_active_image(db, p, "two")
        db.commit()
        assert al.daily_used(db, p) == 2
        assert al.cap(p) == 25
        assert al.summary(db, p) == {
            "used_today": 2,
            "cap": 25,
            "remaining": 23,
            "enabled": False,
        }
        p.settings = {"active_learning": {"enabled": True, "daily_cap": 1}}
        db.commit()
        assert al.cap(p) == 1
        assert al.remaining(db, p) == 0

    base = f"/api/ws/{WS}/projects/{project.slug}"
    assert api.post(f"{base}/active-learning/run", json={"k": 1}).status_code == 409
    body = api.get(f"{base}/active-learning").json()
    assert body["used_today"] == 2 and body["cap"] == 1 and body["remaining"] == 0
    assert body["enabled"] is True
    assert body["batches"][0]["images"] == 2


def test_auto_offer_stops_at_cap(project):
    with SessionLocal() as db:
        p = db.get(Project, project.id)
        p.settings = {
            "active_learning": {
                "enabled": True,
                "below": 0.5,
                "sample_pct": 0,
                "daily_cap": 1,
            }
        }
        db.commit()
        ws = db.get(Workspace, p.workspace_id)
        _add_active_image(db, p, "existing")
        db.commit()
        before = db.scalar(select(func.count(Image.id)).where(Image.project_id == p.id))

        pred = {"predictions": [{"confidence": 0.2, "class": "person"}]}
        assert al.auto_offer(db, ws, p, _jpeg((5, 6, 7)), pred) is False  # daily cap already used
        assert db.scalar(select(func.count(Image.id)).where(Image.project_id == p.id)) == before

        p.settings = {
            "active_learning": {
                "enabled": True,
                "below": 0.5,
                "sample_pct": 0,
                "daily_cap": 2,
            }
        }
        db.commit()
        assert al.auto_offer(db, ws, p, _jpeg((50, 60, 70)), pred) is True
        assert db.scalar(select(func.count(Image.id)).where(Image.project_id == p.id)) == before + 1
        assert al.auto_offer(db, ws, p, _jpeg((80, 90, 100)), pred) is False  # now at cap


class _FakeResolved:
    def predict(self, *args, **kwargs):
        return {}


def test_daily_cap_counts_picks_not_upload_time(project, monkeypatch):
    """C1: an image uploaded 10 days ago still consumes the cap when picked today."""
    with SessionLocal() as db:
        p = db.get(Project, project.id)
        v = Version(project_id=p.id, number=2, status="ready")
        db.add(v)
        db.flush()
        m = TrainedModel(
            workspace_id=p.workspace_id,
            project_id=p.id,
            version_id=v.id,
            name="AL cap model",
            arch="yolo26n",
            task="detect",
            status="ready",
            classes=["person"],
        )
        db.add(m)
        db.flush()
        # a pick made yesterday must not count against today's cap
        stale = Batch(project_id=p.id, name="yesterday", source="active-learning")
        db.add(stale)
        db.flush()
        stale.created = now() - 86400
        db.add(
            Image(
                project_id=p.id,
                batch_id=stale.id,
                name="yesterday-pick.jpg",
                sha256=f"yesterday-{p.id}",
                width=8,
                height=8,
                path="",
                thumb="",
                n_annotations=1,
                created=now() - 86400,
            )
        )
        db.add(
            Image(
                project_id=p.id,
                name="old-candidate.jpg",
                sha256=f"old-{p.id}",
                width=8,
                height=8,
                path="fake/old-candidate.jpg",
                thumb="",
                n_annotations=0,
                created=now() - 10 * 86400,
            )
        )
        db.commit()
        mid, pid, wsid = m.id, p.id, p.workspace_id

    monkeypatch.setattr(al, "resolve", lambda *args, **kwargs: _FakeResolved())
    monkeypatch.setattr(al, "_score_image", lambda resolved, image, classes: (0.9, [1.0, 0.0]))
    job = SimpleNamespace(project_id=pid, workspace_id=wsid, params={"k": 5, "model_id": mid}, created_by=None)

    out = al.run_job(job)
    assert out["selected"] == 1
    with SessionLocal() as db:
        p = db.get(Project, pid)
        assert al.daily_used(db, p) == 1
        assert al.summary(db, p)["used_today"] == 1
        assert al.remaining(db, p) == 24
        p.settings = {"active_learning": {"enabled": True, "daily_cap": 1}}
        db.commit()
        # a backlog must not hand out another pick once the cap is spent
        assert al.run_job(job)["selected"] == 0


def test_run_job_selects_diverse_and_creates_batch(project, monkeypatch):
    with SessionLocal() as db:
        p = db.get(Project, project.id)
        v = Version(project_id=p.id, number=1, status="ready")
        db.add(v)
        db.flush()
        m = TrainedModel(
            workspace_id=p.workspace_id,
            project_id=p.id,
            version_id=v.id,
            name="AL model",
            arch="yolo26n",
            task="detect",
            status="ready",
            classes=["person"],
        )
        db.add(m)
        db.flush()
        for i in range(3):
            db.add(
                Image(
                    project_id=p.id,
                    name=f"cand{i}.jpg",
                    sha256=f"cand{i}-{p.id}",
                    width=8,
                    height=8,
                    path=f"fake/cand{i}.jpg",
                    thumb="",
                    n_annotations=0,
                )
            )
        db.commit()
        mid, pid, wsid = m.id, p.id, p.workspace_id

    class FakeResolved:
        def predict(self, *args, **kwargs):
            return {}

    scores = {
        "cand0.jpg": (0.9, [1.0, 0.0]),
        "cand1.jpg": (0.89, [1.0, 0.01]),  # near-duplicate of cand0
        "cand2.jpg": (0.5, [0.0, 1.0]),  # distinct
    }
    monkeypatch.setattr(al, "resolve", lambda *args, **kwargs: FakeResolved())
    monkeypatch.setattr(al, "_score_image", lambda resolved, image, classes: scores[image.name])

    job = SimpleNamespace(
        project_id=pid,
        workspace_id=wsid,
        params={"k": 2, "model_id": mid},
        created_by=None,
    )
    out = al.run_job(job)
    assert out["selected"] == 2 and out["candidates"] == 3
    with SessionLocal() as db:
        rows = db.scalars(select(Image).where(Image.project_id == pid)).all()
        chosen = {r.name for r in rows if r.batch_id}
        assert chosen == {"cand0.jpg", "cand2.jpg"}
        batch = db.scalar(select(Batch).where(Batch.project_id == pid, Batch.source == "active-learning"))
        assert batch is not None
        assert all(r.status == "review" and "active-learning" in r.tags for r in rows if r.batch_id)


def test_run_job_releases_the_embedding_backend(project, monkeypatch):
    """N2: the active-learning job must not leave CLIP resident after it ends."""
    released = []
    monkeypatch.setattr(al.embeddings, "release", lambda: released.append("release"))
    job = SimpleNamespace(project_id="missing-project", workspace_id=project.workspace_id, params={})
    with pytest.raises(ValueError):
        al.run_job(job)
    assert released == ["release"]
