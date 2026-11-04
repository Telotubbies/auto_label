"""End-to-end: seed → review → version → export → train → predict → hosted API → remote worker.

Run from apps/backend:  pytest -q        (training uses 1 epoch @ 160px on CPU, ~1 min)
"""
import io
import os
import time
import zipfile

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage

from app.main import app

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/ws/{WS}/projects/{PR}"


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        tok = client.post("/api/auth/login", json={"email": "demo@labeldesk.dev", "password": "demo1234"}).json()["token"]
        client.headers["Authorization"] = f"Bearer {tok}"
        yield client


def wait_job(c, jid, timeout=600):
    t = time.time()
    while time.time() - t < timeout:
        j = c.get(f"{BASE}/jobs/{jid}").json()
        if j["status"] in ("done", "failed", "cancelled"):
            assert j["status"] == "done", j
            return j
        time.sleep(1)
    raise TimeoutError(jid)


def jpeg(color=(200, 50, 50)) -> bytes:
    b = io.BytesIO(); PImage.new("RGB", (320, 240), color).save(b, "JPEG"); return b.getvalue()


def test_auth_and_roles(c):
    r = c.post("/api/auth/login", json={"email": "demo@labeldesk.dev", "password": "nope"})
    assert r.status_code == 401
    anon = TestClient(app)
    assert anon.get(f"{BASE}/images").status_code == 401
    lab = anon.post("/api/auth/login", json={"email": "labeler@labeldesk.dev", "password": "demo1234"}).json()["token"]
    h = {"Authorization": f"Bearer {lab}"}
    assert anon.get(f"{BASE}/images", headers=h).json()["total"] == 0          # nothing assigned yet
    assert anon.post(f"{BASE}/versions", json={}, headers=h).status_code == 403


def test_signup_creates_workspace(c):
    anon = TestClient(app)
    r = anon.post("/api/auth/signup", json={"name": "New Person", "email": "new@x.io", "password": "longenough1"})
    assert r.status_code == 200, r.text
    me = anon.get("/api/me", headers={"Authorization": f"Bearer {r.json()['token']}"}).json()
    assert me["workspaces"][0]["role"] == "admin"


def test_upload_dedupe_and_yolo_import(c):
    z = io.BytesIO()
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("train/images/a.jpg", jpeg()); f.writestr("train/labels/a.txt", "0 0.5 0.5 0.2 0.2")
        f.writestr("data.yaml", "names: ['person']\n")
    r = c.post(f"{BASE}/upload", files=[("files", ("d.zip", z.getvalue()))], data={"split": "keep"})
    assert r.status_code == 200, r.text
    assert r.json()["uploaded"] == 1 and r.json()["annotated"] == 1
    again = c.post(f"{BASE}/upload", files=[("files", ("a.jpg", jpeg()))]).json()
    assert again["duplicates"] == 1


def test_annotate_review_flow(c):
    imgs = c.get(f"{BASE}/images", params={"status": "review"}).json()["items"]
    img = imgs[0]
    cls = c.get(f"{BASE}/classes").json()[0]
    ann = [{"id": "x1", "classId": cls["id"], "shape": {"kind": "bbox", "x": .1, "y": .1, "w": .3, "h": .3}}]
    assert c.put(f"/api/images/{img['id']}/annotations", json={"annotations": ann}).json()["saved"] == 1
    assert c.post(f"/api/images/{img['id']}/review", json={"approved": True}).json()["status"] == "done"
    # approve the rest of the seeded batch via the board
    moved = c.post(f"{BASE}/board/move", json={"batch_id": img["batchId"], "from_status": "review", "to_status": "done"})
    assert moved.json()["moved"] >= 1
    sp = c.post(f"/api/images/{img['id']}/smart-polygon", json={"points": [[0.5, 0.5]]})
    assert sp.status_code in (200, 422)
    assert c.post(f"/api/images/{img['id']}/comments", json={"text": "looks good"}).status_code == 200


def test_version_export_train_predict(c):
    v = c.post(f"{BASE}/versions", json={"settings": {
        "split": {"train": 70, "valid": 20, "test": 10},
        "preprocessing": {"resize": {"width": 320, "height": 320, "mode": "fit"}},
        "augmentation": {"outputs": 2, "flip_h": True, "brightness": 15}}}).json()
    wait_job(c, v["job"]["id"])
    v = c.get(f"{BASE}/versions/{v['id']}").json()
    assert v["status"] == "ready" and v["stats"]["images"] > 40
    for fmt in ("coco", "yolo", "voc"):
        e = c.post(f"{BASE}/versions/{v['id']}/export", json={"format": fmt}).json()
        wait_job(c, e["id"])
    ex = c.get(f"{BASE}/versions/{v['id']}").json()["exports"]["yolo"]
    data = c.get(ex["url"]).content
    assert "data.yaml" in zipfile.ZipFile(io.BytesIO(data)).namelist()

    m = c.post(f"{BASE}/train", json={"version_id": v["id"], "epochs": 1, "imgsz": 160, "size": "n", "batch": 4}).json()
    wait_job(c, m["jobId"], timeout=900)
    m = c.get(f"{BASE}/models/{m['id']}").json()
    assert m["status"] == "ready" and m["history"]

    img = jpeg((90, 90, 90))
    r = c.post(f"{BASE}/models/{m['id']}/predict", files={"file": ("t.jpg", img)}, data={"confidence": "0.01"})
    assert r.status_code == 200 and "predictions" in r.json()

    key = c.post(f"/api/ws/{WS}/keys", json={"name": "ci"}).json()["key"]
    anon = TestClient(app)
    hp = anon.post(f"/api/v1/models/{m['id']}/predict", headers={"x-api-key": key}, files={"file": ("t.jpg", img)})
    assert hp.status_code == 200, hp.text
    assert anon.post(f"/api/v1/models/{m['id']}/predict", headers={"x-api-key": "bad"}, files={"file": ("t.jpg", img)}).status_code == 401
    up = anon.post(f"/api/v1/{WS}/{PR}/upload", headers={"x-api-key": key}, files={"file": ("new.jpg", jpeg((1, 2, 3)))})
    assert up.json()["success"]


def test_remote_worker_protocol(c):
    anon = TestClient(app)
    assert anon.post("/api/worker/claim", json={}).status_code == 401
    # nothing queued for remote → empty claim
    r = anon.post("/api/worker/claim", json={"kinds": ["train"]}, headers={"X-Worker-Token": "test-worker-token-0123456789abcdef"})
    assert r.status_code == 200


def test_analytics_and_usage(c):
    a = c.get(f"{BASE}/analytics").json()
    assert a["images"] > 0 and len(a["heatmap"]) == 10
    u = c.get(f"/api/ws/{WS}/usage").json()
    assert u["credits_used"] > 0
    assert any(x["action"] == "train.start" for x in c.get(f"/api/ws/{WS}/audit").json())
