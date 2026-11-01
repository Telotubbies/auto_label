"""PDPA retention: expired frames and snapshots are deleted, kept rows survive, runs are idempotent."""

import io
import os
import tempfile
import time
import types
import uuid

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-test-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from PIL import Image as PImage
from sqlalchemy import delete, select

from app.bootstrap import init_db
from app.config import DATA_DIR
from app.db import SessionLocal
from app.models import Audit, Image, Job, Member, Project, User, Workspace, now
from app.services import retention

DAY = 86400.0


def jpeg_bytes() -> bytes:
    b = io.BytesIO()
    PImage.new("RGB", (8, 8), (120, 130, 140)).save(b, "JPEG")
    return b.getvalue()


def write(rel: str) -> None:
    path = DATA_DIR / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(jpeg_bytes())


@pytest.fixture(scope="module")
def world():
    init_db()
    tag = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        u = User(email=f"retention-{tag}@example.test", name="Retention Tester", email_verified=now())
        db.add(u)
        db.flush()
        ws = Workspace(
            slug=f"retention-{tag}", name="Retention Fixture", owner_id=u.id, credits_period=time.strftime("%Y-%m")
        )
        db.add(ws)
        db.flush()
        db.add(Member(workspace_id=ws.id, user_id=u.id, role="admin"))
        p = Project(workspace_id=ws.id, slug="retention-project", name="Retention Project", retention_days=30)
        db.add(p)
        db.commit()
        ids = {"pid": p.id, "ws": ws.id, "uid": u.id, "tag": tag}
    yield ids
    with SessionLocal() as db:
        db.execute(delete(Job).where(Job.workspace_id == ids["ws"]))
        db.execute(delete(Audit).where(Audit.workspace_id == ids["ws"]))
        db.execute(delete(Project).where(Project.id == ids["pid"]))
        db.execute(delete(Workspace).where(Workspace.id == ids["ws"]))
        db.execute(delete(User).where(User.id == ids["uid"]))
        db.commit()
    root = DATA_DIR / "projects" / ids["pid"]
    for f in sorted(root.rglob("*"), reverse=True) if root.exists() else []:
        f.unlink() if f.is_file() else f.rmdir()
    if root.exists():
        root.rmdir()


def seed_project(world) -> dict:
    """One 40-day-old image and one fresh image, each with a thumbnail, plus an expired snapshot."""
    pid = world["pid"]
    with SessionLocal() as db:
        out = {}
        for label, age in (("old", 40), ("new", 0)):
            stem = f"{label}-{uuid.uuid4().hex[:6]}"
            rel, thumb = f"projects/{pid}/images/{stem}.jpg", f"projects/{pid}/images/thumbs/{stem}.jpg"
            write(rel)
            write(thumb)
            img = Image(
                project_id=pid,
                name=f"{stem}.jpg",
                sha256=uuid.uuid4().hex,
                width=8,
                height=8,
                path=rel,
                thumb=thumb,
                size=8,
                created=now() - age * DAY,
                updated=now() - age * DAY,
            )
            db.add(img)
            db.flush()
            out[label] = {"id": img.id, "path": rel, "thumb": thumb}
        db.commit()
    snap = DATA_DIR / "projects" / pid / "snapshots" / "old.jpg"
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_bytes(jpeg_bytes())
    os.utime(snap, (time.time() - 40 * DAY, time.time() - 40 * DAY))
    out["snap"] = snap
    return out


def test_retention_job_runs_through_the_worker(world):
    """The worker's HANDLERS entry (not just the service) performs the deletion."""
    from app import worker

    items = seed_project(world)
    with SessionLocal() as db:
        job = Job(workspace_id=world["ws"], project_id=world["pid"], kind="retention",
                  params={"project_id": world["pid"]})
        db.add(job)
        db.commit()
        jid = job.id
    worker.run_one(jid)
    with SessionLocal() as db:
        job = db.get(Job, jid)
        assert job.status == "done", job.error
        assert job.result["images_deleted"] == 1
        assert db.get(Image, items["old"]["id"]) is None
        db.delete(job)
        db.commit()


def test_run_retention_deletes_expired_rows_and_files(world):
    items = seed_project(world)
    result = retention.run_retention(types.SimpleNamespace(params={"project_id": world["pid"]}))

    assert result["projects"] == 1
    assert result["images_deleted"] == 1
    assert result["snapshots_deleted"] == 1
    assert result["bytes_freed"] > 0
    with SessionLocal() as db:
        assert db.get(Image, items["old"]["id"]) is None
        assert db.get(Image, items["new"]["id"]) is not None
        row = db.scalar(select(Audit).where(Audit.workspace_id == world["ws"], Audit.action == "retention.run"))
        assert row is not None and row.meta["images"] == 1
    assert not (DATA_DIR / items["old"]["path"]).exists()
    assert not (DATA_DIR / items["old"]["thumb"]).exists()
    assert (DATA_DIR / items["new"]["path"]).exists()
    assert not items["snap"].exists()

    again = retention.run_retention(types.SimpleNamespace(params={"project_id": world["pid"]}))
    assert again["images_deleted"] == 0
    assert again["snapshots_deleted"] == 0
    assert again["projects"] == 1


def test_unknown_project_raises(world):
    with pytest.raises(RuntimeError):
        retention.run_retention(types.SimpleNamespace(params={"project_id": "does-not-exist"}))


def test_enqueue_if_due(world):
    pid = world["pid"]
    with SessionLocal() as db:
        db.execute(delete(Job).where(Job.kind == "retention"))
        others = db.scalars(select(Project).where(Project.id != pid, Project.retention_days > 0)).all()
        saved = {p.id: p.retention_days for p in others}
        for p in others:
            p.retention_days = None
        db.commit()
    try:
        with SessionLocal() as db:
            db.get(Project, pid).retention_days = 0
            db.commit()
            assert retention.enqueue_if_due(db) is None

        with SessionLocal() as db:
            db.get(Project, pid).retention_days = 30
            db.commit()
            jid = retention.enqueue_if_due(db)
            assert jid
            assert retention.enqueue_if_due(db) is None  # one queued job is enough

        with SessionLocal() as db:
            job = db.get(Job, jid)
            job.status, job.finished = "done", now() - 24 * 3600
            db.commit()
            assert retention.enqueue_if_due(db)  # 24 h later it is due again
    finally:
        with SessionLocal() as db:
            db.execute(delete(Job).where(Job.kind == "retention"))
            for other_id, days in saved.items():
                row = db.get(Project, other_id)
                if row:
                    row.retention_days = days
            db.get(Project, pid).retention_days = 30
            db.commit()
