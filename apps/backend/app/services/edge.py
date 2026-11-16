"""Edge deployment presets: which Ultralytics export a device target needs.

`verified` is False until the preset has actually been run on the target device; the API and UI
must present those presets as UNVERIFIED. Task 34 extends the Task 14 TensorRT export.
"""

from ..models import Version
from . import versioning


def _preset(label: str, hint: str, fmt: str, **kw) -> dict:
    return {
        "label": label,
        "hint": hint,
        "format": fmt,
        "options": {},
        "device": None,
        "verified": False,
        "needs_data": False,
        "requires": None,
        **kw,
    }


PRESETS: dict[str, dict] = {
    "onnx": _preset("ONNX (FP32)", "Portable graph for ONNX Runtime and vendor compilers", "onnx"),
    "onnx-nms-free": _preset(
        "ONNX NMS-free (YOLO26)",
        "YOLO26 end-to-end graph with no NMS post-processing",
        "onnx",
        options={"nms": False},
        requires="yolo26",
    ),
    "openvino": _preset("OpenVINO IR", "Intel CPU/iGPU inference through OpenVINO", "openvino"),
    "tflite-int8": _preset(
        "TFLite INT8",
        "Quantized LiteRT/TFLite model for CPU accelerators",
        "tflite",
        needs_data=True,
    ),
    "jetson": _preset(
        "Jetson (TensorRT FP16)",
        "TensorRT engine for NVIDIA Jetson",
        "engine",
        options={"half": True},
        device="NVIDIA Jetson",
    ),
    "hailo": _preset(
        "Hailo-8",
        "Hailo DFC artifact for Hailo-8 accelerators",
        "hailo",
        options={"quantize": 8, "name": "hailo8"},
        device="Hailo-8",
        needs_data=True,
    ),
    "deepx": _preset(
        "DEEPX DX-M1",
        "DEEPX compiler artifact for DX-M1 NPUs",
        "deepx",
        options={"quantize": 8},
        device="DEEPX DX-M1",
        needs_data=True,
    ),
}


def get_preset(preset: str) -> dict:
    if preset not in PRESETS:
        raise ValueError(f"unknown export preset {preset!r}")
    return PRESETS[preset]


def public_presets() -> list[dict]:
    """What the UI may show: no internal export kwargs."""
    return [
        {
            "id": key,
            "label": spec["label"],
            "hint": spec["hint"],
            "device": spec["device"],
            "verified": bool(spec["verified"]),
            "status": "VERIFIED" if spec["verified"] else "UNVERIFIED",
            "needs_data": spec["needs_data"],
            "requires": spec["requires"],
        }
        for key, spec in PRESETS.items()
    ]


def _ultralytics_version() -> tuple[int, int, int]:
    """Installed ultralytics version without importing torch (the API never needs it to list presets)."""
    try:
        from importlib.metadata import version

        parts = [int(p) for p in version("ultralytics").split(".")[:3] if p.isdigit()]
        return tuple((parts + [0, 0, 0])[:3])
    except Exception:
        return (0, 0, 0)


def supported(preset: str) -> tuple[bool, str]:
    """Whether this worker's ultralytics can build the preset; engine availability is probed separately."""
    fmt = get_preset(preset)["format"]
    if fmt == "engine":
        return True, ""
    current = _ultralytics_version()
    if current < (8, 3, 0):
        return False, "ultralytics is not installed on this worker"
    if fmt in ("hailo", "deepx") and current < (8, 4, 0):
        return False, f"the installed ultralytics cannot export {fmt} (8.4+ required)"
    return True, ""


def export_plan(preset: str) -> tuple[str, dict]:
    """(format, kwargs) for `ultralytics.YOLO.export`, tolerant of the 8.3 -> 8.4 rename."""
    spec = get_preset(preset)
    if spec["format"] != "tflite":
        return spec["format"], dict(spec["options"])
    if _ultralytics_version() >= (8, 4, 83):  # tflite became the deprecated alias of litert
        return "litert", {"quantize": 8}
    return "tflite", {"int8": True}  # 8.3's INT8 switch


def calibration_data(version: Version, task: str) -> str:
    """The dataset path `ultralytics` reads INT8 calibration images from.

    Detection/segmentation take a YOLO data.yaml; classification takes the dataset root
    (train/<class>/…), which is what `check_cls_dataset` expects.
    """
    if task == "classify":
        return str(versioning.cached_export(version, "folder"))
    return str(versioning.cached_export(version, "yolo") / "data.yaml")
