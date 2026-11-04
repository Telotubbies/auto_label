"""Smart Polygon simplification: epsilon clamping, point-count monotonicity, mask reuse."""

import io
import os

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage

from app.main import app
from app.services import segment

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/ws/{WS}/projects/{PR}"


def jpeg(color=(12, 200, 90)) -> bytes:
    b = io.BytesIO()
    PImage.new("RGB", (200, 150), color).save(b, "JPEG")
    return b.getvalue()


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        tok = client.post(
            "/api/auth/login",
            json={"email": "demo@labeldesk.dev", "password": "demo1234"},
        ).json()["token"]
        client.headers["Authorization"] = f"Bearer {tok}"
        yield client


def upload(c) -> str:
    r = c.post(f"{BASE}/upload", files=[("files", ("epsilon.jpg", jpeg()))])
    assert r.status_code == 200, r.text
    return r.json()["images"][0]["id"]


def circle_mask(size: int = 600, radius: int = 220) -> np.ndarray:
    """A round blob: a smooth contour, so the epsilon actually moves the point count."""
    mask = np.zeros((size, size), dtype="uint8")
    mask_value = 1
    import cv2

    cv2.circle(mask, (size // 2, size // 2), radius, mask_value, -1)
    return mask


def test_clamp_epsilon_keeps_values_inside_the_range():
    assert segment.clamp_epsilon(0.004) == 0.004
    assert segment.clamp_epsilon(0.0001) == segment.EPS_MIN
    assert segment.clamp_epsilon(1.0) == segment.EPS_MAX
    assert segment.EPS_MIN == 0.0005
    assert segment.EPS_MAX == 0.02


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_clamp_epsilon_rejects_non_finite(bad):
    with pytest.raises(ValueError):
        segment.clamp_epsilon(bad)


def test_fewer_points_as_epsilon_grows():
    mask = circle_mask()
    counts = [
        len(segment.mask_to_polygon(mask, eps=e) or []) // 2
        for e in (0.0005, 0.004, 0.01, 0.02)
    ]
    assert all(count >= 3 for count in counts), counts
    assert counts == sorted(counts, reverse=True), counts
    assert counts[0] > counts[-1]


def test_smart_polygon_clamps_and_passes_epsilon(c, monkeypatch):
    seen: list[float] = []

    def fake(im, points, negatives=None, eps=segment.DEFAULT_EPS, cache_key=None):
        seen.append(eps)
        return [0.1, 0.1, 0.9, 0.1, 0.9, 0.9], "grabcut"

    monkeypatch.setattr(segment, "smart_polygon", fake)
    image_id = upload(c)
    url = f"/api/images/{image_id}/smart-polygon"

    assert c.post(url, json={"points": [[0.5, 0.5]]}).status_code == 200
    assert seen[-1] == segment.DEFAULT_EPS
    over = c.post(url, json={"points": [[0.5, 0.5]], "epsilon": 0.5})
    assert over.status_code == 200
    assert seen[-1] == segment.EPS_MAX
    assert over.json()["epsilon"] == segment.EPS_MAX      # the client learns the clamped value
    assert c.post(url, json={"points": [[0.5, 0.5]], "epsilon": -3}).status_code == 200
    assert seen[-1] == segment.EPS_MIN
    assert (
        c.post(url, json={"points": [[0.5, 0.5]], "epsilon": 0.008}).status_code == 200
    )
    assert seen[-1] == 0.008


def test_slider_moves_reuse_the_mask(monkeypatch):
    torch = pytest.importorskip("torch")
    size = 400
    mask = circle_mask(size, 150)
    calls = {"prompts": 0}

    class FakeSam:
        def set_image(self, im):
            return "state"

        def add_geometric_prompt(self, box, positive, state):
            calls["prompts"] += 1
            return {"masks": torch.as_tensor(mask[None]), "scores": torch.tensor([0.9])}

    monkeypatch.setattr(segment, "_try_lease_sam", lambda: FakeSam())
    im = PImage.new("RGB", (size, size), (128, 128, 128))

    detailed, source = segment.smart_polygon(
        im, [[0.5, 0.5]], eps=segment.EPS_MIN, cache_key="image-1"
    )
    coarse, source2 = segment.smart_polygon(
        im, [[0.5, 0.5]], eps=segment.EPS_MAX, cache_key="image-1"
    )
    assert source == source2 == "sam3.1"
    assert detailed and coarse
    assert calls["prompts"] == 1, "a slider move must not prompt SAM again"
    assert len(coarse) <= len(detailed)
