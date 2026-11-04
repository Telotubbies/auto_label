"""Face anonymisation: pixel-level guarantees, no-cv2 resilience and the ingest hook."""

import io
import os
import tempfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-test-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from PIL import ImageChops

from app.config import DATA_DIR
from app.db import SessionLocal
from app.deps import Ctx
from app.main import app
from app.models import Batch, Image, Project, User, Workspace
from app.routers import images
from app.services import faceblur

WS, PR = "labeldesk-demo", "ppe-detection"


def noisy(size=(400, 300)) -> PImage.Image:
    rng = np.random.default_rng(7)
    return PImage.fromarray(rng.integers(0, 256, (size[1], size[0], 3), dtype=np.uint8), "RGB")


def jpeg(color: tuple[int, int, int]) -> bytes:
    b = io.BytesIO()
    PImage.new("RGB", (320, 240), color).save(b, "JPEG")
    return b.getvalue()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        tok = c.post("/api/auth/login", json={"email": "demo@labeldesk.dev", "password": "demo1234"}).json()["token"]
        c.headers["Authorization"] = f"Bearer {tok}"
        yield c


@pytest.fixture(scope="module")
def demo_ctx(client):
    db = SessionLocal()
    ws = db.query(Workspace).filter(Workspace.slug == WS).one()
    p = db.query(Project).filter(Project.workspace_id == ws.id, Project.slug == PR).one()
    u = db.get(User, ws.owner_id)
    c = Ctx(user=u, ws=ws, role="admin", db=db, project=p, ws_role="owner", project_role="manager")
    yield db, c
    db.close()


def _drop(db, result: dict) -> None:
    for row in result["images"]:
        img = db.get(Image, row["id"])
        if img:
            for rel in (img.path, img.thumb):
                if rel:
                    (DATA_DIR / rel).unlink(missing_ok=True)
            db.delete(img)
    batch = db.get(Batch, result["batch"]["id"])
    if batch:
        db.delete(batch)
    db.commit()


def test_blur_changes_the_face_box_only(monkeypatch):
    im = noisy()
    box = (150, 100, 80, 80)
    monkeypatch.setattr(faceblur, "detect_faces", lambda gray: [box])
    out, n = faceblur.blur_faces(im)
    assert n == 1
    assert out is not im
    assert out.size == im.size
    diff = ImageChops.difference(im, out)
    inside = diff.crop((160, 110, 220, 170)).getbbox()
    assert inside is not None, "the face box must be blurred"
    assert diff.crop((0, 0, 120, 300)).getbbox() is None, "left margin must stay untouched"
    assert diff.crop((340, 0, 400, 300)).getbbox() is None, "right margin must stay untouched"


def test_zero_faces_returns_the_same_object(monkeypatch):
    im = noisy()
    monkeypatch.setattr(faceblur, "detect_faces", lambda gray: [])
    out, n = faceblur.blur_faces(im)
    assert n == 0
    assert out is im
    assert ImageChops.difference(im, out).getbbox() is None


def test_detector_is_injected():
    im = noisy()
    seen = []

    def detector(gray):
        seen.append(gray.shape)
        return []

    faceblur.blur_faces(im, detector=detector)
    assert seen and seen[0][0] <= 640 and seen[0][1] <= 640


def test_missing_cv2_never_raises(monkeypatch):
    monkeypatch.setattr(faceblur, "_cascade", lambda: None)
    assert faceblur.detect_faces(np.zeros((32, 32), dtype=np.uint8)) == []
    im = noisy()
    out, n = faceblur.blur_faces(im)
    assert n == 0 and out is im


def test_ingest_blurs_every_source(client, demo_ctx, monkeypatch):
    """I16: stream frames and ordinary uploads both go through blur_faces when face_blur is on."""
    db, c = demo_ctx
    calls = []

    def marker(im, detector=None):
        calls.append(im.size)
        return im, 1

    monkeypatch.setattr(faceblur, "blur_faces", marker)
    res = images.ingest(
        db, c, [("cam-1.jpg", jpeg((10, 20, 30)))], "stream-test", "train", [], source="stream", user_id=c.user.id
    )
    try:
        assert calls, "stream frames must go through blur_faces"
        assert res["uploaded"] == 1
    finally:
        _drop(db, res)

    calls.clear()
    r = client.post(
        f"/api/ws/{WS}/projects/{PR}/upload", files=[("files", ("plain.jpg", jpeg((30, 40, 50)), "image/jpeg"))]
    )
    assert r.status_code == 200, r.text
    try:
        assert calls, "ordinary uploads must be blurred too"
    finally:
        _drop(db, r.json())


def test_face_blur_off_disables_the_hook(client, demo_ctx, monkeypatch):
    db, c = demo_ctx
    calls = []
    monkeypatch.setattr(faceblur, "blur_faces", lambda im, detector=None: (calls.append(1), im)[1])
    c.project.face_blur = False
    db.commit()
    try:
        res = images.ingest(
            db,
            c,
            [("cam-2.jpg", jpeg((60, 70, 80)))],
            "stream-test-off",
            "train",
            [],
            source="stream",
            user_id=c.user.id,
        )
        try:
            assert calls == []
        finally:
            _drop(db, res)
    finally:
        c.project.face_blur = True
        db.commit()
