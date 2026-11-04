"""Scoped API keys: every route checks its scope; publishable keys are inference-only.

Existing keys created before scopes existed keep full access (NULL scopes = all).
"""
import io
import os

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage

from app.main import app

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/v1/projects/{PR}"


def login(email="demo@labeldesk.dev", pw="demo1234"):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return c


@pytest.fixture(scope="module")
def admin():
    with TestClient(app):
        yield login()


def jpeg(color=(90, 120, 150)):
    b = io.BytesIO(); PImage.new("RGB", (48, 48), color).save(b, "JPEG"); return b.getvalue()


def make_key(admin, name, **kw):
    r = admin.post(f"/api/ws/{WS}/keys", json={"name": name, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def anon():
    return TestClient(app)


def test_create_key_with_scopes(admin):
    k = make_key(admin, "reader", scopes=["read"])
    assert k["scopes"] == ["read"] and k["publishable"] is False
    # the plaintext is only returned once
    listed = admin.get(f"/api/ws/{WS}/keys").json()
    row = next(r for r in listed if r["id"] == k["id"])
    assert row["scopes"] == ["read"] and "key" not in row


def test_unknown_scope_rejected(admin):
    r = admin.post(f"/api/ws/{WS}/keys", json={"name": "bad", "scopes": ["read", "admin"]})
    assert r.status_code == 400


def test_publishable_key_is_inference_only(admin):
    k = make_key(admin, "browser", publishable=True)
    assert k["publishable"] is True and k["scopes"] == ["infer"]
    assert k["key"].startswith("ld_pub_")
    # write and read endpoints refuse it
    h = {"Authorization": f"Bearer {k['key']}"}
    assert anon().get(f"/api/v1/projects", headers=h).status_code == 403
    assert anon().post(f"/api/v1/projects/{PR}/upload", headers=h,
                       files={"files": ("a.jpg", jpeg())}).status_code == 403


def test_read_scope_only(admin):
    k = make_key(admin, "read-only", scopes=["read"])
    h = {"Authorization": f"Bearer {k['key']}"}
    c = anon()
    r = c.get("/api/v1/projects", headers=h)
    assert r.status_code == 200, r.text
    assert any(p["slug"] == PR for p in r.json())
    assert c.get(f"/api/v1/projects/{PR}/images", headers=h).status_code == 200
    assert c.get(f"/api/v1/models", headers=h).status_code == 200
    # upload needs the upload scope; train needs train; predict needs infer
    assert c.post(f"/api/v1/projects/{PR}/upload", headers=h,
                  files={"files": ("a.jpg", jpeg())}).status_code == 403
    assert c.post(f"/api/v1/projects/{PR}/train", headers=h, json={"version_id": "x"}).status_code == 403
    assert c.post("/api/v1/models/nope/predict", headers=h,
                  files={"file": ("a.jpg", jpeg())}).status_code == 403


def test_upload_scope(admin):
    k = make_key(admin, "uploader", scopes=["upload"])
    h = {"Authorization": f"Bearer {k['key']}"}
    r = anon().post(f"/api/v1/projects/{PR}/upload", headers=h,
                    files={"files": ("scope-upload.jpg", jpeg())})
    assert r.status_code == 200, r.text
    assert r.json()["uploaded"] == 1
    # upload scope does not grant reads
    assert anon().get("/api/v1/projects", headers=h).status_code == 403


def test_train_and_infer_scopes_pass_auth(admin):
    k = make_key(admin, "trainer", scopes=["train", "infer"])
    h = {"Authorization": f"Bearer {k['key']}"}
    c = anon()
    # no such version/model: once the scope passes, validation answers 400/404
    assert c.post(f"/api/v1/projects/{PR}/train", headers=h, json={"version_id": "nope"}).status_code == 400
    assert c.post("/api/v1/models/nope/predict", headers=h,
                  files={"file": ("a.jpg", jpeg())}).status_code == 404


def test_legacy_key_without_scopes_keeps_full_access(admin):
    k = make_key(admin, "legacy")
    assert k["scopes"] == ["read", "upload", "train", "infer"]
    h = {"Authorization": f"Bearer {k['key']}"}
    assert anon().get("/api/v1/projects", headers=h).status_code == 200
    assert anon().post(f"/api/v1/projects/{PR}/upload", headers=h,
                       files={"files": ("legacy.jpg", jpeg())}).status_code == 200


def test_key_via_x_api_key_header_and_publishable_query(admin):
    k = make_key(admin, "header", scopes=["read"])
    assert anon().get("/api/v1/projects", headers={"x-api-key": k["key"]}).status_code == 200
    # a workspace key in the query string leaks through logs/referrers: header only
    denied = anon().get("/api/v1/projects", params={"api_key": k["key"]})
    assert denied.status_code == 403 and "publishable" in denied.text
    # publishable keys are designed for browser use, so the query string is allowed for them
    pub = make_key(admin, "pub-query", publishable=True)
    r = anon().post("/api/v1/models/nope/predict", params={"api_key": pub["key"]},
                    files={"file": ("q.jpg", jpeg())})
    assert r.status_code == 404                    # authenticated, then the model is missing


def test_revoked_key_is_rejected(admin):
    k = make_key(admin, "gone", scopes=["read"])
    assert admin.delete(f"/api/ws/{WS}/keys/{k['id']}").status_code == 200
    assert anon().get("/api/v1/projects", headers={"Authorization": f"Bearer {k['key']}"}).status_code == 401


def test_bad_key_is_401(admin):
    assert anon().get("/api/v1/projects", headers={"Authorization": "Bearer ld_nope"}).status_code == 401


def test_null_scopes_row_keeps_full_access(admin):
    """Rows created before scopes existed have NULL scopes; they must still work."""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import ApiKey, Workspace
    from app.security import new_api_key

    key, prefix, h = new_api_key()
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        db.add(ApiKey(workspace_id=ws.id, name="pre-scopes", prefix=prefix, hash=h, scopes=None))
        db.commit()
    hdr = {"Authorization": f"Bearer {key}"}
    assert anon().get("/api/v1/projects", headers=hdr).status_code == 200
    assert anon().post(f"/api/v1/projects/{PR}/upload", headers=hdr,
                       files={"files": ("nullscope.jpg", jpeg())}).status_code == 200


def test_whoami_needs_read_and_refuses_publishable(admin):
    pub = make_key(admin, "browser-who", publishable=True)
    assert anon().get("/api/v1/whoami", headers={"Authorization": f"Bearer {pub['key']}"}).status_code == 403
    reader = make_key(admin, "reader-who", scopes=["read"])
    body = anon().get("/api/v1/whoami", headers={"Authorization": f"Bearer {reader['key']}"})
    assert body.status_code == 200 and body.json()["workspace"] == WS
