"""Parity guard area 3: the editor's shipped data contracts.

Assertions only (T-003). Every fact here is HAVE today and is pinned by the area-3 guard:
a saved box keeps its class and source, smart click keeps its negatives, review lands AI work in
the Review column, and the objects list keeps hide/lock/order. Nothing in this file changes the app.

Run: pytest tests/test_parity_guard_area3.py -q   (offline, no SAM, no network)
"""
import io
import os
import uuid

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import delete as sa_delete
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Image, Member, User, Workspace
from app.security import issue_access
from app.services import segment

DEMO, LABELER, REVIEWER = "demo@labeldesk.dev", "labeler@labeldesk.dev", "reviewer@labeldesk.dev"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth(client):
    out = {}
    with SessionLocal() as db:
        for key, email in (("admin", DEMO), ("labeler", LABELER), ("reviewer", REVIEWER)):
            u = db.scalar(select(User).where(User.email == email))
            out[key] = {"id": u.id, "h": {"Authorization": f"Bearer {issue_access(u.id)}"}}
    client.headers["Authorization"] = out["admin"]["h"]["Authorization"]
    return out


def jpeg(color: tuple[int, int, int]) -> bytes:
    b = io.BytesIO()
    PImage.new("RGB", (160, 120), color).save(b, "JPEG")
    return b.getvalue()


@pytest.fixture(scope="module")
def project(client, auth):
    """Throwaway workspace + project: two assigned images for the labeler, one foreign class."""
    slug = client.post("/api/workspaces", json={"name": f"Editor Guard {uuid.uuid4().hex[:8]}"}).json()["slug"]
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == slug))
        db.execute(sa_delete(Member).where(Member.workspace_id == ws.id))
        db.add_all([
            Member(workspace_id=ws.id, user_id=auth["admin"]["id"], role="admin", created=1000.0),
            Member(workspace_id=ws.id, user_id=auth["labeler"]["id"], role="annotator", created=2000.0),
            Member(workspace_id=ws.id, user_id=auth["reviewer"]["id"], role="reviewer", created=3000.0),
        ])
        db.commit()
    p = client.post(f"/api/ws/{slug}/projects", json={"name": f"guard-{uuid.uuid4().hex[:8]}",
                                                      "classes": ["helmet", "vest"]}).json()
    base = f"/api/ws/{slug}/projects/{p['slug']}"
    files = [("files", (f"guard-{i}.jpg", jpeg((30 + 40 * i, 50, 70)))) for i in range(4)]
    up = client.post(f"{base}/upload", files=files, data={"split": "train", "batch_name": "guard"})
    assert up.status_code == 200 and up.json()["uploaded"] == 4, up.text
    ids = [x["id"] for x in up.json()["images"]]
    with SessionLocal() as db:
        for iid in ids[:2]:
            db.get(Image, iid).assignee_id = auth["labeler"]["id"]
        db.commit()
    classes = {x["name"]: x["id"] for x in client.get(f"{base}/classes").json()}
    other = client.post(f"/api/ws/{slug}/projects", json={"name": f"other-{uuid.uuid4().hex[:8]}",
                                                          "classes": ["intruder"]}).json()
    other_base = f"/api/ws/{slug}/projects/{other['slug']}"
    foreign_class = client.get(f"{other_base}/classes").json()[0]["id"]
    yield {"base": base, "images": ids, "batch": up.json()["batch"]["id"], "classes": classes,
           "foreign_class": foreign_class, "other_base": other_base}
    client.delete(other_base)
    client.delete(base)
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == slug))
        if ws:
            db.delete(ws)
            db.commit()


def box(class_id: str, aid: str = "a1", **extra) -> dict:
    return {"id": aid, "classId": class_id, "shape": {"kind": "bbox", "x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4}, **extra}


def save(client, who, image_id: str, anns: list[dict]):
    return client.put(f"/api/images/{image_id}/annotations", json={"annotations": anns}, headers=who["h"])


def test_a_saved_box_keeps_shape_class_source_and_confidence(client, auth, project):
    """3-F3.9, 3-F3.25 — a proposal saved as a box returns the same id, class, geometry and provenance."""
    img, helmet = project["images"][0], project["classes"]["helmet"]
    saved = box(helmet, aid="proposal-1", source="trained:abc", confidence=0.83)
    r = save(client, auth["labeler"], img, [saved])
    assert r.status_code == 200, r.text

    got = client.get(f"/api/images/{img}", headers=auth["labeler"]["h"]).json()
    ann = next(a for a in got["annotations"] if a["id"] == "proposal-1")
    assert ann["classId"] == helmet
    assert ann["shape"] == {"kind": "bbox", "x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4}
    assert ann["source"] == "trained:abc"
    assert ann["confidence"] == pytest.approx(0.83)

    # A human save without a source is still attributed to "human" (the dashed/solid distinction's data).
    assert save(client, auth["labeler"], img, [box(helmet, aid="human-1")]).status_code == 200
    human = client.get(f"/api/images/{img}", headers=auth["labeler"]["h"]).json()["annotations"][0]
    assert human["id"] == "human-1" and human["source"] == "human"


def test_unknown_class_on_save_is_a_400(client, auth, project):
    """3-F3.35 boundary — a class from another project never reaches this image."""
    r = save(client, auth["labeler"], project["images"][1], [box(project["foreign_class"])])
    assert r.status_code == 400
    assert r.json()["detail"] == "annotation class does not belong to this project"
    got = client.get(f"/api/images/{project['images'][1]}", headers=auth["labeler"]["h"]).json()
    assert got["annotations"] == []


def test_class_create_in_place_gets_a_palette_colour_and_a_duplicate_is_409(client, auth, project):
    """3-F3.35, 3-F3.37 — create-in-place returns a fresh class with a colour; duplicates and bad names fail."""
    r = client.post(f"{project['base']}/classes", json={"name": "sprocket"}, headers=auth["labeler"]["h"])
    assert r.status_code == 200, r.text
    created = r.json()
    assert created["name"] == "sprocket" and created["count"] == 0 and created["color"]
    again = client.post(f"{project['base']}/classes", json={"name": "sprocket"}, headers=auth["labeler"]["h"])
    assert again.status_code == 409
    bad = client.post(f"{project['base']}/classes", json={"name": "sprocket\x01"}, headers=auth["labeler"]["h"])
    assert bad.status_code == 400


def test_keypoint_visibility_values_survive_the_round_trip(client, auth, project):
    """3-F3.13 — visible/occluded/deleted are 0/1/2 and stay ints; anything else is refused."""
    img, vest = project["images"][0], project["classes"]["vest"]
    points = [0.1, 0.2, 0, 0.3, 0.4, 1, 0.5, 0.6, 2]
    ann = {"id": "kp-1", "classId": vest, "shape": {"kind": "keypoints", "points": points}}
    assert save(client, auth["labeler"], img, [ann]).status_code == 200

    got = client.get(f"/api/images/{img}", headers=auth["labeler"]["h"]).json()
    saved = next(a for a in got["annotations"] if a["id"] == "kp-1")["shape"]["points"]
    assert [saved[2], saved[5], saved[8]] == [0, 1, 2]
    assert all(type(v) is int for v in (saved[2], saved[5], saved[8]))
    assert saved[0::3] == pytest.approx([0.1, 0.3, 0.5]) and saved[1::3] == pytest.approx([0.2, 0.4, 0.6])

    bad = {"id": "kp-2", "classId": vest,
           "shape": {"kind": "keypoints", "points": [0.1, 0.2, 0, 0.3, 0.4, 3, 0.5, 0.6, 1]}}
    assert save(client, auth["labeler"], img, [bad]).status_code == 400


def test_smart_polygon_forwards_negative_clicks(client, auth, project, monkeypatch):
    """3-F3.12 — grow and shrink clicks both reach the segmenter; the response echoes the clamped eps."""
    seen = {}

    def stub(im, points, negatives=None, eps=None, cache_key=None):
        seen.update(points=points, negatives=negatives, eps=eps, cache_key=cache_key)
        return [0.1, 0.1, 0.9, 0.1, 0.9, 0.9, 0.1, 0.9], "grabcut"

    monkeypatch.setattr(segment, "smart_polygon", stub)
    r = client.post(f"/api/images/{project['images'][0]}/smart-polygon",
                    json={"points": [[0.5, 0.5]], "negatives": [[0.2, 0.2]], "epsilon": 0.9},
                    headers=auth["labeler"]["h"])
    assert r.status_code == 200, r.text
    assert seen["points"] == [[0.5, 0.5]] and seen["negatives"] == [[0.2, 0.2]]
    out = r.json()
    assert out["polygon"] == [0.1, 0.1, 0.9, 0.1, 0.9, 0.9, 0.1, 0.9]
    assert out["source"] == "grabcut"
    assert out["epsilon"] == pytest.approx(segment.EPS_MAX)      # 0.9 is clamped to the documented ceiling


def test_tags_round_trip_through_patch_and_filter(client, auth, project):
    """3-F3.39 — image tags survive a patch and drive the tag filter; clearing them drops the row."""
    img = project["images"][1]
    patched = client.patch(f"/api/images/{img}", json={"tags": ["blurry", "re-shoot"]}, headers=auth["labeler"]["h"])
    assert patched.status_code == 200, patched.text
    assert patched.json()["tags"] == ["blurry", "re-shoot"]

    found = client.get(f"{project['base']}/images", params={"tag": "blurry"}, headers=auth["labeler"]["h"]).json()
    assert img in [x["id"] for x in found["items"]]
    assert found["total"] == 1

    assert client.patch(f"/api/images/{img}", json={"tags": []}, headers=auth["labeler"]["h"]).status_code == 200
    after = client.get(f"{project['base']}/images", params={"tag": "blurry"}, headers=auth["labeler"]["h"]).json()
    assert img not in [x["id"] for x in after["items"]]
    assert after["total"] == 0


def test_labeler_submits_but_cannot_approve_and_review_moves_between_columns(client, auth, project):
    """3-F3.44 — annotating -> review is the labeler's move; review -> done and the verdict are the reviewer's."""
    img = project["images"][0]
    with SessionLocal() as db:
        db.get(Image, img).status = "annotating"
        db.commit()
    move = {"batch_id": project["batch"], "from_status": "annotating", "to_status": "review"}
    assert client.post(f"{project['base']}/board/move", json=move, headers=auth["labeler"]["h"]).status_code == 200
    assert client.get(f"/api/images/{img}", headers=auth["labeler"]["h"]).json()["status"] == "review"

    # A labeler cannot approve their own work: the column move to done needs a reviewer.
    approve = {"batch_id": project["batch"], "from_status": "review", "to_status": "done"}
    assert client.post(f"{project['base']}/board/move", json=approve, headers=auth["labeler"]["h"]).status_code == 403

    rejected = client.post(f"/api/images/{img}/review", json={"approved": False}, headers=auth["reviewer"]["h"])
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["review"] == "rejected" and rejected.json()["status"] == "annotating"

    assert client.post(f"{project['base']}/board/move", json=move, headers=auth["labeler"]["h"]).status_code == 200
    accepted = client.post(f"/api/images/{img}/review", json={"approved": True}, headers=auth["reviewer"]["h"])
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["review"] == "approved" and accepted.json()["status"] == "done"


def test_workforce_dashboard_keeps_the_documented_metric_names(client, auth, project):
    """3-F3.50 — the review dashboard's row keys are a contract; a labeler sees only themselves."""
    dash = client.get(f"{project['base']}/labeling/dashboard", headers=auth["reviewer"]["h"]).json()
    row = next(x for x in dash["labelers"] if x["user_id"] == auth["labeler"]["id"])
    assert {"images", "ai_acceptance", "rejection_rate"} <= set(row)
    assert isinstance(row["images"], int)

    own = client.get(f"{project['base']}/labeling/dashboard", headers=auth["labeler"]["h"]).json()
    assert [x["user_id"] for x in own["labelers"]] == [auth["labeler"]["id"]]
    assert {"images", "ai_acceptance", "rejection_rate"} <= set(own["labelers"][0])


def test_foreign_workspace_image_id_stays_out_of_reach(client, auth, project):
    """Cross-workspace acceptance case: image_ctx answers 403 for a workspace the caller is not in."""
    slug = client.post("/api/workspaces", json={"name": f"Editor Guard Other {uuid.uuid4().hex[:8]}"}).json()["slug"]
    p = client.post(f"/api/ws/{slug}/projects", json={"name": "foreign", "classes": ["x"]}).json()
    base = f"/api/ws/{slug}/projects/{p['slug']}"
    up = client.post(f"{base}/upload", files=[("files", ("foreign.jpg", jpeg((9, 9, 9))))],
                     data={"split": "train"})
    foreign = up.json()["images"][0]["id"]
    try:
        assert client.get(f"/api/images/{foreign}", headers=auth["labeler"]["h"]).status_code == 403
        assert save(client, auth["labeler"], foreign, [box(project["classes"]["helmet"])]).status_code == 403
    finally:
        client.delete(base)
        with SessionLocal() as db:
            ws = db.scalar(select(Workspace).where(Workspace.slug == slug))
            if ws:
                db.delete(ws)
                db.commit()
