"""PDPA retention: expired frames and snapshots are deleted, kept rows survive, runs are idempotent."""

import io
import json
import os
import shutil
import stat
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
from app.models import Audit, Image, Job, Member, Project, User, Version, Workspace, now
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


def test_retention_sweeps_an_upload_never_attached_to_a_stream(world):
    """I-1: an abandoned camera clip expires with the project and its metered bytes are refunded."""
    from app.models import UsageEvent
    from app.services import metering

    name = f"orphan-{uuid.uuid4().hex[:8]}.mp4"
    path = DATA_DIR / "videos" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * 2048)
    os.utime(path, (time.time() - 40 * DAY, time.time() - 40 * DAY))
    with SessionLocal() as db:
        db.add(UsageEvent(workspace_id=world["ws"], project_id=world["pid"], metric="storage_bytes",
                          quantity=2048.0, meta={"stream_upload": name}))
        db.commit()
        before = metering.used(db, db.get(Workspace, world["ws"]), "storage_bytes")

    result = retention.run_retention(types.SimpleNamespace(params={"project_id": world["pid"]}))
    assert result["uploads_deleted"] == 1
    assert not path.exists(), "an upload with no Stream row outlived the retention window"
    with SessionLocal() as db:
        after = metering.used(db, db.get(Workspace, world["ws"]), "storage_bytes")
    assert after == pytest.approx(before - 2048, abs=1)


def test_unknown_project_raises(world):
    with pytest.raises(RuntimeError):
        retention.run_retention(types.SimpleNamespace(params={"project_id": "does-not-exist"}))


def seed_old_image(pid: str, label: str = "locked") -> dict:
    """One 40-day-old image with its JPEG and thumbnail on disk."""
    stem = f"{label}-{uuid.uuid4().hex[:6]}"
    rel, thumb = f"projects/{pid}/images/{stem}.jpg", f"projects/{pid}/images/thumbs/{stem}.jpg"
    write(rel)
    write(thumb)
    with SessionLocal() as db:
        img = Image(project_id=pid, name=f"{stem}.jpg", sha256=uuid.uuid4().hex, width=8, height=8,
                    path=rel, thumb=thumb, size=8, created=now() - 40 * DAY, updated=now() - 40 * DAY)
        db.add(img)
        db.commit()
        return {"id": img.id, "path": DATA_DIR / rel, "thumb": DATA_DIR / thumb, "rel": rel}


def seed_version_with_sources(pid: str, source_ids: list[str]):
    """A ready version whose manifest lists ``source_ids``, with both export caches on disk."""
    with SessionLocal() as db:
        v = Version(project_id=pid, number=int(uuid.uuid4().hex[:8], 16), status="ready")
        db.add(v)
        db.commit()
        vid = v.id
    vdir = DATA_DIR / "versions" / vid
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "manifest.json").write_text(json.dumps({"sources": [{"id": s, "sha256": "x"} for s in source_ids]}))
    cache = DATA_DIR / "exports" / vid / "yolo.zip"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(b"zip")
    version_cache = vdir / "exports" / "yolo" / "frame.jpg"
    version_cache.parent.mkdir(parents=True, exist_ok=True)
    version_cache.write_bytes(jpeg_bytes())
    return vid, cache, version_cache


def drop_version(vid: str) -> None:
    with SessionLocal() as db:
        row = db.get(Version, vid)
        if row:
            db.delete(row)
        db.commit()
    shutil.rmtree(DATA_DIR / "versions" / vid, ignore_errors=True)
    shutil.rmtree(DATA_DIR / "exports" / vid, ignore_errors=True)


def test_snapshot_sweep_is_scoped_to_this_project(world):
    """C1: another tenant's snapshot files must never be swept by this project's retention run."""
    tag = uuid.uuid4().hex[:8]
    a_snap = DATA_DIR / "projects" / world["pid"] / "snapshots" / f"a-{tag}.jpg"
    a_snap.parent.mkdir(parents=True, exist_ok=True)
    a_snap.write_bytes(jpeg_bytes())

    with SessionLocal() as db:
        u = User(email=f"other-{tag}@example.test", name="Other Tenant", email_verified=now())
        db.add(u)
        db.flush()
        ws = Workspace(slug=f"other-{tag}", name="Other Workspace", owner_id=u.id,
                       credits_period=time.strftime("%Y-%m"))
        db.add(ws)
        db.flush()
        db.add(Member(workspace_id=ws.id, user_id=u.id, role="admin"))
        other = Project(workspace_id=ws.id, slug="other-project", name="Other Project", retention_days=30)
        db.add(other)
        db.commit()
        other_pid, other_ws, other_uid = other.id, ws.id, u.id

    b_snap = DATA_DIR / "projects" / other_pid / "snapshots" / "b.jpg"
    b_snap.parent.mkdir(parents=True, exist_ok=True)
    b_snap.write_bytes(jpeg_bytes())
    # A flat file in the old global folder has no project attribution, so it must survive too.
    legacy = DATA_DIR / "snapshots" / f"unattributed-{tag}.jpg"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_bytes(jpeg_bytes())

    old = time.time() - 40 * DAY
    for path in (a_snap, b_snap, legacy):
        os.utime(path, (old, old))

    try:
        retention.run_retention(types.SimpleNamespace(params={"project_id": world["pid"]}))
        assert not a_snap.exists()                       # this project's expired snapshot goes
        assert b_snap.exists()                           # the other tenant's file stays
        assert legacy.exists()                           # unattributed legacy file stays
    finally:
        with SessionLocal() as db:
            db.execute(delete(Project).where(Project.id == other_pid))
            db.execute(delete(Member).where(Member.workspace_id == other_ws))
            db.execute(delete(Workspace).where(Workspace.id == other_ws))
            db.execute(delete(User).where(User.id == other_uid))
            db.commit()
        for root in (DATA_DIR / "projects" / other_pid,):
            shutil.rmtree(root, ignore_errors=True)
        legacy.unlink(missing_ok=True)


def test_undeletable_image_keeps_the_row_and_is_recorded(world):
    """I2: a locked file must leave the row in place so the next run retries, and count as a failure."""
    item = seed_old_image(world["pid"])
    image_dir = item["path"].parent
    os.chmod(item["path"], stat.S_IREAD)
    os.chmod(image_dir, stat.S_IREAD | stat.S_IEXEC)      # POSIX: no unlink in a read-only directory
    try:
        result = retention.run_retention(types.SimpleNamespace(params={"project_id": world["pid"]}))
        assert result["images_deleted"] == 0
        assert result["failed"] == 1
        assert item["path"].exists()
        with SessionLocal() as db:
            assert db.get(Image, item["id"]) is not None
            row = db.scalar(select(Audit).where(Audit.workspace_id == world["ws"],
                                                Audit.action == "retention.run").order_by(Audit.created.desc()))
            assert row is not None and row.meta["failed"] == 1
    finally:
        os.chmod(image_dir, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        if item["path"].exists():
            os.chmod(item["path"], stat.S_IWRITE | stat.S_IREAD)

    again = retention.run_retention(types.SimpleNamespace(params={"project_id": world["pid"]}))
    assert again["images_deleted"] == 1
    assert again["failed"] == 0
    assert not item["path"].exists()
    with SessionLocal() as db:
        assert db.get(Image, item["id"]) is None


def test_retention_invalidates_cached_exports_of_affected_versions(world):
    """I3: cached export archives that contain a deleted frame must stop being served."""
    pid = world["pid"]
    item = seed_old_image(pid, "exported")
    vid, cache, version_cache = seed_version_with_sources(pid, [item["id"]])
    try:
        result = retention.run_retention(types.SimpleNamespace(params={"project_id": pid}))
        assert result["images_deleted"] == 1
        assert result["exports_deleted"] == 2             # job archive + version export cache
        assert not cache.exists() and not (DATA_DIR / "exports" / vid).exists()
        assert not version_cache.exists()
        with SessionLocal() as db:
            row = db.scalar(select(Audit).where(Audit.workspace_id == world["ws"],
                                                Audit.action == "retention.run").order_by(Audit.created.desc()))
            assert row is not None and row.meta["exports"] == 2
    finally:
        drop_version(vid)


def test_locked_export_cache_is_not_counted_and_is_retried(world, monkeypatch):
    """N1: a Windows sharing violation on an archive must count as a failure, never as deleted."""
    item = seed_old_image(world["pid"], "locked-export")
    vid, cache, version_cache = seed_version_with_sources(world["pid"], [item["id"]])

    def locked(path, *args, **kwargs):
        # WinError 32: the archive is still open (a download or an export job holds it).
        raise PermissionError(13, "Access is denied: the file is in use", str(path))

    try:
        with monkeypatch.context() as m:
            m.setattr(retention.shutil, "rmtree", locked)
            result = retention.run_retention(types.SimpleNamespace(params={"project_id": world["pid"]}))
        assert result["images_deleted"] == 1
        assert result["exports_deleted"] == 0             # not deleted, so not reported as deleted
        assert result["failed"] >= 1
        assert cache.exists() and version_cache.exists()
        with SessionLocal() as db:
            row = db.scalar(select(Audit).where(Audit.workspace_id == world["ws"],
                                                Audit.action == "retention.run").order_by(Audit.created.desc()))
            assert row is not None and row.meta["exports"] == 0 and row.meta["failed"] >= 1

        # The image rows are gone, so only the manifest can make the retry find the stale cache.
        retry = retention.run_retention(types.SimpleNamespace(params={"project_id": world["pid"]}))
        assert retry["images_deleted"] == 0
        assert retry["exports_deleted"] == 2
        assert retry["failed"] == 0
        assert not cache.exists() and not (DATA_DIR / "exports" / vid).exists()
        assert not version_cache.exists()
    finally:
        drop_version(vid)


def test_export_cache_left_in_place_is_not_counted_as_deleted(world, monkeypatch):
    """N1: a remover that returns without deleting must not be trusted — verify the path is gone."""
    item = seed_old_image(world["pid"], "silent-export")
    vid, cache, version_cache = seed_version_with_sources(world["pid"], [item["id"]])
    try:
        with monkeypatch.context() as m:
            m.setattr(retention.shutil, "rmtree", lambda path, *args, **kwargs: None)
            result = retention.run_retention(types.SimpleNamespace(params={"project_id": world["pid"]}))
        assert result["exports_deleted"] == 0
        assert result["failed"] >= 1
        assert cache.exists() and version_cache.exists()
    finally:
        drop_version(vid)


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
