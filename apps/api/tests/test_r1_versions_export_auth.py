"""I14: a signed export URL is a download grant, not something every project reader gets."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Job, Member, Project, ProjectMember, User, Version, Workspace
from app.security import hash_password

DEMO = "longpassword1"


def _login(email: str, pw: str = DEMO):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return c


@pytest.fixture(scope="module")
def world():
    """A project with one ready version and a finished coco export, viewed by four roles."""
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        owner = User(id="u" + uuid.uuid4().hex[:12], email=f"vex-owner-{suffix}@x.io", name="Owen Owner",
                     pw_hash=hash_password(DEMO), email_verified=1.0)
        db.add(owner); db.flush()
        ws = Workspace(id="w" + suffix, slug=f"vex-{suffix}", name="Export auth ws", owner_id=owner.id)
        db.add(ws); db.flush()
        p = Project(workspace_id=ws.id, slug=f"vexp-{suffix}", name="Export auth project")
        db.add(p); db.flush()
        v = Version(project_id=p.id, number=1, status="ready", stats={})
        db.add(v); db.flush()
        j = Job(workspace_id=ws.id, project_id=p.id, kind="export", status="done",
                params={"version_id": v.id, "format": "coco"}, result={"file": f"exports/{v.id}/coco.zip"})
        db.add(j); db.flush()
        emails = {}
        for key, role in (("viewer", "viewer"), ("labeler", "labeler"),
                          ("manager", "manager"), ("reviewer", "reviewer")):
            u = User(id="u" + uuid.uuid4().hex[:12], email=f"{key}-{suffix}@x.io", name=key.title(),
                     pw_hash=hash_password(DEMO), email_verified=1.0)
            db.add(u); db.flush()
            db.add(Member(workspace_id=ws.id, user_id=u.id, role="member"))
            db.add(ProjectMember(project_id=p.id, user_id=u.id, role=role))
            emails[key] = u.email
        db.commit()
        out = {"base": f"/api/ws/{ws.slug}/projects/{p.slug}", "version": v.id, "job": j.id,
               "emails": emails}
    return out


def _export_row(client: TestClient, base: str, vid: str, detail: bool, signed: bool) -> dict:
    path = f"{base}/versions/{vid}" if detail else f"{base}/versions"
    r = client.get(path)
    assert r.status_code == 200, r.text
    if signed:
        assert f"/api/files/exports/{vid}/" in r.text, r.text
    else:
        assert "/api/files/" not in r.text, r.text    # no signed path anywhere in the payload
    body = r.json()
    row = body if detail else next(v for v in body if v["id"] == vid)
    return row["exports"]["coco"]


@pytest.mark.parametrize("who", ["viewer", "labeler"])
def test_restricted_roles_read_versions_without_an_export_url(world, who):
    base, vid = world["base"], world["version"]
    with _login(world["emails"][who]) as c:
        for detail in (False, True):
            exp = _export_row(c, base, vid, detail, signed=False)
            assert exp["id"] == world["job"] and exp["status"] == "done"   # metadata stays readable
            assert exp.get("url") is None, exp


@pytest.mark.parametrize("who", ["manager", "reviewer"])
def test_export_roles_still_get_the_signed_url(world, who):
    base, vid = world["base"], world["version"]
    with _login(world["emails"][who]) as c:
        for detail in (False, True):
            exp = _export_row(c, base, vid, detail, signed=True)
            assert exp["url"].startswith(f"/api/files/exports/{vid}/coco.zip?"), exp
