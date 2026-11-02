"""I3: purging a project removes every file prefix that belongs to it, and only its own."""
import uuid

from app.config import DATA_DIR
from app.db import Base, SessionLocal, engine
from app.models import Image, Project, TrainedModel, User, Version, Workspace
import pytest


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)


def _touch(rel: str) -> None:
    p = DATA_DIR / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")


def test_project_purge_removes_all_prefixes():
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        u = User(id="u" + suffix, email=f"er-{suffix}@x.io", name="E", pw_hash="x")
        db.add(u); db.flush()
        ws = Workspace(id="w" + suffix, slug=f"er-{suffix}", name="E", owner_id=u.id)
        db.add(ws); db.flush()
        p = Project(workspace_id=ws.id, slug=f"erp-{suffix}", name="Erase")
        db.add(p); db.flush()
        v = Version(project_id=p.id, number=1, status="ready", stats={})
        db.add(v); db.flush()
        m = TrainedModel(workspace_id=ws.id, project_id=p.id, version_id=v.id, name="m", arch="yolo26n",
                         variant="yolo26n", task="detect", status="ready", family="ultralytics", classes=[],
                         weights=f"models/{'m' + suffix}/best.pt")
        db.add(m); db.flush()
        img = Image(id="i" + suffix, project_id=p.id, name="a.jpg", sha256="x", width=1, height=1, size=1,
                    path=f"projects/{p.id}/images/{'i' + suffix}.jpg", thumb=f"projects/{p.id}/thumbs/{'i' + suffix}.jpg",
                    annotations=[], n_annotations=0)
        db.add(img)
        from app.models import Video
        db.add(Video(id="v" + suffix, project_id=p.id, workspace_id=ws.id, name="cam.mp4",
                     path=f"videos/{suffix}.mp4"))
        db.commit()
        pid, wid, mid, vid = p.id, ws.id, m.id, v.id
    for rel in (f"projects/{pid}/images/x.jpg", f"projects/{pid}/thumbs/x.jpg",
                f"videos/{suffix}.mp4", f"models/{mid}/best.pt", f"versions/{vid}/manifest.json",
                f"exports/{vid}/coco.zip", f"snapshots/{pid}/a.jpg", f"workspaces/{wid}/drift/{pid}/a.jpg"):
        _touch(rel)
    keep = DATA_DIR / f"projects/other-{suffix}/images/keep.jpg"
    keep.parent.mkdir(parents=True, exist_ok=True); keep.write_bytes(b"keep")

    from app.services.erasure import delete_project_data
    with SessionLocal() as db:
        delete_project_data(db, db.get(Project, pid))
    for rel in (f"projects/{pid}", f"videos/{suffix}.mp4", f"models/{mid}", f"versions/{vid}",
                f"exports/{vid}", f"snapshots/{pid}", f"workspaces/{wid}/drift/{pid}"):
        assert not (DATA_DIR / rel).exists(), rel
    assert keep.exists()


def test_version_delete_erases_its_bytes_only():
    """Deleting one version removes its snapshot and exports, leaving other projects alone."""
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        u = User(id="u" + suffix, email=f"vd-{suffix}@x.io", name="E", pw_hash="x")
        db.add(u); db.flush()
        ws = Workspace(id="w" + suffix, slug=f"vd-{suffix}", name="E", owner_id=u.id)
        db.add(ws); db.flush()
        gone_p = Project(workspace_id=ws.id, slug=f"vd-a-{suffix}", name="Gone")
        keep_p = Project(workspace_id=ws.id, slug=f"vd-b-{suffix}", name="Keep")
        db.add_all([gone_p, keep_p]); db.flush()
        gone = Version(project_id=gone_p.id, number=1, status="ready", stats={})
        keep = Version(project_id=keep_p.id, number=1, status="ready", stats={})
        db.add_all([gone, keep]); db.flush()
        db.commit()
        gone_id, keep_id = gone.id, keep.id
    for rel in (f"versions/{gone_id}/manifest.json", f"exports/{gone_id}/coco.zip",
                f"versions/{keep_id}/manifest.json", f"exports/{keep_id}/coco.zip"):
        _touch(rel)

    from app.services.erasure import delete_version_data
    with SessionLocal() as db:
        freed = delete_version_data(db, db.get(Version, gone_id))

    assert freed > 0
    assert not (DATA_DIR / f"versions/{gone_id}").exists()
    assert not (DATA_DIR / f"exports/{gone_id}").exists()
    assert (DATA_DIR / f"versions/{keep_id}/manifest.json").exists()
    assert (DATA_DIR / f"exports/{keep_id}/coco.zip").exists()
