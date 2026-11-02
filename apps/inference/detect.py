"""Model discovery, runtime selection and response mapping for the self-hosted inference service.

The CPU image installs onnxruntime only. `.pt` models load through ultralytics and `.engine`
models through ultralytics + TensorRT; both imports happen inside the detector constructor so a
container serving only `.onnx` files never imports torch.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import logging
import threading
import time
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

log = logging.getLogger("labeldesk.inference")

SERVICE_VERSION = "1.0.0"

# file suffix -> backend that can serve it
SUPPORTED = {".pt": "ultralytics", ".onnx": "onnxruntime", ".engine": "tensorrt"}

# backend -> third-party modules that must be importable
BACKEND_DEPS: dict[str, tuple[str, ...]] = {
    "ultralytics": ("ultralytics",),
    "onnxruntime": ("onnxruntime",),
    "tensorrt": ("ultralytics", "tensorrt"),  # engines run through YOLO() on the TensorRT runtime
}

# module -> distribution names to read the version from without importing the package
DIST_NAMES: dict[str, tuple[str, ...]] = {
    "ultralytics": ("ultralytics",),
    "onnxruntime": ("onnxruntime", "onnxruntime-gpu"),
    "tensorrt": ("tensorrt",),
}


@dataclass(frozen=True)
class ModelFile:
    """One servable file under the mounted model directory. `name` is unique and path-like."""

    name: str
    path: Path
    backend: str
    size_bytes: int

    def as_dict(self, available: bool, reason: str = "") -> dict:
        return {
            "name": self.name,
            "backend": self.backend,
            "size_bytes": self.size_bytes,
            "available": available,
            "reason": reason,
        }


def _installed(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def missing_dependencies(entry: ModelFile) -> list[str]:
    """Third-party modules this file needs but the current image does not provide."""
    return [module for module in BACKEND_DEPS[entry.backend] if not _installed(module)]


def backend_availability() -> dict[str, bool]:
    return {backend: all(_installed(module) for module in deps) for backend, deps in BACKEND_DEPS.items()}


def backend_versions() -> dict[str, str | None]:
    """Service and backend versions for /healthz; read from distribution metadata, never imports torch."""
    versions: dict[str, str | None] = {"service": SERVICE_VERSION}
    for module, dists in DIST_NAMES.items():
        if not _installed(module):
            versions[module] = None
            continue
        for dist in dists:
            try:
                versions[module] = metadata.version(dist)
                break
            except metadata.PackageNotFoundError:
                continue
        else:
            versions[module] = "unknown"
    return versions


def scan_models(root: Path) -> list[ModelFile]:
    """Every supported model file under `root`, sorted by relative path.

    Raises ValueError for a missing/empty directory so the service refuses to start with no models.
    """
    if not root.is_dir():
        raise ValueError(f"model directory {root} does not exist")
    paths = sorted(
        (p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED),
        key=lambda p: p.relative_to(root).as_posix(),
    )
    found = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        found.append(
            ModelFile(name=relative, path=path, backend=SUPPORTED[path.suffix.lower()], size_bytes=path.stat().st_size)
        )
    if not found:
        raise ValueError(f"no model files (*.pt, *.onnx, *.engine) found under {root}")
    return found


def parse_names(raw: str | None) -> dict[int, str]:
    """Ultralytics stores class names as `{0: 'person', ...}` in ONNX metadata (sometimes JSON)."""
    if not raw:
        return {}
    value: Any
    try:
        value = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    if isinstance(value, dict):
        try:
            return {int(k): str(v) for k, v in value.items()}
        except (TypeError, ValueError):
            return {}
    if isinstance(value, (list, tuple)):
        return {i: str(v) for i, v in enumerate(value)}
    return {}


def map_ultralytics_result(result: Any, im: Image.Image, elapsed: float) -> dict:
    """Map an ultralytics `Results` object to the hosted API response shape (centre-based pixels)."""
    names = getattr(result, "names", None) or {}

    def name(index: int) -> str:
        return names.get(index, str(index))

    preds: list[dict] = []
    probs = getattr(result, "probs", None)
    if probs is not None:  # classification result: no boxes
        values = [float(v) for v in probs.data.float().cpu().tolist()]
        order = sorted(range(len(values)), key=lambda i: -values[i])
        preds = [{"class": name(i), "class_id": i, "confidence": round(values[i], 4)} for i in order[:5]]
        return {
            "predictions": preds,
            "top": preds[0]["class"] if preds else None,
            "time": round(elapsed, 4),
            "image": {"width": im.width, "height": im.height},
        }

    boxes = result.boxes
    masks = getattr(result, "masks", None)
    polys = masks.xyn if masks is not None else None
    for i in range(len(boxes)):
        x1, y1, x2, y2 = boxes.xyxy[i].tolist()
        class_id = int(boxes.cls[i])
        pred = {
            "x": round((x1 + x2) / 2, 1),
            "y": round((y1 + y2) / 2, 1),
            "width": round(x2 - x1, 1),
            "height": round(y2 - y1, 1),
            "confidence": round(float(boxes.conf[i]), 4),
            "class_id": class_id,
            "class": name(class_id),
        }
        if polys is not None and i < len(polys):
            pred["points"] = [
                {"x": round(float(px) * im.width, 1), "y": round(float(py) * im.height, 1)} for px, py in polys[i]
            ]
        preds.append(pred)
    return {"predictions": preds, "time": round(elapsed, 4), "image": {"width": im.width, "height": im.height}}


def _letterbox(im: Image.Image, size: tuple[int, int]) -> tuple[np.ndarray, float, tuple[int, int]]:
    """Resize/pad to the ONNX input like ultralytics does; returns the tensor, scale and (pad_x, pad_y)."""
    target_h, target_w = size
    scale = min(target_w / im.width, target_h / im.height)
    new_w, new_h = max(1, round(im.width * scale)), max(1, round(im.height * scale))
    resized = im.resize((new_w, new_h), Image.Resampling.BILINEAR)
    canvas = Image.new("RGB", (target_w, target_h), (114, 114, 114))
    pad_x, pad_y = (target_w - new_w) // 2, (target_h - new_h) // 2
    canvas.paste(resized, (pad_x, pad_y))
    tensor = np.asarray(canvas, dtype=np.float32).transpose(2, 0, 1)[None] / 255.0
    return np.ascontiguousarray(tensor), scale, (pad_x, pad_y)


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> list[int]:
    """Greedy per-class NMS; boxes are x1, y1, x2, y2."""
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size:
        best = int(order[0])
        keep.append(best)
        if order.size == 1:
            break
        rest = order[1:]
        xx1 = np.maximum(boxes[best, 0], boxes[rest, 0])
        yy1 = np.maximum(boxes[best, 1], boxes[rest, 1])
        xx2 = np.minimum(boxes[best, 2], boxes[rest, 2])
        yy2 = np.minimum(boxes[best, 3], boxes[rest, 3])
        inter = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
        area_best = (boxes[best, 2] - boxes[best, 0]) * (boxes[best, 3] - boxes[best, 1])
        area_rest = (boxes[rest, 2] - boxes[rest, 0]) * (boxes[rest, 3] - boxes[rest, 1])
        iou = inter / np.maximum(area_best + area_rest - inter, 1e-9)
        order = rest[iou <= iou_threshold]
    return keep


def decode_onnx_output(
    output: np.ndarray,
    names: dict[int, str],
    image_size: tuple[int, int],
    *,
    scale: float,
    pad: tuple[int, int],
    confidence: float,
    iou: float,
    num_classes: int | None = None,
) -> list[dict]:
    """Decode a standard Ultralytics detection ONNX output: (1, 4+nc, N) or (1, N, 4+nc).

    Segmentation exports carry 32 extra mask-coefficient columns; only their boxes are decoded.
    Coordinates are letterboxed, so undo the resize/pad before returning image pixels.
    """
    arr = np.asarray(output)
    if arr.ndim == 3:
        arr = arr[0]
    if arr.ndim != 2:
        raise ValueError(f"unsupported ONNX output shape {arr.shape}")
    channels = 4 + num_classes if num_classes else (4 + len(names) if names else None)
    if channels is not None and arr.shape[0] in (channels, channels + 32):
        arr = arr.T  # (4+nc[, +32 mask coeffs], N) -> (N, C)
    elif channels is not None and arr.shape[1] in (channels, channels + 32):
        pass  # already (N, C)
    elif arr.shape[0] < arr.shape[1] or arr.shape[1] < 5:
        arr = arr.T
    if arr.shape[1] < 5:
        raise ValueError(f"unsupported ONNX output shape {arr.shape}")
    nc = num_classes or len(names) or max(1, arr.shape[1] - 4)
    if arr.shape[1] < 4 + nc:
        raise ValueError(f"ONNX output has {arr.shape[1]} columns but {nc} classes need {4 + nc}")
    scores = arr[:, 4 : 4 + nc]
    class_ids = scores.argmax(axis=1)
    confidences = scores[np.arange(len(scores)), class_ids]
    rows = np.where(confidences >= confidence)[0]
    if rows.size == 0:
        return []

    cx, cy, bw, bh = arr[rows, 0], arr[rows, 1], arr[rows, 2], arr[rows, 3]
    x1 = (cx - bw / 2 - pad[0]) / scale
    y1 = (cy - bh / 2 - pad[1]) / scale
    x2 = (cx + bw / 2 - pad[0]) / scale
    y2 = (cy + bh / 2 - pad[1]) / scale
    width, height = image_size
    boxes = np.stack(
        [np.clip(x1, 0, width), np.clip(y1, 0, height), np.clip(x2, 0, width), np.clip(y2, 0, height)], axis=1
    )
    ids, confs = class_ids[rows], confidences[rows]

    preds = []
    for class_id in np.unique(ids):
        group = np.where(ids == class_id)[0]
        for picked in _nms(boxes[group], confs[group], iou):
            index = int(group[picked])
            box = boxes[index]
            preds.append(
                {
                    "x": round(float((box[0] + box[2]) / 2), 1),
                    "y": round(float((box[1] + box[3]) / 2), 1),
                    "width": round(float(box[2] - box[0]), 1),
                    "height": round(float(box[3] - box[1]), 1),
                    "confidence": round(float(confs[index]), 4),
                    "class_id": int(class_id),
                    "class": names.get(int(class_id), str(int(class_id))),
                }
            )
    preds.sort(key=lambda p: -p["confidence"])
    return preds


def _input_size(shape: list[Any]) -> tuple[int, int]:
    """Static ONNX input (1, 3, H, W); dynamic axes fall back to 640x640."""
    height = shape[2] if len(shape) > 2 and isinstance(shape[2], int) and shape[2] > 0 else 640
    width = shape[3] if len(shape) > 3 and isinstance(shape[3], int) and shape[3] > 0 else 640
    return height, width


class UltralyticsDetector:
    """`.pt` checkpoints and `.engine` files through ultralytics (TensorRT is checked by the caller)."""

    def __init__(self, path: Path):
        from ultralytics import YOLO

        self.model = YOLO(str(path))
        self._lock = threading.Lock()  # one model instance handles one image at a time

    def predict(self, im: Image.Image, confidence: float, iou: float = 0.5) -> dict:
        started = time.perf_counter()
        with self._lock:
            result = self.model.predict(im, conf=confidence, iou=iou, verbose=False)[0]
        return map_ultralytics_result(result, im, time.perf_counter() - started)


class OnnxDetector:
    """`.onnx` files through onnxruntime; CPU by default, CUDA when the GPU image provides it."""

    def __init__(self, path: Path):
        import onnxruntime as ort

        available = ort.get_available_providers()
        providers = [p for p in ("CUDAExecutionProvider", "CPUExecutionProvider") if p in available]
        self.session = ort.InferenceSession(str(path), providers=providers or None)
        self._lock = threading.Lock()
        model_input = self.session.get_inputs()[0]
        self.input_name = model_input.name
        self.size = _input_size(model_input.shape)
        meta = dict(self.session.get_modelmeta().custom_metadata_map or {})
        self.names = parse_names(meta.get("names"))
        self.task = meta.get("task", "detect")

    def predict(self, im: Image.Image, confidence: float, iou: float = 0.5) -> dict:
        started = time.perf_counter()
        tensor, scale, pad = _letterbox(im.convert("RGB"), self.size)
        with self._lock:
            outputs = self.session.run(None, {self.input_name: tensor})
        preds = decode_onnx_output(
            outputs[0],
            self.names,
            im.size,
            scale=scale,
            pad=pad,
            confidence=confidence,
            iou=iou,
            num_classes=len(self.names) or None,
        )
        return {
            "predictions": preds,
            "time": round(time.perf_counter() - started, 4),
            "image": {"width": im.width, "height": im.height},
        }


def build_detector(entry: ModelFile) -> OnnxDetector | UltralyticsDetector:
    """Load the runtime for one file. Dependencies are checked by the caller before this is called."""
    if entry.backend == "onnxruntime":
        return OnnxDetector(entry.path)
    return UltralyticsDetector(entry.path)
