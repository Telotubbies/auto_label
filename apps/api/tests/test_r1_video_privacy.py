"""I16/I17: extracted video frames are blurred when asked and obey the plan quotas."""
import os
import uuid
from types import SimpleNamespace

os.environ.setdefault("LD_WORKER_TOKEN", "test-worker-token-0123456789abcdef")

import numpy as np
import pytest
from PIL import Image as PImage
from PIL import ImageOps

from app import worker
from app.config import DATA_DIR
from app.db import Base, SessionLocal, engine
from app.models import Image, Job, Project, User, Video, Workspace


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)


@pytest.fixture()
def video_job(monkeypatch):
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        u = User(id="u" + suffix, email=f"vid-{suffix}@x.io", name="V", pw_hash="x")
        db.add(u); db.flush()
        ws = Workspace(id="w" + suffix, slug=f"vid-{suffix}", name="V", owner_id=u.id)
        db.add(ws); db.flush()
        p = Project(workspace_id=ws.id, slug=f"vidp-{suffix}", name="Video project", type="object-detection",
                    face_blur=True, settings={})
        db.add(p); db.flush()
        v = Video(id="v" + suffix, project_id=p.id, workspace_id=ws.id, name="cam.mp4", path="videos/cam.mp4",
                  frame_count=1, fps=1.0, width=8, height=8)
        db.add(v); db.flush()
        j = Job(workspace_id=ws.id, project_id=p.id, kind="extract_frames",
                params={"video_id": v.id, "mode": "fps", "target_fps": 1})
        db.add(j); db.commit()
        ctx = SimpleNamespace(job=j, ws=ws.id, project=p.id, video=v.id)

    class Cap:
        def __init__(self, *_a, **_kw):
            self.reads = 0

        def isOpened(self):
            return True

        def get(self, prop):
            return {7: 1, 5: 1.0, 3: 8, 4: 8}.get(prop, 0)

        def read(self):
            self.reads += 1
            if self.reads > 1:
                return False, None
            return True, np.zeros((8, 8, 3), dtype=np.uint8)

        def release(self):
            pass

    monkeypatch.setattr(worker.cv2, "VideoCapture", lambda *a, **kw: Cap())
    from app.services import faceblur
    calls: list = []

    def spy(im, detector=None):
        calls.append(im.copy())                   # the frame that reaches the blur, before encoding
        return ImageOps.invert(im), 1             # visibly different bytes, so the stored JPEG proves it ran

    monkeypatch.setattr(faceblur, "blur_faces", spy)
    ctx.blur_calls = calls
    return ctx


def test_extraction_blurs_every_kept_frame(video_job):
    """I16: the PDPA control must actually run before the frame bytes are stored."""
    worker.run_extract_frames(video_job.job)
    assert len(video_job.blur_calls) == 1          # one call for the one kept frame
    with SessionLocal() as db:
        img = db.scalar(__import__("sqlalchemy").select(Image).where(Image.video_id == video_job.video))
        assert img is not None
        stored = PImage.open(DATA_DIR / img.path).convert("RGB")
    # The raw frame is black; the spy inverted it, so the stored JPEG can only be the blurred output.
    assert stored.getpixel((0, 0))[0] > 200


def test_extraction_fails_closed_when_face_blur_is_unavailable(video_job, monkeypatch):
    from app.services import faceblur
    monkeypatch.setattr(faceblur, "available", lambda: False)
    with pytest.raises(RuntimeError, match="face blur"):
        worker.run_extract_frames(video_job.job)
    with SessionLocal() as db:
        assert db.get(Video, video_job.video).status == "failed"
        assert db.scalar(__import__("sqlalchemy").select(Image).where(Image.video_id == video_job.video)) is None


def test_extraction_enforces_the_image_limit(video_job, monkeypatch):
    monkeypatch.setattr(worker, "plan", lambda ws: {"images": 0, "label": "Free"})
    with pytest.raises(worker.QuotaExhausted):
        worker.run_extract_frames(video_job.job)


def test_extraction_meters_frame_storage(video_job, monkeypatch):
    from sqlalchemy import func, select

    from app.models import UsageEvent
    with SessionLocal() as db:
        before = db.scalar(select(func.sum(UsageEvent.quantity)).where(
            UsageEvent.workspace_id == video_job.ws, UsageEvent.metric == "storage_bytes")) or 0
    worker.run_extract_frames(video_job.job)
    with SessionLocal() as db:
        after = db.scalar(select(func.sum(UsageEvent.quantity)).where(
            UsageEvent.workspace_id == video_job.ws, UsageEvent.metric == "storage_bytes")) or 0
    assert after > before
