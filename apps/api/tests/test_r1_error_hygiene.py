"""I11: user-facing job errors must not contain paths, URLs or exception internals."""
import os
import uuid

os.environ.setdefault("LD_WORKER_TOKEN", "test-worker-token-0123456789abcdef")

import pytest
from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.models import Job, Project, Workspace
from app import worker


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)


def test_safe_error_hides_machine_paths():
    from app.errors import safe_error
    msg = safe_error(FileNotFoundError(r"[WinError 3] C:\Users\secret\data\video.mp4"), "video")
    assert "WinError" not in msg and "secret" not in msg and "C:\\" not in msg


def test_safe_error_hides_urls():
    from app.errors import safe_error
    msg = safe_error(RuntimeError("vLLM not reachable at http://10.0.0.5:8000/v1"), "autolabel")
    assert "10.0.0.5" not in msg and "http" not in msg


def test_safe_error_keeps_our_validation_messages():
    from app.errors import safe_error
    assert safe_error(ValueError("pick a generated version to train on"), "train") == \
        "pick a generated version to train on"


def test_run_one_never_stores_a_raw_exception(monkeypatch):
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        from app.models import User
        u = User(id="u" + suffix, email=f"err-{suffix}@x.io", name="Err", pw_hash="x")
        db.add(u); db.flush()
        ws = Workspace(id="w" + suffix, slug=f"err-{suffix}", name="Err", owner_id=u.id)
        db.add(ws); db.flush()
        p = Project(workspace_id=ws.id, slug=f"errp-{suffix}", name="Err project")
        db.add(p); db.flush()
        j = Job(workspace_id=ws.id, project_id=p.id, kind="version", params={})
        db.add(j); db.commit()
        jid = j.id

    def boom(job):
        raise FileNotFoundError(r"[WinError 3] D:\customer\frames\x.jpg")

    monkeypatch.setattr(worker, "HANDLERS", {"version": boom})
    worker.run_one(jid)
    with SessionLocal() as db:
        j = db.get(Job, jid)
        assert j.status == "failed"
        assert "WinError" not in (j.error or "") and "D:\\" not in (j.error or "")
