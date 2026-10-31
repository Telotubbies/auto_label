"""Adapter protocol, catalog and registry."""
import os
import tempfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-test-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import create_engine, inspect

from app.adapters import ADAPTERS, parse_ref, validate_prediction
from app.bootstrap import ensure_columns
from app.main import app

WS = "labeldesk-demo"


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        tok = client.post("/api/auth/login", json={"email": "demo@labeldesk.dev", "password": "demo1234"}).json()["token"]
        client.headers["Authorization"] = f"Bearer {tok}"
        yield client


def test_parse_ref():
    assert parse_ref("ultralytics:rtdetr-l") == ("ultralytics", "rtdetr-l")
    assert parse_ref("trained:abc123") == ("trained", "abc123")
    with pytest.raises(ValueError):
        parse_ref("rtdetr")


def test_catalog_lists_families_with_license(c):
    items = c.get(f"/api/ws/{WS}/registry").json()
    refs = {i["ref"] for i in items}
    assert {"ultralytics:yolo26n", "ultralytics:rtdetr-l", "ultralytics:yolov8s-worldv2", "sam3:sam3.1", "vlm:qwen2.5-vl-7b"} <= refs
    assert all(i["license"] for i in items)
    sam = next(i for i in items if i["ref"] == "sam3:sam3.1")
    assert sam["available"] is False and "LD_SAM_ENABLED" in sam["reason"]
    vlm = next(i for i in items if i["ref"] == "vlm:qwen2.5-vl-7b")
    assert vlm["available"] is False and vlm["reason"] == "vlm adapter not installed" and vlm["kind"] == "vlm"
    assert "yolo26l" not in {i["variant"] for i in items}


def test_every_available_adapter_returns_valid_schema():
    im = PImage.new("RGB", (64, 48))
    for fam, ad in ADAPTERS.items():
        if ad.probe().ok and fam == "ultralytics":
            validate_prediction(ad.predict("yolo26n", im))


def test_validate_prediction_rejects_bad_payload():
    good = {"model": "x:y", "image": {"width": 1, "height": 1}, "time": 0.1, "predictions": []}
    validate_prediction(good)
    with pytest.raises(ValueError):
        validate_prediction({**good, "predictions": [{"class": "a"}]})
    with pytest.raises(ValueError):
        validate_prediction({k: v for k, v in good.items() if k != "model"})


def test_sam3_segment_box_without_sam():
    assert ADAPTERS["sam3"].segment_box(PImage.new("RGB", (64, 48)), (1, 1, 30, 30)) == (None, 0.0)


def test_ensure_columns_is_idempotent(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path/'x.db'}")
    with eng.begin() as cn:
        cn.exec_driver_sql("CREATE TABLE t (id TEXT)")
    ensure_columns(eng, "t", {"family": "VARCHAR(32) DEFAULT 'ultralytics'"})
    ensure_columns(eng, "t", {"family": "VARCHAR(32)"})
    assert "family" in [col["name"] for col in inspect(eng).get_columns("t")]
