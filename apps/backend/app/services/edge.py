"""Edge deployment presets: which Ultralytics export a device target needs.

`verified` is False until the preset has actually been run on the target device; the API and UI
must present those presets as UNVERIFIED. Task 34 extends the Task 14 TensorRT export.
"""

from ..models import Version
from . import versioning


DTYPE_LABEL = {"fp32": "FP32 (full precision)", "fp16": "FP16 (half precision)", "int8": "INT8 (quantized)"}
_DTYPE_SWITCHES = ("half", "int8", "quantize")      # export kwargs a dtype owns


def _preset(label: str, hint: str, fmt: str, **kw) -> dict:
    """``dtypes`` lists what the preset can really build, default first; INT8 needs calibration images."""
    spec = {
        "label": label,
        "hint": hint,
        "format": fmt,
        "options": {},
        "device": None,
        "verified": False,
        "dtypes": ["fp32"],
        "requires": None,
        **kw,
    }
    spec["needs_data"] = spec["dtypes"][0] == "int8"
    return spec


PRESETS: dict[str, dict] = {
    "onnx": _preset("ONNX", "Portable graph for ONNX Runtime and vendor compilers", "onnx", dtypes=["fp32", "fp16"]),
    "onnx-nms-free": _preset(
        "ONNX NMS-free (YOLO26)",
        "YOLO26 end-to-end graph with no NMS post-processing",
        "onnx",
        options={"nms": False},
        requires="yolo26",
        dtypes=["fp32", "fp16"],
    ),
    "openvino": _preset("OpenVINO IR", "Intel CPU/iGPU inference through OpenVINO", "openvino",
                        dtypes=["fp32", "fp16", "int8"]),
    "ncnn": _preset("NCNN", "Lightweight inference for Android, Raspberry Pi and other ARM boards", "ncnn",
                    dtypes=["fp32", "fp16"]),
    "tflite-int8": _preset(
        "TFLite INT8",
        "Quantized LiteRT/TFLite model for CPU accelerators",
        "tflite",
        dtypes=["int8", "fp16", "fp32"],
    ),
    "jetson": _preset(
        "Jetson (TensorRT FP16)",
        "TensorRT engine for NVIDIA Jetson",
        "engine",
        options={"half": True},
        device="NVIDIA Jetson",
        dtypes=["fp16", "int8", "fp32"],
    ),
    "hailo": _preset(
        "Hailo-8",
        "Hailo DFC artifact for Hailo-8 accelerators",
        "hailo",
        options={"quantize": 8, "name": "hailo8"},
        device="Hailo-8",
        dtypes=["int8"],
    ),
    "deepx": _preset(
        "DEEPX DX-M1",
        "DEEPX compiler artifact for DX-M1 NPUs",
        "deepx",
        options={"quantize": 8},
        device="DEEPX DX-M1",
        dtypes=["int8"],
    ),
}


def get_preset(preset: str) -> dict:
    if preset not in PRESETS:
        raise ValueError(f"unknown export preset {preset!r}")
    return PRESETS[preset]


def resolve_dtype(preset: str, dtype: str | None) -> str:
    """The dtype to build: the preset's default for ``None``, otherwise one it can build."""
    allowed = get_preset(preset)["dtypes"]
    if dtype is None:
        return allowed[0]
    if dtype not in allowed:
        raise ValueError(f"{preset} cannot build {dtype}; choose one of {', '.join(allowed)}")
    return dtype


def artifact_key(preset: str, dtype: str | None) -> str:
    """Where a build is stored on the model: the preset itself for its default dtype, ``preset:dtype`` otherwise."""
    chosen = resolve_dtype(preset, dtype)
    return preset if chosen == get_preset(preset)["dtypes"][0] else f"{preset}:{chosen}"


def needs_data(preset: str, dtype: str | None = None) -> bool:
    """INT8 calibration reads the dataset behind the model."""
    return resolve_dtype(preset, dtype) == "int8"


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
            "dtypes": [{"id": d, "label": DTYPE_LABEL[d], "default": i == 0, "needs_data": d == "int8"}
                       for i, d in enumerate(spec["dtypes"])],
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


def export_plan(preset: str, dtype: str | None = None) -> tuple[str, dict]:
    """(format, kwargs) for `ultralytics.YOLO.export`, tolerant of the 8.3 -> 8.4 rename."""
    spec = get_preset(preset)
    chosen = resolve_dtype(preset, dtype)
    fmt, options = spec["format"], dict(spec["options"])
    if len(spec["dtypes"]) > 1:                 # a multi-dtype preset lets the dtype own the precision switches
        options = {k: v for k, v in options.items() if k not in _DTYPE_SWITCHES}
        if chosen == "fp16":
            options["half"] = True
        elif chosen == "int8":
            options["int8"] = True
    if fmt != "tflite":
        return fmt, options
    int8 = options.pop("int8", False)
    if _ultralytics_version() >= (8, 4, 83):    # tflite became the deprecated alias of litert
        return "litert", {**options, **({"quantize": 8} if int8 else {})}
    return "tflite", {**options, **({"int8": True} if int8 else {})}  # 8.3's INT8 switch


def calibration_data(version: Version, task: str) -> str:
    """The dataset path `ultralytics` reads INT8 calibration images from.

    Detection/segmentation take a YOLO data.yaml; classification takes the dataset root
    (train/<class>/…), which is what `check_cls_dataset` expects.
    """
    if task == "classify":
        return str(versioning.cached_export(version, "folder"))
    return str(versioning.cached_export(version, "yolo") / "data.yaml")
