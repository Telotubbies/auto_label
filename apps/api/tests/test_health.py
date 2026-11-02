"""Health check v2: object-size buckets, label quality, missing boxes (cached job), leakage, recommendations."""

import os
import random
import time
from types import SimpleNamespace

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import func, select

from app.config import DATA_DIR
from app.db import SessionLocal
from app.main import app
from app.models import Image, Job, Project, TrainedModel, User, Version, Workspace
from app.security import issue_access
from app.services import health, health_scan

WS = "labeldesk-demo"
NAME = "health-check-qa"


@pytest.fixture(scope="module")
def c():
    # mint the token directly: the shared login rate limit would starve later modules
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


def noise(w: int, h: int, seed: str) -> PImage.Image:
    """Distinct pixels per seed so pHash groups only the images we duplicate on purpose."""
    rng = random.Random(seed)
    return PImage.frombytes("RGB", (w, h), bytes(rng.getrandbits(8) for _ in range(w * h * 3)))


def add_image(
    pid: str,
    name: str,
    w: int,
    h: int,
    anns: list[dict],
    split: str = "train",
    im: PImage.Image | None = None,
) -> str:
    im = im or noise(w, h, name)
    rel = f"health/{name}.jpg"
    (DATA_DIR / rel).parent.mkdir(parents=True, exist_ok=True)
    im.save(DATA_DIR / rel, "JPEG", quality=90)
    with SessionLocal() as db:
        row = Image(
            project_id=pid,
            name=name,
            sha256=name,
            width=w,
            height=h,
            path=rel,
            thumb=rel,
            split=split,
            status="done",
            annotations=anns,
            n_annotations=len(anns),
        )
        db.add(row)
        db.commit()
        return row.id


def box(aid: str, x: float, y: float, w: float, h: float, cid: str = "c1") -> dict:
    return {
        "id": aid,
        "classId": cid,
        "shape": {"kind": "bbox", "x": x, "y": y, "w": w, "h": h},
    }


def test_size_buckets_scale_with_imgsz(project):
    pid = project["id"]
    add_image(
        pid,
        "bucket-mid",
        640,
        640,
        [box("b1", 0.4, 0.4, 0.1, 0.1), box("b2", 0.1, 0.1, 0.01, 0.01)],
    )
    with SessionLocal() as db:
        p = db.get(Project, pid)
        at640 = health.checks(db, p, imgsz=640)["size_buckets"]
        at1280 = health.checks(db, p, imgsz=1280)["size_buckets"]
    # 0.1 x 0.1 of a 640 px image = 64 x 64 px (medium); at 1280 it is 128 x 128 px (large).
    assert at640 == {"small": 1, "medium": 1, "large": 0}
    assert at1280 == {"small": 1, "medium": 0, "large": 1}


def test_label_quality_flags_tiny_and_oob(project):
    pid = project["id"]
    add_image(
        pid,
        "quality",
        640,
        640,
        [
            box("tiny", 0.2, 0.2, 0.002, 0.002),
            box("oob", -0.05, 0.1, 0.2, 0.2),
            box("zero", 0.5, 0.5, 0, 0.1),
            box("dup-a", 0.6, 0.6, 0.1, 0.1),
            box("dup-b", 0.6, 0.6, 0.1, 0.1),
        ],
    )
    with SessionLocal() as db:
        p = db.get(Project, pid)
        found = health.checks(db, p)["label_quality"]
    kinds = {f["annotation_id"]: f["kind"] for f in found}
    assert kinds["tiny"] == "tiny"
    assert kinds["oob"] == "out_of_bounds"
    assert kinds["zero"] == "zero_area"
    assert kinds["dup-b"] == "duplicate"
    assert all(f["image_id"] for f in found)


def test_missing_box_found_when_model_predicts_unlabeled_object(project, monkeypatch):
    pid = project["id"]
    image_id = add_image(pid, "missing", 333, 333, [box("gt", 0.1, 0.1, 0.2, 0.2)])
    with SessionLocal() as db:
        p = db.get(Project, pid)
        v = Version(project_id=pid, number=99, name="health", status="ready", stats={})
        db.add(v)
        db.flush()
        m = TrainedModel(
            workspace_id=p.workspace_id,
            project_id=pid,
            version_id=v.id,
            name="health model",
            arch="yolo26n",
            task="detect",
            status="ready",
            weights="fake.pt",
            metrics={"eval": {"f1_best": {"conf": 0.55}}},
        )
        db.add(m)
        db.commit()
        model_id = m.id

    calls: list[dict] = []

    def predict(im, **kw):
        calls.append(kw)
        if im.size != (333, 333):  # only the target image produces detections
            return {
                "predictions": [],
                "image": {"width": im.width, "height": im.height},
            }
        return {
            "predictions": [
                # unlabeled object: centre 0.5, 0.5, size 0.2 -> no overlap with the GT box
                {
                    "class": "person",
                    "confidence": 0.9,
                    "x": 166.5,
                    "y": 166.5,
                    "width": 66.6,
                    "height": 66.6,
                },
                # matches the GT box at 0.1..0.3 -> not missing
                {
                    "class": "person",
                    "confidence": 0.8,
                    "x": 66.6,
                    "y": 66.6,
                    "width": 66.6,
                    "height": 66.6,
                },
                # below the model threshold -> ignored
                {
                    "class": "person",
                    "confidence": 0.2,
                    "x": 300,
                    "y": 300,
                    "width": 20,
                    "height": 20,
                },
            ],
            "image": {"width": im.width, "height": im.height},
        }

    def fake_resolve(ref, db, workspace_id=None):
        assert ref == f"trained:{model_id}" and workspace_id
        return SimpleNamespace(predict=predict)

    monkeypatch.setattr(health_scan, "resolve", fake_resolve)
    with SessionLocal() as db:
        p = db.get(Project, pid)
        result = health.scan_health(db, p)
        found = result["checks"]["missing_boxes"]
        assert calls and calls[0]["conf"] == pytest.approx(0.55)
        assert [x["image_id"] for x in found] == [image_id]
        assert found[0]["class"] == "person"
        assert found[0]["box"] == pytest.approx([0.4, 0.4, 0.2, 0.2], abs=1e-4)
        # the scan is cached: reading checks() must not run inference again
        calls.clear()
        db.add(
            Job(
                workspace_id=p.workspace_id,
                project_id=pid,
                kind="health",
                status="done",
                result=result,
            )
        )
        db.commit()
        cached = health.checks(db, p)["missing_boxes"]
    assert calls == []
    assert cached == found


def test_model_sourced_box_does_not_hide_a_miss(project, monkeypatch):
    """A trained/SAM box is not ground truth: the same predicted box is still a miss over it."""
    pid = project["id"]
    human = add_image(
        pid,
        "gt-human",
        334,
        334,
        [{**box("h1", 0.1, 0.1, 0.2, 0.2), "source": "human"}],
    )
    model_made = add_image(
        pid,
        "gt-trained",
        335,
        335,
        [{**box("m1", 0.1, 0.1, 0.2, 0.2), "source": "trained:abc"}],
    )

    def predict(im, **kw):
        if im.size not in ((334, 334), (335, 335)):
            return {"predictions": []}
        return {
            "predictions": [
                {
                    "class": "person",
                    "confidence": 0.9,
                    "x": im.width * 0.2,
                    "y": im.height * 0.2,
                    "width": im.width * 0.2,
                    "height": im.height * 0.2,
                }
            ]
        }

    monkeypatch.setattr(health_scan, "resolve", lambda *a, **k: SimpleNamespace(predict=predict))
    with SessionLocal() as db:
        p = db.get(Project, pid)
        found = health.scan_health(db, p)["checks"]["missing_boxes"]
    assert [x["image_id"] for x in found] == [model_made] and human not in [x["image_id"] for x in found]


def test_duplicate_check_ignores_model_sourced_boxes(project, monkeypatch):
    pid = project["id"]
    add_image(
        pid,
        "dup-model",
        320,
        320,
        [
            {**box("dm-a", 0.5, 0.5, 0.1, 0.1), "source": "sam3"},
            {**box("dm-b", 0.5, 0.5, 0.1, 0.1), "source": "trained:abc"},
        ],
    )
    add_image(
        pid,
        "dup-human",
        320,
        320,
        [box("dh-a", 0.5, 0.5, 0.1, 0.1), box("dh-b", 0.5, 0.5, 0.1, 0.1)],
    )
    monkeypatch.setattr(
        health_scan,
        "resolve",
        lambda *a, **k: SimpleNamespace(predict=lambda im, **kw: {"predictions": []}),
    )
    with SessionLocal() as db:
        p = db.get(Project, pid)
        flags = health.compute_checks(db, p)["label_quality"]
    assert {f["annotation_id"] for f in flags if f["kind"] == "duplicate"} >= {"dh-b"}
    assert not {f["annotation_id"] for f in flags if f["kind"] == "duplicate"} & {
        "dm-a",
        "dm-b",
    }


def test_recommendation_for_small_objects():
    recs = health.recommendations(
        {
            "size_buckets": {"small": 41, "medium": 30, "large": 29},
            "label_quality": [],
            "missing_boxes": [],
            "leakage_pairs": 0,
        }
    )
    hit = next(r for r in recs if r["key"] == "imgsz")
    assert hit["suggest"] == {"imgsz": 1024}
    assert "41" in hit["message"] and "1024" in hit["message"]


def test_leakage_pairs_from_phash_groups(project, monkeypatch):
    pid = project["id"]
    shared = noise(320, 320, "leak")
    add_image(
        pid,
        "leak-train",
        320,
        320,
        [box("l1", 0.2, 0.2, 0.2, 0.2)],
        split="train",
        im=shared,
    )
    add_image(
        pid,
        "leak-test",
        320,
        320,
        [box("l2", 0.2, 0.2, 0.2, 0.2)],
        split="test",
        im=shared,
    )
    monkeypatch.setattr(
        health_scan,
        "resolve",
        lambda *a, **k: SimpleNamespace(predict=lambda im, **kw: {"predictions": []}),
    )
    with SessionLocal() as db:
        p = db.get(Project, pid)
        scan = health.scan_health(db, p)
        assert scan["checks"]["leakage_pairs"] == 1
        db.add(
            Job(
                workspace_id=p.workspace_id,
                project_id=pid,
                kind="health",
                status="done",
                result=scan,
            )
        )
        db.commit()
        # analytics reads the count from the job row and never groups images itself
        monkeypatch.setattr(
            health_scan.versioning,
            "phash_groups",
            lambda rows: (_ for _ in ()).throw(AssertionError("no phash in the request")),
        )
        assert health.checks(db, p)["leakage_pairs"] == 1


def test_dataset_grid_filters_for_click_through(c, project):
    pid = project["id"]
    add_image(pid, "huge-2000", 2000, 2000, [])
    add_image(pid, "tall-100x200", 100, 200, [])
    add_image(pid, "wide-300x200", 300, 200, [])
    add_image(pid, "very-wide-500x200", 500, 200, [])
    base = f"/api/ws/{WS}/projects/{project['slug']}/images"
    assert c.get(base, params={"min_mp": 4}).json()["total"] == 1
    assert c.get(base, params={"min_ar": 0, "max_ar": 0.8}).json()["total"] == 1
    assert c.get(base, params={"min_ar": 1.25, "max_ar": 2}).json()["total"] == 1
    assert c.get(base, params={"min_ar": 2}).json()["total"] == 1
    assert c.get(base, params={"min_ann": 0, "max_ann": 0}).json()["total"] == 4
    assert c.get(base, params={"min_ann": 20}).json()["total"] == 0


def test_analytics_merges_checks_and_recommendations(c, project):
    r = c.get(f"/api/ws/{WS}/projects/{project['slug']}/analytics")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body["checks"]) == {
        "imgsz",
        "size_buckets",
        "label_quality",
        "missing_boxes",
        "leakage_pairs",
    }
    assert isinstance(body["recommendations"], list)
    assert isinstance(body["checks"]["missing_boxes"], list)
    assert isinstance(body["health_stale"], bool)


def test_analytics_never_runs_inference_inline(c, project, monkeypatch):
    """The missing-box scan is a background job: the analytics request must not resolve a model."""

    def boom(*a, **kw):
        raise AssertionError("analytics must not run inference inline")

    monkeypatch.setattr(health_scan, "resolve", boom)
    r = c.get(f"/api/ws/{WS}/projects/{project['slug']}/analytics")
    assert r.status_code == 200, r.text
    assert "checks" in r.json()


def test_malformed_annotations_do_not_break_checks(project):
    """Remote workers and hand-edited JSON can store annotations the UI never writes."""
    pid = project["id"]
    add_image(
        pid,
        "malformed",
        320,
        320,
        [
            None,
            "junk",
            {"shape": "bbox"},
            {"shape": {"kind": "bbox", "x": "a", "y": 0, "w": 1, "h": 1}},
            {
                "id": "ok",
                "classId": "c1",
                "shape": {"kind": "bbox", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2},
            },
        ],
    )
    with SessionLocal() as db:
        p = db.get(Project, pid)
        found = health.checks(db, p, auto_scan=False)
    assert sum(found["size_buckets"].values()) >= 1
    assert all(f["kind"] for f in found["label_quality"])


def test_missing_box_conf_falls_back_to_04(c, monkeypatch):
    """No eval metrics: the scan uses the historical 0.4 default (PM ruling)."""
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        p = Project(
            workspace_id=ws.id,
            slug="health-fallback-qa",
            name="health-fallback-qa",
            settings={},
        )
        db.add(p)
        db.commit()
        pid = p.id
    add_image(pid, "fallback-img", 340, 340, [])
    with SessionLocal() as db:
        p = db.get(Project, pid)
        v = Version(project_id=pid, number=1, name="health-fallback", status="ready", stats={})
        db.add(v)
        db.flush()
        db.add(
            TrainedModel(
                workspace_id=p.workspace_id,
                project_id=pid,
                version_id=v.id,
                name="fallback model",
                arch="yolo26n",
                task="detect",
                status="ready",
                weights="fake.pt",
                metrics={},
            )
        )
        db.commit()
        calls: list[dict] = []
        monkeypatch.setattr(
            health_scan,
            "resolve",
            lambda ref, db, workspace_id=None: SimpleNamespace(
                predict=lambda im, **kw: calls.append(kw) or {"predictions": []}
            ),
        )
        health.scan_health(db, p)
    assert calls and calls[0]["conf"] == pytest.approx(0.4)


def test_failed_health_job_does_not_trigger_a_second_scan(c):
    """A failed scan for the same dataset/model must not be retried by GET /analytics polling."""
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        p = Project(workspace_id=ws.id, slug="health-failed-qa", name="health-failed-qa", settings={})
        db.add(p)
        db.commit()
        pid = p.id
    add_image(pid, "failed-img", 341, 341, [])
    with SessionLocal() as db:
        p = db.get(Project, pid)
        v = Version(project_id=pid, number=1, name="failed", status="ready", stats={})
        db.add(v)
        db.flush()
        m = TrainedModel(
            workspace_id=p.workspace_id,
            project_id=pid,
            version_id=v.id,
            name="failed model",
            arch="yolo26n",
            task="detect",
            status="ready",
            weights="fake.pt",
            metrics={},
        )
        db.add(m)
        db.flush()
        db.add(
            Job(
                workspace_id=p.workspace_id,
                project_id=pid,
                kind="health",
                status="failed",
                params={"imgsz": 640, "signature": health.signature(db, p), "model_id": m.id},
            )
        )
        db.commit()
        count = select(func.count(Job.id)).where(Job.project_id == pid, Job.kind == "health")
        before = db.scalar(count)
        out = health.checks(db, p)
        after = db.scalar(count)
    assert after == before
    assert out["missing_boxes"] == []


def test_health_job_endpoint_runs_scan_and_caches_result(c):
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        p = Project(
            workspace_id=ws.id,
            slug="health-job-api",
            name="health-job-api",
            settings={},
        )
        db.add(p)
        db.commit()
    base = f"/api/ws/{WS}/projects/{p.slug}"

    r = c.post(f"{base}/health", json={"imgsz": 640})
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["kind"] == "health" and job["status"] in ("queued", "running")

    deadline = time.time() + 20
    while time.time() < deadline:
        job = c.get(f"{base}/jobs/{job['id']}").json()
        if job["status"] in ("done", "failed", "cancelled"):
            break
        time.sleep(0.1)
    assert job["status"] == "done", job
    assert "signature" in job["result"]

    body = c.get(f"{base}/analytics").json()
    assert body["checks"]["missing_boxes"] == []  # no ready model yet
    assert body["health_job"]["id"] == job["id"]
    assert body["health_stale"] is False
