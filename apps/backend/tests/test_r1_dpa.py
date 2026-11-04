"""I7: the generated DPA must not assert a topology the product cannot enforce."""
import os

os.environ.setdefault("LD_WORKER_TOKEN", "test-worker-token-0123456789abcdef")
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient

from app.main import app

BASE = "/api/ws/labeldesk-demo"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        r = c.post("/api/auth/login", json={"email": "demo@labeldesk.dev", "password": "demo1234"})
        assert r.status_code == 200, r.text
        c.headers["Authorization"] = f"Bearer {r.json()['token']}"
        yield c


def test_dpa_names_remote_workers_instead_of_denying_sub_processors(client):
    md = client.get(f"{BASE}/dpa").json()["markdown"]
    assert "No third-party transfer" not in md
    assert "remote gpu worker" in md.lower()
    assert "that worker is a sub-processor" in md.lower()


def test_dpa_audit_clause_names_only_stream_footage(client):
    """Stored images/video are served by /api/files with no audit row; only stream views are audited."""
    md = client.get(f"{BASE}/dpa").json()["markdown"].lower()
    assert "every view of stream footage" in md
    assert "stored footage" not in md
    assert "video frames" in md
    assert "face blur" in md


def test_stream_view_audit_covers_the_stream_transports_only():
    from app.services.streamaudit import view_of

    assert view_of("/api/ws/acme/projects/p1/streams/s1/frame")
    assert view_of("/api/ws/acme/projects/p1/streams/s1/mjpeg")
    assert view_of("/api/ws/acme/projects/p1/images/i1.jpg") is None
    assert view_of("/api/files/projects/p1/images/i1.jpg") is None
