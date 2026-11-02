"""Home dashboard: workspace stats and the caller's own annotation/review queue."""

import os
import tempfile
import time

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-test-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Image, Member, Project, ProjectMember, TrainedModel, User, Version, Workspace
from app.security import issue_access

WS = "home-dashboard-ws"
OTHER_WS = "home-dashboard-other"


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def _user(db, email: str) -> User:
    u = User(email=email, name=email.split("@")[0], pw_hash="", email_verified=time.time())
    db.add(u)
    return u


@pytest.fixture(scope="module")
def data(c):
    """Two workspaces so the endpoint's tenancy filter is exercised, not just assumed."""
    with SessionLocal() as db:
        owner = _user(db, "home-owner@test.local")
        labeler = _user(db, "home-labeler@test.local")
        reviewer = _user(db, "home-reviewer@test.local")
        viewer = _user(db, "home-viewer@test.local")
        other = _user(db, "home-other@test.local")
        db.flush()

        ws = Workspace(slug=WS, name="Home Test", owner_id=owner.id)
        other_ws = Workspace(slug=OTHER_WS, name="Other", owner_id=other.id)
        db.add_all([ws, other_ws])
        db.flush()
        db.add_all([
            Member(workspace_id=ws.id, user_id=owner.id, role="admin"),
            Member(workspace_id=ws.id, user_id=labeler.id, role="annotator"),
            Member(workspace_id=ws.id, user_id=reviewer.id, role="reviewer"),
            Member(workspace_id=ws.id, user_id=viewer.id, role="billing"),
            Member(workspace_id=other_ws.id, user_id=other.id, role="admin"),
        ])

        alpha = Project(workspace_id=ws.id, slug="alpha", name="Alpha", settings={})
        beta = Project(workspace_id=ws.id, slug="beta", name="Beta", settings={})
        foreign = Project(workspace_id=other_ws.id, slug="foreign", name="Foreign", settings={})
        db.add_all([alpha, beta, foreign])
        db.flush()
        # Per-project roles override the workspace role in both directions: the workspace annotator
        # reviews alpha, and the workspace reviewer is only a labeler on beta.
        db.add_all([
            ProjectMember(project_id=alpha.id, user_id=labeler.id, role="reviewer"),
            ProjectMember(project_id=beta.id, user_id=reviewer.id, role="labeler"),
        ])

        db.add_all([
            Image(project_id=alpha.id, name="a1.jpg", sha256="a" * 64, width=10, height=10, path="a", thumb="a",
                  status="annotating", assignee_id=labeler.id, n_annotations=2),
            Image(project_id=alpha.id, name="a2.jpg", sha256="b" * 64, width=10, height=10, path="b", thumb="b",
                  status="review", n_annotations=1),
            Image(project_id=alpha.id, name="a3.jpg", sha256="c" * 64, width=10, height=10, path="c", thumb="c",
                  status="unassigned", n_annotations=0),
            # Beta holds a review item so a leaked workspace reviewer role would show up here.
            Image(project_id=beta.id, name="b1.jpg", sha256="d" * 64, width=10, height=10, path="d", thumb="d",
                  status="review", n_annotations=3),
            # Must never leak into the home dashboard of WS.
            Image(project_id=foreign.id, name="x.jpg", sha256="e" * 64, width=10, height=10, path="x", thumb="x",
                  status="review", n_annotations=99),
        ])
        db.flush()

        alpha_version = Version(project_id=alpha.id, number=1, status="ready")
        beta_version = Version(project_id=beta.id, number=1, status="ready")
        foreign_version = Version(project_id=foreign.id, number=1, status="ready")
        db.add_all([alpha_version, beta_version, foreign_version])
        db.flush()
        db.add_all([
            TrainedModel(workspace_id=ws.id, project_id=alpha.id, version_id=alpha_version.id, name="alpha-ready",
                         arch="yolo26", task="detect", status="ready"),
            TrainedModel(workspace_id=ws.id, project_id=beta.id, version_id=beta_version.id, name="beta-ready",
                         arch="yolo26", task="detect", status="ready"),
            TrainedModel(workspace_id=ws.id, project_id=alpha.id, version_id=alpha_version.id, name="alpha-training",
                         arch="yolo26", task="detect", status="training"),
            TrainedModel(workspace_id=other_ws.id, project_id=foreign.id, version_id=foreign_version.id,
                         name="foreign-ready", arch="yolo26", task="detect", status="ready"),
        ])
        db.commit()
        return {"owner": owner.id, "labeler": labeler.id, "reviewer": reviewer.id, "viewer": viewer.id}


def _headers(uid: str) -> dict:
    return {"Authorization": f"Bearer {issue_access(uid)}"}


def test_home_stats_are_workspace_scoped(c, data):
    r = c.get(f"/api/ws/{WS}/home", headers=_headers(data["owner"]))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stats"] == {"projects": 2, "images": 4, "annotations": 6, "models": 3, "deployments": 2}
    assert {w["project"] for w in body["waiting"]} == {"alpha", "beta"}
    assert body["totals"] == {"to_annotate": 0, "to_review": 2, "unassigned": 1}


def test_workspace_annotator_promoted_to_reviewer_sees_that_projects_queue(c, data):
    """The override must be resolved per project, not inherited from the workspace role."""
    body = c.get(f"/api/ws/{WS}/home", headers=_headers(data["labeler"])).json()
    assert body["totals"] == {"to_annotate": 1, "to_review": 1, "unassigned": 1}
    assert body["waiting"] == [{"project": "alpha", "project_name": "Alpha",
                                "to_annotate": 1, "to_review": 1, "unassigned": 1}]


def test_workspace_reviewer_demoted_to_labeler_hides_that_projects_review_queue(c, data):
    """Beta's review item stays hidden: the beta role is labeler even though the workspace role is reviewer."""
    body = c.get(f"/api/ws/{WS}/home", headers=_headers(data["reviewer"])).json()
    assert body["totals"] == {"to_annotate": 0, "to_review": 1, "unassigned": 1}
    assert [w["project"] for w in body["waiting"]] == ["alpha"]


def test_viewer_has_no_work_queue(c, data):
    body = c.get(f"/api/ws/{WS}/home", headers=_headers(data["viewer"])).json()
    assert body["totals"] == {"to_annotate": 0, "to_review": 0, "unassigned": 0}
    assert body["waiting"] == []


def test_home_requires_a_session(c):
    assert c.get(f"/api/ws/{WS}/home").status_code == 401
