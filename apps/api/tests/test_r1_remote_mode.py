"""C1/I7: remote-worker restrictions must follow the deployment topology, not *this* process."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("LD_WORKER_TOKEN", "test-worker-token-0123456789abcdef")
os.environ["LD_SAM_ENABLED"] = "0"

from fastapi.testclient import TestClient

from app import config
from app.main import app

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/ws/{WS}/projects/{PR}"
API_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _no_local_train(monkeypatch):
    """These tests queue train jobs for the remote worker, but the embedded worker thread runs in
    this process and reads its claim list from app.worker. A remote deployment does not claim
    train locally either, so hide it here; otherwise a queued train job runs against a version
    that only exists as a ready row and starves every later version job."""
    from app import worker

    monkeypatch.setattr(worker, "LOCAL_JOB_KINDS", ["version", "export", "export_engine"])
    yield
    # The tests only assert that the API accepts these requests; the jobs themselves must not
    # leak into later modules where the embedded worker would claim a real 30-epoch CPU train.
    from app.db import SessionLocal
    from app.models import Job, now

    with SessionLocal() as db:
        db.query(Job).filter(
            Job.kind.in_(("train", "autolabel", "version")),
            Job.status.in_(("queued", "running")),
            Job.executor != "remote",
        ).update({"status": "cancelled", "finished": now()}, synchronize_session=False)
        db.commit()


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


def test_train_worker_flag_is_an_explicit_override_only():
    """I7: an unset LD_TRAIN_WORKER must defer to the workers that are actually online."""
    code = "from app import config; print(repr(config.TRAIN_WORKER))"
    env = {**os.environ, "LD_EMBEDDED_WORKER": "0",
           "LD_LOCAL_JOBS": "train,autolabel,version", "LD_TRAIN_WORKER": "local"}
    local = subprocess.run([sys.executable, "-c", code], cwd=API_ROOT, env=env,
                           capture_output=True, text=True, timeout=120)
    assert local.returncode == 0, local.stderr
    assert local.stdout.strip() == "'local'"

    env["LD_TRAIN_WORKER"] = "remote"
    remote = subprocess.run([sys.executable, "-c", code], cwd=API_ROOT, env=env,
                            capture_output=True, text=True, timeout=120)
    assert remote.returncode == 0, remote.stderr
    assert remote.stdout.strip() == "'remote'"

    env.pop("LD_TRAIN_WORKER")                       # auto: topology service decides per request
    auto = subprocess.run([sys.executable, "-c", code], cwd=API_ROOT, env=env,
                          capture_output=True, text=True, timeout=120)
    assert auto.returncode == 0, auto.stderr
    assert auto.stdout.strip() == "''"


def _online_worker(kinds: list[str]) -> str:
    from app.db import SessionLocal
    from app.models import Worker, now

    wid = f"i7-test:{os.getpid()}"
    with SessionLocal() as db:
        db.query(Worker).delete()                    # this test owns the topology
        db.add(Worker(id=wid, host="cpu-worker", kinds=kinds, started=now(), last_seen=now()))
        db.commit()
    return wid


def test_an_online_worker_advertising_train_unlocks_local_family_options(monkeypatch):
    """I7 root: the API must follow the executor a worker advertises, not a static operator flag."""
    from app import main

    monkeypatch.setattr(config, "TRAIN_WORKER", "")      # auto
    monkeypatch.setattr(config, "EMBEDDED_WORKER", False)
    monkeypatch.setattr(config, "LOCAL_JOB_KINDS", ["version", "export"])
    monkeypatch.setattr(main, "EMBEDDED_WORKER", False)
    _online_worker(["version", "export", "train", "autolabel"])
    with TestClient(app):
        c = _client()
        vid = _version(c)
        r = c.post(f"{BASE}/train", json={"version_id": vid, "family": "rtdetr", "variant": "rtdetr-l"})
        assert r.status_code == 200, r.text
        r = c.post(f"{BASE}/train", json={"version_id": vid, "variant": "yolo26n", "max_minutes": 5})
        assert r.status_code == 200, r.text


def test_no_online_worker_advertising_train_stays_remote(monkeypatch):
    """I7 root: a remote-only deployment keeps the pip-worker restrictions without an env assertion."""
    from app import main

    monkeypatch.setattr(config, "TRAIN_WORKER", "")      # auto
    monkeypatch.setattr(config, "EMBEDDED_WORKER", False)
    monkeypatch.setattr(config, "LOCAL_JOB_KINDS", ["version", "export"])
    monkeypatch.setattr(main, "EMBEDDED_WORKER", False)
    _online_worker(["version", "export", "insights_images"])
    with TestClient(app):
        c = _client()
        vid = _version(c)
        r = c.post(f"{BASE}/train", json={"version_id": vid, "family": "rtdetr", "variant": "rtdetr-l"})
        assert r.status_code == 400, r.text
        assert "remote GPU workers" in r.json()["detail"]


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
