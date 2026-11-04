"""PDPA API: project privacy settings, retention requests, residency and the DPA template."""

import os
import tempfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-test-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.main import app
from app.models import Job, Project, Workspace

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/ws/{WS}"
P = f"{BASE}/projects/{PR}/privacy"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        tok = c.post("/api/auth/login", json={"email": "demo@labeldesk.dev", "password": "demo1234"}).json()["token"]
        c.headers["Authorization"] = f"Bearer {tok}"
        yield c


@pytest.fixture(scope="module")
def labeler_headers(client):
    tok = client.post("/api/auth/login", json={"email": "labeler@labeldesk.dev", "password": "demo1234"}).json()[
        "token"
    ]
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module", autouse=True)
def restore_settings(client):
    with SessionLocal() as db:
        p = db.scalar(select(Project).where(Project.slug == PR))
        ws = db.get(Workspace, p.workspace_id)
        saved = (p.retention_days, p.face_blur, p.biometrics, p.legal_basis, ws.data_region, p.id)
    yield
    with SessionLocal() as db:
        p = db.get(Project, saved[5])
        p.retention_days, p.face_blur, p.biometrics, p.legal_basis = saved[:4]
        db.get(Workspace, p.workspace_id).data_region = saved[4]
        db.execute(delete(Job).where(Job.kind == "retention", Job.project_id == p.id))
        db.commit()


def test_workspace_privacy_overview(client):
    r = client.get(f"{BASE}/privacy")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["data_region"] == "th"
    assert body["region_label"] == "Thailand"
    assert set(body["regions"]) == {"th", "sg", "us"}
    assert 30 in body["retention_presets"]
    project = next(p for p in body["projects"] if p["slug"] == PR)
    assert set(project) == {"slug", "name", "retention_days", "face_blur", "biometrics"}


def test_residency_change_is_audited(client):
    r = client.patch(f"{BASE}/privacy", json={"data_region": "sg"})
    assert r.status_code == 200, r.text
    assert r.json()["data_region"] == "sg"
    assert client.get(f"{BASE}/privacy").json()["data_region"] == "sg"
    assert client.patch(f"{BASE}/privacy", json={"data_region": "mars"}).status_code == 400
    assert client.patch(f"{BASE}/privacy", json={"data_region": "th"}).status_code == 200


def test_residency_requires_workspace_admin(client, labeler_headers):
    assert client.patch(f"{BASE}/privacy", json={"data_region": "us"}, headers=labeler_headers).status_code == 403


def test_project_privacy_get(client):
    body = client.get(P).json()
    for key in (
        "retention_days",
        "face_blur",
        "biometrics",
        "legal_basis",
        "retention_presets",
        "images_expiring",
        "snapshots_expiring",
        "data_region",
    ):
        assert key in body, key
    assert body["face_blur"] is True
    assert body["images_expiring"] == 0


def test_annotator_can_read_but_not_change_privacy(client, labeler_headers):
    assert client.get(P, headers=labeler_headers).status_code == 200
    assert client.patch(P, json={"retention_days": 30}, headers=labeler_headers).status_code == 403


def test_retention_bounds_and_audit(client):
    assert client.patch(P, json={"retention_days": 4000}).status_code == 400
    assert client.patch(P, json={"retention_days": -1}).status_code == 400
    r = client.patch(P, json={"retention_days": 30, "face_blur": False})
    assert r.status_code == 200, r.text
    assert r.json()["retention_days"] == 30 and r.json()["face_blur"] is False
    assert client.patch(P, json={"retention_days": None}).json()["retention_days"] is None
    assert client.patch(P, json={"retention_days": 30}).status_code == 200


def test_biometrics_need_a_documented_legal_basis(client):
    r = client.patch(P, json={"biometrics": True})
    assert r.status_code == 400
    assert "PDPA s.26" in r.json()["detail"]
    assert client.patch(P, json={"legal_basis": "short"}).status_code == 200
    assert client.patch(P, json={"biometrics": True}).status_code == 400
    long_basis = "Consent form signed by every employee on the factory CCTV policy (PDPA s.26)."
    assert client.patch(P, json={"legal_basis": long_basis}).status_code == 200
    r = client.patch(P, json={"biometrics": True})
    assert r.status_code == 200 and r.json()["biometrics"] is True
    assert client.patch(P, json={"biometrics": False}).status_code == 200


def test_retention_run_creates_a_queued_job(client):
    r = client.post(f"{P}/retention/run")
    assert r.status_code == 200, r.text
    jid = r.json()["job_id"]
    with SessionLocal() as db:
        job = db.get(Job, jid)
        assert job is not None and job.kind == "retention"
        assert job.params["project_id"] == db.scalar(select(Project.id).where(Project.slug == PR))


def test_dpa_template_has_real_values(client):
    r = client.get(f"{BASE}/dpa")
    assert r.status_code == 200, r.text
    body = r.json()
    md = body["markdown"].lower()
    assert body["workspace"] == "LabelDesk Demo"
    assert body["region"] == "th"
    assert "labeldesk demo" in md
    assert "processor" in md and "controller" in md
    assert "72" in md
    assert "face blur" in md
    assert "demo@labeldesk.dev" in md
    assert "keep until deletion" in md or "30" in md
    assert client.get(f"{BASE}/dpa?project={PR}").status_code == 200
    assert client.get(f"{BASE}/dpa?project=nope").status_code == 404
