"""Suspect-label queue: ObjectLab-style scoring, cached scan output, feedback statistics, flag gating."""

import os
import time
import uuid

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import (
    Audit, Image, Job, LabelClass, Member, Project, SuspectFeedback, TrainedModel, User, Version, Workspace, now,
)
from app.security import issue_access
from app.services import flags, health, health_scan, suspect_queue, suspects
from conftest import login

WS = "labeldesk-demo"
FLAG = "task_28"


def gt(aid: str, cid: str, x: float, y: float, w: float, h: float, source: str | None = "human") -> dict:
    ann = {"id": aid, "classId": cid, "shape": {"kind": "bbox", "x": x, "y": y, "w": w, "h": h}}
    if source is not None:
        ann["source"] = source
    return ann


def pred(cls: str, cx: float, cy: float, w: float, h: float, conf: float) -> dict:
    """Unified prediction schema: centre x/y and size in pixels."""
    return {"class": cls, "confidence": conf, "x": cx, "y": cy, "width": w, "height": h}


def test_wrong_class_box_is_flagged_above_a_shifted_box():
    anns = [gt("a1", "c1", 0.1, 0.1, 0.2, 0.2)]
    # same box, different class -> a confident classification error
    items = suspects.score_image(anns, [pred("dog", 20, 20, 20, 20, 0.9)], {"c1": "person"}, 100, 100)
    assert [i["kind"] for i in items] == ["wrong_class"]
    assert items[0]["annotation_id"] == "a1"
    assert items[0]["predicted_class"] == "dog"
    assert items[0]["class"] == "person"
    assert items[0]["score"] == pytest.approx(0.9)

    # same class, box shifted by 0.1 at 100 px -> IoU 0.333
    shifted = suspects.score_image(
        [gt("a2", "c1", 0.1, 0.1, 0.2, 0.2)], [pred("person", 30, 20, 20, 20, 0.8)], {"c1": "person"}, 100, 100
    )
    assert [i["kind"] for i in shifted] == ["shifted_box"]
    assert shifted[0]["predicted_class"] == "person"
    assert 0 < shifted[0]["score"] < items[0]["score"]


def test_well_matched_label_is_not_queued():
    items = suspects.score_image(
        [gt("ok", "c1", 0.1, 0.1, 0.2, 0.2)], [pred("person", 20, 20, 20, 20, 0.95)], {"c1": "person"}, 100, 100
    )
    assert items == []


def test_extra_box_needs_a_model_prediction_to_score():
    anns = [gt("lonely", "c1", 0.6, 0.6, 0.2, 0.2)]
    # no detections at all: the model has no opinion, so the label is not queued
    assert suspects.score_image(anns, [], {"c1": "person"}, 100, 100) == []
    # a confident detection elsewhere: the label region has nothing
    items = suspects.score_image(anns, [pred("person", 20, 20, 20, 20, 0.7)], {"c1": "person"}, 100, 100)
    assert [i["kind"] for i in items] == ["extra_box"]
    assert 0 < items[0]["score"] < 0.4


def test_model_made_and_malformed_annotations_are_ignored():
    anns = [
        gt("auto", "c1", 0.1, 0.1, 0.2, 0.2, source="sam3"),
        {"id": "junk", "classId": "c1", "shape": "bbox"},
        gt("keep", "c1", 0.6, 0.6, 0.2, 0.2),
    ]
    items = suspects.score_image(anns, [pred("person", 20, 20, 20, 20, 0.9)], {"c1": "person"}, 100, 100)
    assert [i["annotation_id"] for i in items] == ["keep"]


def test_unknown_class_id_still_scores_geometry():
    """Legacy annotations can reference a deleted class; geometry is still reviewable."""
    items = suspects.score_image(
        [gt("x", "gone", 0.1, 0.1, 0.2, 0.2)], [pred("person", 30, 20, 20, 20, 0.8)], {}, 100, 100
    )
    assert [i["kind"] for i in items] == ["shifted_box"]
    assert items[0]["class"] == ""


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        client.headers.update(login(client))
        yield client


CREATED: list[str] = []


@pytest.fixture(scope="module", autouse=True)
def _release_projects():
    """Free-plan project quota is shared by every module: hand the fixture projects back."""
    yield
    with SessionLocal() as db:
        for pid in CREATED:
            db.query(SuspectFeedback).filter_by(project_id=pid).delete()
            db.query(Job).filter_by(project_id=pid).delete()
            db.query(Image).filter_by(project_id=pid).delete()
            db.query(LabelClass).filter_by(project_id=pid).delete()
            db.query(Project).filter_by(id=pid).delete()
        db.commit()


def make_project(name: str) -> str:
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        p = Project(workspace_id=ws.id, slug=name, name=name, settings={})
        db.add(p)
        db.flush()
        db.add_all([LabelClass(project_id=p.id, name="person"), LabelClass(project_id=p.id, name="dog")])
        db.commit()
        CREATED.append(p.id)
        return p.id


def add_scan(project_id: str, items: list[dict], model_id: str | None = None, signature: list | None = None):
    with SessionLocal() as db:
        p = db.get(Project, project_id)
        db.add(
            Job(
                workspace_id=p.workspace_id,
                project_id=p.id,
                kind="health",
                status="done",
                result={
                    "signature": health_scan.signature(db, p) if signature is None else signature,
                    "model_id": model_id,
                    "suspect_labels": items,
                },
            )
        )
        db.commit()


def stub_model(monkeypatch, model_id: str = "m1"):
    monkeypatch.setattr(suspect_queue.health_scan, "latest_model", lambda db, p: SimpleNamespace(id=model_id, name="m"))


def test_queue_is_sorted_by_score_and_carries_feedback(monkeypatch):
    pid = make_project("suspects-sort")
    add_scan(
        pid,
        [
            {"annotation_id": "low", "image_id": "i1", "kind": "extra_box", "score": 0.2},
            {"annotation_id": "high", "image_id": "i2", "kind": "wrong_class", "score": 0.9},
        ],
        model_id="m1",
    )
    stub_model(monkeypatch)
    with SessionLocal() as db:
        p = db.get(Project, pid)
        assert suspect_queue.record_feedback(db, p, "low", "dismissed", user_id=None) is not None
        out = suspect_queue.queue(db, p)
    assert [i["annotation_id"] for i in out["items"]] == ["high", "low"]
    assert out["items"][1]["feedback"] == "dismissed"
    assert out["stats"]["reviewed"] == 1 and out["stats"]["dismissed"] == 1
    assert out["stale"] is False


def test_feedback_upserts_and_rejects_unknown_or_bad_values(monkeypatch):
    pid = make_project("suspects-feedback")
    add_scan(pid, [{"annotation_id": "a", "image_id": "i", "kind": "shifted_box", "score": 0.4}], model_id="m1")
    stub_model(monkeypatch)
    with SessionLocal() as db:
        p = db.get(Project, pid)
        assert suspect_queue.record_feedback(db, p, "a", "dismissed", user_id=None)
        assert suspect_queue.record_feedback(db, p, "a", "confirmed", user_id=None)
        out = suspect_queue.queue(db, p)
        assert out["items"][0]["feedback"] == "confirmed"
        assert out["stats"] == {
            "reviewed": 1,
            "confirmed": 1,
            "dismissed": 0,
            "precision": 1.0,
            "by_kind": {"shifted_box": {"confirmed": 1, "dismissed": 0}},
        }
        assert suspect_queue.record_feedback(db, p, "not-in-queue", "confirmed", user_id=None) is None
        with pytest.raises(ValueError):
            suspect_queue.record_feedback(db, p, "a", "maybe", user_id=None)


def test_one_verdict_per_annotation_survives_a_kind_change(monkeypatch):
    """A rescan may reclassify an annotation; the reviewer's one verdict must not count twice."""
    pid = make_project("suspects-rekind")
    add_scan(pid, [{"annotation_id": "a", "image_id": "i", "kind": "wrong_class", "score": 0.6}], model_id="m1")
    stub_model(monkeypatch)
    with SessionLocal() as db:
        p = db.get(Project, pid)
        assert suspect_queue.record_feedback(db, p, "a", "confirmed", user_id=None)
        job = db.scalar(select(Job).where(Job.project_id == p.id))
        job.result = {
            **job.result,
            "suspect_labels": [{"annotation_id": "a", "image_id": "i", "kind": "shifted_box", "score": 0.4}],
        }
        db.commit()
        out = suspect_queue.queue(db, p)
        assert out["items"][0]["feedback"] == "confirmed"
        assert suspect_queue.record_feedback(db, p, "a", "dismissed", user_id=None)
        out = suspect_queue.queue(db, p)
    assert out["items"][0]["feedback"] == "dismissed"
    assert out["stats"] == {
        "reviewed": 1,
        "confirmed": 0,
        "dismissed": 1,
        "precision": 0.0,
        "by_kind": {"shifted_box": {"confirmed": 0, "dismissed": 1}},
    }


def test_queue_totals_cover_the_whole_scan_not_just_the_page(monkeypatch):
    """A paged queue still reports how many suspects and open items the scan found."""
    pid = make_project("suspects-totals")
    add_scan(
        pid,
        [
            {"annotation_id": "a1", "image_id": "i1", "kind": "wrong_class", "score": 0.9},
            {"annotation_id": "a2", "image_id": "i2", "kind": "extra_box", "score": 0.2},
        ],
        model_id="m1",
    )
    stub_model(monkeypatch)
    with SessionLocal() as db:
        p = db.get(Project, pid)
        out = suspect_queue.queue(db, p, limit=1)
        assert len(out["items"]) == 1
        assert out["total"] == 2 and out["open"] == 2
        assert suspect_queue.record_feedback(db, p, "a1", "confirmed", user_id=None)
        out = suspect_queue.queue(db, p, limit=1)
    assert out["total"] == 2 and out["open"] == 1


def test_a_scan_that_never_scored_suspects_is_not_reported_as_clean(monkeypatch):
    """A pre-Task-28 health job has no suspect payload: that is unscored, never "no suspects"."""
    pid = make_project("suspects-legacy")
    with SessionLocal() as db:
        p = db.get(Project, pid)
        db.add(
            Job(
                workspace_id=p.workspace_id,
                project_id=p.id,
                kind="health",
                status="done",
                result={
                    "signature": health_scan.signature(db, p),
                    "model_id": "m1",
                    "checks": {"leakage_pairs": 0, "missing_boxes": []},
                },
            )
        )
        db.commit()
    stub_model(monkeypatch)
    with SessionLocal() as db:
        p = db.get(Project, pid)
        out = suspect_queue.queue(db, p)
        assert out["job_id"] is None  # the page must offer a scan instead of claiming agreement
        assert out["items"] == [] and out["total"] == 0
        assert suspect_queue.record_feedback(db, p, "a", "confirmed", user_id=None) is None


def test_scan_caches_suspect_labels_without_changing_health_checks(monkeypatch):
    """The Task 9 payload keeps its keys; suspects ride along in the cached job result."""
    pid = make_project("suspects-scan")
    with SessionLocal() as db:
        p = db.get(Project, pid)
        classes = {x.name: x.id for x in db.scalars(select(LabelClass).where(LabelClass.project_id == p.id))}
        db.add(
            Image(
                project_id=p.id,
                name="suspect-one",
                sha256="suspect-one",
                width=100,
                height=100,
                path="suspects/one.jpg",
                thumb="suspects/one.jpg",
                annotations=[gt("a1", classes["person"], 0.1, 0.1, 0.2, 0.2)],
                n_annotations=1,
            )
        )
        v = Version(project_id=p.id, number=1, name="v", status="ready", stats={})
        db.add(v)
        db.flush()
        db.add(
            TrainedModel(
                workspace_id=p.workspace_id,
                project_id=p.id,
                version_id=v.id,
                name="suspect model",
                arch="yolo26n",
                task="detect",
                status="ready",
                weights="fake.pt",
            )
        )
        db.commit()

    monkeypatch.setattr(
        health_scan,
        "resolve",
        lambda *a, **k: SimpleNamespace(predict=lambda im, **kw: {"predictions": [pred("dog", 20, 20, 20, 20, 0.9)]}),
    )
    monkeypatch.setattr(health_scan.imaging, "load", lambda path: SimpleNamespace(width=100, height=100))
    with SessionLocal() as db:
        p = db.get(Project, pid)
        scan = health.scan_health(db, p)
        assert scan["checks"]["missing_boxes"] == []
        assert [i["kind"] for i in scan["suspect_labels"]] == ["wrong_class"]
        assert scan["suspect_labels"][0]["image_id"]
        db.add(Job(workspace_id=p.workspace_id, project_id=p.id, kind="health", status="done", result=scan))
        db.commit()
        assert {"imgsz", "size_buckets", "label_quality", "missing_boxes", "leakage_pairs"} <= set(health.checks(db, p))
        out = suspect_queue.queue(db, p)
    assert [i["annotation_id"] for i in out["items"]] == ["a1"]


def test_scan_stops_at_the_missing_box_budget_on_an_unlabelled_dataset(monkeypatch):
    """A bulk upload with nothing labelled must not infer the whole dataset (Task 9's bound)."""
    pid = make_project("suspects-budget")
    calls: list[int] = []

    def predict(im, **kw):
        calls.append(1)
        return {"predictions": [pred("person", 20, 20, 20, 20, 0.9)]}

    monkeypatch.setattr(health_scan, "resolve", lambda *a, **k: SimpleNamespace(predict=predict))
    monkeypatch.setattr(health_scan.imaging, "load", lambda path: SimpleNamespace(width=100, height=100))
    rows = [
        SimpleNamespace(id=f"unlabelled-{i}", width=100, height=100, path="x.jpg", annotations=[])
        for i in range(health_scan.MISSING_LIMIT + 200)
    ]
    with SessionLocal() as db:
        p = db.get(Project, pid)
        missing, items = health_scan._model_checks(db, p, rows, SimpleNamespace(id="m1"), 0.4)
    assert len(missing) == health_scan.MISSING_LIMIT
    assert items == []
    assert len(calls) == health_scan.MISSING_LIMIT  # one inference pass, bounded like Task 9


def test_queue_endpoint_is_flag_gated_and_records_feedback(c, monkeypatch):
    before = c.get(f"/api/ws/{WS}/flags").json()
    assert before["enabled"].count(FLAG) == 0
    assert {"key": FLAG, "description": "Suspect-label queue on the dataset health page", "enabled": False} in before[
        "flags"
    ]
    assert FLAG in flags.FLAGS

    pid = make_project("suspects-api")
    with SessionLocal() as db:
        slug = db.get(Project, pid).slug
    base = f"/api/ws/{WS}/projects/{slug}"
    add_scan(
        pid,
        [{"annotation_id": "api-a", "image_id": "i", "kind": "extra_box", "score": 0.31, "class": "person"}],
        model_id="m1",
    )
    stub_model(monkeypatch)

    assert c.get(f"{base}/suspect-labels").status_code == 404  # flag off by default
    assert c.post(f"{base}/suspect-labels/api-a/feedback", json={"verdict": "confirmed"}).status_code == 404

    monkeypatch.setenv("LD_FLAGS_ON", FLAG)
    r = c.get(f"{base}/suspect-labels")
    assert r.status_code == 200, r.text
    body = r.json()
    assert [i["annotation_id"] for i in body["items"]] == ["api-a"]
    assert body["stats"]["reviewed"] == 0

    r = c.post(f"{base}/suspect-labels/api-a/feedback", json={"verdict": "confirmed"})
    assert r.status_code == 200, r.text
    assert r.json()["stats"]["confirmed"] == 1
    with SessionLocal() as db:
        row = db.scalar(select(Audit).where(Audit.action == "suspect.feedback", Audit.target == "api-a"))
        assert row is not None and row.meta["verdict"] == "confirmed"
    assert c.post(f"{base}/suspect-labels/nope/feedback", json={"verdict": "confirmed"}).status_code == 404
    assert c.post(f"{base}/suspect-labels/api-a/feedback", json={"verdict": "maybe"}).status_code == 422


@pytest.fixture(scope="module")
def other_world():
    """A second workspace with its own project, to prove the queue stays tenant-scoped."""
    tag = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        u = User(email=f"suspects-{tag}@example.test", name="Suspects Outsider", email_verified=now())
        db.add(u)
        db.flush()
        ws = Workspace(
            slug=f"suspects-{tag}",
            name="Suspects Fixture",
            owner_id=u.id,
            credits_period=time.strftime("%Y-%m"),
        )
        db.add(ws)
        db.flush()
        db.add(Member(workspace_id=ws.id, user_id=u.id, role="admin"))
        p = Project(workspace_id=ws.id, slug="suspects-other", name="Suspects Other", settings={})
        db.add(p)
        db.commit()
        return {"ws": ws.slug, "pid": p.id, "slug": p.slug, "token": issue_access(u.id)}


def test_queue_and_feedback_stay_inside_their_tenant(c, other_world, monkeypatch):
    """Mirror of the image-quality tenant test: neither another project nor another workspace sees this queue."""
    monkeypatch.setenv("LD_FLAGS_ON", FLAG)
    mine = make_project("suspects-tenant-mine")
    other_project = make_project("suspects-tenant-other-project")
    add_scan(mine, [{"annotation_id": "mine-a", "image_id": "i", "kind": "extra_box", "score": 0.6}], model_id="m1")
    add_scan(
        other_project,
        [{"annotation_id": "project-b", "image_id": "i", "kind": "extra_box", "score": 0.7}],
        model_id="m1",
    )
    add_scan(
        other_world["pid"],
        [{"annotation_id": "world-a", "image_id": "i", "kind": "extra_box", "score": 0.8}],
        model_id="m1",
    )
    stub_model(monkeypatch)
    with SessionLocal() as db:
        mine_slug = db.get(Project, mine).slug
        project_b_slug = db.get(Project, other_project).slug
    mine_base = f"/api/ws/{WS}/projects/{mine_slug}"
    project_b_base = f"/api/ws/{WS}/projects/{project_b_slug}"

    assert [i["annotation_id"] for i in c.get(f"{mine_base}/suspect-labels").json()["items"]] == ["mine-a"]
    assert [i["annotation_id"] for i in c.get(f"{project_b_base}/suspect-labels").json()["items"]] == ["project-b"]
    # a verdict cannot be posted against an id that only exists in another project's queue
    assert c.post(f"{mine_base}/suspect-labels/project-b/feedback", json={"verdict": "confirmed"}).status_code == 404

    other = TestClient(app)
    other.headers["Authorization"] = f"Bearer {other_world['token']}"
    world_base = f"/api/ws/{other_world['ws']}/projects/{other_world['slug']}"
    r = other.get(f"{world_base}/suspect-labels")
    assert r.status_code == 200, r.text
    assert [i["annotation_id"] for i in r.json()["items"]] == ["world-a"]
    # a non-member is refused at the workspace boundary on both routes
    assert other.get(f"{mine_base}/suspect-labels").status_code == 403
    assert other.post(
        f"{mine_base}/suspect-labels/mine-a/feedback", json={"verdict": "confirmed"}
    ).status_code == 403
    other.close()


def test_feedback_requires_a_reviewer(c, monkeypatch):
    """Reads follow the analytics pattern; a verdict changes shared statistics, so it needs the role."""
    pid = make_project("suspects-roles")
    with SessionLocal() as db:
        slug = db.get(Project, pid).slug
        labeler = db.scalar(select(User).where(User.email == "labeler@labeldesk.dev"))
    base = f"/api/ws/{WS}/projects/{slug}"
    add_scan(pid, [{"annotation_id": "r-a", "image_id": "i", "kind": "wrong_class", "score": 0.5}], model_id="m1")
    stub_model(monkeypatch)
    monkeypatch.setenv("LD_FLAGS_ON", FLAG)

    other = TestClient(app)
    other.headers["Authorization"] = f"Bearer {issue_access(labeler.id)}"
    assert other.get(f"{base}/suspect-labels").status_code == 200
    assert other.post(f"{base}/suspect-labels/r-a/feedback", json={"verdict": "confirmed"}).status_code == 403
    assert c.post(f"{base}/suspect-labels/r-a/feedback", json={"verdict": "confirmed"}).status_code == 200
    other.close()
