"""R1 / I15 residual: every endpoint that signs a held-out eval image or returns the eval report
stays behind ``project.models`` (manager/reviewer)."""

import os
import uuid

os.environ.setdefault("LD_WORKER_TOKEN", "test-worker-token-0123456789abcdef")
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Image, Job, Member, Project, ProjectMember, TrainedModel, User, Version, Workspace
from app.security import hash_password
from app.services import insights

WS = "labeldesk-demo"
HELD_OUT = "held-out-other-labeler.jpg"


def _login(email, pw="demo1234"):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return c


def _eval(files: list[str]) -> dict:
    """The slice of a stored eval report that carries per-image names and signed-URL inputs."""
    return {
        "split": "test",
        "note": "",
        "iou": "bbox",
        "coco": {"AP": 0.5, "AP50": 0.7},
        "per_class": [{"class": "person", "AP": 0.5, "AP50": 0.7}],
        "pr_curve": [{"recall": 0.5, "precision": 0.8}],
        "f1_best": {"conf": 0.4, "f1": 0.66},
        "confusion": {"labels": ["person", "background"], "matrix": [[1, 0], [0, 1]],
                      "images": [[files[:1]], [files[1:]]]},
        "worst": files[:1],
        "detections": [{"file": f, "width": 32, "height": 32,
                        "gt": [{"cls": "person", "bbox": [1, 1, 8, 8]}],
                        "pred": [{"cls": "person", "conf": 0.9, "bbox": [1, 1, 8, 8]}]}
                       for f in files],
        "split_images": len(files),
    }


@pytest.fixture(scope="module")
def case():
    insights.clear_cache()
    with TestClient(app):
        slug = f"r1-eval-gate-{uuid.uuid4().hex[:8]}"
        with SessionLocal() as db:
            ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
            p = Project(workspace_id=ws.id, slug=slug, name=slug, type="object-detection", settings={})
            db.add(p)
            db.flush()
            labeler = db.scalar(select(User).where(User.email == "labeler@labeldesk.dev"))
            reviewer = db.scalar(select(User).where(User.email == "reviewer@labeldesk.dev"))
            viewer = User(id="u" + uuid.uuid4().hex[:8], email=f"viewer-{uuid.uuid4().hex[:8]}@x.io",
                          name="Vi Viewer", pw_hash=hash_password("viewerpass1"), email_verified=1.0)
            db.add(viewer)
            db.flush()
            db.add_all([
                Member(workspace_id=ws.id, user_id=viewer.id, role="annotator"),
                ProjectMember(project_id=p.id, user_id=labeler.id, role="labeler"),
                ProjectMember(project_id=p.id, user_id=reviewer.id, role="reviewer"),
                ProjectMember(project_id=p.id, user_id=viewer.id, role="viewer"),
            ])
            # a real held-out image row so the eval file name is not the only leak
            db.add(Image(project_id=p.id, name=HELD_OUT, sha256="b" * 64, width=32, height=32,
                         path=f"r1-eval-gate/{HELD_OUT}", thumb=f"r1-eval-gate/{HELD_OUT}",
                         split="test", status="done", assignee_id=reviewer.id))
            v = Version(project_id=p.id, number=1, name="v1", status="ready",
                        stats={"splits": {"test": 2}, "classes": {"person": 2}})
            db.add(v)
            db.flush()
            models = []
            for i in range(2):
                m = TrainedModel(workspace_id=ws.id, project_id=p.id, version_id=v.id, name=f"run-{i}",
                                 arch="yolo26n", variant="yolo26n", task="detect", status="ready",
                                 family="ultralytics", classes=["person"],
                                 metrics={"map50": 0.7, "eval": _eval([HELD_OUT, "second.jpg"])})
                db.add(m)
                models.append(m)
            db.flush()
            job = Job(workspace_id=ws.id, project_id=p.id, kind="train", status="done",
                      params={"model": models[0].id, "epochs": 3},
                      result={"model_id": models[0].id, "eval": _eval([HELD_OUT, "second.jpg"]),
                              "stages": {"train": {"status": "done"}}})
            db.add(job)
            db.commit()
            ids = {"project": p.id, "version": v.id, "job": job.id,
                   "models": [m.id for m in models], "viewer": viewer.email}
        yield {"slug": slug, **ids}
        with SessionLocal() as db:
            db.execute(sa_delete(ProjectMember).where(ProjectMember.project_id == ids["project"]))
            db.execute(sa_delete(Image).where(Image.project_id == ids["project"]))
            db.execute(sa_delete(TrainedModel).where(TrainedModel.project_id == ids["project"]))
            db.execute(sa_delete(Job).where(Job.project_id == ids["project"]))
            db.execute(sa_delete(Version).where(Version.project_id == ids["project"]))
            db.execute(sa_delete(Project).where(Project.id == ids["project"]))
            db.commit()
            viewer = db.scalar(select(User).where(User.email == ids["viewer"]))
            if viewer:
                db.execute(sa_delete(Member).where(Member.user_id == viewer.id))
                db.execute(sa_delete(User).where(User.id == viewer.id))
                db.commit()
        insights.clear_cache()


def _url(case, path: str) -> str:
    return f"/api/ws/{WS}/projects/{case['slug']}/insights{path}"


@pytest.mark.parametrize("path", [
    "/training",
    "/models/{mid}",
    "/models/{mid}/detections?files=" + HELD_OUT,
    "/compare?models={m1},{m2}",
])
@pytest.mark.parametrize("who", ["labeler", "viewer"])
def test_eval_endpoints_reject_readers_without_project_models(case, path, who):
    email, pw = ("labeler@labeldesk.dev", "demo1234") if who == "labeler" else (case["viewer"], "viewerpass1")
    mid, m2 = case["models"]
    r = _login(email, pw).get(_url(case, path.format(mid=mid, m1=mid, m2=m2)))
    assert r.status_code == 403, r.text


@pytest.mark.parametrize("path", [
    "/models/{mid}",
    "/models/{mid}/detections?files=" + HELD_OUT,
])
def test_reviewer_still_reads_the_signed_eval_images(case, path):
    mid, m2 = case["models"]
    r = _login("reviewer@labeldesk.dev").get(_url(case, path.format(mid=mid, m1=mid, m2=m2)))
    assert r.status_code == 200, r.text
    assert "/api/files/versions/" in r.text and "sig=" in r.text


@pytest.mark.parametrize("path", ["/training", "/compare?models={m1},{m2}"])
def test_reviewer_still_reads_training_and_compare(case, path):
    mid, m2 = case["models"]
    r = _login("reviewer@labeldesk.dev").get(_url(case, path.format(mid=mid, m1=mid, m2=m2)))
    assert r.status_code == 200, r.text


def test_project_jobs_hide_the_eval_report_from_labelers(case):
    url = f"/api/ws/{WS}/projects/{case['slug']}/jobs"
    lean = _login("labeler@labeldesk.dev").get(url).json()
    row = next(j for j in lean if j["id"] == case["job"])
    assert "params" not in row and "eval" not in (row.get("result") or {})
    assert row["kind"] == "train" and row["status"] == "done"

    detail = _login("labeler@labeldesk.dev").get(f"{url}/{case['job']}").json()
    assert "eval" not in (detail.get("result") or {})
    assert "params" not in detail

    full = _login("reviewer@labeldesk.dev").get(f"{url}/{case['job']}").json()
    assert full["params"]["epochs"] == 3
    assert full["result"]["eval"]["detections"][0]["file"] == HELD_OUT


def test_workspace_jobs_hide_the_eval_report_from_labelers(case):
    url = f"/api/ws/{WS}/jobs"
    lean = _login("labeler@labeldesk.dev").get(url).json()
    row = next(j for j in lean if j["id"] == case["job"])
    assert "params" not in row and "eval" not in (row.get("result") or {})
    assert row["project"] == case["slug"]

    full = _login("reviewer@labeldesk.dev").get(url).json()
    row = next(j for j in full if j["id"] == case["job"])
    assert row["result"]["eval"]["detections"][0]["file"] == HELD_OUT
