"""R1 upgrades: schema lock, partial image-class repair, storage-meter backfill."""
import threading
import time
import uuid

import pytest
from sqlalchemy import func, select

from app import bootstrap
from app.db import Base, SessionLocal
from app.models import Image, ImageClass, Project, UsageEvent, User, Workspace
from app.security import hash_password


@pytest.fixture(scope="module", autouse=True)
def _schema():
    from app.db import Base, engine
    Base.metadata.create_all(engine)


def _workspace_with_images(n=2, size=12345):
    with SessionLocal() as db:
        suffix = uuid.uuid4().hex[:8]
        u = User(id="u" + suffix, email=f"bf-{suffix}@x.io", name="BF", pw_hash=hash_password("longpassword1"))
        db.add(u); db.flush()
        ws = Workspace(id="w" + suffix, slug=f"bf-{suffix}", name="BF ws", owner_id=u.id)
        db.add(ws); db.flush()
        p = Project(workspace_id=ws.id, slug=f"bfp-{suffix}", name="BF project")
        db.add(p); db.flush()
        ids = []
        for i in range(n):
            img = Image(id=f"i{suffix}{i}", project_id=p.id, name=f"{i}.jpg", sha256=f"{suffix}{i}", width=2,
                        height=2, size=size, path="x", thumb="y", annotations=[], n_annotations=0)
            db.add(img); db.flush()
            ids.append(img.id)
        db.commit()
        return ws.id, p.id, ids


def test_seed_creates_demo_even_when_other_users_exist(monkeypatch):
    """I8: a module that inserts a user first must not stop another module's demo login."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    sessions = sessionmaker(bind=eng)
    with sessions() as db:
        db.add(User(id="ureal", email="real@x.io", name="Real", pw_hash="x"))
        db.commit()
    monkeypatch.setattr(bootstrap, "SessionLocal", sessions)
    bootstrap.seed()
    with sessions() as db:
        assert db.scalar(select(User.id).where(User.email == bootstrap.DEMO_EMAIL))


def test_storage_backfill_is_idempotent():
    ws_id, _, _ = _workspace_with_images(2, 1000)
    bootstrap._backfill_storage()
    with SessionLocal() as db:
        qty = db.scalar(select(func.sum(UsageEvent.quantity)).where(
            UsageEvent.workspace_id == ws_id, UsageEvent.metric == "storage_bytes"))
        assert qty == 2000
    bootstrap._backfill_storage()
    with SessionLocal() as db:
        rows = db.scalars(select(UsageEvent).where(UsageEvent.workspace_id == ws_id,
                                                   UsageEvent.metric == "storage_bytes")).all()
        assert len(rows) == 1


def test_image_class_backfill_repairs_a_partial_index():
    ws_id, p_id, ids = _workspace_with_images(2)
    with SessionLocal() as db:
        img = db.get(Image, ids[0])
        img.annotations = [{"id": "a1", "classId": "c1", "shape": {"kind": "class"}}]
        img.n_annotations = 1
        db.add(ImageClass(image_id=ids[1], class_id="c1", project_id=p_id, n=1))   # partial index exists
        db.commit()
    bootstrap._backfill_image_classes()
    with SessionLocal() as db:
        indexed = set(db.scalars(select(ImageClass.image_id).where(ImageClass.project_id == p_id)))
    assert set(ids) <= indexed


def test_image_class_backfill_survives_a_null_annotation():
    """A legacy row can hold a null list element; the repair must not crash the startup path."""
    _, p_id, ids = _workspace_with_images(1)
    with SessionLocal() as db:
        img = db.get(Image, ids[0])
        img.annotations = [None, {"id": "a1", "classId": "c1", "shape": {"kind": "class"}}]
        img.n_annotations = 2
        db.commit()
    bootstrap._backfill_image_classes()          # no AttributeError
    with SessionLocal() as db:
        assert db.scalar(select(ImageClass.image_id).where(ImageClass.image_id == ids[0]))


def test_schema_lock_serialises_writers(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, "DATA_DIR", tmp_path)
    active = []
    peak = []

    def worker():
        with bootstrap._schema_lock():
            active.append(1)
            peak.append(len(active))
            time.sleep(0.05)
            active.pop()

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert max(peak) == 1
