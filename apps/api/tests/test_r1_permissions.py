"""R1 tenancy/permission regressions: cross-project classes, viewer access, connector sync."""
import io
import json
import os
import uuid

os.environ.setdefault("LD_WORKER_TOKEN", "test-worker-token-0123456789abcdef")
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import Text, cast, select
from sqlalchemy.dialects import postgresql

from app.db import SessionLocal
from app.main import app
from app.models import (Connector, Image, Job, LabelClass, Member, Project, ProjectMember, TrainedModel, User, Version,
                        Workspace)
from app.security import hash_password

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/ws/{WS}/projects/{PR}"


def jpeg(color=(9, 9, 9)):
    b = io.BytesIO(); PImage.new("RGB", (32, 32), color).save(b, "JPEG"); return b.getvalue()


def _login(email, pw="demo1234"):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return c


@pytest.fixture(scope="module")
def admin():
    with TestClient(app):
        yield _login("demo@labeldesk.dev")


@pytest.fixture(scope="module")
def ids(admin):
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        p = db.scalar(select(Project).where(Project.slug == PR))
        v = Version(project_id=p.id, number=900 + int(suffix, 16) % 90, status="ready", stats={"splits": {"train": 4}})
        db.add(v); db.flush()
        m = TrainedModel(workspace_id=ws.id, project_id=p.id, version_id=v.id, name="r1-model",
                         arch="yolo26n", variant="yolo26n", task="detect", status="ready",
                         family="ultralytics", license="AGPL-3.0", weights="models/x/best.pt", classes=["person"])
        db.add(m); db.flush()
        viewer = User(id="u" + uuid.uuid4().hex[:12], email=f"viewer-{suffix}@x.io", name="Vera Viewer",
                      pw_hash=hash_password("longpassword1"), email_verified=1.0)
        manager = User(id="u" + uuid.uuid4().hex[:12], email=f"manager-{suffix}@x.io", name="Mana Manager",
                       pw_hash=hash_password("longpassword1"), email_verified=1.0)
        db.add_all([viewer, manager]); db.flush()
        db.add_all([
            Member(workspace_id=ws.id, user_id=viewer.id, role="member"),
            Member(workspace_id=ws.id, user_id=manager.id, role="member"),
            ProjectMember(project_id=p.id, user_id=viewer.id, role="viewer"),
            ProjectMember(project_id=p.id, user_id=manager.id, role="manager"),
        ])
        db.commit()
        out = {"version": v.id, "model": m.id, "viewer": viewer.email, "manager": manager.email,
               "ws": ws.id, "project": p.id}
    return out


@pytest.fixture(scope="module")
def viewer(ids):
    return _login(ids["viewer"], "longpassword1")


@pytest.fixture(scope="module")
def manager(ids):
    return _login(ids["manager"], "longpassword1")


def test_viewer_cannot_export_a_version(viewer, ids):
    r = viewer.post(f"{BASE}/versions/{ids['version']}/export", json={"format": "coco"})
    assert r.status_code == 403, r.text


def test_viewer_cannot_read_models_or_leaderboard(viewer, ids):
    for path in (f"{BASE}/models", f"{BASE}/leaderboard", f"{BASE}/models/{ids['model']}"):
        assert viewer.get(path).status_code == 403, path


def test_labeler_can_list_models_without_weights_or_metrics(ids):
    """I14/I15: label assist needs the ready list, but weights and eval stay behind project.models."""
    lab = _login("labeler@labeldesk.dev")
    r = lab.get(f"{BASE}/models")
    assert r.status_code == 200, r.text
    row = next((m for m in r.json() if m["id"] == ids["model"]), None)
    assert row is not None
    assert row["weightsUrl"] is None and row["metrics"] == {} and row["runtimeRefs"] == {}
    assert lab.get(f"{BASE}/models/{ids['model']}").status_code == 403


def test_labeler_model_list_drops_the_eval_report_inside_the_job(ids, admin):
    """I15: the lean list must not hand back the held-out eval report through job.result either."""
    with SessionLocal() as db:
        j = Job(workspace_id=ids["ws"], project_id=ids["project"], kind="train", status="done",
                params={"options": {"family": "ultralytics", "max_minutes": 5}},
                result={"stages": {"train": {"status": "done"}},
                        "eval": {"split": "test", "worst": [{"file": "held-out-secret.jpg"}],
                                 "confusion": {"images": {"a": ["held-out-secret.jpg"]}}}})
        db.add(j); db.flush()
        m = db.get(TrainedModel, ids["model"])
        m.job_id = j.id
        db.commit()
    lab = _login("labeler@labeldesk.dev")
    row = next(m for m in lab.get(f"{BASE}/models").json() if m["id"] == ids["model"])
    blob = json.dumps(row["job"])
    assert "eval" not in blob and "held-out-secret.jpg" not in blob, blob
    assert "options" not in blob and "max_minutes" not in blob, blob
    assert row["job"]["result"]["stages"]["train"]["status"] == "done"
    manager_row = next(m for m in admin.get(f"{BASE}/models").json() if m["id"] == ids["model"])
    assert "eval" in json.dumps(manager_row["job"])          # project.models still sees the report


def test_viewer_cannot_run_model_inference(viewer, ids):
    r = viewer.post(f"{BASE}/models/{ids['model']}/predict", files={"file": ("x.jpg", jpeg())})
    assert r.status_code == 403, r.text


def test_labeler_insights_hide_image_bearing_payloads(ids):
    lab = _login("labeler@labeldesk.dev")
    for path in ("image-stats", "leakage", "embedding"):
        assert lab.get(f"{BASE}/insights/{path}").status_code == 403, path


def test_project_manager_cannot_sync_workspace_connector(manager, ids, admin):
    conn = admin.post(f"/api/ws/{WS}/connectors", json={"name": "r1", "kind": "s3", "config": {"bucket": "b"}})
    if conn.status_code != 200:
        pytest.skip(f"s3 connector validation unavailable: {conn.text}")
    r = manager.post(f"{BASE}/connectors/{conn.json()['id']}/sync", json={})
    assert r.status_code == 403, r.text
    admin.delete(f"/api/ws/{WS}/connectors/{conn.json()['id']}")


def test_merge_rejects_a_class_from_another_project(admin, ids):
    with SessionLocal() as db:
        other = Project(workspace_id=ids["ws"], slug=f"other-{uuid.uuid4().hex[:8]}", name="Other")
        db.add(other); db.flush()
        foreign = LabelClass(project_id=other.id, name="foreign", color="#000000")
        db.add(foreign); db.commit()
        fid = foreign.id
    r = admin.post(f"{BASE}/classes/merge", json={"source_ids": [], "target_id": fid})
    assert r.status_code == 404, r.text


def test_annotation_rejects_a_class_from_another_project(admin, ids):
    with SessionLocal() as db:
        other = Project(workspace_id=ids["ws"], slug=f"other-{uuid.uuid4().hex[:8]}", name="Other")
        db.add(other); db.flush()
        foreign = LabelClass(project_id=other.id, name="foreign", color="#000000")
        db.add(foreign); db.commit()
        fid = foreign.id
        img = db.scalar(select(Image).where(Image.project_id == ids["project"],
                                            Image.deleted_at.is_(None)))
    if img is None:
        r = admin.post(f"{BASE}/upload", files=[("files", ("r1.jpg", jpeg()))])
        assert r.status_code == 200, r.text
        with SessionLocal() as db:
            img = db.scalar(select(Image).where(Image.project_id == ids["project"],
                                                Image.deleted_at.is_(None)))
    r = admin.put(f"/api/images/{img.id}/annotations",
                  json={"annotations": [{"id": "a1", "classId": fid, "shape": {"kind": "class"}}]})
    assert r.status_code == 400, r.text


def test_custom_roles_cannot_grant_workspace_members(admin):
    r = admin.post(f"/api/ws/{WS}/roles", json={"name": "self-power", "level": "workspace",
                                                "permissions": ["workspace.members", "workspace.audit"]})
    assert r.status_code == 400, r.text


def test_model_detail_includes_the_list_contract_fields(admin, ids):
    """I9: the detail response must carry version/job, not drop fields the list adds."""
    from app.db import SessionLocal
    from app.models import TrainedModel, Version
    with SessionLocal() as db:
        m = db.get(TrainedModel, ids["model"])
        number = db.get(Version, m.version_id).number
    d = admin.get(f"{BASE}/models/{ids['model']}")
    assert d.status_code == 200, d.text
    body = d.json()
    assert body["version"] == number
    assert "job" in body


def test_tag_filter_casts_json_to_text_for_postgres():
    from app.routers.images import _tag_filter
    sql = str(_tag_filter("person").compile(dialect=postgresql.dialect()))
    assert "AS TEXT" in sql.upper(), sql
