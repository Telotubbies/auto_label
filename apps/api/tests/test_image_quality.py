"""Data-quality signals: ingest-time sharpness/luminance, health counts and the dataset quality filter."""

import os
import random
import time
import uuid
from io import BytesIO

os.environ.setdefault("LD_EMBEDDED_WORKER", "1")
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from PIL import ImageDraw, ImageFilter
from sqlalchemy import select

import cv2
import numpy as np

from app import worker
from app.config import DATA_DIR
from app.db import SessionLocal
from app.main import app
from app.models import Image, Job, Member, Project, User, Video, Workspace, now
from app.security import issue_access
from app.services import health, quality

WS = "labeldesk-demo"
NAME = "image-quality-qa"


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
        client.headers["Authorization"] = f"Bearer {issue_access(user.id)}"
        yield client


@pytest.fixture(scope="module")
def project(c):
    r = c.post(f"/api/ws/{WS}/projects", json={"name": NAME, "classes": ["person"]})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def other_world():
    """A second workspace with its own project, to prove the quality filter stays tenant-scoped."""
    tag = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        u = User(
            email=f"quality-{tag}@example.test",
            name="Quality Tester",
            email_verified=now(),
        )
        db.add(u)
        db.flush()
        ws = Workspace(
            slug=f"quality-{tag}",
            name="Quality Fixture",
            owner_id=u.id,
            credits_period=time.strftime("%Y-%m"),
        )
        db.add(ws)
        db.flush()
        db.add(Member(workspace_id=ws.id, user_id=u.id, role="admin"))
        p = Project(workspace_id=ws.id, slug="quality-other", name="Quality Other")
        db.add(p)
        db.commit()
        ids = {"ws": ws.slug, "pid": p.id, "uid": u.id}
        ids["token"] = issue_access(u.id)
    yield ids


def textured(seed: int = 1, size: tuple[int, int] = (480, 360)) -> PImage.Image:
    """A synthetic photo: colour gradient plus high-contrast shapes, so Laplacian edges are real."""
    rng = random.Random(seed)
    w, h = size
    im = PImage.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = (
                int(40 + 150 * x / w),
                int(60 + 120 * y / h),
                int(180 - 100 * y / h),
            )
    d = ImageDraw.Draw(im)
    for _ in range(30):
        x, y = rng.randrange(0, w - 24), rng.randrange(0, h - 24)
        d.rectangle([x, y, x + 18, y + 12], fill=(250, 240, 30))
    return im


def dark_checker(size: int = 256, level: int = 25) -> PImage.Image:
    """Sharp edges at ~5 % brightness: low luminance, enough Laplacian contrast to stay 'dark', not 'blurry'."""
    im = PImage.new("L", (size, size))
    px = im.load()
    for y in range(size):
        for x in range(size):
            px[x, y] = level if ((x // 8) + (y // 8)) % 2 else 0
    return im.convert("RGB")


def blurred(im: PImage.Image) -> PImage.Image:
    return im.filter(ImageFilter.GaussianBlur(6))


def jpeg(im: PImage.Image) -> bytes:
    buf = BytesIO()
    im.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def add_row(
    pid: str, name: str, sharpness: float | None, luminance: float | None
) -> str:
    """A row with scores set directly: the filter must read columns, never decode pixels."""
    rel = f"quality/{name}.jpg"
    with SessionLocal() as db:
        row = Image(
            project_id=pid,
            name=name,
            sha256=name,
            width=64,
            height=64,
            path=rel,
            thumb=rel,
            split="train",
            status="done",
            annotations=[],
            n_annotations=0,
            sharpness=sharpness,
            luminance=luminance,
        )
        db.add(row)
        db.commit()
        return row.id


def listed(c, project, **params) -> list[str]:
    r = c.get(
        f"/api/ws/{WS}/projects/{project['slug']}/images",
        params={"limit": 1000, **params},
    )
    assert r.status_code == 200, r.text
    return [i["id"] for i in r.json()["items"]]


def test_sharp_blurry_and_dark_images_classify_correctly():
    sharpness, luminance = quality.analyze(textured())
    assert 0.0 <= sharpness <= 1.0 and 0.0 <= luminance <= 1.0
    assert quality.classify(sharpness, luminance) == "ok"

    assert quality.classify(*quality.analyze(blurred(textured()))) == "blurry"

    dark_score, dark_mean = quality.analyze(dark_checker())
    assert dark_mean < quality.DARK_MEAN
    assert quality.classify(dark_score, dark_mean) == "dark"


def test_missing_scores_are_unknown_never_ok():
    assert quality.classify(None, 0.5) == "unknown"
    assert quality.classify(0.5, None) == "unknown"
    assert quality.classify(None, None) == "unknown"


def test_ingest_stores_quality_on_the_image_row(c, project):
    files = [
        ("sharp.jpg", jpeg(textured(2))),
        ("blurry.jpg", jpeg(blurred(textured(3)))),
        ("dark.jpg", jpeg(dark_checker())),
    ]
    r = c.post(
        f"/api/ws/{WS}/projects/{project['slug']}/upload",
        files=[("files", f) for f in files],
        data={"split": "keep"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["uploaded"] == 3
    names = {i["name"] for i in r.json()["images"]}
    with SessionLocal() as db:
        rows = db.scalars(
            select(Image).where(
                Image.project_id == project["id"], Image.name.in_(names)
            )
        ).all()
        stored = {
            row.name: quality.classify(row.sharpness, row.luminance) for row in rows
        }
    assert stored == {"sharp.jpg": "ok", "blurry.jpg": "blurry", "dark.jpg": "dark"}


def test_quality_filter_returns_only_matching_rows(c, project):
    pid = project["id"]
    expected = {
        "blurry": add_row(pid, "q-blurry", quality.BLUR_FLOOR / 2, 0.5),
        "dark": add_row(pid, "q-dark", 0.5, quality.DARK_MEAN / 2),
        "ok": add_row(pid, "q-ok", 0.5, 0.5),
        "unknown": add_row(pid, "q-unknown", None, None),
    }
    for kind, image_id in expected.items():
        found = listed(c, project, quality=kind)
        assert image_id in found, kind
        with SessionLocal() as db:
            rows = db.scalars(select(Image).where(Image.id.in_(found))).all()
        # every row the API returned classifies as the requested bucket, NULL scores included
        assert {quality.classify(r.sharpness, r.luminance) for r in rows} == {kind}
    assert (
        c.get(
            f"/api/ws/{WS}/projects/{project['slug']}/images",
            params={"quality": "gorgeous"},
        ).status_code
        == 400
    )


def test_filter_reads_the_stored_score_not_the_pixels(c, project):
    image_id = add_row(project["id"], "q-flip", quality.BLUR_FLOOR / 2, 0.5)
    assert image_id in listed(c, project, quality="blurry")
    with SessionLocal() as db:
        db.get(Image, image_id).sharpness = 1.0
        db.commit()
    assert image_id not in listed(c, project, quality="blurry")
    assert image_id in listed(c, project, quality="ok")


def test_quality_filter_respects_the_workspace(c, project, other_world):
    mine = add_row(project["id"], "q-ws-mine", quality.BLUR_FLOOR / 2, 0.5)
    theirs = add_row(other_world["pid"], "q-other-blurry", quality.BLUR_FLOOR / 2, 0.5)

    found = listed(c, project, quality="blurry")
    assert mine in found
    assert theirs not in found

    other = TestClient(app)
    other.headers["Authorization"] = f"Bearer {other_world['token']}"
    r = other.get(
        f"/api/ws/{other_world['ws']}/projects/quality-other/images",
        params={"quality": "blurry"},
    )
    assert r.status_code == 200, r.text
    assert [i["id"] for i in r.json()["items"]] == [theirs]


def test_health_payload_exposes_counts_samples_and_links(c, project):
    pid = project["id"]
    blurry = [
        add_row(pid, f"q-sample-{i}", quality.BLUR_FLOOR / 2, 0.5) for i in range(3)
    ]
    with SessionLocal() as db:
        p = db.get(Project, pid)
        checks = health.checks(db, p, auto_scan=False)
    payload = checks["quality"]
    assert payload["counts"]["blurry"] >= 3
    assert set(payload["counts"]) == {"blurry", "dark", "ok", "unknown"}
    assert payload["counts"]["unknown"] >= 1  # pre-existing rows with no scores
    assert set(payload["samples"]["blurry"]) >= set(blurry)
    assert len(payload["samples"]["blurry"]) <= quality.SAMPLE

    recs = {r["key"]: r for r in health.recommendations(checks)}
    assert "blurry" in recs["quality_blurry"]["message"].lower()
    assert recs["quality_blurry"]["suggest"] == {"quality": "blurry"}
    assert "dark" in recs["quality_dark"]["message"].lower()
    assert recs["quality_dark"]["suggest"] == {"quality": "dark"}


def test_analytics_exposes_the_quality_card(c, project):
    r = c.get(f"/api/ws/{WS}/projects/{project['slug']}/analytics")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "quality" in body["checks"]
    assert isinstance(body["checks"]["quality"]["counts"]["blurry"], int)


def write_test_video(rel: str, frames: int = 4) -> None:
    """A tiny MJPG clip whose frames are visibly sharp, so a score must land in `ok`."""
    path = DATA_DIR / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"MJPG"), 5.0, (320, 240)
    )
    assert writer.isOpened()
    for i in range(frames):
        im = textured(seed=20 + i, size=(320, 240))
        writer.write(cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR))
    writer.release()


def test_video_extracted_frames_get_a_quality_score(c, other_world):
    """Frames become images outside ingest(); they must still carry a score, never stay 'unknown'."""
    tag = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == other_world["ws"]))
        p = Project(
            workspace_id=ws.id, slug=f"quality-video-{tag}", name="Quality video"
        )
        db.add(p)
        db.flush()
        rel = f"quality/video-{tag}.avi"
        write_test_video(rel)
        v = Video(
            project_id=p.id,
            workspace_id=ws.id,
            name="quality clip",
            path=rel,
            status="queued",
        )
        db.add(v)
        db.flush()
        job = Job(
            workspace_id=ws.id,
            project_id=p.id,
            kind="extract_frames",
            params={"video_id": v.id, "mode": "fps", "target_fps": 5.0},
        )
        db.add(job)
        db.commit()
        pid, vid, job_id = p.id, v.id, job.id
        assert quality.summary(db, p)["counts"]["unknown"] == 0  # no rows yet

    with SessionLocal() as db:
        worker.run_extract_frames(db.get(Job, job_id))

    with SessionLocal() as db:
        frames = db.scalars(select(Image).where(Image.video_id == vid)).all()
        assert len(frames) == 4
        assert all(f.sharpness is not None and f.luminance is not None for f in frames)
        assert {quality.classify(f.sharpness, f.luminance) for f in frames} == {"ok"}
        counts = quality.summary(db, db.get(Project, pid))["counts"]
    assert counts == {"blurry": 0, "dark": 0, "ok": 4, "unknown": 0}
