"""C1: remote-worker restrictions must follow the executor, not the default job list."""
import os

os.environ.setdefault("LD_WORKER_TOKEN", "test-worker-token-0123456789abcdef")
os.environ["LD_SAM_ENABLED"] = "0"

from fastapi.testclient import TestClient

from app import config
from app.main import app

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/ws/{WS}/projects/{PR}"


def _client() -> TestClient:
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": "demo@labeldesk.dev", "password": "demo1234"})
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return c


def _version(c: TestClient) -> str:
    from app.db import SessionLocal
    from app.models import Version
    vid = c.post(f"{BASE}/versions", json={"name": "r1"}).json()["id"]
    with SessionLocal() as db:                       # the route only needs a ready version
        v = db.get(Version, vid)
        v.status, v.stats = "ready", {"splits": {"train": 4}, "class_names": ["person"]}
        db.commit()
    return vid


def test_runs_locally_requires_the_embedded_worker(monkeypatch):
    """The compose API has EMBEDDED_WORKER=0 but the default job list still names train."""
    monkeypatch.setattr(config, "EMBEDDED_WORKER", False)
    monkeypatch.setattr(config, "LOCAL_JOB_KINDS", ["train", "autolabel", "export_engine"])
    assert config.runs_locally("train") is False
    monkeypatch.setattr(config, "EMBEDDED_WORKER", True)
    assert config.runs_locally("train") is True


def test_remote_mode_rejects_non_ultralytics_and_unsupported_options(monkeypatch):
    """With the embedded worker off, every restriction must still apply (C1)."""
    from app import main

    monkeypatch.setattr(config, "EMBEDDED_WORKER", False)
    monkeypatch.setattr(config, "LOCAL_JOB_KINDS", ["train", "autolabel", "export_engine"])
    monkeypatch.setattr(main, "EMBEDDED_WORKER", False)      # no embedded thread in remote mode
    with TestClient(app):
        c = _client()
        vid = _version(c)
        for body in ({"variant": "rtdetr-l"}, {"variant": "yolov8s-worldv2"}, {"max_minutes": 5},
                     {"resume_from": "any-model"}):
            r = c.post(f"{BASE}/train", json={"version_id": vid, **body})
            assert r.status_code == 400, (body, r.status_code, r.text)
            assert "remote GPU workers" in r.json()["detail"]
