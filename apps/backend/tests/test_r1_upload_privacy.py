"""I16: every ingest source blurs faces when the project asks, and fails closed without a detector."""

import io
import shutil
import uuid

import pytest
from fastapi import HTTPException
from PIL import Image as PImage
from PIL import ImageOps
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select

from app.config import DATA_DIR
from app.db import Base, SessionLocal, engine
from app.deps import Ctx
from app.models import Batch, Image, Project, User, Workspace
from app.routers import images
from app.services import imaging


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)


@pytest.fixture()
def ctx():
    suffix = uuid.uuid4().hex[:8]
    db = SessionLocal()
    u = User(id="u" + suffix, email=f"blur-{suffix}@x.io", name="B", pw_hash="x")
    db.add(u)
    db.flush()
    ws = Workspace(id="w" + suffix, slug=f"blur-{suffix}", name="B", owner_id=u.id)
    db.add(ws)
    db.flush()
    p = Project(workspace_id=ws.id, slug=f"blurp-{suffix}", name="Face project", type="object-detection",
                face_blur=True, settings={})
    db.add(p)
    db.commit()
    c = Ctx(user=u, ws=ws, role="owner", db=db, project=p, ws_role="owner", project_role="manager")
    yield c
    project_id = p.id
    db.close()
    with SessionLocal() as cleanup:
        cleanup.execute(sa_delete(Image).where(Image.project_id == project_id))
        cleanup.execute(sa_delete(Batch).where(Batch.project_id == project_id))
        cleanup.execute(sa_delete(Project).where(Project.id == project_id))
        cleanup.execute(sa_delete(Workspace).where(Workspace.id == ws.id))
        cleanup.execute(sa_delete(User).where(User.id == u.id))
        cleanup.commit()
    shutil.rmtree(DATA_DIR / "projects" / project_id, ignore_errors=True)


def jpeg(color: tuple[int, int, int]) -> bytes:
    b = io.BytesIO()
    PImage.new("RGB", (64, 48), color).save(b, "JPEG")
    return b.getvalue()


@pytest.mark.parametrize("source", ["upload", "connector", "stream"])
def test_every_source_blurs_before_store(ctx, monkeypatch, source):
    """A direct upload or connector import must be anonymised exactly like a stream frame."""
    calls = []

    def spy(im, detector=None):
        calls.append(im.size)
        return ImageOps.invert(im), 1          # visibly different pixels, so the stored JPEG proves it ran

    monkeypatch.setattr(images.faceblur, "available", lambda: True)
    monkeypatch.setattr(images.faceblur, "blur_faces", spy)

    raw = jpeg((0, 0, 0))
    res = images.ingest(ctx.db, ctx, [("frame.jpg", raw)], f"blur-{source}", "train", [], source=source,
                        user_id=ctx.user.id)

    assert res["uploaded"] == 1
    assert calls == [(64, 48)], "blur_faces must run once per stored image"
    row = ctx.db.get(Image, res["images"][0]["id"])
    stored = imaging.load(row.path)
    # The raw frame is black; the spy inverted it, so white pixels can only be the blurred output.
    assert stored.getpixel((0, 0))[0] > 200
    assert stored.tobytes() != PImage.open(io.BytesIO(raw)).convert("RGB").tobytes()


def test_ingest_fails_closed_when_the_detector_is_unavailable(ctx, monkeypatch):
    monkeypatch.setattr(images.faceblur, "available", lambda: False)
    before = ctx.db.scalar(select(func.count(Image.id)).where(Image.project_id == ctx.project.id))

    with pytest.raises(HTTPException) as exc:
        images.ingest(ctx.db, ctx, [("frame.jpg", jpeg((10, 20, 30)))], "no-detector", "train", [],
                      source="upload", user_id=ctx.user.id)

    assert exc.value.status_code == 503
    assert "face detector is unavailable" in exc.value.detail
    after = ctx.db.scalar(select(func.count(Image.id)).where(Image.project_id == ctx.project.id))
    assert after == before
    assert ctx.db.scalar(select(func.count(Batch.id)).where(Batch.project_id == ctx.project.id)) == 0
