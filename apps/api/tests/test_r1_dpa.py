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
    assert "records" in md.lower()


def test_dpa_does_not_claim_stream_audit_or_blur_before_10b(client):
    md = client.get(f"{BASE}/dpa").json()["markdown"]
    assert "stream footage" not in md.lower()
    assert "video frames" in md.lower()
    assert "face blur" in md.lower()
