"""C5: class names must never become paths outside the export root."""
import json
import os
from pathlib import Path

os.environ.setdefault("LD_WORKER_TOKEN", "test-worker-token-0123456789abcdef")
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import exporters

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/ws/{WS}/projects/{PR}"


@pytest.fixture(scope="module")
def admin():
    c = TestClient(app)
    with TestClient(app):
        r = c.post("/api/auth/login", json={"email": "demo@labeldesk.dev", "password": "demo1234"})
        assert r.status_code == 200, r.text
        c.headers["Authorization"] = f"Bearer {r.json()['token']}"
        yield c


@pytest.mark.parametrize("name", ["../../../../escaped", r"..\\..\\escaped", "..", ".", "a/b", "a\\b"])
def test_class_name_rejects_path_segments(admin, name):
    r = admin.post(f"{BASE}/classes", json={"name": name})
    assert r.status_code == 400, (name, r.status_code, r.text)


def test_class_name_accepts_normal_names(admin):
    r = admin.post(f"{BASE}/classes", json={"name": "traffic cone (orange) 2"})
    assert r.status_code in (200, 409), r.text


def test_class_name_accepts_thai_marks(admin):
    """Thai vowels and tone marks are combining characters, not word characters (C5 must not ban them)."""
    r = admin.post(f"{BASE}/classes", json={"name": "คนขับรถ"})
    assert r.status_code in (200, 409), r.text


def test_exporter_cannot_escape_the_export_root(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.jpg").write_bytes(b"jpeg")
    out = tmp_path / "exports" / "v1"
    out.mkdir(parents=True)
    manifest = {"classes": ["../../../../escaped"], "type": "classification",
                "items": [{"file": "a.jpg", "split": "train", "width": 10, "height": 10, "anns": [{"cls": 0, "shape": {"kind": "class"}}]}]}
    (src / "manifest.json").write_text(json.dumps(manifest))
    exporters.build_dir("folder", src, out)
    assert not (tmp_path / "escaped" / "a.jpg").exists()
    assert (out / "train" / "escaped" / "a.jpg").exists()
