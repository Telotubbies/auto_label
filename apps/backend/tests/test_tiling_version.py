"""Version generation with tile preprocessing: the source image becomes overlapping tiles."""
import json
import os
import time
import uuid

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import delete, func, select

from app.config import DATA_DIR
from app.db import SessionLocal
from app.main import app
from app.models import Image, LabelClass, Member, Project, ProjectMember, User, Version, Workspace, WorkspaceFlag
from app.security import hash_password, issue_access

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/ws/{WS}/projects/{PR}"
TILING = {"tile_size": 400, "overlap": 0.2}


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        r = client.post("/api/auth/login", json={"email": "demo@labeldesk.dev", "password": "demo1234"})
        client.headers["Authorization"] = f"Bearer {r.json()['token']}"
        yield client


@pytest.fixture(autouse=True)
def _flag_off(monkeypatch):
    """Every test starts with task_30 off; the tiling tests opt in through the workspace row."""
    keys = [k for k in os.environ.get("LD_FLAGS_ON", "").split(",") if k and k != "task_30"]
    monkeypatch.setenv("LD_FLAGS_ON", ",".join(keys))
    clear()
    yield
    clear()


def clear():
    with SessionLocal() as db:
        db.execute(delete(WorkspaceFlag).where(WorkspaceFlag.key == "task_30"))
        db.commit()


def enable_tiling():
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace.id).where(Workspace.slug == WS))
        db.merge(WorkspaceFlag(workspace_id=ws, key="task_30", enabled=True))
        db.commit()


def _seed_source_image() -> str:
    """One 800x600 source with a left and a right object; returns the image id."""
    with SessionLocal() as db:
        pid = db.scalar(select(Project.id).where(Project.slug == PR))
        cid = db.scalar(select(LabelClass.id).where(LabelClass.project_id == pid))
        rel = "uploads/tile_source.jpg"
        (DATA_DIR / rel).parent.mkdir(parents=True, exist_ok=True)
        rng = np.random.default_rng(7)
        PImage.fromarray(rng.integers(0, 255, (600, 800, 3), dtype=np.uint8)).save(DATA_DIR / rel, "JPEG")
        iid = "tile-source-01"
        db.merge(Image(
            id=iid, project_id=pid, name="tile_source.jpg", sha256="t" * 64, width=800, height=600,
            path=rel, thumb=rel, split="train", status="done",
            annotations=[
                {"id": "l", "classId": cid, "shape": {"kind": "bbox", "x": 0.05, "y": 0.1, "w": 0.1, "h": 0.1}},
                {"id": "r", "classId": cid, "shape": {"kind": "bbox", "x": 0.8, "y": 0.2, "w": 0.1, "h": 0.1}},
            ],
        ))
        db.commit()
        return iid


def _make_version(c, settings) -> dict:
    v = c.post(f"{BASE}/versions", json={"settings": settings}).json()
    t = time.time()
    while time.time() - t < 300:
        j = c.get(f"{BASE}/jobs/{v['job']['id']}").json()
        if j["status"] in ("done", "failed", "cancelled"):
            assert j["status"] == "done", j
            break
        time.sleep(0.5)
    return c.get(f"{BASE}/versions/{v['id']}").json()


def _manifest(v) -> dict:
    return json.loads((DATA_DIR / "versions" / v["id"] / "manifest.json").read_text())


def test_version_tiles_the_source_image(c):
    enable_tiling()
    iid = _seed_source_image()
    v = _make_version(c, {"preprocessing": {"tiling": TILING}, "augmentation": {}})
    mine = [it for it in _manifest(v)["items"] if it["source"] == iid]
    assert len(mine) == 6, mine
    assert all(it["width"] <= 400 and it["height"] <= 400 for it in mine)
    assert any(it["anns"] for it in mine)
    assert all(0.0 <= a["shape"].get("x", 0) <= 1.0 and 0.0 <= a["shape"].get("w", 0) <= 1.0
               for it in mine for a in it["anns"])
    # the right-hand object only survives on tiles that reach the right edge
    assert [it for it in mine if any(a["shape"].get("x", 0) > 0.5 for a in it["anns"])]
    assert _manifest(v)["config"]["preprocessing"]["tiling"]["tile_size"] == 400


def test_version_without_tiling_keeps_one_item_per_source(c):
    iid = _seed_source_image()
    v = _make_version(c, {"preprocessing": {}, "augmentation": {}})
    mine = [it for it in _manifest(v)["items"] if it["source"] == iid]
    assert len(mine) == 1 and mine[0]["width"] == 800


def test_tiling_slices_the_source_before_the_resize(c):
    """The resize must not shrink a large image before the 400 px tiles are cut."""
    enable_tiling()
    iid = _seed_source_image()
    v = _make_version(c, {"preprocessing": {
        "resize": {"width": 200, "height": 200, "mode": "stretch"}, "tiling": {"tile_size": 400, "overlap": 0},
    }, "augmentation": {}})
    mine = [it for it in _manifest(v)["items"] if it["source"] == iid]
    assert len(mine) == 4, mine
    assert all((it["width"], it["height"]) == (200, 200) for it in mine)
    assert sum(len(it["anns"]) for it in mine) == 2


def test_tiling_an_image_smaller_than_the_tile_keeps_its_real_size(c):
    """I3: the 1024 px default over an 800x600 image is one 800x600 item, not a padded crop."""
    enable_tiling()
    iid = _seed_source_image()
    v = _make_version(c, {"preprocessing": {"tiling": {"tile_size": 1024}}, "augmentation": {}})
    mine = [it for it in _manifest(v)["items"] if it["source"] == iid]
    assert len(mine) == 1, mine
    assert (mine[0]["width"], mine[0]["height"]) == (800, 600)


def test_filter_null_drops_the_tiles_without_annotations(c):
    """I4: "drop images with no annotations" must mean the same thing for the tiles it creates."""
    enable_tiling()
    iid = _seed_source_image()
    v = _make_version(c, {"preprocessing": {"tiling": TILING, "filter_null": True}, "augmentation": {}})
    mine = [it for it in _manifest(v)["items"] if it["source"] == iid]
    assert mine and all(it["anns"] for it in mine), mine
    assert len(mine) < 6
    assert v["stats"]["tiles_skipped"] >= 6 - len(mine)


def test_tiling_is_hidden_when_the_flag_is_off(c):
    _seed_source_image()
    with SessionLocal() as db:
        pid = db.scalar(select(Project.id).where(Project.slug == PR))
        before = db.scalar(select(func.count()).select_from(Version).where(Version.project_id == pid))
    r = c.post(f"{BASE}/versions", json={"settings": {"preprocessing": {"tiling": {"tile_size": 400}}}})
    assert r.status_code == 404, r.text
    with SessionLocal() as db:
        pid = db.scalar(select(Project.id).where(Project.slug == PR))
        after = db.scalar(select(func.count()).select_from(Version).where(Version.project_id == pid))
    assert after == before


def test_bad_tiling_settings_are_a_400(c):
    enable_tiling()
    r = c.post(f"{BASE}/versions", json={"settings": {"preprocessing": {"tiling": {"tile_size": 16}}}})
    assert r.status_code == 400, r.text
    assert "tiling" in r.json()["detail"]


def test_a_viewer_cannot_tile_a_version(c):
    """Tiling must not become a way around the reviewer permission."""
    enable_tiling()
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        p = db.scalar(select(Project).where(Project.slug == PR))
        u = User(id=f"u{suffix}", email=f"t30-viewer-{suffix}@x.io", name="T30 Viewer",
                 pw_hash=hash_password("longpassword1"), email_verified=1.0)
        db.add(u)
        db.flush()
        db.add_all([Member(workspace_id=ws.id, user_id=u.id, role="member"),
                    ProjectMember(project_id=p.id, user_id=u.id, role="viewer")])
        db.commit()
        token = issue_access(u.id)
    r = TestClient(app).post(f"{BASE}/versions", headers={"Authorization": f"Bearer {token}"},
                             json={"settings": {"preprocessing": {"tiling": TILING}}})
    assert r.status_code == 403, r.text


def test_tiling_on_a_classification_project_is_a_400(c):
    """A classification label has no geometry, so there is nothing to slice."""
    enable_tiling()
    slug = f"t30-classify-{uuid.uuid4().hex[:6]}"
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        p = Project(workspace_id=ws.id, slug=slug, name=slug, type="classification", settings={})
        db.add(p)
        db.commit()
    try:
        r = c.post(f"/api/ws/{WS}/projects/{slug}/versions",
                   json={"settings": {"preprocessing": {"tiling": TILING}}})
        assert r.status_code == 400, r.text
        assert "detection" in r.json()["detail"]
    finally:
        with SessionLocal() as db:
            db.delete(db.scalar(select(Project).where(Project.slug == slug)))
            db.commit()
