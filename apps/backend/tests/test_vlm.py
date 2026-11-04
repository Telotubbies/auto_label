import base64
import io
import json
import os

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import httpx
import pytest
from PIL import Image as PImage

from app.adapters import ADAPTERS, validate_prediction
from app.adapters.vlm_ad import VlmAdapter, smart_resize

URL = "http://localhost:8000/v1"


def vlm_with_reply(content, capture=None, status=200):
    def handler(req: httpx.Request):
        if capture is not None:
            capture.append(json.loads(req.content) if req.content else {"url": str(req.url), "method": req.method})
            capture[-1].setdefault("url", str(req.url))
        if req.url.path.endswith("/chat/completions"):
            text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
            return httpx.Response(status, json={"choices": [{"message": {"content": text}}]})
        return httpx.Response(200, json={"data": [{"id": "m"}], "is_sleeping": False})
    return VlmAdapter(url=URL, model="m", transport=httpx.MockTransport(handler))


@pytest.fixture
def captured():
    return []


def test_ground_rescales_to_original_pixels():
    ad = vlm_with_reply({"objects": [{"label": "helmet", "bbox_2d": [28, 28, 56, 56]}]})
    im = PImage.new("RGB", (6000, 4000))
    h2, w2 = smart_resize(4000, 6000)
    p = ad.ground(im, ["helmet"])["predictions"][0]
    assert p["x"] == pytest.approx((28 + 56) / 2 * 6000 / w2, rel=1e-3)
    assert p["confidence"] == 0.5


def test_sent_image_is_smart_resized(captured):
    vlm_with_reply({"objects": []}, capture=captured).ground(PImage.new("RGB", (6000, 4000)), ["a"])
    url = captured[0]["messages"][0]["content"][0]["image_url"]["url"]
    sent = PImage.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))
    h2, w2 = smart_resize(4000, 6000)
    assert sent.size == (w2, h2) and w2 * h2 <= 589824


def test_smart_resize_rules():
    assert smart_resize(100, 100) == (112, 112)
    h, w = smart_resize(4000, 6000)
    assert h % 28 == 0 and w % 28 == 0 and h * w <= 589824
    h, w = smart_resize(10, 10)
    assert h * w >= 3136


def test_request_uses_json_schema_enum_and_never_guided(captured):
    vlm_with_reply({"objects": []}, capture=captured).ground(PImage.new("RGB", (64, 64)), ["หมวกนิรภัย", "safety vest"])
    body = captured[0]
    assert body["response_format"]["type"] == "json_schema"
    assert body["temperature"] == 0
    assert "guided_json" not in json.dumps(body) and "หมวกนิรภัย" in json.dumps(body, ensure_ascii=False)
    enum = body["response_format"]["json_schema"]["schema"]["properties"]["objects"]["items"]["properties"]["label"]["enum"]
    assert enum == ["หมวกนิรภัย", "safety vest"]


def test_thai_label_maps_to_class_id():
    ad = vlm_with_reply({"objects": [{"label": "safety vest", "bbox_2d": [0, 0, 28, 28]}]})
    p = ad.ground(PImage.new("RGB", (280, 280)), ["หมวกนิรภัย", "safety vest"])["predictions"][0]
    assert p["class"] == "safety vest" and p["class_id"] == 1


def test_bad_json_returns_empty():
    assert vlm_with_reply("not json").ground(PImage.new("RGB", (64, 64)), ["a"])["predictions"] == []


def test_verify_uses_choice(captured):
    ad = vlm_with_reply("no", capture=captured)
    assert ad.verify(PImage.new("RGB", (200, 200)), (50, 50, 100, 100), "helmet") is False
    assert captured[0]["structured_outputs"]["choice"] == ["yes", "no"]
    assert "guided_choice" not in json.dumps(captured[0])
    assert vlm_with_reply("yes").verify(PImage.new("RGB", (200, 200)), (50, 50, 100, 100), "helmet") is True


def test_parse_prompt_caps_at_8():
    ad = vlm_with_reply({"phrases": [f"p{i}" for i in range(12)]})
    assert ad.parse_prompt("x") == [f"p{i}" for i in range(8)]
    assert vlm_with_reply("garbage").parse_prompt("x") == []


def test_ask_and_yes_no():
    assert vlm_with_reply("a cat").ask(PImage.new("RGB", (64, 64)), "what?") == "a cat"
    assert vlm_with_reply("yes").ask_yes_no(PImage.new("RGB", (64, 64)), "cat?") is True


def test_predict_prompt_and_ground_validate():
    ad = vlm_with_reply("a cat")
    out = ad.predict("qwen2.5-vl-7b", PImage.new("RGB", (64, 64)), prompt="what?")
    validate_prediction(out)
    assert out["text"] == "a cat" and out["predictions"] == []
    out = vlm_with_reply({"objects": []}).predict("qwen2.5-vl-7b", PImage.new("RGB", (64, 64)), classes=["a"])
    validate_prediction(out)


def test_probe_unreachable_reason():
    def boom(req):
        raise httpx.ConnectError("no")
    ad = VlmAdapter(url=URL, model="m", transport=httpx.MockTransport(boom))
    av = ad.probe()
    assert av.ok is False and "not reachable" in av.reason
    with pytest.raises(RuntimeError, match="vLLM not reachable at"):
        ad.ask(PImage.new("RGB", (64, 64)), "q")


def test_probe_ok():
    assert vlm_with_reply("x").probe().ok is True


def test_sleep_hits_root_not_v1(captured):
    ad = vlm_with_reply("x", capture=captured)
    ad.sleep()
    assert captured[0]["url"] == "http://localhost:8000/sleep?level=1" and captured[0]["method"] == "POST"
    ad.wake()
    assert captured[1]["url"] == "http://localhost:8000/wake_up"
    assert ad.is_sleeping() is False


def test_registered_and_capabilities():
    ad = ADAPTERS["vlm"]
    assert ad.capabilities("qwen2.5-vl-7b") == {"detect", "open-vocab", "vqa"}
