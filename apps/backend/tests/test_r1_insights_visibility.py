"""R1 / I15: version-diff signs a thumbnail per image, so it stays behind project.review."""

import json
import os
import uuid

os.environ.setdefault("LD_WORKER_TOKEN", "test-worker-token-0123456789abcdef")
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import DATA_DIR
from app.db import SessionLocal
from app.main import app
from app.models import Image, Project, ProjectMember, User, Version, Workspace

WS = "labeldesk-demo"


def _login(email, pw="demo1234"):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return c


@pytest.fixture(scope="module")
def case():
    """A project with two real versions whose manifests put one held-out image in the diff."""
    with TestClient(app):
        slug = f"r1-visibility-{uuid.uuid4().hex[:8]}"
        with SessionLocal() as db:
            ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
            p = Project(workspace_id=ws.id, slug=slug, name=slug, type="object-detection", settings={})
            db.add(p)
            db.flush()
            labeler = db.scalar(select(User).where(User.email == "labeler@labeldesk.dev"))
            reviewer = db.scalar(select(User).where(User.email == "reviewer@labeldesk.dev"))
            db.add_all(
                [
                    ProjectMember(project_id=p.id, user_id=labeler.id, role="labeler"),
                    ProjectMember(project_id=p.id, user_id=reviewer.id, role="reviewer"),
                ]
            )
            # Assigned to another labeler and held out in the test split: the exact image a
            # project labeler must not receive a signed thumbnail for.
            img = Image(
                project_id=p.id,
                name="held-out.jpg",
                sha256="a" * 64,
                width=32,
                height=32,
                path="r1-visibility/held-out.jpg",
                thumb="r1-visibility/held-out.jpg",
                split="test",
                status="done",
                assignee_id=reviewer.id,
            )
            db.add(img)
            db.flush()
            base = Version(project_id=p.id, number=1, name="base", status="ready",
                           stats={"splits": {}, "classes": {}})
            target = Version(project_id=p.id, number=2, name="target", status="ready",
                             stats={"splits": {"test": 1}, "classes": {"person": 1}})
            db.add_all([base, target])
            db.flush()
            ids = {"base": base.id, "target": target.id, "image": img.id}
            db.commit()
        for vid, items in (
            (ids["base"], []),
            (ids["target"], [{"file": "test/held-out.jpg", "split": "test", "source": ids["image"],
                              "width": 32, "height": 32}]),
        ):
            d = DATA_DIR / "versions" / vid
            d.mkdir(parents=True, exist_ok=True)
            (d / "manifest.json").write_text(json.dumps({"items": items, "version_hash": f"hash-{vid}"}))
        yield {"slug": slug, "project": p.id, **ids}
        from sqlalchemy import delete as sa_delete
        with SessionLocal() as db:
            db.execute(sa_delete(ProjectMember).where(ProjectMember.project_id == p.id))
            db.execute(sa_delete(Image).where(Image.project_id == p.id))
            db.execute(sa_delete(Version).where(Version.project_id == p.id))
            db.execute(sa_delete(Project).where(Project.id == p.id))
            db.commit()
        import shutil
        for vid in (ids["base"], ids["target"]):
            shutil.rmtree(DATA_DIR / "versions" / vid, ignore_errors=True)


def _diff(c, case):
    return c.get(
        f"/api/ws/{WS}/projects/{case['slug']}/insights/version-diff",
        params={"base": case["base"], "target": case["target"]},
    )


def test_labeler_cannot_read_version_diff_thumbnails(case):
    r = _diff(_login("labeler@labeldesk.dev"), case)
    assert r.status_code == 403, r.text


def test_reviewer_and_manager_can_read_version_diff(case):
    r = _diff(_login("reviewer@labeldesk.dev"), case)
    assert r.status_code == 200, r.text
    added = r.json()["added"]
    assert [x["image_id"] for x in added] == [case["image"]]
    assert added[0]["split"] == "test"
    assert added[0]["thumb"].startswith("/api/files/")  # the payload the labeler must not get

    assert _diff(_login("demo@labeldesk.dev"), case).status_code == 200
