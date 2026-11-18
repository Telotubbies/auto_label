"""T-035 — the anonymous public dataset payload and its sample thumbnails.

The public surface must never reveal more than a published project: every miss (private,
deleted, unpublished, flag off, foreign image) is the same 404 with no hint of existence,
and the bytes route serves the cached thumbnail, never the stored original.
"""
import io
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import select

from app import ratelimit
from app.config import DATA_DIR
from app.db import SessionLocal
from app.main import app
from app.models import Image, LabelClass, Project, User, Workspace, WorkspaceFlag, Member, set_annotations

WS = "public-dataset"
FLAG = "task_a1_public_page"
BASE = f"/api/public/datasets/{WS}"


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module", autouse=True)
def _workspace():
    """One throwaway workspace with the public-page flag on for its lifetime."""
    with SessionLocal() as db:
        u = User(email="public-dataset@test.local", name="Public Dataset", pw_hash="",
                 email_verified=time.time())
        db.add(u)
        db.flush()
        ws = Workspace(slug=WS, name="Public Test", owner_id=u.id)
        db.add(ws)
        db.flush()
        db.add(Member(workspace_id=ws.id, user_id=u.id, role="admin"))
        db.add(WorkspaceFlag(workspace_id=ws.id, key=FLAG, enabled=True))
        db.commit()
    yield
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        if ws is not None:
            db.delete(ws)
            db.commit()


def _write(rel: str, im: PImage.Image) -> None:
    path = DATA_DIR / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, "JPEG", quality=90)


def _image(db, project: Project, name: str, colour: tuple[int, int, int],
           labels: list[str] | None = None) -> Image:
    """A real original plus the cached thumbnail ingest would have written."""
    stem = f"{project.id}/{uuid.uuid4().hex[:10]}"
    original = PImage.new("RGB", (1024, 768), colour)
    rel = f"projects/{stem}.jpg"
    thumb = f"projects/{stem}/thumbs/{stem.rsplit('/', 1)[-1]}.jpg"
    _write(rel, original)
    small = original.copy()
    small.thumbnail((480, 480))
    _write(thumb, small)
    row = Image(project_id=project.id, name=name, sha256=uuid.uuid4().hex * 2,
                width=1024, height=768, path=rel, thumb=thumb)
    db.add(row)
    db.flush()
    set_annotations(db, row, [{"classId": cid} for cid in labels or []])
    return row


def _project(*, public: bool = True, with_images: int = 0) -> dict:
    """A project, its two classes and (optionally) real samples. Returns ids the test needs."""
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        p = Project(workspace_id=ws.id, slug=f"public-{uuid.uuid4().hex[:8]}",
                    name="PPE Detection", type="object-detection",
                    description="Helmets and vests on a factory floor.",
                    visibility="public" if public else "private", license="CC BY 4.0")
        db.add(p)
        db.flush()
        helmet = LabelClass(project_id=p.id, name="helmet")
        vest = LabelClass(project_id=p.id, name="vest")
        db.add_all([helmet, vest])
        db.flush()
        samples = []
        for i in range(with_images):
            class_ids = [helmet.id, helmet.id] if i == 0 else [vest.id]
            samples.append(_image(db, p, f"sample-{i}.jpg", (20 + i, 60, 90), class_ids))
        db.commit()
        return {"id": p.id, "slug": p.slug, "name": p.name, "created": p.created,
                "helmet": helmet.id, "vest": vest.id,
                "samples": [{"id": s.id, "path": s.path, "thumb": s.thumb} for s in samples]}


def _set_flag(enabled: bool) -> None:
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        row = db.get(WorkspaceFlag, (ws.id, FLAG))
        row.enabled = enabled
        db.commit()


def test_public_project_payload_shape(c):
    p = _project(with_images=13)

    r = c.get(f"{BASE}/{p['slug']}")

    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"name", "description", "type", "workspace", "license", "images",
                         "classes", "citation", "samples"}
    assert body["name"] == "PPE Detection"
    assert body["description"] == "Helmets and vests on a factory floor."
    assert body["type"] == "object-detection"
    assert body["workspace"] == "Public Test"
    assert body["license"] == "CC BY 4.0"
    assert body["images"] == 13
    assert {(x["name"], x["count"]) for x in body["classes"]} == {("helmet", 2), ("vest", 12)}
    assert len(body["samples"]) == 12
    assert all(set(s) == {"id", "width", "height", "url"} for s in body["samples"])
    assert body["samples"][0]["url"] == f"{BASE}/{p['slug']}/images/{body['samples'][0]['id']}"
    assert body["citation"].startswith("PPE Detection · Public Test · ")
    assert body["citation"].endswith(" · CC BY 4.0")


def test_empty_dataset_still_has_metadata(c):
    p = _project(with_images=0)

    body = c.get(f"{BASE}/{p['slug']}").json()

    assert body["images"] == 0 and body["samples"] == []
    assert body["description"] and body["license"] and body["classes"]


def test_private_project_is_404_for_payload_and_image(c):
    private = _project(public=False, with_images=1)
    public = _project(with_images=1)

    payload = c.get(f"{BASE}/{private['slug']}")
    image = c.get(f"{BASE}/{public['slug']}/images/{private['samples'][0]['id']}")

    assert payload.status_code == 404
    assert image.status_code == 404
    # The refusal must not say the project exists but is private.
    assert "private" not in payload.text.lower()
    assert "private" not in image.text.lower()


def test_deleted_image_is_404(c):
    p = _project(with_images=1)
    image_id = p["samples"][0]["id"]
    with SessionLocal() as db:
        db.get(Image, image_id).deleted_at = time.time()
        db.commit()

    assert c.get(f"{BASE}/{p['slug']}/images/{image_id}").status_code == 404
    assert c.get(f"{BASE}/{p['slug']}").status_code == 200


def test_image_from_another_project_is_404(c):
    mine = _project(with_images=1)
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == "public-dataset@test.local"))
        other = Workspace(slug=f"other-{uuid.uuid4().hex[:8]}", name="Other", owner_id=owner.id)
        db.add(other)
        db.flush()
        foreign = Project(workspace_id=other.id, slug="foreign", name="Foreign",
                          visibility="public", license="CC BY 4.0")
        db.add(foreign)
        db.flush()
        foreign_image = _image(db, foreign, "theirs.jpg", (1, 2, 3))
        db.commit()
        foreign_id, other_slug = foreign_image.id, other.slug

    assert c.get(f"{BASE}/{mine['slug']}/images/{foreign_id}").status_code == 404
    assert c.get(f"/api/public/datasets/{other_slug}/foreign/images/{mine['samples'][0]['id']}").status_code == 404


def test_unpublish_hides_the_page_immediately(c):
    p = _project(with_images=1)
    image_url = f"{BASE}/{p['slug']}/images/{p['samples'][0]['id']}"
    assert c.get(f"{BASE}/{p['slug']}").status_code == 200
    with SessionLocal() as db:
        db.get(Project, p["id"]).visibility = "private"   # T-033's unpublish
        db.commit()

    assert c.get(f"{BASE}/{p['slug']}").status_code == 404
    assert c.get(image_url).status_code == 404


def test_original_bytes_are_not_served(c):
    p = _project(with_images=1)
    s = p["samples"][0]

    r = c.get(f"{BASE}/{p['slug']}/images/{s['id']}")

    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("image/")
    assert r.headers["cache-control"] == "public, max-age=3600"
    served = PImage.open(io.BytesIO(r.content))
    assert max(served.size) <= 512
    assert r.content != (DATA_DIR / s["path"]).read_bytes()


def test_rate_limit_returns_429(c):
    p = _project(with_images=1)
    url = f"{BASE}/{p['slug']}/images/{p['samples'][0]['id']}"
    was = ratelimit.ENABLED
    ratelimit.ENABLED = True
    ratelimit._hits.clear()
    try:
        assert c.get(url).status_code == 200
        # 121 real round trips can outlast the 60 s window on this harness, so drive the same
        # limiter key for the other 119 hits of the minute; the 121st is still a real request.
        (key,) = ratelimit._hits
        for _ in range(119):
            ratelimit.limit(key, 120, 60)
        last = c.get(url)
    finally:
        ratelimit.ENABLED = was
    assert last.status_code == 429
    assert last.json()["detail"] == "Too many requests — try again shortly."


def test_flag_off_is_404(c):
    p = _project(with_images=1)
    image_url = f"{BASE}/{p['slug']}/images/{p['samples'][0]['id']}"
    _set_flag(False)
    try:
        assert c.get(f"{BASE}/{p['slug']}").status_code == 404
        assert c.get(image_url).status_code == 404
    finally:
        _set_flag(True)
    assert c.get(f"{BASE}/{p['slug']}").status_code == 200
