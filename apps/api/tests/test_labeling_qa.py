"""Labeling QA & workforce: IoU agreement metrics, consensus jobs, honeypots, review queue, dashboard."""
import io
import json
import os
import tempfile
import time
import uuid

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp())
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
from app.models import ConsensusAssignment, ConsensusJob, Image, LabelEvent, Member, User, Workspace, set_annotations
from app.security import issue_access
from app.services import labeling, labeling_ops

DEMO, LABELER, REVIEWER = "demo@labeldesk.dev", "labeler@labeldesk.dev", "reviewer@labeldesk.dev"
JOB: dict = {}


# --- pure metrics -----------------------------------------------------------------------

def box(cls: str, x: float = 0.1, y: float = 0.1, w: float = 0.2, h: float = 0.2, aid: str = "b1",
        source: str | None = "human") -> dict:
    ann = {"id": aid, "classId": cls, "shape": {"kind": "bbox", "x": x, "y": y, "w": w, "h": h}}
    if source:
        ann["source"] = source
    return ann


def poly(cls: str, points: list[float], aid: str) -> dict:
    return {"id": aid, "classId": cls, "shape": {"kind": "polygon", "points": points}, "source": "human"}


def test_bbox_iou_identical_disjoint_half_and_degenerate():
    assert labeling.bbox_iou((0.0, 0.0, 1.0, 1.0), (0.0, 0.0, 1.0, 1.0)) == 1.0
    assert labeling.bbox_iou((0.0, 0.0, 0.2, 0.2), (0.5, 0.5, 0.2, 0.2)) == 0.0
    assert labeling.bbox_iou((0.0, 0.0, 0.5, 1.0), (0.25, 0.0, 0.5, 1.0)) == pytest.approx(1 / 3)
    assert labeling.bbox_iou((0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 1.0, 1.0)) == 0.0


def test_sets_agreement_matches_and_edges():
    one = [box("person")]
    assert labeling.sets_agreement(one, [box("person", aid="other")]) == 1.0
    assert labeling.sets_agreement(one, [box("person", x=0.7, y=0.7)]) == 0.0
    assert labeling.sets_agreement(one, []) == 0.0
    assert labeling.sets_agreement([], []) == 1.0
    assert labeling.sets_agreement([], one) == 0.0
    two = [box("person", aid="a1"), box("helmet", x=0.6, y=0.6, aid="a2")]
    partial = [box("person", aid="b1"), box("helmet", x=0.1, y=0.7, aid="b2")]
    assert labeling.sets_agreement(two, partial) == pytest.approx(0.5)
    assert labeling.sets_agreement(one, [box("helmet")]) == 0.0


def test_iou_threshold_boundary():
    a = [box("person", 0.1, 0.1, 0.7, 0.7, aid="a")]
    b = [box("person", 0.24, 0.24, 0.7, 0.7, aid="b")]
    assert labeling.bbox_iou((0.1, 0.1, 0.7, 0.7), (0.24, 0.24, 0.7, 0.7)) == pytest.approx(0.4706, abs=1e-3)
    assert labeling.sets_agreement(a, b, 0.4) == 1.0
    assert labeling.sets_agreement(a, b, 0.5) == 0.0


def test_polygon_bounds_and_class_kind():
    p = poly("person", [0.2, 0.3, 0.6, 0.3, 0.6, 0.7, 0.2, 0.7], "p1")
    assert labeling.shape_box(p["shape"]) == pytest.approx((0.2, 0.3, 0.4, 0.4))
    assert labeling.sets_agreement([p], [box("person", 0.2, 0.3, 0.4, 0.4)]) == 1.0
    c1 = {"id": "c1", "classId": "person", "shape": {"kind": "class"}, "source": "human"}
    c2 = {"id": "c2", "classId": "person", "shape": {"kind": "class"}, "source": "human"}
    assert labeling.shape_box(c1["shape"]) is None
    assert labeling.sets_agreement([c1], [c2]) == 1.0
    assert labeling.sets_agreement([c1], [{"id": "c3", "classId": "helmet", "shape": {"kind": "class"}}]) == 0.0


def test_group_agreement_is_mean_of_pairs():
    s1 = [box("person", aid="s1")]
    s2 = [box("person", aid="s2")]
    s3 = [box("person", x=0.7, y=0.7, aid="s3")]
    assert labeling.group_agreement([s1]) == 1.0
    assert labeling.group_agreement([s1, s2, s3]) == pytest.approx(1 / 3)


def test_merge_sets_majority_mean_and_drops_minority():
    a1 = box("person", 0.1, 0.1, 0.2, 0.2, aid="a")
    a2 = box("person", 0.12, 0.1, 0.2, 0.2, aid="b")
    lone = box("person", 0.7, 0.7, 0.1, 0.1, aid="c")
    merged = labeling.merge_sets([[a1], [a2], [lone]])
    assert len(merged) == 1
    assert merged[0]["source"] == "human"
    assert merged[0]["id"].startswith("m") and "confidence" not in merged[0]
    assert merged[0]["classId"] == "person"
    assert merged[0]["shape"]["x"] == pytest.approx(0.11)
    assert merged[0]["shape"]["y"] == pytest.approx(0.1)
    assert labeling.merge_sets([[a1], [lone]]) == []


def test_merge_sets_mean_polygon_points():
    p1 = poly("person", [0.2, 0.2, 0.6, 0.2, 0.6, 0.6], "p1")
    p2 = poly("person", [0.24, 0.2, 0.6, 0.2, 0.6, 0.6], "p2")
    merged = labeling.merge_sets([[p1], [p2]])
    assert len(merged) == 1
    shape = merged[0]["shape"]
    assert shape["kind"] == "polygon" and len(shape["points"]) == 6
    assert shape["points"][0] == pytest.approx(0.22)
    assert shape["points"][1] == pytest.approx(0.2)


def test_honeypot_score_identical_and_shifted():
    gt = [box("person", aid="g1"), box("helmet", 0.6, 0.6, aid="g2")]
    assert labeling.honeypot_score(gt, [box("person", aid="s1"), box("helmet", 0.6, 0.6, aid="s2")]) == 1.0
    partial = [box("person", aid="s1"), box("helmet", 0.1, 0.1, aid="s2")]
    assert labeling.honeypot_score(gt, partial) == 0.5


# --- API fixtures -------------------------------------------------------------------------

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


@pytest.fixture(scope="module")
def project(client, auth):
    """Throwaway workspace + project with 5 images (4 assigned, 1 unassigned); member order is pinned."""
    slug = client.post("/api/workspaces", json={"name": f"QA Ops {uuid.uuid4().hex[:8]}"}).json()["slug"]
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == slug))
        db.execute(sa_delete(Member).where(Member.workspace_id == ws.id))
        db.add_all([
            Member(workspace_id=ws.id, user_id=auth["admin"]["id"], role="admin", created=1000.0),
            Member(workspace_id=ws.id, user_id=auth["labeler"]["id"], role="annotator", created=2000.0),
            Member(workspace_id=ws.id, user_id=auth["reviewer"]["id"], role="reviewer", created=3000.0),
        ])
        db.commit()
    p = client.post(f"/api/ws/{slug}/projects", json={"name": f"qa-{uuid.uuid4().hex[:8]}",
                                                      "classes": ["person", "helmet"]}).json()
    base = f"/api/ws/{slug}/projects/{p['slug']}"
    files = [("files", (f"qa-{i}.jpg", jpeg((20 + 50 * i, 40, 60 + 10 * i)))) for i in range(5)]
    up = client.post(f"{base}/upload", files=files, data={"split": "train", "batch_name": "qa"})
    assert up.status_code == 200 and up.json()["uploaded"] == 5, up.text
    ids = [x["id"] for x in up.json()["images"]]
    classes = {x["name"]: x["id"] for x in client.get(f"{base}/classes").json()}
    with SessionLocal() as db:
        for iid in ids[:4]:                       # labelers only reach images assigned to them
            db.get(Image, iid).assignee_id = auth["labeler"]["id"]
        db.commit()
    yield {"ws": slug, "base": base, "labels": f"{base}/labeling", "images": ids, "classes": classes}
    client.delete(base)
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == slug))
        if ws:
            db.delete(ws)
            db.commit()


def jpeg(color: tuple[int, int, int]) -> bytes:
    b = io.BytesIO()
    PImage.new("RGB", (160, 120), color).save(b, "JPEG")
    return b.getvalue()


def seed(image_id: str, anns: list[dict]) -> None:
    with SessionLocal() as db:
        set_annotations(db, db.get(Image, image_id), anns)
        db.commit()


def stored(image_id: str) -> list[dict]:
    with SessionLocal() as db:
        return list(db.get(Image, image_id).annotations or [])


def save(client, auth, who: str, image_id: str, anns: list[dict]):
    return client.put(f"/api/images/{image_id}/annotations", json={"annotations": anns}, headers=auth[who]["h"])


def submit(client, auth, who: str, labels: str, job_id: str, image_id: str, anns: list[dict] | None = None):
    body = {} if anns is None else {"annotations": anns}
    return client.post(f"{labels}/consensus/{job_id}/images/{image_id}/submit", json=body,
                       headers=auth[who]["h"])


def upload_image(client, project, name: str, color: tuple[int, int, int] = (12, 12, 12)) -> str:
    """A fresh image in the QA project, so a test never borrows module-global job state."""
    up = client.post(f"{project['base']}/upload", files=[("files", (name, jpeg(color)))],
                     data={"split": "train", "batch_name": "qa-fix"})
    assert up.status_code == 200, up.text
    return up.json()["images"][0]["id"]


def assign(image_id: str, user_id: str | None) -> None:
    with SessionLocal() as db:
        db.get(Image, image_id).assignee_id = user_id
        db.commit()


def labeler_row(client, auth, project, user_id: str) -> tuple[dict, dict]:
    dash = client.get(f"{project['labels']}/dashboard", headers=auth["reviewer"]["h"]).json()
    return next(x for x in dash["labelers"] if x["user_id"] == user_id), dash


def drop_job(job_id: str, reset: list[str] | None = None) -> None:
    """Remove a throwaway consensus job (and its assignments) so module state does not leak."""
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


# --- API flow -----------------------------------------------------------------------------

def test_consensus_create_requires_reviewer(client, auth, project):
    r = client.post(f"{project['labels']}/consensus", json={"image_ids": project["images"][:1], "k": 2},
                    headers=auth["labeler"]["h"])
    assert r.status_code == 403


def test_consensus_job_collects_k_assignments(client, auth, project):
    r = client.post(f"{project['labels']}/consensus", json={"image_ids": project["images"][:2], "k": 2})
    assert r.status_code == 200, r.text
    job = r.json()
    JOB["id"] = job["id"]
    assert job["status"] == "collecting"
    assert job["images"] == 2 and job["assignments"] == 4 and job["submitted"] == 0
    assert job["image_ids"] == project["images"][:2]
    tasks = client.get(f"{project['labels']}/my-tasks", headers=auth["labeler"]["h"]).json()["tasks"]
    assert len(tasks) == 2
    assert {t["image_id"] for t in tasks} == set(project["images"][:2])


def test_consensus_draft_reachable_for_unassigned_image(client, auth, project):
    """Round-robin consensus work reaches annotators even when the image is not assigned to them."""
    img = project["images"][4]
    person = project["classes"]["person"]
    with SessionLocal() as db:
        assert db.get(Image, img).assignee_id != auth["labeler"]["id"]
    r = client.post(f"{project['labels']}/consensus", json={"image_ids": [img], "k": 2})
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]
    try:
        draft = client.get(f"/api/images/{img}", headers=auth["labeler"]["h"])
        assert draft.status_code == 200, draft.text
        body = draft.json()
        assert body["consensusJob"] == job_id and body["annotations"] == []
        r = save(client, auth, "labeler", img, [box(person, 0.4, 0.4, aid="unassigned")])
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "consensus" and r.json()["jobId"] == job_id
        r = submit(client, auth, "labeler", project["labels"], job_id, img)
        assert r.status_code == 200, r.text
        assert r.json() == {"submitted": 1, "total": 2, "agreement": None, "jobStatus": "collecting",
                            "jobId": job_id}
    finally:
        drop_job(job_id)


def test_merge_without_two_drafts_is_rejected(client, auth, project):
    """A job is mergeable only once it is ready (every assignee submitted)."""
    img = project["images"][4]
    person = project["classes"]["person"]
    r = client.post(f"{project['labels']}/consensus", json={"image_ids": [img], "k": 2})
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]
    try:
        assert save(client, auth, "admin", img, [box(person, 0.3, 0.3, aid="adm")]).json()["status"] == "consensus"
        r = client.post(f"{project['labels']}/consensus/{job_id}/merge")
        assert r.status_code == 409 and "not ready to merge" in r.json()["detail"]
        assert submit(client, auth, "admin", project["labels"], job_id, img).status_code == 200
        r = client.post(f"{project['labels']}/consensus/{job_id}/merge")
        assert r.status_code == 409 and "not ready to merge" in r.json()["detail"]
        det = client.get(f"{project['labels']}/consensus/{job_id}").json()
        assert det["status"] == "collecting" and det["submitted"] == 1
        assert save(client, auth, "labeler", img, [box(person, 0.31, 0.31, aid="lab")]).json()["status"] == "consensus"
        assert submit(client, auth, "labeler", project["labels"], job_id, img).status_code == 200
        r = client.post(f"{project['labels']}/consensus/{job_id}/merge")
        assert r.status_code == 200, r.text
        assert r.json()["merged"] == 1 and r.json()["status"] == "merged"
    finally:
        drop_job(job_id, reset=[img])


def test_consensus_drafts_are_private(client, auth, project):
    img = project["images"][1]
    person = project["classes"]["person"]
    original = box(person, aid="orig")
    seed(img, [original])
    draft = client.get(f"/api/images/{img}", headers=auth["labeler"]["h"]).json()
    assert draft["annotations"] == [] and draft["consensusJob"] == JOB["id"]
    mine = box(person, 0.2, 0.2, aid="l1")
    r = save(client, auth, "labeler", img, [mine])
    assert r.status_code == 200, r.text
    assert r.json() == {"saved": 1, "status": "consensus", "jobId": JOB["id"]}
    assert stored(img) == [original]                       # the project row is untouched
    with SessionLocal() as db:
        row = db.scalar(select(ConsensusAssignment).where(ConsensusAssignment.image_id == img,
                                                          ConsensusAssignment.user_id == auth["labeler"]["id"]))
        assert [a["id"] for a in row.annotations] == ["l1"]
        assert row.submitted is None                       # autosave is not a submission
    det = client.get(f"{project['labels']}/consensus/{JOB['id']}").json()
    assert det["submitted"] == 0 and det["status"] == "collecting"
    r = submit(client, auth, "labeler", project["labels"], JOB["id"], img)
    assert r.status_code == 200, r.text
    assert r.json()["jobStatus"] == "collecting"
    theirs = client.get(f"/api/images/{img}", headers=auth["reviewer"]["h"]).json()
    assert theirs["annotations"] == [] and theirs["consensusJob"] == JOB["id"]
    r = save(client, auth, "reviewer", img, [box(person, 0.2, 0.2, aid="r1")])
    assert r.json()["status"] == "consensus"
    with SessionLocal() as db:
        row = db.scalar(select(ConsensusAssignment).where(ConsensusAssignment.image_id == img,
                                                          ConsensusAssignment.user_id == auth["reviewer"]["id"]))
        assert [a["id"] for a in row.annotations] == ["r1"]
    assert submit(client, auth, "reviewer", project["labels"], JOB["id"], img).status_code == 200


def test_job_ready_and_agreement(client, auth, project):
    img0, img1 = project["images"][0], project["images"][1]
    person = project["classes"]["person"]
    assert save(client, auth, "admin", img0, [box(person, 0.05, 0.05, aid="adm")]).json()["status"] == "consensus"
    assert submit(client, auth, "admin", project["labels"], JOB["id"], img0).status_code == 200
    assert save(client, auth, "labeler", img0, [box(person, 0.7, 0.7, aid="far")]).json()["status"] == "consensus"
    assert submit(client, auth, "labeler", project["labels"], JOB["id"], img0).status_code == 200
    det = client.get(f"{project['labels']}/consensus/{JOB['id']}").json()
    assert det["status"] == "ready"
    assert det["submitted"] == 4
    assert det["agreement"] == pytest.approx(0.5)
    per_image = {i["image_id"]: i for i in det["images"]}
    assert per_image[img0]["agreement"] == 0.0
    assert per_image[img1]["agreement"] == 1.0
    assert per_image[img1]["submissions"] == 2
    # A ready-but-unmerged job keeps each labeler's private draft visible until the reviewer merges.
    draft = client.get(f"/api/images/{img1}", headers=auth["labeler"]["h"]).json()
    assert draft["consensusJob"] == JOB["id"] and [a["id"] for a in draft["annotations"]] == ["l1"]


def test_merge_writes_consensus_annotations(client, auth, project):
    img1 = project["images"][1]
    r = client.post(f"{project['labels']}/consensus/{JOB['id']}/merge")
    assert r.status_code == 200, r.text
    assert r.json()["merged"] >= 1
    merged = stored(img1)
    assert len(merged) == 1
    assert merged[0]["source"] == "human" and "confidence" not in merged[0]
    assert merged[0]["classId"] == project["classes"]["person"]
    assert merged[0]["shape"]["x"] == pytest.approx(0.2)
    with SessionLocal() as db:
        img = db.get(Image, img1)
        assert img.status == "review" and img.review is None
    assert client.post(f"{project['labels']}/consensus/{JOB['id']}/merge").status_code == 409


def test_job_is_project_scoped_and_k_needs_members(client, auth, project):
    other = client.post(f"/api/ws/{project['ws']}/projects", json={"name": f"qa-empty-{uuid.uuid4().hex[:6]}"}).json()
    obase = f"/api/ws/{project['ws']}/projects/{other['slug']}"
    try:
        assert client.get(f"{obase}/labeling/consensus/{JOB['id']}").status_code == 404
        assert client.post(f"{obase}/labeling/consensus/{JOB['id']}/merge").status_code == 404
    finally:
        client.delete(obase)
    r = client.post(f"{project['labels']}/consensus", json={"image_ids": project["images"][:1], "k": 5})
    assert r.status_code == 400 and "member" in r.json()["detail"]


def test_honeypot_scoring_and_dashboard_accuracy(client, auth, project):
    img = project["images"][2]
    person = project["classes"]["person"]
    gt = box(person, 0.1, 0.1, aid="gt")
    seed(img, [gt])
    assert client.post(f"{project['labels']}/honeypots", json={"image_id": img},
                       headers=auth["labeler"]["h"]).status_code == 403
    r = client.post(f"{project['labels']}/honeypots", json={"image_id": img}, headers=auth["reviewer"]["h"])
    assert r.status_code == 200, r.text
    hid = r.json()["id"]
    # The answer key must never reach the labeler being scored: no annotations, no honeypot hint.
    mine_view = client.get(f"/api/images/{img}", headers=auth["labeler"]["h"])
    assert mine_view.status_code == 200, mine_view.text
    leaked = mine_view.json()
    assert leaked["annotations"] == []
    assert leaked["annotationCount"] == 0 and leaked["annotated"] is False
    assert leaked["classIds"] == [] and leaked["review"] is None
    seen = json.dumps(leaked).lower()
    assert "honeypot" not in seen and "ground" not in seen
    # PATCH returns the full image too; it must not become a second way to read the key.
    patched = client.patch(f"/api/images/{img}", json={"tags": ["qa"]}, headers=auth["labeler"]["h"]).json()
    assert patched["annotations"] == [] and "honeypot" not in json.dumps(patched).lower()
    # The dataset list must not become a third way: every GT-derived field is blanked there too.
    listed = client.get(f"{project['base']}/images", headers=auth["labeler"]["h"]).json()["items"]
    row = next(x for x in listed if x["id"] == img)
    assert row["annotationCount"] == 0 and row["annotated"] is False and row["classIds"] == []
    assert row["review"] is None
    truth = client.get(f"/api/images/{img}", headers=auth["reviewer"]["h"]).json()
    assert [a["id"] for a in truth["annotations"]] == ["gt"]        # reviewers keep the key
    # no oracle: suggesting a class for a GT annotation the labeler cannot see must 404.
    sug = client.post(f"/api/images/{img}/suggest-class", json={"annotation_id": "gt"},
                      headers=auth["labeler"]["h"])
    assert sug.status_code == 404 and sug.json()["detail"] == "annotation not found"
    r = save(client, auth, "labeler", img, [box(person, 0.1, 0.1, aid="mine")])
    assert r.status_code == 200 and r.json() == {"saved": 1, "status": "honeypot"}
    assert stored(img) == [gt]                             # the answer image is never overwritten
    items = client.get(f"{project['labels']}/honeypots", headers=auth["reviewer"]["h"]).json()
    item = next(x for x in items["items"] if x["id"] == hid)
    assert item["attempts"] == 1 and item["accuracy"] == pytest.approx(1.0)
    assert item["annotations"] == 1 and item["name"]
    save(client, auth, "labeler", img, [box(person, 0.7, 0.7, aid="mine2")])
    assert stored(img) == [gt]                             # still untouched after a re-open save
    items = client.get(f"{project['labels']}/honeypots", headers=auth["reviewer"]["h"]).json()
    item = next(x for x in items["items"] if x["id"] == hid)
    assert item["attempts"] == 1 and item["accuracy"] < 1.0           # re-saved, not duplicated
    reopened = client.get(f"/api/images/{img}", headers=auth["labeler"]["h"]).json()
    assert reopened["annotations"] == []                   # the attempt left no trace on the canvas
    labeler_row = next(x for x in items["labelers"] if x["user_id"] == auth["labeler"]["id"])
    assert labeler_row["attempts"] == 1
    dash = client.get(f"{project['labels']}/dashboard", headers=auth["reviewer"]["h"]).json()
    row = next(x for x in dash["labelers"] if x["user_id"] == auth["labeler"]["id"])
    assert row["honeypot_accuracy"] == pytest.approx(item["accuracy"])


def test_annotator_without_assignment_or_honeypot_is_denied(client, auth, project):
    """The honeypot carve-out must not widen ordinary annotator access."""
    img = project["images"][4]
    with SessionLocal() as db:
        assert db.get(Image, img).assignee_id != auth["labeler"]["id"]
        assert labeling_ops.honeypot_for_image(db, img) is None
    assert client.get(f"/api/images/{img}", headers=auth["labeler"]["h"]).status_code == 403


def test_dashboard_ai_acceptance_and_rejection_rate(client, auth, project):
    """AI acceptance is provenance-based: AI ids seen that survive on an approved image."""
    img = project["images"][3]
    person = project["classes"]["person"]
    ai = box(person, 0.3, 0.3, aid="ai1", source="ultralytics:yolo26n")
    ai["confidence"] = 0.9
    seed(img, [ai])
    assert save(client, auth, "labeler", img, [ai]).status_code == 200
    row, _ = labeler_row(client, auth, project, auth["labeler"]["id"])
    assert row["ai_acceptance"] == 0.0                         # seen, but the image is not approved yet
    r = client.post(f"/api/images/{img}/review", json={"approved": True}, headers=auth["reviewer"]["h"])
    assert r.status_code == 200, r.text
    row, _ = labeler_row(client, auth, project, auth["labeler"]["id"])
    assert row["ai_acceptance"] == 1.0                         # the AI label survived on an approved image
    assert save(client, auth, "labeler", img, [box(person, 0.5, 0.5, aid="human1")]).status_code == 200
    row, dash = labeler_row(client, auth, project, auth["labeler"]["id"])
    assert row["ai_acceptance"] == 0.0                         # rewritten by a human, so not accepted
    assert dash["totals"]["ai_acceptance"] == 0.0
    r = client.post(f"/api/images/{img}/review", json={"approved": False}, headers=auth["reviewer"]["h"])
    assert r.status_code == 200, r.text
    row, dash = labeler_row(client, auth, project, auth["labeler"]["id"])
    assert row["rejection_rate"] == 1.0
    assert dash["window_days"] == 30
    assert len(dash["daily"]) == 30 and all(d["images"] >= 0 for d in dash["daily"])
    own = client.get(f"{project['labels']}/dashboard", headers=auth["labeler"]["h"]).json()
    assert [x["user_id"] for x in own["labelers"]] == [auth["labeler"]["id"]]


def test_review_queue_sorted_by_disagreement(client, auth, project):
    disagree, agree = project["images"][0], project["images"][1]
    # img0's tied drafts are deliberately not merged (C1); park it in review so the queue scores them.
    with SessionLocal() as db:
        db.get(Image, disagree).status = "review"
        db.commit()
    items = client.get(f"{project['labels']}/review-queue", headers=auth["reviewer"]["h"]).json()["items"]
    ids = [x["image_id"] for x in items]
    assert disagree in ids and agree in ids
    assert ids.index(disagree) < ids.index(agree)
    assert items[ids.index(disagree)]["disagreement"] > 0
    assert items[ids.index(agree)]["disagreement"] == 0
    assert items[ids.index(disagree)]["thumbnail"] and items[ids.index(disagree)]["name"]


def test_submission_is_explicit_and_tracks_redraft(client, auth, project):
    """Autosave never marks a draft submitted; only the submit endpoint does, and re-edits re-score."""
    img = project["images"][4]
    person = project["classes"]["person"]
    r = client.post(f"{project['labels']}/consensus", json={"image_ids": [img], "k": 2})
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]
    try:
        assert save(client, auth, "admin", img, [box(person, 0.3, 0.3, aid="a1")]).status_code == 200
        det = client.get(f"{project['labels']}/consensus/{job_id}").json()
        assert det["submitted"] == 0 and det["status"] == "collecting"
        # the task stays in the queue until the labeler explicitly submits
        tasks = client.get(f"{project['labels']}/my-tasks", headers=auth["labeler"]["h"]).json()["tasks"]
        assert img in {t["image_id"] for t in tasks}
        r = submit(client, auth, "reviewer", project["labels"], job_id, img)
        assert r.status_code == 404 and r.json()["detail"] == "not your assignment"
        r = submit(client, auth, "admin", project["labels"], job_id, img)
        assert r.status_code == 200, r.text
        assert r.json() == {"submitted": 1, "total": 2, "agreement": None, "jobStatus": "collecting",
                            "jobId": job_id}
        # a second submit replaces the draft and is still just one submission
        r = submit(client, auth, "admin", project["labels"], job_id, img, [box(person, 0.35, 0.35, aid="a2")])
        assert r.status_code == 200, r.text
        assert r.json()["submitted"] == 1 and r.json()["jobStatus"] == "collecting"
        assert save(client, auth, "labeler", img, [box(person, 0.7, 0.7, aid="l1")]).status_code == 200
        det = client.get(f"{project['labels']}/consensus/{job_id}").json()
        assert det["submitted"] == 1 and det["status"] == "collecting"      # drafting alone is not ready
        r = submit(client, auth, "labeler", project["labels"], job_id, img)
        assert r.status_code == 200, r.text
        assert r.json() == {"submitted": 2, "total": 2, "agreement": 0.0, "jobStatus": "ready", "jobId": job_id}
        # re-submitting an assignment moves the agreement with the new draft
        r = submit(client, auth, "labeler", project["labels"], job_id, img, [box(person, 0.35, 0.35, aid="l2")])
        assert r.status_code == 200, r.text
        assert r.json()["agreement"] == 1.0 and r.json()["jobStatus"] == "ready"
        # autosaving an already-submitted draft keeps it submitted but refreshes the agreement
        assert save(client, auth, "labeler", img, [box(person, 0.7, 0.7, aid="l3")]).status_code == 200
        det = client.get(f"{project['labels']}/consensus/{job_id}").json()
        assert det["submitted"] == 2 and det["status"] == "ready"
        assert det["agreement"] == 0.0
    finally:
        drop_job(job_id)


def test_consensus_rejects_merging_collecting_job(client, auth, project):
    img = project["images"][4]
    r = client.post(f"{project['labels']}/consensus", json={"image_ids": [img], "k": 2})
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]
    try:
        r = client.post(f"{project['labels']}/consensus/{job_id}/merge")
        assert r.status_code == 409 and "not ready to merge" in r.json()["detail"]
        assert client.get(f"{project['labels']}/consensus/{job_id}").json()["status"] == "collecting"
    finally:
        drop_job(job_id)


def test_consensus_job_rules_keep_images_clean_and_exclusive(client, auth, project):
    # merging already-labeled images would erase existing work, so they are refused up front
    r = client.post(f"{project['labels']}/consensus", json={"image_ids": [project["images"][1]], "k": 2})
    assert r.status_code == 400 and "consensus needs unlabeled images" in r.json()["detail"]
    img = project["images"][4]
    r = client.post(f"{project['labels']}/consensus", json={"image_ids": [img], "k": 2})
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]
    try:
        r = client.post(f"{project['labels']}/consensus", json={"image_ids": [img], "k": 2})
        assert r.status_code == 400 and "already in an open consensus job" in r.json()["detail"]
    finally:
        drop_job(job_id)
    # auto-pick only ever sends unlabeled images that are not already in an open job
    r = client.post(f"{project['labels']}/consensus", json={"count": 20, "k": 2})
    assert r.status_code == 200, r.text
    auto = r.json()
    try:
        picked = auto["image_ids"]
        assert img in picked and project["images"][1] not in picked
        with SessionLocal() as db:
            assert all(db.get(Image, iid).n_annotations == 0 for iid in picked)
    finally:
        drop_job(auto["id"])


def test_consensus_and_honeypot_inputs_are_bounded(client, auth, project):
    r = client.post(f"{project['labels']}/consensus",
                    json={"image_ids": [f"missing{i}" for i in range(101)], "k": 2})
    assert r.status_code == 400 and "100" in r.json()["detail"]
    gt = [box(project["classes"]["person"], aid=f"h{i}") for i in range(5001)]
    r = client.post(f"{project['labels']}/honeypots", json={"image_id": project["images"][4], "annotations": gt},
                    headers=auth["reviewer"]["h"])
    assert r.status_code == 400 and "5000" in r.json()["detail"]


def test_annotator_cannot_autosave_after_merge(client, auth, project):
    img = project["images"][1]
    merged = stored(img)
    assert merged
    person = project["classes"]["person"]
    r = save(client, auth, "labeler", img, [box(person, 0.9, 0.9, aid="late")])
    assert r.status_code == 409 and "already merged" in r.json()["detail"]
    assert stored(img) == merged                         # the merged result survives
    r = save(client, auth, "reviewer", img, merged)      # reviewers keep editing the result
    assert r.status_code == 200, r.text
    assert stored(img) == merged
    # Rejecting sends the merged image back to the labeler; the freeze must lift with it.
    r = client.post(f"/api/images/{img}/review", json={"approved": False}, headers=auth["reviewer"]["h"])
    assert r.status_code == 200, r.text
    fixed = [box(person, 0.15, 0.15, aid="fixed")]
    r = save(client, auth, "labeler", img, fixed)
    assert r.status_code == 200, r.text
    assert [a["id"] for a in stored(img)] == ["fixed"]


def test_my_tasks_excludes_deleted_images(client, auth, project):
    img = project["images"][4]
    r = client.post(f"{project['labels']}/consensus", json={"image_ids": [img], "k": 2})
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]
    try:
        tasks = client.get(f"{project['labels']}/my-tasks", headers=auth["labeler"]["h"]).json()["tasks"]
        assert img in {t["image_id"] for t in tasks}
        with SessionLocal() as db:
            db.get(Image, img).deleted_at = 1.0
            db.commit()
        tasks = client.get(f"{project['labels']}/my-tasks", headers=auth["labeler"]["h"]).json()["tasks"]
        assert img not in {t["image_id"] for t in tasks}
    finally:
        with SessionLocal() as db:
            db.get(Image, img).deleted_at = None
            db.commit()
        drop_job(job_id)


def test_dashboard_counts_max_annotations_per_image(client, auth, project):
    """Autosave stores a running total; throughput must count the latest draft, not every save."""
    person = project["classes"]["person"]
    up = client.post(f"{project['base']}/upload", files=[("files", ("metrics.jpg", jpeg((9, 9, 9))))],
                     data={"split": "train", "batch_name": "qa-metrics"})
    assert up.status_code == 200, up.text
    img = up.json()["images"][0]["id"]
    with SessionLocal() as db:
        db.get(Image, img).assignee_id = auth["labeler"]["id"]
        db.commit()
    before = client.get(f"{project['labels']}/dashboard", headers=auth["reviewer"]["h"]).json()
    assert save(client, auth, "labeler", img, [box(person, 0.1, 0.1, aid="m1")]).status_code == 200
    assert save(client, auth, "labeler", img, [box(person, 0.1, 0.1, aid="m1"),
                                               box(person, 0.5, 0.5, aid="m2")]).status_code == 200
    after = client.get(f"{project['labels']}/dashboard", headers=auth["reviewer"]["h"]).json()
    assert after["totals"]["annotations"] - before["totals"]["annotations"] == 2   # not 1 + 2
    row_b = next(x for x in before["labelers"] if x["user_id"] == auth["labeler"]["id"])
    row_a = next(x for x in after["labelers"] if x["user_id"] == auth["labeler"]["id"])
    assert row_a["annotations"] - row_b["annotations"] == 2
    today = time.strftime("%Y-%m-%d")
    day_b = next(d for d in before["daily"] if d["date"] == today)
    day_a = next(d for d in after["daily"] if d["date"] == today)
    assert day_a["annotations"] - day_b["annotations"] == 2


# --- fix round 1: consensus, acceptance, honeypot privacy --------------------------------

def draft_assignments(client, auth, project, job_id: str, plans: dict[str, list[dict]]) -> dict:
    """Autosave + submit one draft per assignee, in job-detail order; returns the refreshed detail."""
    who = {auth[k]["id"]: k for k in ("admin", "labeler", "reviewer")}
    det = client.get(f"{project['labels']}/consensus/{job_id}").json()
    for im in det["images"]:
        for ann, assignee in zip(plans[im["image_id"]], im["assignees"], strict=True):
            key = who[assignee["user_id"]]
            assert save(client, auth, key, im["image_id"], [ann]).status_code == 200
            r = submit(client, auth, key, project["labels"], job_id, im["image_id"], [ann])
            assert r.status_code == 200, r.text
    return client.get(f"{project['labels']}/consensus/{job_id}").json()


def test_merge_without_majority_keeps_image_and_exposes_drafts(client, auth, project):
    """C1: a tie is not a majority — keep the image, flag it, and let the reviewer read the drafts."""
    agree = upload_image(client, project, "consensus-agree.jpg", (30, 30, 30))
    split = upload_image(client, project, "consensus-split.jpg", (31, 31, 31))
    for img in (agree, split):
        assign(img, auth["labeler"]["id"])
    person = project["classes"]["person"]
    r = client.post(f"{project['labels']}/consensus", json={"image_ids": [agree, split], "k": 2})
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]
    try:
        det = draft_assignments(client, auth, project, job_id, {
            agree: [box(person, 0.2, 0.2, aid="agree-a"), box(person, 0.2, 0.2, aid="agree-b")],
            split: [box(person, 0.05, 0.05, aid="left"), box(person, 0.75, 0.75, aid="right")],
        })
        assert det["status"] == "ready"
        out = client.post(f"{project['labels']}/consensus/{job_id}/merge")
        assert out.status_code == 200, out.text
        body = out.json()
        assert body["merged"] == 1 and body["status"] == "merged"
        assert body["no_consensus"] == [split]
        assert len(stored(agree)) == 1 and stored(agree)[0]["classId"] == person
        assert stored(split) == []
        with SessionLocal() as db:
            img = db.get(Image, split)
            assert img.status != "review" and img.n_annotations == 0      # not cleared, not parked as review
        det = client.get(f"{project['labels']}/consensus/{job_id}").json()
        rows = {row["image_id"]: row for row in det["images"]}
        assert rows[agree]["no_consensus"] is False
        assert rows[split]["no_consensus"] is True
        drafts = {d["user_id"]: d["annotations"] for d in rows[split]["drafts"]}
        assert len(drafts) == 2
        assert {a["id"] for anns in drafts.values() for a in anns} == {"left", "right"}
    finally:
        drop_job(job_id, reset=[agree, split])


def test_merge_without_any_majority_is_rejected_and_keeps_the_job_open(client, auth, project):
    """C1: with no majority anywhere, merge fails closed instead of wiping the drafts."""
    img = upload_image(client, project, "consensus-tie.jpg", (32, 32, 32))
    assign(img, auth["labeler"]["id"])
    person = project["classes"]["person"]
    r = client.post(f"{project['labels']}/consensus", json={"image_ids": [img], "k": 2})
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]
    try:
        det = draft_assignments(client, auth, project, job_id, {
            img: [box(person, 0.05, 0.05, aid="far-left"), box(person, 0.75, 0.75, aid="far-right")],
        })
        assert det["status"] == "ready"
        r = client.post(f"{project['labels']}/consensus/{job_id}/merge")
        assert r.status_code == 409 and "strict majority" in r.json()["detail"]
        assert stored(img) == []
        with SessionLocal() as db:
            assert db.get(Image, img).status != "review"
        det = client.get(f"{project['labels']}/consensus/{job_id}").json()
        assert det["status"] == "ready" and det["submitted"] == 2
        assert det["images"][0]["no_consensus"] is True
        assert len(det["images"][0]["drafts"]) == 2
    finally:
        drop_job(job_id, reset=[img])


def test_ai_acceptance_is_per_image_state_not_per_autosave(client, auth, project):
    """I1: repeated autosaves of one AI box must not multiply the acceptance denominator."""
    with SessionLocal() as db:                            # a dedicated labeler keeps the rate unambiguous
        ws = db.scalar(select(Workspace).where(Workspace.slug == project["ws"]))
        user = User(email=f"accept-{uuid.uuid4().hex[:8]}@labeldesk.dev", name="Acceptance Tester", pw_hash="x")
        db.add(user)
        db.flush()
        db.add(Member(workspace_id=ws.id, user_id=user.id, role="annotator", created=4000.0))
        db.commit()
        uid = user.id
    h = {"Authorization": f"Bearer {issue_access(uid)}"}
    img = upload_image(client, project, "acceptance.jpg", (33, 33, 33))
    assign(img, uid)
    person = project["classes"]["person"]
    ai = box(person, 0.3, 0.3, aid="ai-fix", source="ultralytics:yolo26n")
    ai["confidence"] = 0.9
    seed(img, [ai])
    try:
        for _ in range(3):                                # autosave the same AI box three times
            r = client.put(f"/api/images/{img}/annotations", json={"annotations": [ai]}, headers=h)
            assert r.status_code == 200, r.text
        row, _ = labeler_row(client, auth, project, uid)
        assert row["ai_acceptance"] == 0.0                # seen once, not approved yet
        r = client.post(f"/api/images/{img}/review", json={"approved": True}, headers=auth["reviewer"]["h"])
        assert r.status_code == 200, r.text
        row, _ = labeler_row(client, auth, project, uid)
        assert row["ai_acceptance"] == 1.0                # one AI id seen, one kept — not 3/3 or 3/4
        r = client.put(f"/api/images/{img}/annotations",
                       json={"annotations": [box(person, 0.4, 0.4, aid="human-fix")]}, headers=h)
        assert r.status_code == 200, r.text
        row, _ = labeler_row(client, auth, project, uid)
        assert row["ai_acceptance"] == 0.0                # deleting the AI box leaves 0 %, never 0.75
    finally:
        with SessionLocal() as db:
            db.execute(sa_delete(LabelEvent).where(LabelEvent.user_id == uid))
            db.execute(sa_delete(Member).where(Member.user_id == uid))
            db.delete(db.get(User, uid))
            db.commit()


def test_audit_log_requires_reviewer(client, auth, project):
    """I2: the audit feed names honeypot images, so annotators must not read it."""
    img = upload_image(client, project, "audit-honeypot.jpg", (34, 34, 34))
    assign(img, auth["labeler"]["id"])
    seed(img, [box(project["classes"]["helmet"], 0.2, 0.2, aid="hp-audit")])
    r = client.post(f"{project['labels']}/honeypots", json={"image_id": img}, headers=auth["reviewer"]["h"])
    assert r.status_code == 200, r.text
    hid = r.json()["id"]
    try:
        assert client.get(f"/api/ws/{project['ws']}/audit", headers=auth["labeler"]["h"]).status_code == 403
        # Task 26 moved the audit feed behind workspace.audit (owner/admin), not merely reviewer.
        rows = client.get(f"/api/ws/{project['ws']}/audit", headers=auth["admin"]["h"]).json()
        assert any(row["action"].startswith("labeling.honeypot") for row in rows)
    finally:
        client.delete(f"{project['labels']}/honeypots/{hid}", headers=auth["reviewer"]["h"])


def test_annotator_dataset_filters_do_not_reveal_honeypots(client, auth, project):
    """I2: the real count must not leak through annotated/min_ann/sort/class/board."""
    img = upload_image(client, project, "honeypot-filters.jpg", (35, 35, 35))
    assign(img, auth["labeler"]["id"])
    helmet = project["classes"]["helmet"]
    seed(img, [box(helmet, 0.05 * i, 0.05 * i, aid=f"hp-filter-{i}") for i in range(5)])
    with SessionLocal() as db:
        batch_id = db.get(Image, img).batch_id
    r = client.post(f"{project['labels']}/honeypots", json={"image_id": img}, headers=auth["reviewer"]["h"])
    assert r.status_code == 200, r.text
    hid = r.json()["id"]
    base = project["base"]

    def ids_of(query: str, who: str = "labeler") -> set[str]:
        return {x["id"] for x in client.get(f"{base}/images?limit=1000{query}",
                                            headers=auth[who]["h"]).json()["items"]}
    try:
        assert img in ids_of("")                                   # visible, but blanked
        assert img not in ids_of("&annotated=yes")
        assert img in ids_of("&annotated=no")
        assert img not in ids_of("&min_ann=1")
        assert img in ids_of("&max_ann=0")
        assert img not in ids_of(f"&class_id={helmet}")
        most = client.get(f"{base}/images?limit=1000&sort=most", headers=auth["labeler"]["h"]).json()["items"]
        assert most and most[0]["id"] != img                       # five hidden labels do not sort it first
        board = client.get(f"{base}/board", headers=auth["labeler"]["h"]).json()
        card = next(c for col in board["columns"].values() for c in col if c["batchId"] == batch_id)
        assert card["images"] == 1 and card["annotated"] == 0
        # reviewers still see the truth in the same filters
        assert img in ids_of("&annotated=yes", "reviewer")
        assert img in ids_of(f"&class_id={helmet}", "reviewer")
        row = next(x for x in client.get(f"{base}/images?limit=1000", headers=auth["labeler"]["h"]).json()["items"]
                   if x["id"] == img)
        assert row["annotationCount"] == 0 and row["annotated"] is False and row["classIds"] == []
    finally:
        client.delete(f"{project['labels']}/honeypots/{hid}", headers=auth["reviewer"]["h"])


def test_honeypot_on_unassigned_image_is_assigned_and_attemptable(client, auth, project):
    """I3: creating a honeypot on an unassigned image must put it in a labeler's queue."""
    img = upload_image(client, project, "honeypot-unassigned.jpg", (36, 36, 36))
    with SessionLocal() as db:
        assert db.get(Image, img).assignee_id is None
    seed(img, [box(project["classes"]["person"], 0.25, 0.25, aid="hp-unassigned")])
    r = client.post(f"{project['labels']}/honeypots", json={"image_id": img}, headers=auth["reviewer"]["h"])
    assert r.status_code == 200, r.text
    item = r.json()
    hid = item["id"]
    try:
        assert item["needs_assignee"] is False
        with SessionLocal() as db:
            assert db.get(Image, img).assignee_id == auth["labeler"]["id"]
        view = client.get(f"/api/images/{img}", headers=auth["labeler"]["h"])
        assert view.status_code == 200, view.text
        assert view.json()["annotations"] == []
        r = save(client, auth, "labeler", img, [box(project["classes"]["person"], 0.25, 0.25, aid="try")])
        assert r.status_code == 200 and r.json()["status"] == "honeypot"
        items = client.get(f"{project['labels']}/honeypots", headers=auth["reviewer"]["h"]).json()["items"]
        assert next(x for x in items if x["id"] == hid)["attempts"] == 1
    finally:
        client.delete(f"{project['labels']}/honeypots/{hid}", headers=auth["reviewer"]["h"])


def test_consensus_drafts_are_capped(client, auth, project):
    """I5: a draft cannot carry an unbounded annotation list into the merge pass."""
    img = upload_image(client, project, "consensus-cap.jpg", (37, 37, 37))
    assign(img, auth["labeler"]["id"])
    person = project["classes"]["person"]
    r = client.post(f"{project['labels']}/consensus", json={"image_ids": [img], "k": 2})
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]
    try:
        cap = labeling.MAX_DRAFT_ANNOTATIONS
        too_many = [box(person, 0.01 * i, 0.01, aid=f"cap{i}") for i in range(cap + 1)]
        r = save(client, auth, "admin", img, too_many)
        assert r.status_code == 413 and str(cap) in r.json()["detail"]
        r = submit(client, auth, "admin", project["labels"], job_id, img, too_many)
        assert r.status_code == 413 and str(cap) in r.json()["detail"]
    finally:
        drop_job(job_id, reset=[img])


def test_merge_large_input_is_bounded():
    """I5: class/spatial bucketing keeps a 4 000-annotation merge well under a second-scale pass."""
    sets = []
    for s in range(10):
        anns = []
        for gx in range(20):
            for gy in range(20):
                anns.append(box("person", gx / 20, gy / 20, 0.04, 0.04, aid=f"s{s}-{gx}-{gy}"))
        sets.append(anns)
    started = time.perf_counter()
    merged = labeling.merge_sets(sets)
    elapsed = time.perf_counter() - started
    assert len(merged) == 400
    assert elapsed < 5.0

