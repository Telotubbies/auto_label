"""Deployment aliases: promote a ready model to production/staging, roll back, read state."""

import os
import secrets
import tempfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-deploy-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.db import SessionLocal
from app.main import app
from app.models import (
    Audit,
    DeploymentAlias,
    DeploymentEvent,
    DriftRun,
    Member,
    Project,
    TrainedModel,
    User,
    Version,
    Workspace,
    now,
)
from app.security import issue_access
from app.services import deployments as svc

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/ws/{WS}/projects/{PR}/deployments"


def _demo(db) -> tuple[Workspace, Project]:
    ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
    p = db.scalar(select(Project).where(Project.workspace_id == ws.id, Project.slug == PR))
    return ws, p


def make_model(name: str, status: str = "ready", project: Project | None = None) -> str:
    """A trained-model row (with its version) for the demo project."""
    with SessionLocal() as db:
        if project is None:
            _, project = _demo(db)
        else:
            project = db.get(Project, project.id)
        number = (db.scalar(select(func.max(Version.number)).where(Version.project_id == project.id)) or 0) + 1
        v = Version(project_id=project.id, number=number, name=f"deploy-{number}", status="ready")
        db.add(v)
        db.flush()
        m = TrainedModel(
            workspace_id=project.workspace_id,
            project_id=project.id,
            version_id=v.id,
            name=name,
            arch="yolo26n",
            task="detect",
            status=status,
            metrics={"eval": {"coco": {"AP": 0.42}}},
        )
        db.add(m)
        db.commit()
        return m.id


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
        c.headers["Authorization"] = f"Bearer {issue_access(user.id)}"
        yield c


@pytest.fixture(scope="module")
def models(client) -> dict[str, str]:
    return {
        "a": make_model("deploy-a"),
        "b": make_model("deploy-b"),
        "training": make_model("deploy-training", status="training"),
    }


@pytest.fixture(scope="module")
def other_project(client):
    """A second project in the same workspace: no aliases, and its models must stay invisible."""
    with SessionLocal() as db:
        ws, _ = _demo(db)
        p = Project(workspace_id=ws.id, slug=f"other-{secrets.token_hex(3)}", name="Other project")
        db.add(p)
        db.commit()
        pid = p.id
    yield p
    with SessionLocal() as db:  # keep the shared demo workspace under the Free project limit
        row = db.get(Project, pid)
        if row is not None:
            db.delete(row)
            db.commit()


def _drop_aliases() -> None:
    with SessionLocal() as db:
        _, p = _demo(db)
        db.execute(delete(DeploymentEvent).where(DeploymentEvent.project_id == p.id))
        db.execute(delete(DeploymentAlias).where(DeploymentAlias.project_id == p.id))
        db.commit()


@pytest.fixture(autouse=True)
def _clean_aliases():
    """Each test starts and ends with no aliases/events, so module order cannot leak state."""
    _drop_aliases()
    yield
    _drop_aliases()


def test_switch_and_state(client, models):
    r = client.put(f"{BASE}/production", json={"model_id": models["a"]})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["alias"] == "production"
    assert out["model_id"] == models["a"] and out["model_name"] == "deploy-a"
    assert out["model_arch"] == "yolo26n" and out["model_status"] == "ready"
    assert out["previous_model_id"] is None and out["previous_model_name"] is None
    assert out["updated_by"]

    st = client.get(BASE).json()
    assert [x["alias"] for x in st["aliases"]] == ["production"]
    assert st["aliases"][0]["model_id"] == models["a"]
    assert st["events"][0]["action"] == "deploy" and st["events"][0]["model_id"] == models["a"]
    assert st["events"][0]["from_model_id"] is None
    assert any(
        m["id"] == models["a"] and m["arch"] == "yolo26n" and m["score"] == pytest.approx(0.42) for m in st["models"]
    )

    with SessionLocal() as db:
        row = db.scalar(
            select(Audit).where(Audit.action == "deployment.deploy", Audit.target == "production -> deploy-a")
        )
        assert row and row.target == "production -> deploy-a"
        assert row.meta["model_id"] == models["a"]


def test_switch_sets_previous_and_rollback(client, models):
    assert client.put(f"{BASE}/production", json={"model_id": models["a"]}).status_code == 200
    r = client.put(f"{BASE}/production", json={"model_id": models["b"]})
    assert r.status_code == 200, r.text
    assert r.json()["previous_model_id"] == models["a"]
    assert r.json()["previous_model_name"] == "deploy-a"

    rb = client.post(f"{BASE}/production/rollback")
    assert rb.status_code == 200, rb.text
    assert rb.json()["model_id"] == models["a"] and rb.json()["previous_model_id"] == models["b"]

    st = client.get(BASE).json()
    assert [e["action"] for e in st["events"]][:2] == ["rollback", "deploy"]
    assert st["events"][0]["from_model_id"] == models["b"]
    with SessionLocal() as db:
        events = db.scalars(
            select(DeploymentEvent).where(
                DeploymentEvent.action == "rollback", DeploymentEvent.model_id.in_([models["a"], models["b"]])
            )
        ).all()
        assert len(events) == 1
        audit = db.scalar(
            select(Audit).where(Audit.action == "deployment.rollback", Audit.target == "production -> deploy-a")
        )
        assert audit and audit.meta["model_id"] == models["a"]


def test_same_model_keeps_previous(client, models):
    assert client.put(f"{BASE}/production", json={"model_id": models["a"]}).status_code == 200
    assert client.put(f"{BASE}/production", json={"model_id": models["b"]}).status_code == 200
    again = client.put(f"{BASE}/production", json={"model_id": models["b"]})
    assert again.status_code == 200
    assert again.json()["previous_model_id"] == models["a"]  # a no-op deploy keeps the rollback target


def test_invalid_alias_and_model_errors(client, models, other_project):
    bad_alias = client.put(f"{BASE}/live", json={"model_id": models["a"]})
    assert bad_alias.status_code == 400 and bad_alias.json()["detail"] == "unknown deployment alias"

    unknown = client.put(f"{BASE}/production", json={"model_id": "nope"})
    assert unknown.status_code == 400 and unknown.json()["detail"] == "unknown model"

    foreign = make_model("foreign", project=other_project)
    leaked = client.put(f"{BASE}/production", json={"model_id": foreign})
    assert leaked.status_code == 400 and leaked.json()["detail"] == "unknown model"

    not_ready = client.put(f"{BASE}/production", json={"model_id": models["training"]})
    assert not_ready.status_code == 400 and not_ready.json()["detail"] == "model is not ready"


def test_rollback_without_target_is_409(client, models):
    assert client.post(f"{BASE}/staging/rollback").status_code == 409
    assert client.put(f"{BASE}/staging", json={"model_id": models["a"]}).status_code == 200
    conflict = client.post(f"{BASE}/staging/rollback")
    assert conflict.status_code == 409 and conflict.json()["detail"] == "no previous model to roll back to"


def test_switch_requires_admin(client, models):
    with SessionLocal() as db:
        ws, _ = _demo(db)
        email = f"anno-{secrets.token_hex(3)}@labeldesk.dev"
        user = User(email=email, name="Anno")
        db.add(user)
        db.flush()
        db.add(Member(workspace_id=ws.id, user_id=user.id, role="annotator"))
        db.commit()
        token = issue_access(user.id)
    anno = TestClient(app)
    anno.headers["Authorization"] = f"Bearer {token}"
    assert anno.put(f"{BASE}/production", json={"model_id": models["a"]}).status_code == 403
    assert anno.get(BASE).status_code == 200  # viewing is fine for any member


def test_workspace_state_lists_every_project(client, other_project, models):
    with SessionLocal() as db:
        ws, _ = _demo(db)
        gone = Project(workspace_id=ws.id, slug=f"gone-{secrets.token_hex(3)}", name="Gone", deleted_at=now())
        db.add(gone)
        db.commit()
        gone_slug = gone.slug
    assert client.put(f"{BASE}/production", json={"model_id": models["a"]}).status_code == 200

    state = client.get(f"/api/ws/{WS}/deployments").json()
    slugs = [p["slug"] for p in state["projects"]]
    assert PR in slugs and other_project.slug in slugs
    assert gone_slug not in slugs

    row = next(p for p in state["projects"] if p["slug"] == PR)
    assert [a["alias"] for a in row["aliases"]] == ["production"]
    assert row["aliases"][0]["model_id"] == models["a"]
    assert any(m["id"] == models["a"] for m in row["ready_models"])
    assert row["drift"] is None or set(row["drift"]) == {
        "run_id",
        "status",
        "alert",
        "statistic",
        "p_value",
        "n_reference",
        "n_current",
        "feature_source",
        "error",
        "min_samples",
        "created",
    }

    empty = next(p for p in state["projects"] if p["slug"] == other_project.slug)
    assert empty["aliases"] == [] and empty["drift"] is None
    assert all(m["name"] == "foreign" for m in empty["ready_models"])


def test_workspace_state_carries_drift_detail(client, models):
    """I3: the drift strip needs counts, the source and the error, not just `alert`."""
    with SessionLocal() as db:
        _, p = _demo(db)
        run = DriftRun(
            workspace_id=p.workspace_id,
            project_id=p.id,
            status="failed",
            error="OSError: data volume is full",
            n_reference=40,
            n_current=7,
            feature_source="clip",
            created=now(),
            finished=now(),
        )
        db.add(run)
        db.commit()
        run_id = run.id
    try:
        state = client.get(f"/api/ws/{WS}/deployments").json()
        row = next(p for p in state["projects"] if p["slug"] == PR)
        drift_out = row["drift"]
        assert drift_out["status"] == "failed"
        assert drift_out["error"] == "OSError: data volume is full"
        assert drift_out["n_reference"] == 40 and drift_out["n_current"] == 7
        assert drift_out["feature_source"] == "clip"
        assert drift_out["min_samples"] >= 1
    finally:
        with SessionLocal() as db:
            db.delete(db.get(DriftRun, run_id))
            db.commit()


def test_alias_model_helper(client, models):
    with SessionLocal() as db:
        _, p = _demo(db)
        assert svc.alias_model(db, p, "production") is None
    assert client.put(f"{BASE}/production", json={"model_id": models["a"]}).status_code == 200
    with SessionLocal() as db:
        _, p = _demo(db)
        m = svc.alias_model(db, p, "production")
        assert m is not None and m.id == models["a"]
        assert svc.alias_model(db, p, "staging") is None
