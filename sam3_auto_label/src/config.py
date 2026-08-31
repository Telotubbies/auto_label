"""Load and validate YAML config for SAM 3.1 batch segmentation."""

import os
import sys
import yaml
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Category:
    id: int
    name: str
    prompt: str
    threshold: float = -1.0  # per-category override; -1 = use global, 0 = accept all


@dataclass
class InferenceConfig:
    confidence_threshold: float = 0.4
    resolution: int = 1008
    device: str = "auto"
    # GPU acceleration: use SAM 3.1 perflib for RLE encode + mask IoU NMS on GPU
    gpu_ops: bool = True
    # Pipeline: overlap CPU export with GPU inference for ~100% GPU utilization
    pipeline_export: bool = True


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


@dataclass
class AnnotationConfig:
    """What each annotation contains. At least one of bbox/segmentation must be on."""
    bbox: bool = True
    segmentation: bool = True
    segmentation_encoding: str = "rle"  # rle | polygon (COCO / API responses)


@dataclass
class OutputConfig:
    formats: list = field(default_factory=lambda: ["coco"])
    save_viz: bool = True
    input_dir: str = "input"
    output_dir: str = "output"
    viz_dpi: int = 100
    viz_figsize: tuple = (10, 7)


@dataclass
class CheckpointConfig:
    enabled: bool = True
    auto_resume: bool = True
    clear_on_success: bool = True


@dataclass
class Config:
    categories: list = field(default_factory=list)
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


def load_config(path: str) -> Config:
    """Load and validate YAML config."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raise ValueError(f"Config is empty: {path}")

    cfg = Config()
    cfg.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Categories
    raw_cats = raw.get("categories", [])
    if not raw_cats:
        raise ValueError("No categories defined in config")
    seen_ids = set()
    for c in raw_cats:
        if "id" not in c or "name" not in c or "prompt" not in c:
            raise ValueError(f"Category missing required fields (id, name, prompt): {c}")
        if c["id"] in seen_ids:
            raise ValueError(f"Duplicate category id: {c['id']}")
        seen_ids.add(c["id"])
        cfg.categories.append(Category(
            id=c["id"],
            name=c["name"],
            prompt=c["prompt"],
            threshold=float(c.get("threshold", -1.0)),
        ))

    # Inference
    inf = raw.get("inference", {})
    cfg.inference = InferenceConfig(
        confidence_threshold=float(inf.get("confidence_threshold", 0.4)),
        resolution=int(inf.get("resolution", 1008)),
        device=inf.get("device", "auto"),
        gpu_ops=bool(inf.get("gpu_ops", True)),
        pipeline_export=bool(inf.get("pipeline_export", True)),
    )
    if not 0.0 <= cfg.inference.confidence_threshold <= 1.0:
        raise ValueError(f"confidence_threshold must be 0-1, got {cfg.inference.confidence_threshold}")

    # Annotation
    ann = raw.get("annotation", {})
    cfg.annotation = AnnotationConfig(
        bbox=bool(ann.get("bbox", True)),
        segmentation=bool(ann.get("segmentation", True)),
        segmentation_encoding=str(ann.get("segmentation_encoding", "rle")).lower(),
    )
    if not cfg.annotation.bbox and not cfg.annotation.segmentation:
        raise ValueError("annotation: at least one of bbox / segmentation must be true")
    if cfg.annotation.segmentation_encoding not in ("rle", "polygon"):
        raise ValueError(
            f"segmentation_encoding must be 'rle' or 'polygon', got {cfg.annotation.segmentation_encoding}"
        )

    # Output
    out = raw.get("output", {})
    formats = out.get("formats", ["coco"])
    if isinstance(formats, str):
        formats = [formats]
    unknown = [f for f in formats if f not in SUPPORTED_FORMATS]
    if unknown:
        raise ValueError(f"unknown output format(s): {unknown} — supported: {list(SUPPORTED_FORMATS)}")
    cfg.output = OutputConfig(
        formats=list(dict.fromkeys(formats)),
        save_viz=bool(out.get("save_viz", True)),
        input_dir=out.get("input_dir", "input"),
        output_dir=out.get("output_dir", "output"),
        viz_dpi=int(out.get("viz_dpi", 100)),
        viz_figsize=tuple(out.get("viz_figsize", (10, 7))),
    )

    # Checkpoint
    ckpt = raw.get("checkpoint", {})
    cfg.checkpoint = CheckpointConfig(
        enabled=bool(ckpt.get("enabled", True)),
        auto_resume=bool(ckpt.get("auto_resume", True)),
        clear_on_success=bool(ckpt.get("clear_on_success", True)),
    )

    return cfg


def save_config(cfg: Config, path: str):
    """Save config back to YAML file."""
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
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
