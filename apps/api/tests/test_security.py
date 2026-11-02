"""Attack-style tests for the hardening: each one tries the exploit and expects it to fail."""
import io
import os
import zipfile

os.environ.setdefault("LD_WORKER_TOKEN", "test-worker-token-0123456789abcdef")
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage

from app import ratelimit
from app.main import app
from app.services import safefetch

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/ws/{WS}/projects/{PR}"


def login(email, pw="demo1234"):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return c


@pytest.fixture(scope="module")
def admin():
    with TestClient(app):
        yield login("demo@labeldesk.dev")


def jpeg(color=(10, 20, 30)):
    b = io.BytesIO(); PImage.new("RGB", (64, 64), color).save(b, "JPEG"); return b.getvalue()


def test_ssrf_blocked():
    for url in ("http://127.0.0.1:8000/api/health", "http://169.254.169.254/latest/meta-data/", "http://10.0.0.5/x.jpg",
                "http://localhost/x.jpg", "file:///etc/passwd", "ftp://example.com/a.jpg", "http://[::1]/x"):
        with pytest.raises(safefetch.BlockedURL):
            safefetch.fetch(url)


def test_hosted_api_rejects_internal_url(admin):
    key = admin.post(f"/api/ws/{WS}/keys", json={"name": "sec"}).json()["key"]
    r = TestClient(app).post(f"/api/v1/{WS}/{PR}/upload", headers={"x-api-key": key}, params={"image": "http://127.0.0.1:22/"})
    assert r.status_code == 400 and "private" in r.text


def test_file_links_cannot_escape_data_dir(admin):
    for rel in ("../../etc/passwd", "..%2F..%2Fsecret", ".secret"):
        r = admin.get(f"/api/files/{rel}?exp=9999999999&sig=deadbeef")
        assert r.status_code in (403, 404)
    img = admin.get(f"{BASE}/images?limit=1").json()["items"][0]
    tampered = img["thumbnail"].replace("thumbs/", "")          # valid sig for another path
    assert TestClient(app).get(tampered).status_code == 403


def test_zip_bomb_rejected(admin):
    z = io.BytesIO()
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as f:
        f.writestr("a.jpg", jpeg())
        f.writestr("bomb.txt", b"0" * (50 * 1024 * 1024))       # ~1000:1 ratio
    r = admin.post(f"{BASE}/upload", files=[("files", ("x.zip", z.getvalue()))])
    assert r.status_code == 400 and "ratio" in r.text


def test_path_traversal_filename_sanitised(admin):
    r = admin.post(f"{BASE}/upload", files=[("files", ("..\\..\\evil<script>.jpg", jpeg((99, 1, 1))))]).json()
    name = r["images"][0]["name"]
    assert "/" not in name and "\\" not in name and "<" not in name


def test_invite_bound_to_email(admin):
    from app.db import SessionLocal
    from app.models import Workspace
    with SessionLocal() as db:                       # free plan's 3 seats are taken by the demo users
        db.query(Workspace).filter_by(slug=WS).update({"plan": "pro"}); db.commit()
    link = admin.post(f"/api/ws/{WS}/invites", json={"email": "invitee@x.io", "role": "annotator"}).json()["token"]
    other = TestClient(app).post("/api/auth/signup", json={"name": "Mallory", "email": "mallory@x.io", "password": "longpassword1", "invite": link})
    assert other.status_code == 403
    # an existing different account can't redeem it either
    assert login("reviewer@labeldesk.dev").post(f"/api/invites/{link}/accept").status_code == 403
    ok = TestClient(app).post("/api/auth/signup", json={"name": "Ivy", "email": "invitee@x.io", "password": "longpassword1", "invite": link})
    assert ok.status_code == 200


def test_labeler_cannot_touch_unassigned_images(admin):
    lab = login("labeler@labeldesk.dev")
    img = admin.get(f"{BASE}/images?limit=1&assignee=none").json()["items"][0]["id"]
    for method, path, body in (("get", f"/api/images/{img}", None), ("get", f"/api/images/{img}/comments", None),
                               ("post", f"/api/images/{img}/comments", {"text": "hi"}),
                               ("patch", f"/api/images/{img}", {"tags": ["x"]}),
                               ("post", f"/api/images/{img}/smart-polygon", {"points": [[.5, .5]]}),
                               ("put", f"/api/images/{img}/annotations", {"annotations": []})):
        r = getattr(lab, method)(path, **({"json": body} if body is not None else {}))
        assert r.status_code == 403, (path, r.status_code)
    assert lab.post(f"{BASE}/train", json={"version_id": "x"}).status_code == 403
    assert lab.get(f"/api/ws/{WS}/keys").status_code == 403


def test_cross_workspace_isolation(admin):
    outsider = TestClient(app)
    tok = outsider.post("/api/auth/signup", json={"name": "Eve", "email": "eve@x.io", "password": "longpassword1"}).json()["token"]
    outsider.headers["Authorization"] = f"Bearer {tok}"
    img = admin.get(f"{BASE}/images?limit=1").json()["items"][0]["id"]
    assert outsider.get(f"{BASE}/images").status_code == 403
    assert outsider.get(f"/api/images/{img}").status_code == 403
    assert outsider.get(f"/api/ws/{WS}/members").status_code == 403


def test_annotation_payload_validation(admin):
    img = admin.get(f"{BASE}/images?limit=1").json()["items"][0]["id"]
    bad = [
        [{"id": "a", "classId": "c", "shape": {"kind": "bbox", "x": "1;drop", "y": 0, "w": 1, "h": 1}}],
        [{"id": "a", "classId": "c", "shape": {"kind": "polygon", "points": [0, 0, 1]}}],
        [{"id": "a", "classId": "c", "shape": {"kind": "bbox", "x": 1e308, "y": 0, "w": 1, "h": 1}}],
        [{"id": "a" * 500, "classId": "c", "shape": {"kind": "class"}}],
        ["not-an-object"],
    ]
    for anns in bad:
        assert admin.put(f"/api/images/{img}/annotations", json={"annotations": anns}).status_code in (400, 422), anns
    many = [{"id": f"a{i}", "classId": "c", "shape": {"kind": "class"}} for i in range(5001)]
    assert admin.put(f"/api/images/{img}/annotations", json={"annotations": many}).status_code == 413


def test_login_rate_limited_and_no_user_enumeration():
    was = ratelimit.ENABLED
    ratelimit.ENABLED = True
    try:
        c = TestClient(app)
        codes = [c.post("/api/auth/login", json={"email": "nobody@x.io", "password": "x"}).status_code for _ in range(10)]
        assert codes[0] == 401 and 429 in codes
        r1 = c.post("/api/auth/login", json={"email": "ghost1@x.io", "password": "x"}).json()["detail"]
        r2 = c.post("/api/auth/login", json={"email": "demo@labeldesk.dev", "password": "wrong"}).json()["detail"]
        assert r1 == r2
    finally:
        ratelimit.ENABLED = was


def test_refresh_tokens_hashed_and_rotated():
    from app.db import SessionLocal
    from app.models import RefreshToken
    c = TestClient(app)
    rt = c.post("/api/auth/login", json={"email": "reviewer@labeldesk.dev", "password": "demo1234"}).json()["refresh_token"]
    with SessionLocal() as db:
        assert db.get(RefreshToken, rt) is None                 # plaintext never stored
    assert c.post("/api/auth/refresh", json={"refresh_token": rt}).status_code == 200
    assert c.post("/api/auth/refresh", json={"refresh_token": rt}).status_code == 401   # one-time use


def test_security_headers(admin):
    h = admin.get("/api/me").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
    assert h["cache-control"] == "no-store" and "default-src 'none'" in h["content-security-policy"]


def test_worker_endpoints_need_token():
    c = TestClient(app)
    assert c.post("/api/worker/claim", json={}).status_code == 401
    assert c.post("/api/worker/claim", json={}, headers={"X-Worker-Token": "guess"}).status_code == 401
    assert c.post("/api/worker/jobs/x/complete", data={"result": "{}"}).status_code == 401
