"""C1/I7: remote-worker restrictions must follow the deployment topology, not *this* process."""
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("LD_WORKER_TOKEN", "test-worker-token-0123456789abcdef")
os.environ["LD_SAM_ENABLED"] = "0"

from fastapi.testclient import TestClient

from app import config
from app.main import app

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/ws/{WS}/projects/{PR}"
API_ROOT = Path(__file__).resolve().parents[1]


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


def test_train_worker_flag_is_independent_of_the_api_process():
    """I7: LD_EMBEDDED_WORKER=0 plus a CPU worker service still means train runs locally in this deploy."""
    code = "from app import config; print(config.runs_locally('train'), config.remote_training())"
    env = {**os.environ, "LD_EMBEDDED_WORKER": "0",
           "LD_LOCAL_JOBS": "train,autolabel,version", "LD_TRAIN_WORKER": "local"}
    local = subprocess.run([sys.executable, "-c", code], cwd=API_ROOT, env=env,
                           capture_output=True, text=True, timeout=120)
    assert local.returncode == 0, local.stderr
    assert local.stdout.strip() == "False False"

    env.pop("LD_TRAIN_WORKER")                       # no explicit flag: remote when the API runs no jobs
    remote = subprocess.run([sys.executable, "-c", code], cwd=API_ROOT, env=env,
                            capture_output=True, text=True, timeout=120)
    assert remote.returncode == 0, remote.stderr
    assert remote.stdout.strip() == "False True"


def test_remote_mode_rejects_non_ultralytics_and_unsupported_options(monkeypatch):
    """With a remote GPU worker, every restriction must still apply (C1)."""
    from app import main

    monkeypatch.setattr(config, "TRAIN_WORKER", "remote")
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


def test_local_train_topology_accepts_non_yolo_and_options(monkeypatch):
    """I7: the documented no-GPU recipe runs train in a local worker, so nothing is remote-restricted."""
    from app import main

    monkeypatch.setattr(config, "TRAIN_WORKER", "local")
    monkeypatch.setattr(config, "EMBEDDED_WORKER", False)    # the API itself still runs no jobs
    monkeypatch.setattr(main, "EMBEDDED_WORKER", False)
    with TestClient(app):
        c = _client()
        vid = _version(c)
        for body in ({"family": "rtdetr", "variant": "rtdetr-l"},
                     {"family": "ultralytics", "variant": "yolo26n", "max_minutes": 5}):
            r = c.post(f"{BASE}/train", json={"version_id": vid, **body})
            assert r.status_code == 200, (body, r.status_code, r.text)
