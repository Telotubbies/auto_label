"""Regression tests for the NO_GO review findings I1, I4, I5 and I6.

I1: a user-supplied model_ref must never turn into an arbitrary filesystem path.
I4: honeypot concealment/scoring keys off the effective project role, not the legacy Member.role.
I5: consensus/workforce uses only members who can annotate this project, and a labeler sees only
    their own metrics.
I6: consensus drafts/merges and honeypots reject class ids from another project.
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

from app.adapters import resolve
from app.adapters.ultralytics_ad import _weights_path
from app.db import SessionLocal
from app.main import app
from app.models import (
    ConsensusAssignment,
    ConsensusJob,
    Honeypot,
    Image,
    Member,
    ProjectMember,
    User,
    Workspace,
    set_annotations,
)
from app.security import issue_access


# --- I1: model_ref cannot name an arbitrary local file ------------------------------------

class _NoDb:
    def get(self, *_args):
        return None


@pytest.mark.parametrize("variant", [
    "/tmp/evil",
    "../../../../models/victim/best",
    "..\\..\\models\\victim\\best",
    "C:\\models\\victim\\best",
    "C:evil",
])
def test_weights_path_refuses_paths_outside_pretrained(variant):
    with pytest.raises(ValueError):
        _weights_path(variant, None)


@pytest.mark.parametrize("ref", [
    "ultralytics:/tmp/evil",
    "ultralytics:../../../../models/victim/best",
    "ultralytics:..\\..\\models\\victim\\best",
    "tensorrt:/tmp/evil.engine",
])
def test_resolve_refuses_traversing_model_refs(ref):
    with pytest.raises(ValueError):
        resolve(ref, _NoDb())


def test_resolve_keeps_plain_variants():
    """The guard must not reject the real zoo/classification variants."""
    assert resolve("ultralytics:yolo26n", _NoDb()).variant == "yolo26n"
    assert resolve("ultralytics:yolo26n-cls", _NoDb()).variant == "yolo26n-cls"
    assert resolve("hf:PekingU/rtdetr_v2_r18vd", _NoDb()).variant == "PekingU/rtdetr_v2_r18vd"


def test_playground_reports_traversing_ref_without_loading(client, world, monkeypatch):
    from app.adapters import ultralytics_ad as ul

    calls = []
    monkeypatch.setattr(ul, "_load", lambda weights, cls="YOLO": calls.append(weights))
    r = client.post(f"/api/ws/{world['ws']}/playground/predict",
                    files={"file": ("a.png", png(), "image/png")},
                    data={"model_refs": "ultralytics:../../../../models/victim/best"})
    assert r.status_code == 200, r.text
    res = r.json()["results"][0]
    assert res["prediction"] is None and res["error"]
    assert calls == []                       # the traversal never reaches a model loader


def test_streams_reject_traversing_model_ref(client, world):
    for ref in ("ultralytics:/tmp/evil", "ultralytics:../../models/victim/best"):
        r = client.post(f"{world['base']}/streams",
                        json={"name": "bad", "source": "file:videos/none.mp4", "model_ref": ref})
        assert r.status_code == 400, (ref, r.text)


def test_autolabel_rejects_traversing_model_ref(client, world):
    r = client.post(f"{world['base']}/autolabel",
                    json={"method": "model", "model_ref": "ultralytics:../../models/victim/best"})
    assert r.status_code == 400, r.text


# --- fixtures ----------------------------------------------------------------------------

def png() -> bytes:
    b = io.BytesIO()
    PImage.new("RGB", (32, 32), (7, 7, 7)).save(b, "PNG")
    return b.getvalue()


def jpeg(color: tuple[int, int, int]) -> bytes:
    b = io.BytesIO()
    PImage.new("RGB", (160, 120), color).save(b, "JPEG")
    return b.getvalue()


def box(cls: str, x: float = 0.1, y: float = 0.1, aid: str = "b1") -> dict:
    return {"id": aid, "classId": cls, "shape": {"kind": "bbox", "x": x, "y": y, "w": 0.2, "h": 0.2},
            "source": "human"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        tok = c.post("/api/auth/login", json={"email": "demo@labeldesk.dev", "password": "demo1234"}).json()["token"]
        c.headers["Authorization"] = f"Bearer {tok}"
        yield c


@pytest.fixture(scope="module")
def world(client):
    """A workspace using the current invite model: a workspace `member` who is a project labeler,
    a `billing` member (project viewer) and a reviewer. Legacy Member.role must not drive access."""
    slug = client.post("/api/workspaces", json={"name": f"NOGO {uuid.uuid4().hex[:8]}"}).json()["slug"]
    ids: dict[str, str] = {}
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == slug))
        for key, role, email in (("labeler", "member", "labeler"), ("billing", "billing", "billing"),
                                 ("reviewer", "reviewer", "reviewer")):
            u = User(email=f"nogo-{email}-{uuid.uuid4().hex[:8]}@labeldesk.dev", name=f"NOGO {email}", pw_hash="x")
            db.add(u)
            db.flush()
            db.add(Member(workspace_id=ws.id, user_id=u.id, role=role, created=2000.0 + len(ids)))
            ids[key] = u.id
        ids["owner"] = ws.owner_id
        db.commit()
    p = client.post(f"/api/ws/{slug}/projects", json={"name": f"nogo-{uuid.uuid4().hex[:8]}",
                                                      "classes": ["person", "helmet"]}).json()
    with SessionLocal() as db:
        db.add(ProjectMember(project_id=p["id"], user_id=ids["labeler"], role="labeler"))
        db.add(ProjectMember(project_id=p["id"], user_id=ids["billing"], role="viewer"))
        db.commit()
    base = f"/api/ws/{slug}/projects/{p['slug']}"
    classes = {x["name"]: x["id"] for x in client.get(f"{base}/classes").json()}
    images = []
    for i in range(6):
        up = client.post(f"{base}/upload",
                         files=[("files", (f"nogo-{i}.jpg", jpeg((10 + 20 * i, 20, 30))))],
                         data={"split": "train", "batch_name": "nogo"})
        assert up.status_code == 200, up.text
        images.extend(x["id"] for x in up.json()["images"])
    h = {key: {"Authorization": f"Bearer {issue_access(uid)}"}
         for key, uid in ids.items() if key != "owner"}
    yield {"ws": slug, "base": base, "labels": f"{base}/labeling", "ids": ids, "h": h,
           "images": images, "classes": classes}
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == slug))
        if ws:
            db.delete(ws)
            db.commit()
        for key, uid in ids.items():
            if key == "owner":                      # the shared demo account is not ours to delete
                continue
            u = db.get(User, uid)
            if u is not None:
                db.delete(u)
        db.commit()


def seed(image_id: str, anns: list[dict]) -> None:
    with SessionLocal() as db:
        set_annotations(db, db.get(Image, image_id), anns)
        db.commit()


def stored(image_id: str) -> list[dict]:
    with SessionLocal() as db:
        return list(db.get(Image, image_id).annotations or [])


def drop_job(job_id: str, reset: list[str] | None = None) -> None:
    with SessionLocal() as db:
        db.execute(sa_delete(ConsensusAssignment).where(ConsensusAssignment.job_id == job_id))
        job = db.get(ConsensusJob, job_id)
        if job is not None:
            db.delete(job)
        for image_id in reset or []:
            img = db.get(Image, image_id)
            if img is not None:
                set_annotations(db, img, [])
                img.status, img.review, img.assignee_id = "unassigned", None, None
        db.commit()


def auth_for(world, user_id: str) -> dict | None:
    """Headers for one fixture user; None means the module client's owner token."""
    if user_id == world["ids"]["owner"]:
        return None
    for key, headers in world["h"].items():
        if world["ids"][key] == user_id:
            return headers
    raise AssertionError(f"no token for {user_id}")


def upload(world, client, name: str, color: tuple[int, int, int]) -> str:
    up = client.post(f"{world['base']}/upload", files=[("files", (name, jpeg(color)))],
                     data={"split": "train", "batch_name": "nogo-more"})
    assert up.status_code == 200, up.text
    return up.json()["images"][0]["id"]


# --- I5: consensus assignment and workforce roles -----------------------------------------

def test_consensus_assignments_skip_billing_and_viewers(client, world):
    r = client.post(f"{world['labels']}/consensus", json={"image_ids": world["images"][:2], "k": 2})
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]
    try:
        with SessionLocal() as db:
            assigned = set(db.scalars(select(ConsensusAssignment.user_id)
                                      .where(ConsensusAssignment.job_id == job_id)))
        assert world["ids"]["billing"] not in assigned
        assert assigned == {world["ids"]["owner"], world["ids"]["labeler"], world["ids"]["reviewer"]}
    finally:
        drop_job(job_id)


def test_labeler_dashboard_is_scoped_and_insights_labeling_is_gated(client, world):
    dash = client.get(f"{world['labels']}/dashboard", headers=world["h"]["labeler"])
    assert dash.status_code == 200, dash.text
    assert [x["user_id"] for x in dash.json()["labelers"]] == [world["ids"]["labeler"]]
    team = client.get(f"{world['labels']}/dashboard", headers=world["h"]["reviewer"]).json()
    assert world["ids"]["labeler"] in {x["user_id"] for x in team["labelers"]}
    assert client.get(f"{world['base']}/insights/labeling",
                      headers=world["h"]["labeler"]).status_code == 403


def test_workforce_lists_new_style_labelers(client, world):
    """A workspace `member` with project role `labeler` must appear in the team statistics."""
    row = next((x for x in client.get(f"{world['labels']}/dashboard",
                                      headers=world["h"]["reviewer"]).json()["labelers"]
                if x["user_id"] == world["ids"]["labeler"]), None)
    assert row is not None and "member" in row["role"]


# --- I4: honeypot concealment follows the effective project role --------------------------

def test_new_role_labeler_never_sees_the_honeypot_key(client, world):
    img = upload(world, client, "hp-new-role.jpg", (44, 44, 44))
    person = world["classes"]["person"]
    seed(img, [box(person, 0.1, 0.1, aid="gt")])
    r = client.post(f"{world['labels']}/honeypots", json={"image_id": img})
    assert r.status_code == 200, r.text
    hid = r.json()["id"]
    try:
        with SessionLocal() as db:
            assert db.get(Image, img).assignee_id == world["ids"]["labeler"]
            assert db.scalar(select(Honeypot.id).where(Honeypot.id == hid))

        view = client.get(f"/api/images/{img}", headers=world["h"]["labeler"])
        assert view.status_code == 200, view.text
        body = view.json()
        assert body["annotations"] == [] and body["annotationCount"] == 0
        assert body["annotated"] is False and body["classIds"] == [] and body["review"] is None

        listed = client.get(f"{world['base']}/images", headers=world["h"]["labeler"]).json()["items"]
        row = next(x for x in listed if x["id"] == img)
        assert row["annotationCount"] == 0 and row["classIds"] == [] and row["review"] is None

        # filters and the kanban badge are the other two ways the hidden count used to leak
        def ids_of(query: str) -> set[str]:
            return {x["id"] for x in client.get(f"{world['base']}/images?limit=1000{query}",
                                               headers=world["h"]["labeler"]).json()["items"]}
        assert img not in ids_of("&annotated=yes")
        assert img in ids_of("&annotated=no")
        assert img not in ids_of(f"&class_id={person}")
        with SessionLocal() as db:
            batch_id = db.get(Image, img).batch_id
        board = client.get(f"{world['base']}/board", headers=world["h"]["labeler"]).json()
        card = next(x for col in board["columns"].values() for x in col if x["batchId"] == batch_id)
        assert card["annotated"] == 0

        assert client.post(f"/api/images/{img}/suggest-class", json={"annotation_id": "gt"},
                           headers=world["h"]["labeler"]).status_code == 404

        save = client.put(f"/api/images/{img}/annotations",
                          json={"annotations": [box(person, 0.1, 0.1, aid="mine")]},
                          headers=world["h"]["labeler"])
        assert save.status_code == 200 and save.json()["status"] == "honeypot"
        assert stored(img) == [box(person, 0.1, 0.1, aid="gt")]      # the answer key is untouched
    finally:
        client.delete(f"{world['labels']}/honeypots/{hid}")


# --- I6: class ids are project-scoped on every write path --------------------------------

@pytest.fixture(scope="module")
def foreign_class(client, world):
    other = client.post(f"/api/ws/{world['ws']}/projects", json={"name": f"nogo-other-{uuid.uuid4().hex[:6]}",
                                                                 "classes": ["zebra"]}).json()
    obase = f"/api/ws/{world['ws']}/projects/{other['slug']}"
    classes = {x["name"]: x["id"] for x in client.get(f"{obase}/classes").json()}
    yield classes["zebra"]
    client.delete(obase)


def test_consensus_rejects_foreign_class_drafts(client, world, foreign_class):
    img = upload(world, client, "foreign-submit.jpg", (55, 55, 55))
    r = client.post(f"{world['labels']}/consensus", json={"image_ids": [img], "k": 2})
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]
    try:
        with SessionLocal() as db:
            row = db.scalar(select(ConsensusAssignment).where(ConsensusAssignment.job_id == job_id).limit(1))
            assignee = row.user_id
        r = client.post(f"{world['labels']}/consensus/{job_id}/images/{img}/submit",
                        json={"annotations": [box(foreign_class, aid="foreign")]},
                        headers=auth_for(world, assignee))
        assert r.status_code == 400, r.text
        with SessionLocal() as db:
            row = db.scalar(select(ConsensusAssignment).where(ConsensusAssignment.job_id == job_id,
                                                              ConsensusAssignment.user_id == assignee))
            assert row is not None and not row.annotations and row.submitted is None
    finally:
        drop_job(job_id, reset=[img])


def test_honeypot_rejects_foreign_classes(client, world, foreign_class):
    img = upload(world, client, "foreign-honeypot.jpg", (56, 56, 56))
    r = client.post(f"{world['labels']}/honeypots",
                    json={"image_id": img, "annotations": [box(foreign_class, aid="foreign-gt")]})
    assert r.status_code == 400, r.text
    with SessionLocal() as db:
        assert db.scalar(select(Honeypot.id).where(Honeypot.image_id == img)) is None


def test_merge_revalidates_classes_before_writing(client, world, foreign_class):
    good, bad = world["images"][4], world["images"][5]
    person = world["classes"]["person"]
    r = client.post(f"{world['labels']}/consensus", json={"image_ids": [good, bad], "k": 2})
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]
    try:
        for image_id in (good, bad):
            det = client.get(f"{world['labels']}/consensus/{job_id}").json()
            row = next(x for x in det["images"] if x["image_id"] == image_id)
            assert len(row["assignees"]) == 2
            for who in row["assignees"]:
                assert client.post(f"{world['labels']}/consensus/{job_id}/images/{image_id}/submit",
                                   json={"annotations": [box(person, aid=f"ok-{image_id}")]},
                                   headers=auth_for(world, who["user_id"])).status_code == 200
        # Tamper with both stored drafts (a legacy row / direct DB write) to simulate data that
        # predates the submit validation; the merge must still refuse before writing anything.
        with SessionLocal() as db:
            rows = db.scalars(select(ConsensusAssignment).where(ConsensusAssignment.job_id == job_id,
                                                                ConsensusAssignment.image_id == bad)).all()
            assert len(rows) == 2
            for row in rows:
                row.annotations = [box(foreign_class, aid=f"foreign-{row.user_id}")]
            db.commit()
        r = client.post(f"{world['labels']}/consensus/{job_id}/merge")
        assert r.status_code == 400, r.text
        assert stored(good) == [] and stored(bad) == []
        with SessionLocal() as db:
            img = db.get(Image, good)
            assert img.status == "unassigned"
            job = db.get(ConsensusJob, job_id)
            assert job.status != "merged"
    finally:
        drop_job(job_id, reset=[good, bad])
