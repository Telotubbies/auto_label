"""R1/I3: retention must expire drift samples (files and rows) alongside frames and snapshots."""

import os
import shutil
import stat
import time
import types
import uuid

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from sqlalchemy import delete, select

from app.bootstrap import init_db
from app.config import DATA_DIR
from app.db import SessionLocal
from app.models import Audit, DriftSample, Job, Member, Project, User, Workspace, now
from app.services import retention

DAY = 86400.0


@pytest.fixture(scope="module")
def world():
    init_db()
    tag = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        u = User(email=f"retention-drift-{tag}@example.test", name="Drift Retention", email_verified=now())
        db.add(u)
        db.flush()
        ws = Workspace(
            slug=f"retention-drift-{tag}",
            name="Drift Retention Fixture",
            owner_id=u.id,
            credits_period=time.strftime("%Y-%m"),
        )
        db.add(ws)
        db.flush()
        db.add(Member(workspace_id=ws.id, user_id=u.id, role="admin"))
        p = Project(workspace_id=ws.id, slug="drift-retention", name="Drift Retention", retention_days=1)
        db.add(p)
        db.commit()
        ids = {"pid": p.id, "ws": ws.id, "uid": u.id}
    yield ids
    with SessionLocal() as db:
        db.execute(delete(DriftSample).where(DriftSample.project_id == ids["pid"]))
        db.execute(delete(Job).where(Job.workspace_id == ids["ws"]))
        db.execute(delete(Audit).where(Audit.workspace_id == ids["ws"]))
        db.execute(delete(Project).where(Project.id == ids["pid"]))
        db.execute(delete(Workspace).where(Workspace.id == ids["ws"]))
        db.execute(delete(User).where(User.id == ids["uid"]))
        db.commit()
    for root in (DATA_DIR / "workspaces" / ids["ws"], DATA_DIR / "projects" / ids["pid"]):
        shutil.rmtree(root, ignore_errors=True)


def seed_sample(pid: str, ws: str, label: str, age_days: float) -> dict:
    """One DriftSample row plus its stored JPEG, aged on both `created` and mtime."""
    rel = f"workspaces/{ws}/drift/{pid}/{label}-{uuid.uuid4().hex[:6]}.jpg"
    path = DATA_DIR / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"drift-frame" * 128)
    stamp = time.time() - age_days * DAY
    os.utime(path, (stamp, stamp))
    with SessionLocal() as db:
        row = DriftSample(
            workspace_id=ws,
            project_id=pid,
            sha256=uuid.uuid4().hex,
            path=rel,
            source="api",
            created=now() - age_days * DAY,
        )
        db.add(row)
        db.commit()
        return {"id": row.id, "path": path, "rel": rel}


def run(world) -> dict:
    return retention.run_retention(types.SimpleNamespace(params={"project_id": world["pid"]}))


def test_retention_deletes_expired_drift_samples(world):
    """An expired drift frame and its row go; a fresh one stays and the stats report the sweep."""
    old = seed_sample(world["pid"], world["ws"], "old", 3)
    new = seed_sample(world["pid"], world["ws"], "new", 0)
    size = old["path"].stat().st_size

    result = run(world)

    assert result["drift_deleted"] == 1
    assert result["failed"] == 0
    assert result["bytes_freed"] >= size
    assert not old["path"].exists()
    assert new["path"].exists()
    with SessionLocal() as db:
        assert db.get(DriftSample, old["id"]) is None
        assert db.get(DriftSample, new["id"]) is not None
        row = db.scalar(
            select(Audit)
            .where(Audit.workspace_id == world["ws"], Audit.action == "retention.run")
            .order_by(Audit.created.desc())
        )
        assert row is not None and row.meta["drift"] == 1


def test_locked_drift_sample_keeps_its_row_and_is_retried(world):
    """A file held open on Windows must leave the row so the next run retries it."""
    item = seed_sample(world["pid"], world["ws"], "locked", 3)

    with open(item["path"], "rb"):
        if os.name != "nt":  # POSIX unlinks an open file: a read-only directory blocks it instead
            os.chmod(item["path"].parent, stat.S_IREAD | stat.S_IEXEC)
        try:
            result = run(world)
            assert result["drift_deleted"] == 0
            assert result["failed"] >= 1
            assert item["path"].exists()
            with SessionLocal() as db:
                assert db.get(DriftSample, item["id"]) is not None
        finally:
            if os.name != "nt":
                os.chmod(item["path"].parent, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)

    again = run(world)
    assert again["drift_deleted"] == 1
    assert again["failed"] == 0
    assert not item["path"].exists()
    with SessionLocal() as db:
        assert db.get(DriftSample, item["id"]) is None
