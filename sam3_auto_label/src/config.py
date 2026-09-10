"""Load and validate YAML config for SAM 3.1 batch segmentation."""

import math
import os
from dataclasses import dataclass, field
from typing import Any, Mapping

import yaml


# Dataset formats the batch exporter can write (see src/exporters.py).
SUPPORTED_FORMATS = (
    "coco",         # COCO JSON (per-image + combined) — bbox and/or seg (RLE or polygon)
    "yolo",         # YOLO TXT per image + data.yaml — bbox or polygon (by annotation switches)
    "voc",          # Pascal VOC XML per image — bbox only
    "labelme",      # LabelMe JSON per image — bbox/seg (polygon)
    "cvat",         # CVAT-for-images XML (single file) — bbox/seg (polygon)
    "label_studio", # Label Studio tasks JSON (single file) — bbox/seg (RLE)
    "kitti",        # KITTI TXT per image — bbox only
    "createml",     # CreateML JSON (single file) — bbox only
    "openimages",   # OpenImages CSV (single file) — bbox only
    "supervisely",  # Supervisely JSON per image + meta.json — bbox/seg (polygon)
    "masks",        # Instance mask PNGs per annotation — seg only
)


# ---------------------------------------------------------------------------
# Typed schema and domain error
# ---------------------------------------------------------------------------

class ConfigError(ValueError):
    """Configuration data is invalid."""


@dataclass
class Category:
    """One model prompt and its optional confidence-threshold override."""

    id: int
    name: str
    prompt: str
    threshold: float = -1.0  # per-category override; -1 = use global, 0 = accept all


@dataclass
class InferenceConfig:
    """Runtime settings that control model execution and export concurrency."""

    confidence_threshold: float = 0.4
    resolution: int = 1008
    device: str = "auto"
    # GPU acceleration: use SAM 3.1 perflib for RLE encode + mask IoU NMS on GPU
    gpu_ops: bool = True
    # Pipeline: overlap CPU export with GPU inference for ~100% GPU utilization
    pipeline_export: bool = True
    # torch.compile: enable operation fusion for faster inference (SAM 3.1).
    # First forward pass is slower due to compilation; subsequent batches are faster.
    compile: bool = False
    # Minimum object area in pixels. Annotations with area < min_area are dropped.
    # 0 = disabled (keep all). Set to e.g. 100 to filter tiny false positives.
    min_area: int = 0


@dataclass
class AnnotationConfig:
    """What each annotation contains. At least one of bbox/segmentation must be on."""
    bbox: bool = True
    segmentation: bool = True
    segmentation_encoding: str = "rle"  # rle | polygon (COCO / API responses)


@dataclass
class OutputConfig:
    """Output formats, visualization settings, and application-relative paths."""

    formats: list[str] = field(default_factory=lambda: ["coco"])
    save_viz: bool = True
    input_dir: str = "input"
    output_dir: str = "output"
    viz_dpi: int = 100
    viz_figsize: tuple[float, float] = (10, 7)


@dataclass
class CheckpointConfig:
    """Persistence policy for interruption recovery and successful cleanup."""

    enabled: bool = True
    auto_resume: bool = True
    clear_on_success: bool = True


@dataclass
class Config:
    """Validated application configuration consumed by pipeline components."""

    categories: list[Category] = field(default_factory=list)
    inference: InferenceConfig = field(default_factory=InferenceConfig)
    annotation: AnnotationConfig = field(default_factory=AnnotationConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    checkpoint: CheckpointConfig = field(default_factory=CheckpointConfig)
    base_dir: str = ""

    @property
    def input_path(self):
        """Resolve input path — supports absolute or project-relative."""
        p = self.output.input_dir
        if os.path.isabs(p):
            return p
        return os.path.join(self.base_dir, p)

    @property
    def output_path(self):
        """Resolve output path — supports absolute or project-relative."""
        p = self.output.output_dir
        if os.path.isabs(p):
            return p
        return os.path.join(self.base_dir, p)

    @property
    def coco_path(self):
        return os.path.join(self.output_path, "coco")

    @property
    def viz_path(self):
        return os.path.join(self.output_path, "viz")

    @property
    def masks_path(self):
        return os.path.join(self.output_path, "masks")

    @property
    def combined_json_path(self):
        return os.path.join(self.output_path, "all_annotations.json")

    @property
    def ckpt_path(self):
        return os.path.join(self.base_dir, "checkpoints", "sam3.1_multiplex.pt")

    @property
    def bpe_path(self):
        return os.path.join(self.base_dir, "sam3", "sam3", "assets", "bpe_simple_vocab_16e6.txt.gz")

    @property
    def category_names(self):
        return {c.id: c.name for c in self.categories}

    @property
    def category_by_name(self):
        return {c.name: c for c in self.categories}


# ---------------------------------------------------------------------------
# Boundary coercion helpers
# ---------------------------------------------------------------------------

def _mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    """Require a YAML mapping at a named configuration boundary."""
    if not isinstance(value, Mapping):
        raise ConfigError(f"{field_name}: must be a mapping, got {type(value).__name__}")
    return value


def _required(data: Mapping[str, Any], key: str, field_name: str) -> Any:
    """Return a required field or raise a field-addressable configuration error."""
    if key not in data:
        raise ConfigError(f"{field_name}: required field is missing")
    return data[key]


def _string(value: Any, field_name: str) -> str:
    """Accept only non-empty YAML strings without silently coercing other types."""
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{field_name}: must be a non-empty string")
    return value


def _boolean(value: Any, field_name: str) -> bool:
    """Reject quoted booleans so values such as 'false' cannot become truthy."""
    if not isinstance(value, bool):
        raise ConfigError(f"{field_name}: must be a boolean, got {value!r}")
    return value


def _integer(value: Any, field_name: str) -> int:
    """Accept YAML integers while excluding booleans, which subclass int in Python."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{field_name}: must be an integer, got {value!r}")
    return value


def _number(value: Any, field_name: str) -> float:
    """Normalize finite YAML numbers to float for typed configuration fields."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{field_name}: must be a number, got {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise ConfigError(f"{field_name}: must be finite, got {value!r}")
    return result


# ---------------------------------------------------------------------------
# Parsing and validation lifecycle
# ---------------------------------------------------------------------------

def _parse_categories(value: Any) -> list[Category]:
    if not isinstance(value, list) or not value:
        raise ConfigError("categories: must be a non-empty list")

    categories = []
    for index, item in enumerate(value):
        field_name = f"categories[{index}]"
        data = _mapping(item, field_name)
        categories.append(Category(
            id=_integer(_required(data, "id", f"{field_name}.id"), f"{field_name}.id"),
            name=_string(_required(data, "name", f"{field_name}.name"), f"{field_name}.name"),
            prompt=_string(_required(data, "prompt", f"{field_name}.prompt"), f"{field_name}.prompt"),
            threshold=_number(data.get("threshold", -1.0), f"{field_name}.threshold"),
        ))
    return categories


def _parse_inference(value: Any) -> InferenceConfig:
    data = _mapping(value, "inference")
    return InferenceConfig(
        confidence_threshold=_number(data.get("confidence_threshold", 0.4), "inference.confidence_threshold"),
        resolution=_integer(data.get("resolution", 1008), "inference.resolution"),
        device=_string(data.get("device", "auto"), "inference.device").lower(),
        gpu_ops=_boolean(data.get("gpu_ops", True), "inference.gpu_ops"),
        pipeline_export=_boolean(data.get("pipeline_export", True), "inference.pipeline_export"),
        compile=_boolean(data.get("compile", False), "inference.compile"),
        min_area=_integer(data.get("min_area", 0), "inference.min_area"),
    )


def _parse_annotation(value: Any) -> AnnotationConfig:
    data = _mapping(value, "annotation")
    return AnnotationConfig(
        bbox=_boolean(data.get("bbox", True), "annotation.bbox"),
        segmentation=_boolean(data.get("segmentation", True), "annotation.segmentation"),
        segmentation_encoding=_string(
            data.get("segmentation_encoding", "rle"),
            "annotation.segmentation_encoding",
        ).lower(),
    )


def _parse_output(value: Any) -> OutputConfig:
    data = _mapping(value, "output")
    formats = data.get("formats", ["coco"])
    if isinstance(formats, str):
        formats = [formats]
    if not isinstance(formats, list) or any(not isinstance(fmt, str) for fmt in formats):
        raise ConfigError("output.formats: must be a list of strings or a string")

    raw_figsize = data.get("viz_figsize", (10, 7))
    if not isinstance(raw_figsize, (list, tuple)) or len(raw_figsize) != 2:
        raise ConfigError("output.viz_figsize: must contain exactly two numbers")

    return OutputConfig(
        formats=list(dict.fromkeys(formats)),
        save_viz=_boolean(data.get("save_viz", True), "output.save_viz"),
        input_dir=_string(data.get("input_dir", "input"), "output.input_dir"),
        output_dir=_string(data.get("output_dir", "output"), "output.output_dir"),
        viz_dpi=_integer(data.get("viz_dpi", 100), "output.viz_dpi"),
        viz_figsize=(
            _number(raw_figsize[0], "output.viz_figsize[0]"),
            _number(raw_figsize[1], "output.viz_figsize[1]"),
        ),
    )


def _parse_checkpoint(value: Any) -> CheckpointConfig:
    data = _mapping(value, "checkpoint")
    return CheckpointConfig(
        enabled=_boolean(data.get("enabled", True), "checkpoint.enabled"),
        auto_resume=_boolean(data.get("auto_resume", True), "checkpoint.auto_resume"),
        clear_on_success=_boolean(data.get("clear_on_success", True), "checkpoint.clear_on_success"),
    )


def validate_config(cfg: Config) -> None:
    """Validate cross-field invariants after parsing or runtime overrides."""
    seen_ids = set()
    seen_names = set()
    for index, category in enumerate(cfg.categories):
        if category.id <= 0:
            raise ConfigError(f"categories[{index}].id: must be greater than zero")
        if category.id in seen_ids:
            raise ConfigError(f"categories[{index}].id: duplicate value {category.id}")
        if category.name in seen_names:
            raise ConfigError(f"categories[{index}].name: duplicate value {category.name!r}")
        if category.threshold != -1.0 and not 0.0 <= category.threshold <= 1.0:
            raise ConfigError(f"categories[{index}].threshold: must be -1 or between 0 and 1")
        seen_ids.add(category.id)
        seen_names.add(category.name)

    if not 0.0 <= cfg.inference.confidence_threshold <= 1.0:
        raise ConfigError("inference.confidence_threshold: must be between 0 and 1")
    if cfg.inference.resolution <= 0:
        raise ConfigError("inference.resolution: must be greater than zero")
    if cfg.inference.device not in ("auto", "cpu", "cuda", "rocm", "mps"):
        raise ConfigError("inference.device: must be one of auto, cpu, cuda, rocm, mps")

    if not cfg.annotation.bbox and not cfg.annotation.segmentation:
        raise ConfigError("annotation: at least one of bbox or segmentation must be true")
    if cfg.annotation.segmentation_encoding not in ("rle", "polygon"):
        raise ConfigError("annotation.segmentation_encoding: must be 'rle' or 'polygon'")

    unknown_formats = [fmt for fmt in cfg.output.formats if fmt not in SUPPORTED_FORMATS]
    if unknown_formats:
        raise ConfigError(
            f"output.formats: unknown value(s) {unknown_formats}; supported: {list(SUPPORTED_FORMATS)}"
        )
    if cfg.output.viz_dpi <= 0:
        raise ConfigError("output.viz_dpi: must be greater than zero")
    if any(value <= 0 for value in cfg.output.viz_figsize):
        raise ConfigError("output.viz_figsize: values must be greater than zero")


def parse_config(raw: Any, base_dir: str = "") -> Config:
    """Convert safe-loaded YAML primitives into a validated typed configuration."""
    data = _mapping(raw, "config")
    cfg = Config(
        categories=_parse_categories(data.get("categories")),
        inference=_parse_inference(data.get("inference", {})),
        annotation=_parse_annotation(data.get("annotation", {})),
        output=_parse_output(data.get("output", {})),
        checkpoint=_parse_checkpoint(data.get("checkpoint", {})),
        base_dir=base_dir,
    )
    validate_config(cfg)
    return cfg


def load_config(path: str) -> Config:
    """Load and validate YAML config."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Config {path}: invalid YAML: {exc}") from exc

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return parse_config(raw, base_dir=base_dir)


def save_config(cfg: Config, path: str):
    """Serialize typed configuration as portable safe YAML primitives."""
    data = {
        "categories": [
            {
                "id": c.id,
                "name": c.name,
                "prompt": c.prompt,
                "threshold": c.threshold,
            }
            for c in cfg.categories
        ],
        "inference": {
            "confidence_threshold": cfg.inference.confidence_threshold,
            "resolution": cfg.inference.resolution,
            "device": cfg.inference.device,
            "gpu_ops": cfg.inference.gpu_ops,
            "pipeline_export": cfg.inference.pipeline_export,
            "compile": cfg.inference.compile,
            "min_area": cfg.inference.min_area,
        },
        "annotation": {
            "bbox": cfg.annotation.bbox,
            "segmentation": cfg.annotation.segmentation,
            "segmentation_encoding": cfg.annotation.segmentation_encoding,
        },
        "output": {
            "formats": list(cfg.output.formats),
            "save_viz": cfg.output.save_viz,
            "input_dir": cfg.output.input_dir,
            "output_dir": cfg.output.output_dir,
            "viz_dpi": cfg.output.viz_dpi,
            "viz_figsize": list(cfg.output.viz_figsize),
        },
        "checkpoint": {
            "enabled": cfg.checkpoint.enabled,
            "auto_resume": cfg.checkpoint.auto_resume,
            "clear_on_success": cfg.checkpoint.clear_on_success,
        },
    }
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
