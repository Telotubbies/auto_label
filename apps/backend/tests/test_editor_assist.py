"""Editor assists: upload failure reporting and VLM class suggestion."""
import io
import os

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage

import numpy as np

from app.main import app
from app.routers import images as images_router
from app.services import segment

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/ws/{WS}/projects/{PR}"


def jpeg(color=(180, 60, 60)) -> bytes:
    b = io.BytesIO()
    PImage.new("RGB", (200, 150), color).save(b, "JPEG")
    return b.getvalue()


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        tok = client.post("/api/auth/login", json={"email": "demo@labeldesk.dev", "password": "demo1234"}).json()["token"]
        client.headers["Authorization"] = f"Bearer {tok}"
        yield client


def upload(c, name="assist.jpg", color=(120, 90, 40)) -> str:
    r = c.post(f"{BASE}/upload", files=[("files", (name, jpeg(color)))])
    assert r.status_code == 200, r.text
    return r.json()["images"][0]["id"]


class _FakeAdapter:
    def __init__(self, verdict):
        self._verdict = verdict

    def verify(self, im, box, name):
        return self._verdict(name)


class _FakeResolved:
    def __init__(self, verdict):
        self.adapter = _FakeAdapter(verdict)


def test_upload_reports_unreadable_files(c):
    r = c.post(f"{BASE}/upload", files=[("files", ("good.jpg", jpeg())), ("files", ("broken.jpg", b"not an image"))])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["uploaded"] == 1
    assert body["failed"] == [{"name": "broken.jpg", "reason": "unreadable image"}]


def test_suggest_class_picks_first_matching_class(c, monkeypatch):
    image_id = upload(c, "suggest.jpg", (30, 200, 100))
    classes = c.get(f"{BASE}/classes").json()
    assert classes
    ann = [{"id": "suggest-1", "classId": classes[0]["id"],
            "shape": {"kind": "bbox", "x": .2, "y": .2, "w": .3, "h": .3}}]
    assert c.put(f"/api/images/{image_id}/annotations", json={"annotations": ann}).status_code == 200

    monkeypatch.setattr(images_router, "resolve", lambda *a, **k: _FakeResolved(lambda name: name == classes[0]["name"]))
    r = c.post(f"/api/images/{image_id}/suggest-class", json={"annotation_id": "suggest-1"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["classId"] == classes[0]["id"]
    assert body["name"] == classes[0]["name"]
    assert body["checked"] == len(classes)


def test_suggest_class_passes_the_annotation_box(c, monkeypatch):
    image_id = upload(c, "box.jpg", (200, 20, 20))
    classes = c.get(f"{BASE}/classes").json()
    ann = [{"id": "box-1", "classId": classes[0]["id"],
            "shape": {"kind": "bbox", "x": .2, "y": .2, "w": .3, "h": .3}}]
    assert c.put(f"/api/images/{image_id}/annotations", json={"annotations": ann}).status_code == 200
    seen = []

    class Adapter:
        def verify(self, im, box, name):
            seen.append(box)
            return False

    monkeypatch.setattr(images_router, "resolve", lambda *a, **k: type("R", (), {"adapter": Adapter()})())
    r = c.post(f"/api/images/{image_id}/suggest-class", json={"annotation_id": "box-1"})
    assert r.status_code == 200, r.text
    assert seen and seen[0] == pytest.approx((40, 30, 100, 75))   # 200x150 image, normalized .2/.2/.3/.3


def test_suggest_class_requires_annotator_assignment(c):
    image_id = upload(c, "not-mine.jpg", (60, 10, 10))
    anon = TestClient(app)
    tok = anon.post("/api/auth/login", json={"email": "labeler@labeldesk.dev", "password": "demo1234"}).json()["token"]
    r = anon.post(f"/api/images/{image_id}/suggest-class", json={"annotation_id": "who"},
                  headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403


def test_suggest_class_unknown_annotation(c):
    image_id = upload(c, "unknown.jpg", (10, 60, 10))
    r = c.post(f"/api/images/{image_id}/suggest-class", json={"annotation_id": "missing"})
    assert r.status_code == 404


def test_suggest_class_model_unavailable(c, monkeypatch):
    image_id = upload(c, "unavailable.jpg", (40, 40, 200))
    classes = c.get(f"{BASE}/classes").json()

    def boom(*a, **k):
        raise RuntimeError("vLLM not reachable at http://localhost:8000/v1")

    monkeypatch.setattr(images_router, "resolve", lambda *a, **k: _FakeResolved(boom))
    ann = [{"id": "suggest-2", "classId": classes[0]["id"],
            "shape": {"kind": "bbox", "x": .1, "y": .1, "w": .2, "h": .2}}]
    c.put(f"/api/images/{image_id}/annotations", json={"annotations": ann})
    r = c.post(f"/api/images/{image_id}/suggest-class", json={"annotation_id": "suggest-2"})
    assert r.status_code == 503
    assert r.json()["detail"] == "model unavailable"


def _area(poly: list[float]) -> float:
    pts = list(zip(poly[0::2], poly[1::2]))
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))) / 2


def test_smart_polygon_negative_clicks_shrink_sam_mask(monkeypatch):
    torch = pytest.importorskip("torch")
    h = w = 400
    mask = np.zeros((h, w), dtype="float32")
    mask[50:350, 50:150] = 1                 # dumbbell: two squares joined by a thin bar
    mask[50:350, 250:350] = 1
    mask[198:202, 150:250] = 1               # thin bar: a 4px circle fully severs it

    class FakeSam:
        def set_image(self, im):
            return "state"

        def add_geometric_prompt(self, box, positive, state):
            return {"masks": torch.as_tensor(mask[None]), "scores": torch.tensor([0.9])}

    monkeypatch.setattr(segment, "_try_lease_sam", lambda: FakeSam())
    im = PImage.new("RGB", (w, h), (128, 128, 128))
    base, source = segment.smart_polygon(im, [[0.5, 0.5]])
    assert source == "sam3.1" and base
    shrunk, source = segment.smart_polygon(im, [[0.5, 0.5]], [[0.45, 0.5], [0.55, 0.5]])
    assert source == "sam3.1" and shrunk
    assert _area(shrunk) < _area(base) * 0.2   # negatives cut the bar, leaving only the seed segment
