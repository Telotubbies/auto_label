"""T-990: the key-authenticated surface an agent drives the label loop with.

Read a project, search its images, read one image's annotations, replace them. Every call uses a
workspace API key, so the permission model is the key's scopes and the tenancy rule is the key's
workspace — there is no second permission system to keep in step.
"""
import io
import os

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import API_SCOPES, Image, LabelClass, LabelEvent, Member, Project, User, Workspace
from app.security import issue_access
from conftest import login as shared_login

DEMO_WS, PR = "labeldesk-demo", "ppe-detection"     # read-only use: the seeded demo project
LAB_WS = "devapi-labels-lab"                        # this module's workspace, so the demo plan quota stays put
OTHER_WS = "devapi-labels-other"
SURFACE, FOREIGN, EMPTY = "agent-surface", "agent-foreign", "agent-blank"


@pytest.fixture(scope="module")
def admin():
    """The seeded demo admin: the card's read of `ppe-detection` and the workspace flag live here."""
    with TestClient(app) as c:
        c.headers.update(shared_login(c))
        yield c


def _workspace(slug: str, email: str) -> tuple[str, Workspace]:
    with SessionLocal() as db:
        owner = User(email=email, name=slug, pw_hash="")
        db.add(owner)
        db.flush()
        ws = Workspace(slug=slug, name=slug, owner_id=owner.id)
        db.add(ws)
        db.flush()
        db.add(Member(workspace_id=ws.id, user_id=owner.id, role="admin"))
        db.commit()
        return owner.id, ws


@pytest.fixture(scope="module")
def lab():
    """This module's own workspace with three projects, so no demo-workspace row or plan quota moves."""
    uid, ws = _workspace(LAB_WS, "devapi-lab@test.local")
    with SessionLocal() as db:
        surface = Project(workspace_id=ws.id, slug=SURFACE, name="Agent surface", settings={})
        foreign = Project(workspace_id=ws.id, slug=FOREIGN, name="Agent foreign", settings={})
        blank = Project(workspace_id=ws.id, slug=EMPTY, name="Agent blank", settings={})
        db.add_all([surface, foreign, blank])
        db.flush()
        db.add_all([LabelClass(project_id=surface.id, name="helmet", color="#22c55e"),
                    LabelClass(project_id=surface.id, name="vest", color="#3b82f6"),
                    LabelClass(project_id=foreign.id, name="forklift", color="#f97316")])
        db.commit()
        foreign_class = db.scalar(select(LabelClass.id).where(LabelClass.project_id == foreign.id))
    h = {"Authorization": f"Bearer {issue_access(uid)}"}
    c = TestClient(app)
    c.headers.update(h)
    return {"c": c, "h": h, "uid": uid, "foreignClassId": foreign_class}


@pytest.fixture(scope="module")
def other_world():
    """A second workspace, so isolation is exercised rather than assumed."""
    _, ws = _workspace(OTHER_WS, "devapi-other@test.local")
    with SessionLocal() as db:
        p = Project(workspace_id=ws.id, slug="theirs", name="Theirs", settings={})
        db.add(p)
        db.flush()
        img = Image(project_id=p.id, name="theirs.jpg", sha256="d" * 64, width=10, height=10,
                    path="theirs.jpg", thumb="theirs.jpg", status="unassigned", n_annotations=2)
        db.add(img)
        db.commit()
        return {"image": img.id}


def jpeg(color=(90, 120, 150)):
    b = io.BytesIO()
    PImage.new("RGB", (48, 48), color).save(b, "JPEG")
    return b.getvalue()


def anon():
    """A client with no session: the developer API only ever sees the key."""
    return TestClient(app)


def mint(c, ws, name, **kw):
    r = c.post(f"/api/ws/{ws}/keys", json={"name": name, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def lab_key(lab, name, **kw):
    return mint(lab["c"], LAB_WS, name, **kw)


def auth(key):
    return {"Authorization": f"Bearer {key['key']}"}


def classes_of(lab, slug=SURFACE):
    r = lab["c"].get(f"/api/ws/{LAB_WS}/projects/{slug}")
    assert r.status_code == 200, r.text
    return {x["name"]: x["id"] for x in r.json()["classes"]}


def upload(lab, name, split="train", color=(10, 20, 30)):
    r = lab["c"].post(f"/api/ws/{LAB_WS}/projects/{SURFACE}/upload",
                      files=[("files", (name, jpeg(color)))], data={"split": split})
    assert r.status_code == 200, r.text
    return r.json()["images"][0]


def boxes(class_ids, n=2):
    return [{"id": f"a{i}", "classId": class_ids[i % len(class_ids)],
             "shape": {"kind": "bbox", "x": .1 + .1 * i, "y": .1, "w": .2, "h": .2}}
            for i in range(n)]


# --- 1. read a project --------------------------------------------------------------------------

def test_get_project_carries_class_ids_and_status_counts(admin):
    k = mint(admin, DEMO_WS, "demo-reader", scopes=["read"])
    r = anon().get(f"/api/v1/projects/{PR}", headers=auth(k))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["slug"] == PR and all(x["id"] for x in body["classes"])
    assert body["statusCounts"], "the seeded demo project has images, so its statuses are counted"
    assert "settings" not in body, "a project's settings can carry webhook and connector values"


def test_get_project_empty_state_is_not_404(lab):
    k = lab_key(lab, "blank-reader", scopes=["read"])
    r = anon().get(f"/api/v1/projects/{EMPTY}", headers=auth(k))
    assert r.status_code == 200, r.text
    assert r.json()["classes"] == [] and r.json()["statusCounts"] == {}

    missing = anon().get("/api/v1/projects/nope-nope", headers=auth(k))
    assert missing.status_code == 404 and "project not found" in missing.text
    # a slug from another workspace answers the same way as one that never existed
    assert anon().get("/api/v1/projects/theirs", headers=auth(k)).status_code == 404


# --- 2. search images ---------------------------------------------------------------------------

def test_list_images_filters_like_the_dataset_screen(lab):
    upload(lab, "tile-left-1.jpg", "train", (10, 10, 10))
    upload(lab, "tile-left-2.jpg", "train", (20, 20, 20))
    upload(lab, "tile-right-1.jpg", "valid", (30, 30, 30))

    k = lab_key(lab, "searcher", scopes=["read"])
    base = f"/api/v1/projects/{SURFACE}/images"
    everything = anon().get(base, headers=auth(k)).json()
    assert everything["total"] == 3 and everything["total"] == len(everything["items"])

    valid = anon().get(base, params={"split": "valid"}, headers=auth(k)).json()
    assert [i["name"] for i in valid["items"]] == ["tile-right-1.jpg"] and valid["total"] == 1

    narrowed = anon().get(base, params={"q": "tile-left"}, headers=auth(k)).json()
    assert {i["name"] for i in narrowed["items"]} == {"tile-left-1.jpg", "tile-left-2.jpg"}
    assert narrowed["total"] == 2

    unlabelled = anon().get(base, params={"annotated": "no", "split": "train"}, headers=auth(k)).json()
    assert unlabelled["total"] == 2, "find the unlabelled train images in one call"
    newest = anon().get(base, params={"sort": "newest"}, headers=auth(k)).json()
    assert newest["items"][0]["name"] == "tile-right-1.jpg"


def test_list_images_clamps_the_page_size(admin, lab):
    k = lab_key(lab, "pager", scopes=["read"])
    r = anon().get(f"/api/v1/projects/{SURFACE}/images", params={"limit": 5000}, headers=auth(k))
    assert r.status_code == 200, r.text
    assert len(r.json()["items"]) <= 1000
    demo = mint(admin, DEMO_WS, "demo-pager", scopes=["read"])
    big = anon().get(f"/api/v1/projects/{PR}/images", params={"limit": 5000}, headers=auth(demo))
    assert big.status_code == 200 and len(big.json()["items"]) <= 1000
    blank = anon().get(f"/api/v1/projects/{EMPTY}/images", params={"limit": 5000}, headers=auth(k))
    assert blank.status_code == 200 and blank.json() == {"total": 0, "items": []}


# --- 3. read one image --------------------------------------------------------------------------

def test_get_image_returns_the_annotation_set(lab):
    ids = classes_of(lab)
    img = upload(lab, "read-back.jpg", "train", (40, 40, 40))
    ann = boxes([ids["helmet"], ids["vest"]])
    assert lab["c"].put(f"/api/images/{img['id']}/annotations", json={"annotations": ann}).status_code == 200

    k = lab_key(lab, "image-reader", scopes=["read"])
    r = anon().get(f"/api/v1/images/{img['id']}", headers=auth(k))
    assert r.status_code == 200, r.text
    got = r.json()
    assert [a["classId"] for a in got["annotations"]] == [ids["helmet"], ids["vest"]]
    assert got["id"] == img["id"]

    blank = upload(lab, "read-empty.jpg", "train", (50, 50, 50))
    assert anon().get(f"/api/v1/images/{blank['id']}", headers=auth(k)).json()["annotations"] == []


# --- 4. write one image's annotations -----------------------------------------------------------

def test_write_annotations_saves_and_attributes_the_key_issuer(lab):
    ids = classes_of(lab)
    img = upload(lab, "written-by-key.jpg", "train", (60, 60, 60))
    k = lab_key(lab, "writer", scopes=["read", "write"])
    r = anon().put(f"/api/v1/images/{img['id']}/annotations",
                   json={"annotations": boxes([ids["helmet"], ids["vest"]])}, headers=auth(k))
    assert r.status_code == 200, r.text
    assert r.json() == {"saved": 2, "status": "annotating"}

    with SessionLocal() as db:
        row = db.scalar(select(LabelEvent).where(LabelEvent.image_id == img["id"]))
        assert row is not None, "every label write lands as one LabelEvent"
        assert row.annotations == 2 and row.user_id is not None
        assert row.user_id == lab["uid"], "a key's write is attributed to the key's issuer"
        assert row.project_id == db.get(Image, img["id"]).project_id


def test_write_annotations_rejects_a_foreign_class(lab):
    img = upload(lab, "foreign-class.jpg", "train", (70, 70, 70))
    k = lab_key(lab, "writer-foreign", scopes=["read", "write"])
    bad = [{"id": "a0", "classId": lab["foreignClassId"],
            "shape": {"kind": "bbox", "x": .1, "y": .1, "w": .2, "h": .2}}]
    r = anon().put(f"/api/v1/images/{img['id']}/annotations", json={"annotations": bad}, headers=auth(k))
    assert r.status_code == 400 and "class does not belong to this project" in r.text


def test_write_annotations_rejects_a_bad_shape(lab):
    ids = classes_of(lab)
    img = upload(lab, "bad-shape.jpg", "train", (80, 80, 80))
    k = lab_key(lab, "writer-shape", scopes=["read", "write"])
    bad = [{"id": "a0", "classId": ids["helmet"], "shape": {"kind": "bbox", "x": .1, "y": .1, "w": "wide"}}]
    r = anon().put(f"/api/v1/images/{img['id']}/annotations", json={"annotations": bad}, headers=auth(k))
    assert r.status_code == 400 and "bbox" in r.text


def test_write_annotations_requires_the_write_scope(lab):
    ids = classes_of(lab)
    img = upload(lab, "no-scope.jpg", "train", (90, 90, 90))
    k = lab_key(lab, "no-writer", scopes=["read", "upload"])
    r = anon().put(f"/api/v1/images/{img['id']}/annotations",
                   json={"annotations": boxes(list(ids.values()))}, headers=auth(k))
    assert r.status_code == 403 and "'write'" in r.text


# --- isolation and the scope registry -----------------------------------------------------------

def test_a_foreign_image_is_404_not_403(lab, other_world):
    k = lab_key(lab, "writer-cross", scopes=["read", "write"])
    ids = classes_of(lab)
    r = anon().put(f"/api/v1/images/{other_world['image']}/annotations",
                   json={"annotations": boxes(list(ids.values()))}, headers=auth(k))
    assert r.status_code == 404 and "image not found" in r.text
    assert anon().get(f"/api/v1/images/{other_world['image']}", headers=auth(k)).status_code == 404
    with SessionLocal() as db:
        assert db.get(Image, other_world["image"]).n_annotations == 2, "a foreign write changes nothing"


def test_the_scope_registry_offers_write(lab):
    assert "write" in API_SCOPES
    k = lab_key(lab, "scope-pair", scopes=["read", "write"])
    assert k["scopes"] == ["read", "write"]


def test_whoami_reports_the_mcp_gate(lab):
    k = lab_key(lab, "mcp-gate", scopes=["read"])
    h = auth(k)
    off = anon().get("/api/v1/whoami", headers=h)
    assert off.status_code == 200 and off.json()["mcp"] is False
    assert off.json()["workspace"] == LAB_WS and off.json()["scopes"] == ["read"], "the field is additive"

    assert lab["c"].put(f"/api/ws/{LAB_WS}/flags/task_992", json={"enabled": True}).status_code == 200
    try:
        assert anon().get("/api/v1/whoami", headers=h).json()["mcp"] is True
    finally:
        lab["c"].put(f"/api/ws/{LAB_WS}/flags/task_992", json={"enabled": False})
    assert anon().get("/api/v1/whoami", headers=h).json()["mcp"] is False
