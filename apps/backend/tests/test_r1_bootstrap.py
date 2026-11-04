"""R1 upgrades: schema lock, partial image-class repair, storage-meter backfill."""
import threading
import time
import uuid

import pytest
from sqlalchemy import func, select

from app import bootstrap
from app.config import DATA_DIR
from app.db import Base, SessionLocal
from app.models import Image, ImageClass, Project, UsageEvent, User, Video, Workspace
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


def test_seed_skips_a_database_that_already_has_users(monkeypatch):
    """M7: a live installation must never gain the known demo admin on the next restart."""
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
        assert db.scalar(select(User.id).where(User.email == bootstrap.DEMO_EMAIL)) is None


def test_seed_is_disabled_in_production(monkeypatch):
    monkeypatch.setattr(bootstrap, "SEED_DEMO", True)
    monkeypatch.setattr(bootstrap, "ENVIRONMENT", "production")
    assert bootstrap._should_seed() is False
    monkeypatch.setattr(bootstrap, "ENVIRONMENT", "development")
    assert bootstrap._should_seed() is True


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


def test_storage_backfill_reconciles_a_partial_meter():
    """I10: a workspace that already metered one upload must still be topped up to its image bytes."""
    ws_id, _, _ = _workspace_with_images(2, 1000)
    with SessionLocal() as db:
        db.add(UsageEvent(workspace_id=ws_id, metric="storage_bytes", quantity=500))
        db.commit()

    bootstrap._backfill_storage()
    with SessionLocal() as db:
        qty = db.scalar(select(func.sum(UsageEvent.quantity)).where(
            UsageEvent.workspace_id == ws_id, UsageEvent.metric == "storage_bytes"))
        assert qty == pytest.approx(2000)
        rows = db.scalars(select(UsageEvent).where(UsageEvent.workspace_id == ws_id,
                                                   UsageEvent.metric == "storage_bytes")).all()
        assert len(rows) == 2                       # the existing event plus one reconciliation delta

    bootstrap._backfill_storage()                   # repeated boots are no-ops
    with SessionLocal() as db:
        qty = db.scalar(select(func.sum(UsageEvent.quantity)).where(
            UsageEvent.workspace_id == ws_id, UsageEvent.metric == "storage_bytes"))
        assert qty == pytest.approx(2000)
        rows = db.scalars(select(UsageEvent).where(UsageEvent.workspace_id == ws_id,
                                                   UsageEvent.metric == "storage_bytes")).all()
        assert len(rows) == 2


def test_storage_backfill_reconciles_video_bytes_hidden_by_an_image_undercount():
    """I10 root: the meter covers images *and* videos; topping up to Image.size alone loses bytes.

    A workspace whose only existing event is a video upload (500 B) must still be raised to the
    live image bytes (2 × 1000) plus that video, not to the image subtotal.
    """
    ws_id, p_id, _ = _workspace_with_images(2, 1000)
    rel = "videos/i10-video.mp4"
    path = DATA_DIR / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"v" * 500)
    with SessionLocal() as db:
        db.add(Video(id="i10video", project_id=p_id, workspace_id=ws_id, name="clip",
                     path=rel, status="ready"))
        db.add(UsageEvent(workspace_id=ws_id, metric="storage_bytes", quantity=500))
        db.commit()
    try:
        bootstrap._backfill_storage()
        with SessionLocal() as db:
            qty = db.scalar(select(func.sum(UsageEvent.quantity)).where(
                UsageEvent.workspace_id == ws_id, UsageEvent.metric == "storage_bytes"))
            assert qty == pytest.approx(2500)

        bootstrap._backfill_storage()               # repeated boots must stay a no-op
        with SessionLocal() as db:
            qty = db.scalar(select(func.sum(UsageEvent.quantity)).where(
                UsageEvent.workspace_id == ws_id, UsageEvent.metric == "storage_bytes"))
            assert qty == pytest.approx(2500)
    finally:
        path.unlink(missing_ok=True)


def test_storage_backfill_never_reduces_an_over_counted_meter():
    """Deletes are negative events; the boot reconciler must not invent a second downward delta."""
    ws_id, _, _ = _workspace_with_images(1, 1000)
    with SessionLocal() as db:
        db.add(UsageEvent(workspace_id=ws_id, metric="storage_bytes", quantity=1500))
        db.commit()
    bootstrap._backfill_storage()
    with SessionLocal() as db:
        qty = db.scalar(select(func.sum(UsageEvent.quantity)).where(
            UsageEvent.workspace_id == ws_id, UsageEvent.metric == "storage_bytes"))
        assert qty == pytest.approx(1500)


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


def _backfill_with_deadline(seconds: float = 3.0) -> None:
    """Run the backfill on a daemon thread so a non-terminating repair fails instead of hanging."""
    errors: list[BaseException] = []

    def run():
        try:
            bootstrap._backfill_image_classes()
        except BaseException as e:                # surfaced on the test thread below
            errors.append(e)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(seconds)
    assert not t.is_alive(), (
        "image-class backfill did not finish: a row with no indexable classId is selected forever "
        "while the schema lock is held")
    if errors:
        raise errors[0]


@pytest.mark.parametrize("anns", [[None], {"label": "cat"}], ids=["null-list", "v1-dict"])
def test_image_class_backfill_finishes_when_nothing_is_indexable(anns):
    """C1: legacy annotations without a classId can never produce ImageClass; stop instead of looping."""
    _, p_id, ids = _workspace_with_images(1)
    with SessionLocal() as db:
        img = db.get(Image, ids[0])
        img.annotations = anns
        img.n_annotations = 1
        db.commit()
    _backfill_with_deadline()
    with SessionLocal() as db:
        assert db.scalar(select(ImageClass.image_id).where(ImageClass.image_id == ids[0])) is None


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
