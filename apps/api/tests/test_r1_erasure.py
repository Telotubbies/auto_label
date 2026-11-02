"""I3: purging a project removes every file prefix that belongs to it, and only its own."""
import os
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
                f"videos/{suffix}.mp4", f"models/{mid}/best.pt", f"runs/{mid}/weights/last.pt",
                f"versions/{vid}/manifest.json",
                f"exports/{vid}/coco.zip", f"snapshots/{pid}/a.jpg", f"workspaces/{wid}/drift/{pid}/a.jpg"):
        _touch(rel)
    keep = DATA_DIR / f"projects/other-{suffix}/images/keep.jpg"
    keep.parent.mkdir(parents=True, exist_ok=True); keep.write_bytes(b"keep")

    from app.services.erasure import delete_project_data
    with SessionLocal() as db:
        freed, ok = delete_project_data(db, db.get(Project, pid))
    assert ok and freed > 0
    for rel in (f"projects/{pid}", f"videos/{suffix}.mp4", f"models/{mid}", f"runs/{mid}", f"versions/{vid}",
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
        freed, ok = delete_version_data(db, db.get(Version, gone_id))

    assert ok
    assert freed > 0
    assert not (DATA_DIR / f"versions/{gone_id}").exists()
    assert not (DATA_DIR / f"exports/{gone_id}").exists()
    assert (DATA_DIR / f"versions/{keep_id}/manifest.json").exists()
    assert (DATA_DIR / f"exports/{keep_id}/coco.zip").exists()


def _login(email: str, password: str = "longpassword1"):
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    client.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return client


def _route_project():
    """A workspace admin (legacy role) who can reach the bulk and model routes."""
    from app.security import hash_password
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        from app.models import Member
        u = User(id="u" + suffix, email=f"rt-{suffix}@x.io", name="Route", pw_hash=hash_password("longpassword1"),
                 email_verified=1.0)
        db.add(u); db.flush()
        ws = Workspace(id="w" + suffix, slug=f"rt-{suffix}", name="Route ws", owner_id=u.id)
        db.add(ws); db.flush()
        p = Project(workspace_id=ws.id, slug=f"rtp-{suffix}", name="Route project")
        db.add(p); db.flush()
        db.add(Member(workspace_id=ws.id, user_id=u.id, role="admin"))
        db.commit()
        return u.email, ws.slug, ws.id, p.id, p.slug


def test_bulk_delete_erases_every_image_and_credits_the_meter():
    """The Dataset page uses the bulk route: it must purge bytes like the single delete does."""
    from app.services import metering
    email, ws_slug, ws_id, p_id, slug = _route_project()
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        rows = []
        for i in range(2):
            rel = f"projects/{p_id}/images/bulk-{suffix}-{i}.jpg"
            _touch(rel)
            rows.append(Image(id=f"ib{suffix}{i}", project_id=p_id, name=f"{i}.jpg", sha256=f"{suffix}{i}",
                              width=2, height=2, size=100, path=rel, thumb="", annotations=[], n_annotations=0))
        db.add_all(rows)
        ws = db.get(Workspace, ws_id)
        metering.record(db, ws.id, "storage_bytes", 200, project_id=p_id)
        db.commit()
        ids = [r.id for r in rows]

    with _login(email) as c:
        r = c.post(f"/api/ws/{ws_slug}/projects/{slug}/images/bulk", json={"ids": ids, "action": "delete"})
    assert r.status_code == 200, r.text
    for i in range(2):
        assert not (DATA_DIR / f"projects/{p_id}/images/bulk-{suffix}-{i}.jpg").exists()
    with SessionLocal() as db:
        assert metering.used(db, db.get(Workspace, ws_id), "storage_bytes") == 0


def test_delete_model_route_erases_weights_runs_and_engine():
    email, ws_slug, ws_id, p_id, slug = _route_project()
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        v = Version(project_id=p_id, number=1, status="ready", stats={})
        db.add(v); db.flush()
        m = TrainedModel(workspace_id=ws_id, project_id=p_id, version_id=v.id, name="erase-me", arch="yolo26n",
                         variant="yolo26n", task="detect", status="ready", family="ultralytics", classes=[],
                         weights=f"models/run{suffix}/best.pt")
        db.add(m); db.commit()
        mid = m.id
    for rel in (f"models/{mid}/best.pt", f"runs/{mid}/weights/last.pt", f"runs/{mid}/results.csv",
                f"engines/{mid}.engine"):
        _touch(rel)

    with _login(email) as c:
        r = c.delete(f"/api/ws/{ws_slug}/projects/{slug}/models/{mid}")
    assert r.status_code == 200, r.text
    assert not (DATA_DIR / f"models/{mid}").exists()
    assert not (DATA_DIR / f"runs/{mid}").exists()
    assert not (DATA_DIR / f"engines/{mid}.engine").exists()


@pytest.mark.skipif(os.name != "nt", reason="POSIX allows unlinking a file that is still open")
def test_version_delete_route_keeps_the_row_when_a_file_is_locked():
    """A Windows sharing violation must 409 and keep the row, so the retry can finish the erase."""
    email, ws_slug, ws_id, p_id, slug = _route_project()
    with SessionLocal() as db:
        v = Version(project_id=p_id, number=2, status="ready", stats={})
        db.add(v); db.commit(); vid = v.id
    rel = f"versions/{vid}/manifest.json"
    _touch(rel)
    path = DATA_DIR / rel
    url = f"/api/ws/{ws_slug}/projects/{slug}/versions/{vid}"

    with _login(email) as c:
        with open(path, "rb") as locked:
            r = c.delete(url)
            assert r.status_code == 409, r.text
            assert locked.read() == b"x"                 # the locked byte is still on disk
        with SessionLocal() as db:
            assert db.get(Version, vid) is not None      # no row without the bytes
        r = c.delete(url)
        assert r.status_code == 200, r.text
    assert not path.exists()
    with SessionLocal() as db:
        assert db.get(Version, vid) is None


@pytest.mark.skipif(os.name != "nt", reason="POSIX allows unlinking a file that is still open")
def test_model_delete_route_keeps_the_row_when_a_weight_is_locked():
    email, ws_slug, ws_id, p_id, slug = _route_project()
    suffix = uuid.uuid4().hex[:8]
    weights = f"models/locked-{suffix}/best.pt"
    with SessionLocal() as db:
        v = Version(project_id=p_id, number=1, status="ready", stats={})
        db.add(v); db.flush()
        m = TrainedModel(workspace_id=ws_id, project_id=p_id, version_id=v.id, name="locked-model", arch="yolo26n",
                         variant="yolo26n", task="detect", status="ready", family="ultralytics", classes=[],
                         weights=weights)
        db.add(m); db.commit(); mid = m.id
    _touch(weights)
    path = DATA_DIR / weights
    url = f"/api/ws/{ws_slug}/projects/{slug}/models/{mid}"

    with _login(email) as c:
        with open(path, "rb"):
            r = c.delete(url)
            assert r.status_code == 409, r.text
        with SessionLocal() as db:
            assert db.get(TrainedModel, mid) is not None
        r = c.delete(url)
        assert r.status_code == 200, r.text
    assert not path.exists()
    with SessionLocal() as db:
        assert db.get(TrainedModel, mid) is None


@pytest.mark.skipif(os.name != "nt", reason="POSIX allows unlinking a file that is still open")
def test_image_delete_route_keeps_the_row_when_a_file_is_locked():
    """A locked JPEG must 409 and keep the row, so a retry can finish the erase and credit the meter."""
    from app.services import metering
    email, ws_slug, ws_id, p_id, slug = _route_project()
    suffix = uuid.uuid4().hex[:8]
    rel = f"projects/{p_id}/images/locked-{suffix}.jpg"
    with SessionLocal() as db:
        img = Image(id=f"il{suffix}", project_id=p_id, name="locked.jpg", sha256=f"lk{suffix}",
                    width=2, height=2, size=100, path=rel, thumb="", annotations=[], n_annotations=0)
        db.add(img)
        metering.record(db, ws_id, "storage_bytes", 100, project_id=p_id)
        db.commit()
        iid = img.id
    _touch(rel)
    path = DATA_DIR / rel

    with _login(email) as c:
        with open(path, "rb") as locked:
            r = c.delete(f"/api/images/{iid}")
            assert r.status_code == 409, r.text
            assert locked.read() == b"x"                 # the locked byte is still on disk
        with SessionLocal() as db:
            row = db.get(Image, iid)
            assert row is not None and row.deleted_at is None      # no row without the bytes
            assert metering.used(db, db.get(Workspace, ws_id), "storage_bytes") == 100
        r = c.delete(f"/api/images/{iid}")
        assert r.status_code == 200, r.text
    assert not path.exists()
    with SessionLocal() as db:
        assert db.get(Image, iid).deleted_at is not None
        assert metering.used(db, db.get(Workspace, ws_id), "storage_bytes") == 0


@pytest.mark.skipif(os.name != "nt", reason="POSIX allows unlinking a file that is still open")
def test_bulk_delete_keeps_rows_and_bytes_consistent_when_a_file_is_locked():
    """A locked file only spares its own row; rows whose bytes are already gone stay deleted."""
    from app.services import metering
    email, ws_slug, ws_id, p_id, slug = _route_project()
    suffix = uuid.uuid4().hex[:8]
    rels = [f"projects/{p_id}/images/bulk-lock-{suffix}-{i}.jpg" for i in range(2)]
    paths = []
    with SessionLocal() as db:
        ids = []
        for i, rel in enumerate(rels):
            _touch(rel)
            paths.append(DATA_DIR / rel)
            img = Image(id=f"ibl{suffix}{i}", project_id=p_id, name=f"{i}.jpg", sha256=f"bl{suffix}{i}",
                        width=2, height=2, size=100, path=rel, thumb="", annotations=[], n_annotations=0)
            db.add(img)
            ids.append(img.id)
        metering.record(db, ws_id, "storage_bytes", 200, project_id=p_id)
        db.commit()

    url = f"/api/ws/{ws_slug}/projects/{slug}/images/bulk"
    with _login(email) as c:
        with open(paths[1], "rb"):
            r = c.post(url, json={"ids": ids, "action": "delete"})
            assert r.status_code == 409, r.text
            assert r.json()["deleted"] == [ids[0]]
            assert r.json()["survived"] == [ids[1]]
        # The first file is gone, so its row and meter entry must be committed with it: a visible
        # row over erased bytes is the partial-erase bug this regression guards.
        assert not paths[0].exists() and paths[1].exists()
        with SessionLocal() as db:
            assert db.get(Image, ids[0]).deleted_at is not None
            assert db.get(Image, ids[1]).deleted_at is None
            assert metering.used(db, db.get(Workspace, ws_id), "storage_bytes") == 100
        r = c.post(url, json={"ids": ids, "action": "delete"})
        assert r.status_code == 200, r.text
    assert not paths[0].exists() and not paths[1].exists()
    with SessionLocal() as db:
        for iid in ids:
            assert db.get(Image, iid).deleted_at is not None
        assert metering.used(db, db.get(Workspace, ws_id), "storage_bytes") == 0


@pytest.mark.skipif(os.name != "nt", reason="POSIX allows unlinking a file that is still open")
def test_delete_model_files_reports_a_surviving_locked_weight():
    """Unit contract: (freed, ok) is false while a locked weight survives, true after the retry."""
    from app.services.erasure import delete_model_files
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        u = User(id="u" + suffix, email=f"ml-{suffix}@x.io", name="E", pw_hash="x")
        db.add(u); db.flush()
        ws = Workspace(id="w" + suffix, slug=f"ml-{suffix}", name="E", owner_id=u.id)
        db.add(ws); db.flush()
        p = Project(workspace_id=ws.id, slug=f"mlp-{suffix}", name="Locked")
        db.add(p); db.flush()
        v = Version(project_id=p.id, number=1, status="ready", stats={})
        db.add(v); db.flush()
        m = TrainedModel(workspace_id=ws.id, project_id=p.id, version_id=v.id, name="m", arch="yolo26n",
                         variant="yolo26n", task="detect", status="ready", family="ultralytics", classes=[],
                         weights=f"models/lock-{suffix}/best.pt")
        db.add(m); db.commit(); mid, weights = m.id, m.weights

        _touch(weights)
        _touch(f"runs/{mid}/last.pt")
        path = DATA_DIR / weights
        with open(path, "rb"):
            _, ok = delete_model_files(db.get(TrainedModel, mid))
        assert ok is False
        assert path.exists()
        _, ok = delete_model_files(db.get(TrainedModel, mid))
        assert ok is True
        assert not path.exists()
