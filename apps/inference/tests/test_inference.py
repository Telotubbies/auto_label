"""Unit tests for the self-hosted inference service: scan, mapping, startup, upload validation.

No GPU, no network, no real weights: detectors are faked and ONNX output is synthesised.
"""

import io
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

import main
from detect import decode_onnx_output, map_ultralytics_result, scan_models

PNG = io.BytesIO()
Image.new("RGB", (64, 64), "red").save(PNG, format="PNG")
PNG_BYTES = PNG.getvalue()


def _model(root: Path, name: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"placeholder")
    return path


class _Boxes:
    def __init__(self, rows):  # rows: [(xyxy, class_id, confidence)]
        self.xyxy = [SimpleNamespace(tolist=lambda r=r[0]: list(r)) for r in rows]
        self.cls = [r[1] for r in rows]
        self.conf = [r[2] for r in rows]

    def __len__(self):
        return len(self.cls)


def test_scan_models_finds_supported_files_and_ignores_the_rest(tmp_path):
    _model(tmp_path, "ppe/best.onnx")
    _model(tmp_path, "detector.pt")
    _model(tmp_path, "best.engine")
    (tmp_path / "notes.txt").write_text("not a model")

    models = scan_models(tmp_path)

    assert [(m.name, m.backend) for m in models] == [
        ("best.engine", "tensorrt"),
        ("detector.pt", "ultralytics"),
        ("ppe/best.onnx", "onnxruntime"),
    ]
    assert all(m.size_bytes > 0 for m in models)


def test_scan_models_refuses_an_empty_directory(tmp_path):
    with pytest.raises(ValueError, match="no model files"):
        scan_models(tmp_path)


def test_map_ultralytics_result_uses_the_hosted_response_shape():
    boxes = _Boxes([((100.0, 50.0, 140.0, 90.0), 0, 0.87654)])
    result = SimpleNamespace(names={0: "helmet"}, boxes=boxes, masks=None, probs=None)

    out = map_ultralytics_result(result, Image.new("RGB", (640, 480)), 0.0123)

    assert out["image"] == {"width": 640, "height": 480}
    assert out["time"] == 0.0123
    assert out["predictions"] == [
        {
            "x": 120.0,
            "y": 70.0,
            "width": 40.0,
            "height": 40.0,
            "confidence": 0.8765,
            "class_id": 0,
            "class": "helmet",
        }
    ]


def test_decode_onnx_output_maps_letterboxed_boxes_back_to_the_image():
    # One class, one detection at the centre of a 640x640 letterboxed canvas.
    output = np.array([[[320.0], [320.0], [64.0], [64.0], [0.9]]], dtype=np.float32)

    preds = decode_onnx_output(output, {0: "person"}, (640, 320), scale=1.0, pad=(0, 160), confidence=0.25, iou=0.5)

    assert preds == [
        {
            "x": 320.0,
            "y": 160.0,
            "width": 64.0,
            "height": 64.0,
            "confidence": 0.9,
            "class_id": 0,
            "class": "person",
        }
    ]


def test_decode_onnx_output_drops_low_confidence_rows():
    output = np.array([[[320.0], [320.0], [64.0], [64.0], [0.1]]], dtype=np.float32)

    assert decode_onnx_output(output, {0: "person"}, (640, 640), scale=1.0, pad=(0, 0), confidence=0.25, iou=0.5) == []


def test_refuses_to_start_when_the_model_directory_is_empty(tmp_path):
    app = main.create_app(tmp_path)

    with pytest.raises(ValueError, match="no model files"):
        with TestClient(app):
            pass


def test_healthz_and_models_report_what_is_mounted(tmp_path):
    _model(tmp_path, "ppe/best.onnx")
    _model(tmp_path, "detector.pt")

    with TestClient(main.create_app(tmp_path)) as client:
        health = client.get("/healthz")
        catalog = client.get("/models")

    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    assert body["models"]["count"] == 2
    assert body["models"]["files"] == ["detector.pt", "ppe/best.onnx"]
    assert set(body["backends"]) == {"ultralytics", "onnxruntime", "tensorrt"}
    assert body["versions"]["service"]

    assert catalog.status_code == 200
    rows = catalog.json()["models"]
    assert [row["name"] for row in rows] == ["detector.pt", "ppe/best.onnx"]
    assert [row["backend"] for row in rows] == ["ultralytics", "onnxruntime"]
    assert all({"name", "backend", "size_bytes", "available", "reason"} <= set(row) for row in rows)


def test_predict_rejects_a_non_image_upload(tmp_path):
    _model(tmp_path, "best.onnx")

    with TestClient(main.create_app(tmp_path)) as client:
        response = client.post("/predict", files={"file": ("notes.txt", b"not an image", "text/plain")})

    assert response.status_code == 400
    assert response.json()["detail"] == "not a valid image"


def test_predict_requires_a_model_name_when_several_are_mounted(tmp_path):
    _model(tmp_path, "a.onnx")
    _model(tmp_path, "b.onnx")

    with TestClient(main.create_app(tmp_path)) as client:
        missing = client.post("/predict", files={"file": ("x.png", PNG_BYTES, "image/png")})
        unknown = client.post("/predict", files={"file": ("x.png", PNG_BYTES, "image/png")}, data={"model": "nope"})

    assert missing.status_code == 400
    assert "pass model=" in missing.json()["detail"]
    assert unknown.status_code == 404


def test_predict_returns_the_detector_result_with_the_model_name(tmp_path, monkeypatch):
    _model(tmp_path, "best.pt")

    class FakeDetector:
        def predict(self, im, confidence):
            assert confidence == 0.5
            return {
                "predictions": [
                    {
                        "x": 10.0,
                        "y": 20.0,
                        "width": 30.0,
                        "height": 40.0,
                        "confidence": 0.75,
                        "class_id": 0,
                        "class": "box",
                    }
                ],
                "time": 0.01,
                "image": {"width": im.width, "height": im.height},
            }

    monkeypatch.setattr(main, "missing_dependencies", lambda entry: [])
    monkeypatch.setattr(main, "build_detector", lambda entry: FakeDetector())

    with TestClient(main.create_app(tmp_path)) as client:
        response = client.post(
            "/predict", files={"file": ("x.png", PNG_BYTES, "image/png")}, data={"confidence": "0.5"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "best.pt"
    assert body["predictions"][0]["class"] == "box"
    assert body["image"] == {"width": 64, "height": 64}
