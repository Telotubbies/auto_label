#!/usr/bin/env python3
"""Auto-Label PPE Pipeline — Production-grade Interactive CLI.

A polished, dashboard-style CLI for the PPE auto-labeling and YOLO26 training
pipeline. Built with rich + questionary.

Modes:
  SAM   — Auto-label raw images with SAM 3.1 → COCO annotations
  YOLO  — Train YOLO26 PPE models (4 versions: nano/small × detect/segment)
  PRED  — Run inference with production models → prediction images

Usage:
  python pipeline_cli.py                          # interactive mode
  python pipeline_cli.py --sam --batch blurred    # direct mode
  python pipeline_cli.py --yolo --model nano_detection,small_detection
  python pipeline_cli.py --version                # show version
  python pipeline_cli.py --dry-run --yolo ...     # preview without executing
  python pipeline_cli.py -v --sam ...             # verbose output
"""
import argparse
import os
import subprocess
import sys
import time
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Tuple

import questionary
from questionary import Style
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.progress import (
    Progress, SpinnerColumn, BarColumn, TextColumn,
    TimeElapsedColumn, TimeRemainingColumn, MofNCompleteColumn,
)
from rich.text import Text
from rich.rule import Rule
from rich import box

# =============================================================================
# Version
# =============================================================================
__version__ = "2.0.0"
__app_name__ = "Auto-Label PPE Pipeline"

# =============================================================================
# Verbosity / Output Format Enums (production pattern)
# =============================================================================

class Verbosity(str, Enum):
    QUIET = "quiet"
    NORMAL = "normal"
    VERBOSE = "verbose"
    DEBUG = "debug"


class OutputFormat(str, Enum):
    TABLE = "table"
    JSON = "json"
    PLAIN = "plain"


# Global state (set by global flags before any command runs)
_verbosity = Verbosity.NORMAL
_output_format = OutputFormat.TABLE
_dry_run = False

# =============================================================================
# Config — all paths and model definitions (testable without GPU)
# =============================================================================
# Platform-aware repo root: use WSL path on Linux/WSL, Windows path on Windows.
# This allows the CLI to run on both WSL2 (training/inference) and Windows (dry-run, checks).
if os.name == "nt":
    REPO_ROOT = Path(__file__).resolve().parent
else:
    REPO_ROOT = Path(__file__).resolve().parent
SAM_DIR = REPO_ROOT / "sam3_auto_label"
YOLO_DIR = REPO_ROOT / "yolo26_ppe"
RAW_DIR = REPO_ROOT / "data" / "raw"
SAM_OUTPUTS_DIR = REPO_ROOT / "data" / "sam_outputs_ground_truth"
PREDICTIONS_DIR = YOLO_DIR / "data" / "predictions"

# Resolve SAM/YOLO Python from the repo-local venv created by setup.py.
# Allow override via YOLO_PYTHON env var (for advanced users / CI).
if os.name == "nt":
    _default_python = str(SAM_DIR / "sam3_venv" / "Scripts" / "python.exe")
else:
    _default_python = str(SAM_DIR / "sam3_venv" / "bin" / "python")
SAM_PYTHON = os.environ.get("SAM_PYTHON", _default_python)
YOLO_PYTHON = os.environ.get("YOLO_PYTHON", SAM_PYTHON)

VERSION = "v4_recipe"

MODELS: Dict[str, dict] = {
    "nano_detection": {
        "weights": "yolo26n.pt",
        "task": "detect",
        "label": "YOLO26n Detect",
        "desc": "Nano · Object Detection",
        "project": "yolo26_ppe/models/production/nano_detection",
        "best": YOLO_DIR / "models" / "production" / "nano_detection" / "stage_2_final_fine_tuning" / "weights" / "best.pt",
        "data": "/tmp/yolo_detect_data/data.yaml",
        "batch": 64,
        "size": "n",
    },
    "small_detection": {
        "weights": "yolo26s.pt",
        "task": "detect",
        "label": "YOLO26s Detect",
        "desc": "Small · Object Detection",
        "project": "yolo26_ppe/models/production/small_detection",
        "best": YOLO_DIR / "models" / "production" / "small_detection" / "stage_2_final_fine_tuning" / "weights" / "best.pt",
        "data": "/tmp/yolo_detect_data/data.yaml",
        "batch": 48,
        "size": "s",
    },
    "nano_segmentation": {
        "weights": "yolo26n-seg.pt",
        "task": "segment",
        "label": "YOLO26n Seg",
        "desc": "Nano · Instance Segmentation",
        "project": "yolo26_ppe/models/production/nano_segmentation",
        "best": YOLO_DIR / "models" / "production" / "nano_segmentation" / "stage_2_final_fine_tuning" / "weights" / "best.pt",
        "data": "/tmp/yolo_seg_data/data.yaml",
        "batch": 16,
        "size": "n",
    },
    "small_segmentation": {
        "weights": "yolo26s-seg.pt",
        "task": "segment",
        "label": "YOLO26s Seg",
        "desc": "Small · Instance Segmentation",
        "project": "yolo26_ppe/models/production/small_segmentation",
        "best": YOLO_DIR / "models" / "production" / "small_segmentation" / "stage_2_final_fine_tuning" / "weights" / "best.pt",
        "data": "/tmp/yolo_seg_data/data.yaml",
        "batch": 16,
        "size": "s",
    },
    "medium_detection": {
        "weights": "yolo26m.pt",
        "task": "detect",
        "label": "YOLO26m Detect",
        "desc": "Medium · Object Detection",
        "project": "yolo26_ppe/models/production/medium_detection",
        "best": YOLO_DIR / "models" / "production" / "medium_detection" / "stage_2_final_fine_tuning" / "weights" / "best.pt",
        "data": "/tmp/yolo_detect_data/data.yaml",
        "batch": 32,
        "size": "m",
    },
    "medium_segmentation": {
        "weights": "yolo26m-seg.pt",
        "task": "segment",
        "label": "YOLO26m Seg",
        "desc": "Medium · Instance Segmentation",
        "project": "yolo26_ppe/models/production/medium_segmentation",
        "best": YOLO_DIR / "models" / "production" / "medium_segmentation" / "stage_2_final_fine_tuning" / "weights" / "best.pt",
        "data": "/tmp/yolo_seg_data/data.yaml",
        "batch": 12,
        "size": "m",
    },
}

CLASS_NAMES = ["person", "helmet", "closed footwear", "harness"]

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif"}

# --- Processing device options ---
PROCESSING_DEVICES = {
    "rocm": {
        "label": "AMD ROCm (GPU)",
        "value": "0",
        "desc": "AMD Radeon GPU via ROCm — fastest on RX 7800 XT",
    },
    "cuda": {
        "label": "NVIDIA CUDA (GPU)",
        "value": "0",
        "desc": "NVIDIA GPU via CUDA",
    },
    "apple": {
        "label": "Apple MPS",
        "value": "mps",
        "desc": "Apple Silicon Metal Performance Shaders",
    },
    "cpu": {
        "label": "CPU (slow)",
        "value": "cpu",
        "desc": "CPU only — very slow, not recommended for training",
    },
}

# =============================================================================
# Typed Exception Hierarchy (production pattern — raise, don't exit)
# =============================================================================

class PipelineError(Exception):
    """Base exception for all pipeline errors."""
    def __init__(self, message: str, hint: str = ""):
        self.message = message
        self.hint = hint
        super().__init__(message)


class ConfigError(PipelineError):
    """Configuration or argument error."""


class DatasetError(PipelineError):
    """Dataset not found, empty, or invalid."""


class DeviceError(PipelineError):
    """GPU/device unavailable or incompatible."""


class CheckpointError(PipelineError):
    """SAM checkpoint or YOLO weights missing."""


class TrainingError(PipelineError):
    """Training execution failure."""


class PredictionError(PipelineError):
    """Inference execution failure."""


# --- Training config defaults (Advanced mode can override) ---
TRAINING_DEFAULTS = {
    "epochs_stage1": 150,
    "epochs_stage2": 50,
    "batch": None,  # None = use model-specific default
    "workers": 4,
    "optimizer": "SGD",
    "lr0_stage1": 0.01,
    "lr0_stage2": 0.001,
    "imgsz": 640,
    "patience_stage1": 30,
    "patience_stage2": 15,
}

OPTIMIZER_CHOICES = ["SGD", "Adam", "AdamW", "RMSProp"]

# =============================================================================
# Pure logic functions (unit-testable, no GPU/terminal needed)
# =============================================================================

def discover_datasets(base_dir: Optional[Path] = None) -> List[Tuple[str, int]]:
    """Find all subdirectories in data/raw/ that contain images.

    Returns: list of (dataset_name, image_count) sorted by name.
    """
    raw = base_dir or RAW_DIR
    if not raw.exists():
        return []
    datasets = []
    for d in sorted(raw.iterdir()):
        if not d.is_dir():
            continue
        count = count_images(d)
        if count > 0:
            datasets.append((d.name, count))
    return datasets


def count_images(path: Path) -> int:
    """Count image files in a directory (non-recursive)."""
    if not path.exists():
        return 0
    if path.is_file():
        return 1 if path.suffix.lower() in IMAGE_EXTS else 0
    return sum(1 for f in path.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS)


def _sanitize_path(user_path: str, base_dir: Optional[Path] = None) -> Path:
    """Sanitize a user-supplied path to prevent path traversal.

    If base_dir is provided, the resolved path must stay within base_dir.
    Raises ValueError if the path escapes base_dir.
    """
    p = Path(user_path).resolve()
    if base_dir is not None:
        base = base_dir.resolve()
        try:
            p.relative_to(base)
        except ValueError:
            raise ValueError(f"Path '{user_path}' escapes base directory '{base}'")
    return p


def resolve_input_dir(batch: Optional[str], input_path: Optional[str], base_dir: Optional[Path] = None) -> Path:
    """Resolve input directory from --batch or --input.

    Paths are sanitized to prevent traversal outside the base directory.
    """
    if input_path:
        return _sanitize_path(input_path, base_dir)
    if batch:
        resolved = (base_dir or RAW_DIR) / batch
        return _sanitize_path(str(resolved), base_dir or RAW_DIR)
    raise ValueError("Must specify either batch or input_path")


def resolve_output_dir(mode: str, batch: Optional[str], output_path: Optional[str]) -> Path:
    """Resolve output directory based on mode and batch name.

    Paths are sanitized to prevent traversal outside expected output directories.
    """
    if output_path:
        return _sanitize_path(output_path)
    if not batch:
        raise ValueError("batch name required to resolve output directory")
    if mode == "sam":
        return _sanitize_path(str(SAM_OUTPUTS_DIR / batch), SAM_OUTPUTS_DIR)
    elif mode in ("yolo", "pred"):
        return PREDICTIONS_DIR / batch
    raise ValueError(f"Unknown mode: {mode}")


def parse_model_list(model_str: Optional[str]) -> List[str]:
    """Parse comma-separated model string into list of valid model keys."""
    if not model_str:
        return list(MODELS.keys())
    keys = [k.strip() for k in model_str.split(",") if k.strip()]
    invalid = [k for k in keys if k not in MODELS]
    if invalid:
        raise ValueError(f"Unknown model(s): {invalid}. Valid: {list(MODELS.keys())}")
    return keys


def parse_batch_list(batch_str: Optional[str], base_dir: Optional[Path] = None) -> List[str]:
    """Parse comma-separated batch string into list of valid dataset names."""
    if not batch_str:
        return []
    names = [b.strip() for b in batch_str.split(",") if b.strip()]
    raw = base_dir or RAW_DIR
    missing = [n for n in names if not (raw / n).exists()]
    if missing:
        raise ValueError(f"Dataset(s) not found: {missing}. Available: {[d[0] for d in discover_datasets(raw)]}")
    return names


def estimate_eta_sam(n_images: int) -> int:
    """Estimate SAM 3.1 processing time in seconds (~35s/image)."""
    return n_images * 35


def estimate_eta_yolo_train(n_models: int, stage: int = 12) -> int:
    """Estimate YOLO26 training time in seconds.
    Stage 1: ~45min/model, Stage 2: ~15min/model.
    """
    s1 = 45 * 60 if stage in (1, 12) else 0
    s2 = 15 * 60 if stage in (2, 12) else 0
    return n_models * (s1 + s2)


def estimate_eta_yolo_pred(n_images: int, n_models: int) -> int:
    """Estimate YOLO26 inference time (~25ms/image + 5s load per model)."""
    return n_models * 5 + int(n_images * 0.025 * n_models)


def format_eta(seconds: float) -> str:
    """Format seconds into human-readable time string."""
    if seconds < 0:
        return "—"
    if seconds < 60:
        return f"~{int(seconds)}s"
    if seconds < 3600:
        return f"~{int(seconds // 60)}m {int(seconds % 60)}s"
    hours = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    return f"~{hours}h {mins}m"


def check_sam_checkpoint() -> Tuple[bool, str]:
    """Check if SAM checkpoint exists. Returns (exists, path)."""
    ckpt = SAM_DIR / "checkpoints" / "sam3.1_multiplex.pt"
    return ckpt.exists(), str(ckpt)


def check_production_models() -> Tuple[int, List[str]]:
    """Check which production models have trained weights.
    Returns (count_trained, list_of_trained_model_keys).
    """
    trained = []
    for key, cfg in MODELS.items():
        if cfg["best"].exists():
            trained.append(key)
    return len(trained), trained


def check_python_venv() -> bool:
    """Check if Python venv exists."""
    return Path(SAM_PYTHON).exists()


def validate_mode_args(mode: str, batch: Optional[str], model: Optional[str],
                        input_path: Optional[str] = None) -> List[str]:
    """Validate that required args are present for the given mode.
    Returns list of error messages (empty if valid).
    --input can substitute for --batch in sam/pred modes.
    """
    errors = []
    if not mode:
        errors.append("No mode specified. Use --sam, --yolo, or --pred.")
    if mode in ("sam", "pred") and not batch and not input_path:
        errors.append(f"--batch (or --input) is required for --{mode} mode.")
    if mode == "yolo" and model:
        try:
            parse_model_list(model)
        except ValueError as e:
            errors.append(str(e))
    return errors


def resolve_device(device_key: str) -> str:
    """Map a device key (rocm/cuda/apple/cpu) to a Ultralytics device string."""
    if device_key in PROCESSING_DEVICES:
        return PROCESSING_DEVICES[device_key]["value"]
    # Pass through raw values (0, 1, cpu, mps)
    return device_key


def detect_available_device() -> str:
    """Auto-detect the best available processing device.
    Returns one of: 'rocm', 'cuda', 'apple', 'cpu'.
    """
    try:
        import torch
        if torch.cuda.is_available():
            # Check if it's ROCm or CUDA
            try:
                version = torch.version.hip
                if version:
                    return "rocm"
            except Exception:
                pass
            return "cuda"
        try:
            if torch.backends.mps.is_available():
                return "apple"
        except Exception:
            pass
    except ImportError:
        pass
    return "cpu"


def build_train_overrides(config: dict) -> List[str]:
    """Build CLI arg list for 02_train_models.py from custom config dict.
    Only includes non-None values.
    """
    args = []
    if config.get("epochs"):
        args.extend(["--epochs", str(config["epochs"])])
    if config.get("batch"):
        args.extend(["--batch", str(config["batch"])])
    if config.get("workers") is not None:
        args.extend(["--workers", str(config["workers"])])
    if config.get("optimizer"):
        args.extend(["--optimizer", config["optimizer"]])
    if config.get("lr0"):
        args.extend(["--lr0", str(config["lr0"])])
    if config.get("imgsz"):
        args.extend(["--imgsz", str(config["imgsz"])])
    if config.get("device"):
        args.extend(["--device", config["device"]])
    if config.get("patience"):
        args.extend(["--patience", str(config["patience"])])
    return args


# =============================================================================
# Rich console + questionary style
# =============================================================================
console = Console(highlight=False)

QSTYLE = Style([
    ("qmark", "fg:#673ab7 bold"),
    ("question", "bold"),
    ("selected", "fg:#00e676 bold"),
    ("pointer", "fg:#00e676 bold"),
    ("highlighted", "fg:#00e676 bold"),
    ("answer", "fg:#42a5f5 bold"),
    ("instruction", "fg:#9e9e9e italic"),
])

# =============================================================================
# UI Components — Production-grade dashboard
# =============================================================================

def render_header():
    """Render the project header banner."""
    header = Table(show_header=False, box=None, padding=(0, 2), expand=True)
    header.add_column(justify="center", style="bold cyan", ratio=1)
    header.add_row("╔═══════════════════════════════════════════════════════════════╗")
    header.add_row("║                                                               ║")
    header.add_row("║   🔬  Auto-Label PPE Pipeline   ·   SAM 3.1  +  YOLO26       ║")
    header.add_row("║                                                               ║")
    header.add_row("╚═══════════════════════════════════════════════════════════════╝")
    console.print(header)
    console.print()


def render_welcome():
    """Render a welcome / quick-start guide for first-time users."""
    guide = Table(show_header=False, box=box.ROUNDED, border_style="dim", padding=(1, 2), expand=True)
    guide.add_column(style="white")

    guide.add_row("[bold cyan]Quick Start Guide[/bold cyan]")
    guide.add_row("")
    guide.add_row("[dim]This tool helps you do two things:[/dim]")
    guide.add_row("")
    guide.add_row("  [green]🔬 SAM 3.1[/green]    —  Automatically label raw images")
    guide.add_row("                       Place photos → Get COCO annotations")
    guide.add_row("")
    guide.add_row("  [green]🎯 YOLO26[/green]     —  Train PPE detection models")
    guide.add_row("                       4 versions: nano/small × detect/segment")
    guide.add_row("")
    guide.add_row("  [green]📸 Predict[/green]    —  Run trained models on new images")
    guide.add_row("                       Get annotated prediction images")
    guide.add_row("")
    guide.add_row("[dim]Tip: Use [bold]SPACE[/bold] to select multiple items, [bold]ENTER[/bold] to confirm.[/dim]")
    guide.add_row("[dim]Tip: Press [bold]Ctrl+C[/bold] anytime to cancel.[/dim]")

    console.print(Panel(guide, title="[bold]Welcome[/bold]", border_style="cyan", box=box.ROUNDED))
    console.print()


def render_env_status():
    """Render environment status dashboard — shows what's ready before you start."""
    env_table = Table(show_header=False, box=box.SIMPLE_HEAD, border_style="dim", padding=(0, 1), expand=True)
    env_table.add_column("Component", style="bold dim", ratio=2)
    env_table.add_column("Status", ratio=1)
    env_table.add_column("Path / Value", style="dim", ratio=4)

    # Python
    py_ok = check_python_venv()
    env_table.add_row(
        "Python venv",
        "[green]✓ Ready[/green]" if py_ok else "[red]✗ Missing[/red]",
        SAM_PYTHON,
    )

    # SAM checkpoint
    ckpt_ok, ckpt_path = check_sam_checkpoint()
    if ckpt_ok:
        size_gb = Path(ckpt_path).stat().st_size / 1e9
        env_table.add_row("SAM 3.1 checkpoint", f"[green]✓ Ready[/green] ({size_gb:.1f} GB)", ckpt_path)
    else:
        env_table.add_row("SAM 3.1 checkpoint", "[red]✗ Missing[/red]", ckpt_path)

    # Production models
    trained_count, trained_keys = check_production_models()
    if trained_count == 4:
        env_table.add_row("Production models", "[green]✓ 4/4 trained[/green]", "All models ready for inference")
    elif trained_count > 0:
        env_table.add_row("Production models", f"[yellow]○ {trained_count}/4 trained[/yellow]", ", ".join(trained_keys))
    else:
        env_table.add_row("Production models", "[yellow]○ 0/4 trained[/yellow]", "Run --yolo to train first")

    # Datasets
    datasets = discover_datasets()
    total_imgs = sum(c for _, c in datasets)
    if datasets:
        env_table.add_row("Raw datasets", f"[green]✓ {len(datasets)} batches[/green]", f"data/raw/  ({total_imgs} images total)")
    else:
        env_table.add_row("Raw datasets", "[yellow]○ Empty[/yellow]", "Place images in data/raw/<batch_name>/")

    # GPU
    env_table.add_row("GPU target", "[magenta]AMD RX 7800 XT · ROCm[/magenta]", "16 GB VRAM · GPU-only")

    console.print(Panel(env_table, title="[bold]System Status[/bold]", border_style="cyan", box=box.ROUNDED, padding=(1, 1)))
    console.print()


def render_step(n: int, total: int, title: str):
    """Render a step header with progress indicator."""
    console.print()
    console.print(Rule(f"[bold cyan]  Step {n}/{total}:  {title}  [/bold cyan]", style="cyan"))
    console.print()


def render_selection_summary(items: List[str], label: str):
    """Render selected items as a compact summary."""
    if not items:
        console.print(f"  [yellow]No {label} selected.[/yellow]")
        return
    console.print(f"  [green]✓[/green] [bold]{label}:[/bold]")
    for item in items:
        console.print(f"      [dim]•[/dim] {item}")
    console.print()


def render_plan_panel(mode, datasets, models, stage, eta_s, output_dirs):
    """Render the execution plan panel — the final review before running."""
    plan = Table(show_header=False, box=box.ROUNDED, border_style="cyan", padding=(0, 1), expand=True)
    plan.add_column("Field", style="bold dim", width=16)
    plan.add_column("Value", style="white")

    mode_labels = {
        "sam": "🔬 SAM 3.1 Auto-Labeling",
        "yolo": "🎯 YOLO26 Training",
        "pred": "📸 YOLO26 Inference",
    }
    plan.add_row("Mode", mode_labels.get(mode, mode))

    if datasets:
        ds_text = "\n".join(f"  • {d}" for d in datasets)
        plan.add_row("Datasets", ds_text)

    if models:
        model_text = "\n".join(f"  • {MODELS[m]['label']}  [dim]({MODELS[m]['desc']})[/dim]" for m in models if m in MODELS)
        plan.add_row("Models", model_text)

    if stage and mode == "yolo":
        stage_text = {1: "Stage 1 only (frozen backbone, 150 epochs)", 2: "Stage 2 only (fine-tune, 50 epochs)", 12: "Both stages (full training)"}
        plan.add_row("Training stage", stage_text.get(stage, str(stage)))

    eta_str = format_eta(eta_s) if eta_s > 0 else "—"
    plan.add_row("Est. time", f"[yellow]{eta_str}[/yellow]")

    if output_dirs:
        out_text = "\n".join(f"  • {d}" for d in output_dirs)
        plan.add_row("Output", out_text)

    console.print(Panel(plan, title="[bold]📋 Execution Plan[/bold]", border_style="cyan", box=box.ROUNDED, padding=(1, 2)))
    console.print()


def render_results_panel(mode, output_dirs, success, elapsed, details=None):
    """Render results panel after completion."""
    if success:
        title = "[bold green]  ✅  Pipeline Complete  [/bold green]"
        border = "green"
    else:
        title = "[bold red]  ❌  Pipeline Failed  [/bold red]"
        border = "red"

    content = Table(show_header=False, box=None, padding=(0, 1), expand=True)
    content.add_column(style="dim", width=14)
    content.add_column(style="white")

    content.add_row("Elapsed", f"[bold]{format_eta(elapsed)}[/bold]")
    content.add_row("Status", f"[{'green' if success else 'red'}]{'Success' if success else 'Failed'}[/]")

    if output_dirs:
        for d in output_dirs:
            content.add_row("Output", str(d))

    if details:
        for label, value in details.items():
            content.add_row(label, str(value))

    console.print()
    console.print(Panel(content, title=title, border_style=border, box=box.ROUNDED, padding=(1, 2)))
    console.print()


def render_error(msg: str, hint: str = ""):
    """Render a user-friendly error message with optional hint."""
    console.print(f"\n  [red]❌ {msg}[/red]")
    if hint:
        console.print(f"  [dim]💡 {hint}[/dim]")
    console.print()


def render_error_panel(error: PipelineError):
    """Render a typed PipelineError as a Rich panel (production pattern)."""
    content = Table(show_header=False, show_edge=False, box=None, padding=(0, 1))
    content.add_row("[red]Error[/red]", error.message)
    if error.hint:
        content.add_row("[cyan]Fix[/cyan]", error.hint)
    console.print()
    console.print(Panel(content, title="[red]❌ Pipeline Error[/red]",
                        border_style="red", box=box.ROUNDED, padding=(1, 2)))
    console.print()


def handle_pipeline_error(error: PipelineError) -> int:
    """Handle a PipelineError → render + return exit code. Never call sys.exit directly."""
    render_error_panel(error)
    if _verbosity == Verbosity.DEBUG:
        import traceback
        console.print("[dim]Traceback:[/dim]")
        console.print(traceback.format_exc())
    return 1


def render_tip(msg: str):
    """Render a helpful tip."""
    console.print(f"  [dim]💡 {msg}[/dim]")


# =============================================================================
# Pipeline Runners
# =============================================================================

def run_sam_batch(datasets: List[str], fresh=False, resume=False,
                   input_override: Optional[str] = None,
                   output_override: Optional[str] = None) -> Tuple[bool, Dict]:
    """Run SAM 3.1 on multiple datasets sequentially.

    If input_override/output_override are given, they are used directly and
    datasets is expected to be a single-element list (the batch name is used
    only for display). Otherwise input/output are resolved from RAW_DIR /
    SAM_OUTPUTS_DIR + dataset name.
    """
    results = {}
    for ds_name in datasets:
        if input_override:
            input_dir = Path(input_override)
        else:
            input_dir = RAW_DIR / ds_name
        if output_override:
            output_dir = Path(output_override)
        else:
            output_dir = SAM_OUTPUTS_DIR / ds_name
        n = count_images(input_dir)

        console.print(f"\n  [cyan]▶ Processing:[/cyan] [bold]{ds_name}[/bold] ({n} images)")
        console.print(f"    [dim]Input:  {input_dir}[/dim]")
        console.print(f"    [dim]Output: {output_dir}[/dim]")

        ckpt_ok, ckpt_path = check_sam_checkpoint()
        if not ckpt_ok:
            render_error(f"SAM checkpoint missing: {ckpt_path}",
                        "Place sam3.1_multiplex.pt in sam3_auto_label/checkpoints/")
            results[ds_name] = False
            continue

        cmd = [
            SAM_PYTHON, "src/batch_segment.py",
            "-c", "config/ppe_4class.yaml",
            "--input", str(input_dir),
            "--output", str(output_dir),
        ]
        if fresh:
            cmd.append("--fresh")
        if resume:
            cmd.append("--resume")

        console.print(f"    [dim]$ {' '.join(cmd)}[/dim]\n")
        proc = subprocess.run(cmd, cwd=str(SAM_DIR))
        results[ds_name] = (proc.returncode == 0)

        if results[ds_name]:
            console.print(f"  [green]✅ {ds_name} complete[/green]")
        else:
            console.print(f"  [red]❌ {ds_name} failed[/red]")

    return all(results.values()), results


def run_prepare_dataset() -> bool:
    """Run dataset preparation (01_prepare_dataset.py)."""
    console.print(f"\n  [cyan]▶ Preparing YOLO datasets from combined COCO...[/cyan]")
    cmd = [YOLO_PYTHON, "scripts/pipeline/01_prepare_dataset.py"]
    console.print(f"    [dim]$ {' '.join(cmd)}[/dim]\n")
    proc = subprocess.run(cmd, cwd=str(YOLO_DIR))
    return proc.returncode == 0


def copy_datasets_to_tmp() -> bool:
    """Copy prepared datasets to /tmp for fast I/O during training."""
    console.print(f"\n  [cyan]▶ Copying datasets to /tmp for fast I/O...[/cyan]")

    import shutil as _shutil

    det_src = YOLO_DIR / "data" / "yolo_detection_dataset_version_2"
    seg_src = YOLO_DIR / "data" / "yolo_segmentation_dataset_version_2"

    # Create target directories first
    targets = []
    if det_src.exists():
        targets.append(("Detection", det_src, Path("/tmp/yolo_detect_data")))
    if seg_src.exists():
        targets.append(("Segmentation", seg_src, Path("/tmp/yolo_seg_data")))

    if not targets:
        render_error("No prepared datasets found to copy",
                    "Run dataset preparation first (01_prepare_dataset.py)")
        return False

    for label, src, dst in targets:
        dst.mkdir(parents=True, exist_ok=True)
        console.print(f"    [dim]{label}: {src} → {dst}[/dim]")
        try:
            for item in src.iterdir():
                target = dst / item.name
                if item.is_dir():
                    _shutil.copytree(item, target, dirs_exist_ok=True)
                else:
                    _shutil.copy2(item, target)
        except OSError as e:
            render_error(f"Copy failed for {label}: {e}")
            return False

    console.print(f"  [green]✅ Datasets copied to /tmp[/green]")
    return True


def run_yolo_train(models: List[str], stage: int = 12, config: Optional[dict] = None) -> Tuple[bool, Dict]:
    """Run YOLO26 training for selected models with optional custom config."""
    results = {}
    config = config or {}

    for model_key in models:
        if model_key not in MODELS:
            render_error(f"Unknown model: {model_key}")
            results[model_key] = False
            continue

        cfg = MODELS[model_key]
        console.print(f"\n  [cyan]▶ Training:[/cyan] [bold]{cfg['label']}[/bold]  [dim]({cfg['desc']})[/dim]")
        console.print(f"    [dim]Project: {cfg['project']}[/dim]")
        console.print(f"    [dim]Task:    {cfg['task']}[/dim]")
        console.print(f"    [dim]Batch:   {config.get('batch') or cfg['batch']}[/dim]")

        cmd = [
            YOLO_PYTHON, "scripts/pipeline/02_train_models.py",
            "--stage", str(stage),
            "--model", cfg["size"],
            "--task", cfg["task"],
        ]

        # Add custom overrides
        cmd.extend(build_train_overrides(config))

        stage_label = {1: "Stage 1", 2: "Stage 2", 12: "Stage 1 + 2"}[stage]
        console.print(f"    [dim]Stage:   {stage_label}[/dim]")
        if config:
            console.print(f"    [dim]Config:  {config}[/dim]")
        console.print(f"    [dim]$ {' '.join(cmd)}[/dim]\n")

        proc = subprocess.run(cmd, cwd=str(YOLO_DIR))
        results[model_key] = (proc.returncode == 0)

        if results[model_key]:
            console.print(f"  [green]✅ {cfg['label']} training complete[/green]")
        else:
            console.print(f"  [red]❌ {cfg['label']} training failed[/red]")

    return all(results.values()), results


def run_yolo_predict(datasets: List[str], models: List[str], conf, iou, imgsz, device,
                     input_override: Optional[str] = None,
                     output_override: Optional[str] = None) -> Tuple[bool, Dict]:
    """Run YOLO26 inference on multiple datasets.

    If input_override/output_override are given, they are used directly and
    datasets is expected to be a single-element list (batch name for display).
    """
    results = {}

    for ds_name in datasets:
        if input_override:
            input_dir = Path(input_override)
        else:
            input_dir = RAW_DIR / ds_name
        if output_override:
            output_dir = Path(output_override)
        else:
            output_dir = PREDICTIONS_DIR / ds_name
        n = count_images(input_dir)

        console.print(f"\n  [cyan]▶ Predicting:[/cyan] [bold]{ds_name}[/bold] ({n} images)")

        cmd = [
            YOLO_PYTHON, "scripts/pipeline/09_predict_raw_images.py",
            "--input", str(input_dir),
            "--output", str(output_dir),
            "--conf", str(conf),
            "--iou", str(iou),
            "--imgsz", str(imgsz),
            "--device", device,
        ]

        if len(models) < len(MODELS):
            for m in models:
                if m not in MODELS or not MODELS[m]["best"].exists():
                    render_error(f"Missing weights: {m}", "Train the model first with --yolo")
                    results[ds_name] = False
                    continue
                console.print(f"    [dim]▶ {MODELS[m]['label']}...[/dim]")
                m_cmd = cmd + ["--model", m]
                proc = subprocess.run(m_cmd, cwd=str(YOLO_DIR))
                if proc.returncode != 0:
                    console.print(f"  [red]❌ {m} failed on {ds_name}[/red]")
                    results[ds_name] = False
                else:
                    results[ds_name] = True
        else:
            for m, cfg in MODELS.items():
                if not cfg["best"].exists():
                    render_error(f"Missing: {cfg['best']}", "Train the model first with --yolo")
                    results[ds_name] = False
            console.print(f"    [dim]$ {' '.join(cmd)}[/dim]\n")
            proc = subprocess.run(cmd, cwd=str(YOLO_DIR))
            if proc.returncode != 0:
                console.print(f"  [red]❌ Prediction failed on {ds_name}[/red]")
                results[ds_name] = False
            elif ds_name not in results:
                results[ds_name] = True

    return all(results.values()), results


# =============================================================================
# Interactive Flow
# =============================================================================

def _pick_datasets_interactive(mode: str, datasets: List[Tuple[str, int]]) -> List[str]:
    """Show the dataset selection menu and return the selected dataset names.

    Raises PipelineError (via render_error + sys.exit) if no datasets found.
    """
    if not datasets:
        render_error(f"No datasets found in {RAW_DIR}",
                    f"Place images in subdirectories under {RAW_DIR}/<batch_name>/")
        sys.exit(1)

    all_choice = questionary.Choice(
        f"All datasets   ({sum(c for _, c in datasets)} images total)",
        value="__all__",
    )
    ds_choices = [all_choice] + [
        questionary.Choice(f"{name}   ({count} images)", value=name)
        for name, count in datasets
    ]

    if mode == "sam":
        prompt = "Select a dataset to auto-label"
    elif mode == "yolo":
        prompt = "Select raw dataset to include in training"
    else:
        prompt = "Select a dataset for inference"

    selected = questionary.select(
        f"{prompt}\n  Press ENTER to confirm your selection.",
        choices=ds_choices,
        style=QSTYLE,
    ).ask()

    if selected == "__all__":
        selected_datasets = [name for name, _ in datasets]
        console.print(f"\n  [green]✓[/green] Selected: [bold]All datasets[/bold]")
    else:
        selected_datasets = [selected]
        render_selection_summary(selected_datasets, "Selected datasets")
    return selected_datasets


def _discover_input_dirs() -> List[Tuple[str, str]]:
    """Find candidate input directories containing images.

    Scans data/raw/ subdirectories plus any subdirectories under data/ that
    contain image files. Returns list of (display_label, absolute_path).
    """
    candidates = []
    seen = set()

    # 1. data/raw/ subdirectories (standard dataset location)
    if RAW_DIR.exists():
        for d in sorted(RAW_DIR.iterdir()):
            if d.is_dir() and str(d) not in seen:
                n = count_images(d)
                if n > 0:
                    candidates.append((f"{d.name}/   ({n} images)   [data/raw/]", str(d)))
                    seen.add(str(d))

    # 2. Any other subdirectories under data/ that contain images directly
    data_root = REPO_ROOT / "data"
    if data_root.exists():
        for d in sorted(data_root.iterdir()):
            if not d.is_dir() or str(d) in seen:
                continue
            # Skip known output directories
            if d.name in ("sam_outputs_ground_truth", "raw"):
                continue
            n = count_images(d)
            if n > 0:
                candidates.append((f"{d.name}/   ({n} images)   [data/]", str(d)))
                seen.add(str(d))
            # Check one level deeper
            for sub in sorted(d.iterdir()):
                if sub.is_dir() and str(sub) not in seen:
                    n = count_images(sub)
                    if n > 0:
                        candidates.append((f"{d.name}/{sub.name}/   ({n} images)", str(sub)))
                        seen.add(str(sub))

    return candidates


def _pick_custom_paths_interactive(mode: str) -> Tuple[str, str]:
    """Present list-based selection for custom input and output paths.

    Returns (input_path, output_path) as strings.
    Falls back to manual text entry if user selects "Type manually".
    """
    # --- Input selection ---
    input_candidates = _discover_input_dirs()
    input_choices = []
    for label, path in input_candidates:
        input_choices.append(questionary.Choice(label, value=path))
    input_choices.append(questionary.Choice(
        "✍  Type path manually...",
        value="__manual__",
    ))

    selected_input = questionary.select(
        "Select input directory (folder with images):",
        choices=input_choices,
        style=QSTYLE,
    ).ask()

    if not selected_input:
        render_error("Input path selection cancelled.")
        sys.exit(0)

    if selected_input == "__manual__":
        custom_input = questionary.text(
            "Input directory path:",
            style=QSTYLE,
        ).ask()
        if not custom_input:
            render_error("Input path is required.")
            sys.exit(1)
    else:
        custom_input = selected_input

    # Validate input directory exists
    if not Path(custom_input).exists():
        render_error(f"Input directory not found: {custom_input}")
        sys.exit(1)
    n_images = count_images(Path(custom_input))
    if n_images == 0:
        render_error(f"No images found in: {custom_input}",
                    f"Supported formats: {', '.join(IMAGE_EXTS)}")
        sys.exit(1)
    console.print(f"  [dim]Found {n_images} images[/dim]")

    # --- Output selection ---
    # Build output candidates based on mode defaults + sibling directories
    default_output = SAM_OUTPUTS_DIR if mode == "sam" else PREDICTIONS_DIR
    input_name = Path(custom_input).name
    default_output_path = str(default_output / input_name)

    output_choices = []
    # Default output path
    output_choices.append(questionary.Choice(
        f"Default: {default_output_path}   [auto]",
        value=default_output_path,
    ))
    # Sibling of input (next to input folder)
    sibling_output = str(Path(custom_input).parent / (input_name + "_output"))
    output_choices.append(questionary.Choice(
        f"Next to input: {sibling_output}",
        value=sibling_output,
    ))
    # Existing output directories for this mode
    if default_output.exists():
        for d in sorted(default_output.iterdir()):
            if d.is_dir():
                output_choices.append(questionary.Choice(
                    f"{d.name}/   [existing {default_output.name}/]",
                    value=str(d),
                ))
    # Manual entry
    output_choices.append(questionary.Choice(
        "✍  Type path manually...",
        value="__manual__",
    ))

    selected_output = questionary.select(
        "Select output directory (where to save results):",
        choices=output_choices,
        style=QSTYLE,
    ).ask()

    if not selected_output:
        render_error("Output path selection cancelled.")
        sys.exit(0)

    if selected_output == "__manual__":
        custom_output = questionary.text(
            "Output directory path:",
            default=default_output_path,
            style=QSTYLE,
        ).ask()
        if not custom_output:
            custom_output = default_output_path
    else:
        custom_output = selected_output

    return custom_input, custom_output


def interactive_mode():
    """Run the full interactive CLI flow."""
    render_header()
    render_welcome()
    render_env_status()

    # --- Step 1: Select mode ---
    render_step(1, 4, "What do you want to do?")

    mode = questionary.select(
        "Choose an operation:",
        choices=[
            questionary.Choice(
                "🔬  SAM 3.1 Auto-Labeling\n      Automatically label raw images with SAM 3.1\n      Output: COCO annotations + visualizations",
                value="sam",
            ),
            questionary.Choice(
                "🎯  YOLO26 Training\n      Train PPE detection/segmentation models\n      4 versions: nano/small × detect/segment",
                value="yolo",
            ),
            questionary.Choice(
                "📸  YOLO26 Inference\n      Run trained models on new images\n      Output: annotated prediction images",
                value="pred",
            ),
        ],
        style=QSTYLE,
    ).ask()

    if not mode:
        console.print("  [yellow]Cancelled.[/yellow]")
        sys.exit(0)

    mode_names = {"sam": "SAM 3.1 Auto-Labeling", "yolo": "YOLO26 Training", "pred": "YOLO26 Inference"}
    console.print(f"\n  [green]✓[/green] Selected: [bold]{mode_names[mode]}[/bold]")

    # --- Step 2: Select datasets ---
    render_step(2, 4, "Select Datasets")

    # For sam/pred modes, offer a custom input/output path option.
    custom_input = None
    custom_output = None
    if mode in ("sam", "pred"):
        use_custom = questionary.confirm(
            "Use a custom input/output path instead of data/raw/?\n"
            "  (choose No to pick from existing datasets under data/raw/)",
            default=False,
            style=QSTYLE,
        ).ask()
        if use_custom:
            custom_input, custom_output = _pick_custom_paths_interactive(mode)
            console.print(f"\n  [green]✓[/green] Input:  [bold]{custom_input}[/bold]")
            console.print(f"  [green]✓[/green] Output: [bold]{custom_output}[/bold]")
            selected_datasets = [Path(custom_input).name]
        else:
            selected_datasets = _pick_datasets_interactive(mode, datasets)
    else:
        selected_datasets = _pick_datasets_interactive(mode, datasets)

    # --- Step 3: Mode-specific options ---
    selected_models = None
    stage = 12
    conf, iou, imgsz, device = 0.25, 0.45, 640, "0"
    do_prepare = False
    do_copy = False
    train_config = {}

    if mode == "yolo":
        render_step(3, 5, "Select Models to Train")

        all_models_choice = questionary.Choice(
            "All 6 models   —   Train everything",
            value="__all__",
        )
        model_choices = [all_models_choice] + [
            questionary.Choice(
                f"{MODELS[k]['label']}   —   {MODELS[k]['desc']}",
                value=k,
            )
            for k in MODELS
        ]

        selected = questionary.select(
            "Which models to train?\n  Press ENTER to confirm your selection.",
            choices=model_choices,
            style=QSTYLE,
        ).ask()

        if selected == "__all__":
            selected_models = list(MODELS.keys())
            console.print(f"\n  [green]✓[/green] Selected: [bold]All 6 models[/bold]")
        else:
            selected_models = [selected]
            render_selection_summary([MODELS[selected]["label"]], "Selected models")

        # Training stage
        console.print()
        render_tip("Stage 1 = frozen backbone (faster), Stage 2 = full fine-tune (better accuracy)")
        stage = questionary.select(
            "Training stage?",
            choices=[
                questionary.Choice("Stage 1 + 2  (full training, ~60min/model)", value=12),
                questionary.Choice("Stage 1 only  (frozen backbone, 150 epochs)", value=1),
                questionary.Choice("Stage 2 only  (fine-tune, 50 epochs, requires Stage 1)", value=2),
            ],
            style=QSTYLE,
        ).ask()

        # --- Step 4: Processing device + config mode ---
        render_step(4, 5, "Processing Device & Configuration")

        # Auto-detect device
        detected = detect_available_device()
        detected_label = PROCESSING_DEVICES.get(detected, {}).get("label", detected)
        render_tip(f"Auto-detected: {detected_label}")

        device_key = questionary.select(
            "Select processing device:",
            choices=[
                questionary.Choice(
                    f"{PROCESSING_DEVICES[k]['label']}  —  {PROCESSING_DEVICES[k]['desc']}"
                    + ("  [detected]" if k == detected else ""),
                    value=k,
                )
                for k in ["rocm", "cuda", "apple", "cpu"]
            ],
            style=QSTYLE,
        ).ask()

        device = resolve_device(device_key)
        train_config["device"] = device
        console.print(f"\n  [green]✓[/green] Device: [bold]{PROCESSING_DEVICES[device_key]['label']}[/bold]")

        # Config mode: Default vs Advanced
        console.print()
        config_mode = questionary.select(
            "Configuration mode?",
            choices=[
                questionary.Choice("Default (recommended)  —  uses optimized recipe values", value="default"),
                questionary.Choice("Advanced  —  customize epochs, batch, optimizer, lr, workers", value="advanced"),
            ],
            style=QSTYLE,
        ).ask()

        if config_mode == "advanced":
            console.print()
            render_tip("Press ENTER to keep default value shown in brackets")

            train_config["epochs"] = int(questionary.text(
                "Epochs?", default=str(TRAINING_DEFAULTS["epochs_stage1"]), style=QSTYLE
            ).ask() or str(TRAINING_DEFAULTS["epochs_stage1"]))

            train_config["batch"] = int(questionary.text(
                "Batch size? (empty = model-specific auto)", default=str(TRAINING_DEFAULTS["batch"] or 32), style=QSTYLE
            ).ask() or 32)

            train_config["workers"] = int(questionary.text(
                "Dataloader workers?", default=str(TRAINING_DEFAULTS["workers"]), style=QSTYLE
            ).ask() or str(TRAINING_DEFAULTS["workers"]))

            train_config["optimizer"] = questionary.select(
                "Optimizer?",
                choices=[questionary.Choice(o, value=o) for o in OPTIMIZER_CHOICES],
                style=QSTYLE,
            ).ask()

            train_config["lr0"] = float(questionary.text(
                "Initial learning rate (lr0)?", default=str(TRAINING_DEFAULTS["lr0_stage1"]), style=QSTYLE
            ).ask() or str(TRAINING_DEFAULTS["lr0_stage1"]))

            train_config["imgsz"] = int(questionary.text(
                "Image size?", default=str(TRAINING_DEFAULTS["imgsz"]), style=QSTYLE
            ).ask() or str(TRAINING_DEFAULTS["imgsz"]))

            train_config["patience"] = int(questionary.text(
                "Early stopping patience?", default=str(TRAINING_DEFAULTS["patience_stage1"]), style=QSTYLE
            ).ask() or str(TRAINING_DEFAULTS["patience_stage1"]))

            console.print()
            render_selection_summary(
                [f"{k}: {v}" for k, v in train_config.items()],
                "Custom training config",
            )
        else:
            console.print(f"\n  [green]✓[/green] Using [bold]Default[/bold] recipe (optimized for PPE)")

        # Data prep
        console.print()
        do_prepare = questionary.confirm(
            "Prepare dataset from SAM outputs first?\n  (runs 01_prepare_dataset.py — needed if SAM outputs changed)",
            default=True,
            style=QSTYLE,
        ).ask()

        if do_prepare:
            do_copy = questionary.confirm(
                "Copy datasets to /tmp for fast I/O?\n  (recommended — speeds up training significantly)",
                default=True,
                style=QSTYLE,
            ).ask()

    elif mode == "pred":
        render_step(3, 4, "Select Models for Inference")

        all_models_choice = questionary.Choice(
            "All trained models",
            value="__all__",
        )
        model_choices = [all_models_choice]
        for k in MODELS:
            trained = MODELS[k]["best"].exists()
            status = "[green]✓ trained[/green]" if trained else "[red]✗ not trained[/red]"
            model_choices.append(
                questionary.Choice(
                    f"{MODELS[k]['label']}   —   {MODELS[k]['desc']}   ({status})",
                    value=k,
                )
            )

        selected = questionary.select(
            "Which model to run?\n  Press ENTER to confirm your selection.",
            choices=model_choices,
            style=QSTYLE,
        ).ask()

        if selected == "__all__":
            selected_models = [k for k in MODELS if MODELS[k]["best"].exists()]
            if not selected_models:
                render_error("No trained models found!", "Train models first with --yolo mode")
                sys.exit(1)
            console.print(f"\n  [green]✓[/green] Selected: [bold]All trained models ({len(selected_models)})[/bold]")
        else:
            selected_models = [selected]
            render_selection_summary([MODELS[selected]["label"]], "Selected models")

        # Advanced options
        console.print()
        use_advanced = questionary.confirm(
            "Adjust inference options?\n  (confidence, IoU, image size, device — defaults are usually fine)",
            default=False,
            style=QSTYLE,
        ).ask()

        if use_advanced:
            console.print()
            render_tip("Lower confidence = more detections (but more false positives)")
            conf = float(questionary.text("Confidence threshold?", default="0.25", style=QSTYLE).ask() or "0.25")
            iou = float(questionary.text("IoU threshold (NMS)?", default="0.45", style=QSTYLE).ask() or "0.45")
            imgsz = int(questionary.text("Image size?", default="640", style=QSTYLE).ask() or "640")
            device_key = questionary.select(
                "Device?",
                choices=[
                    questionary.Choice(f"{PROCESSING_DEVICES[k]['label']}", value=k)
                    for k in ["rocm", "cuda", "apple", "cpu"]
                ],
                style=QSTYLE,
            ).ask()
            device = resolve_device(device_key)

    # --- Step 5: Review & Confirm ---
    total_steps = 5 if mode == "yolo" else 4
    render_step(total_steps, total_steps, "Review & Confirm")

    # Calculate ETA
    if custom_input:
        total_images = count_images(Path(custom_input))
    else:
        total_images = sum(count_images(RAW_DIR / d) for d in selected_datasets)
    if mode == "sam":
        eta_s = estimate_eta_sam(total_images)
    elif mode == "yolo":
        eta_s = estimate_eta_yolo_train(len(selected_models), stage)
        if do_prepare:
            eta_s += 120
        if do_copy:
            eta_s += 60
    else:
        eta_s = estimate_eta_yolo_pred(total_images, len(selected_models))

    # Output dirs
    if mode == "sam":
        if custom_output:
            output_dirs = [custom_output]
        else:
            output_dirs = [str(SAM_OUTPUTS_DIR / d) for d in selected_datasets]
    elif mode == "yolo":
        output_dirs = [str(YOLO_DIR / "models" / "production" / m) for m in selected_models]
    else:
        if custom_output:
            output_dirs = [custom_output]
        else:
            output_dirs = [str(PREDICTIONS_DIR / d) for d in selected_datasets]

    render_plan_panel(mode, selected_datasets, selected_models, stage, eta_s, output_dirs)

    # Confirm
    ready = questionary.confirm("🚀 Ready to start?", default=True, style=QSTYLE).ask()
    if not ready:
        console.print("\n  [yellow]Cancelled.[/yellow]")
        sys.exit(0)

    # --- Execute ---
    console.print()
    console.print(Rule("[bold cyan]  🚀  Executing Pipeline  [/bold cyan]", style="cyan"))
    console.print()

    start_time = time.time()

    if mode == "sam":
        success, details = run_sam_batch(selected_datasets,
                                          input_override=custom_input,
                                          output_override=custom_output)
    elif mode == "yolo":
        if do_prepare:
            console.print(Rule("[dim]  Data Preparation  [/dim]", style="dim"))
            prep_ok = run_prepare_dataset()
            if not prep_ok:
                render_error("Data preparation failed.")
                render_results_panel(mode, output_dirs, False, time.time() - start_time)
                sys.exit(1)

        if do_copy:
            copy_ok = copy_datasets_to_tmp()
            if not copy_ok:
                console.print("  [yellow]⚠ Copy to /tmp failed, continuing with direct paths...[/yellow]")

        console.print(Rule("[dim]  Training  [/dim]", style="dim"))
        success, details = run_yolo_train(selected_models, stage, train_config)
    else:
        success, details = run_yolo_predict(selected_datasets, selected_models,
                                             conf, iou, imgsz, device,
                                             input_override=custom_input,
                                             output_override=custom_output)

    elapsed = time.time() - start_time

    # --- Results ---
    detail_str = {}
    if mode == "sam" and details:
        for ds, ok in details.items():
            detail_str[ds] = "[green]✓[/green]" if ok else "[red]✗[/red]"
    elif mode == "yolo" and details:
        for m, ok in details.items():
            detail_str[MODELS[m]["label"]] = "[green]✓[/green]" if ok else "[red]✗[/red]"

    render_results_panel(mode, output_dirs, success, elapsed, detail_str if detail_str else None)

    sys.exit(0 if success else 1)


# =============================================================================
# Direct Mode (CLI args, no menus)
# =============================================================================

def direct_mode(args):
    """Run directly from CLI args without interactive menus."""
    render_header()

    # Validate
    errors = validate_mode_args(args.mode, args.batch, args.model, args.input)
    if errors:
        for e in errors:
            render_error(e)
        sys.exit(1)

    # When --input is given, batch is optional (used only for display name).
    # When --input is absent, batch is required and validated against RAW_DIR.
    if args.input:
        datasets = [args.batch or Path(args.input).name]
    else:
        try:
            datasets = parse_batch_list(args.batch)
        except ValueError as e:
            render_error(str(e))
            sys.exit(1)

    if args.mode == "yolo":
        try:
            models = parse_model_list(args.model)
        except ValueError as e:
            render_error(str(e))
            sys.exit(1)
        stage = args.stage
        eta_s = estimate_eta_yolo_train(len(models), stage)
        output_dirs = [str(YOLO_DIR / "models" / "production" / m) for m in models]
        # Build train config from CLI args
        train_config = {}
        if args.epochs:
            train_config["epochs"] = args.epochs
        if args.batch_size:
            train_config["batch"] = args.batch_size
        if args.workers is not None:
            train_config["workers"] = args.workers
        if args.optimizer:
            train_config["optimizer"] = args.optimizer
        if args.lr0:
            train_config["lr0"] = args.lr0
        if args.imgsz:
            train_config["imgsz"] = args.imgsz
        if args.patience:
            train_config["patience"] = args.patience
        # Resolve device
        device = resolve_device(args.device) if args.device in PROCESSING_DEVICES else args.device
        train_config["device"] = device
    elif args.mode == "sam":
        models = None
        stage = None
        train_config = {}
        if args.input:
            total_images = count_images(Path(args.input))
        else:
            total_images = sum(count_images(RAW_DIR / d) for d in datasets)
        eta_s = estimate_eta_sam(total_images)
        if args.output:
            output_dirs = [args.output]
        else:
            output_dirs = [str(SAM_OUTPUTS_DIR / d) for d in datasets]
    else:  # pred
        try:
            models = parse_model_list(args.model)
        except ValueError as e:
            render_error(str(e))
            sys.exit(1)
        stage = None
        train_config = {}
        if args.input:
            total_images = count_images(Path(args.input))
        else:
            total_images = sum(count_images(RAW_DIR / d) for d in datasets)
        eta_s = estimate_eta_yolo_pred(total_images, len(models))
        if args.output:
            output_dirs = [args.output]
        else:
            output_dirs = [str(PREDICTIONS_DIR / d) for d in datasets]

    render_plan_panel(args.mode, datasets, models, stage, eta_s, output_dirs)

    # Dry-run: show plan only, don't execute
    if _dry_run:
        console.print("\n  [yellow]🔍 DRY RUN — execution skipped[/yellow]")
        console.print("  [dim]Would execute:[/dim]")
        if args.mode == "sam":
            in_disp = args.input or datasets
            out_disp = args.output or output_dirs
            console.print(f"  [dim]  SAM batch_segment input: {in_disp}[/dim]")
            console.print(f"  [dim]  SAM output: {out_disp}[/dim]")
        elif args.mode == "yolo":
            console.print(f"  [dim]  YOLO train: {models}, stage={stage}, config={train_config}[/dim]")
        else:
            in_disp = args.input or datasets
            out_disp = args.output or output_dirs
            console.print(f"  [dim]  YOLO predict input: {in_disp}, models: {models}, conf={args.conf}, iou={args.iou}[/dim]")
            console.print(f"  [dim]  YOLO output: {out_disp}[/dim]")
        console.print()
        return

    console.print("  [bold cyan]🚀 Starting...[/bold cyan]\n")
    start_time = time.time()

    if args.mode == "sam":
        success, _ = run_sam_batch(datasets, fresh=args.fresh, resume=args.resume,
                                    input_override=args.input, output_override=args.output)
    elif args.mode == "yolo":
        if args.prepare:
            run_prepare_dataset()
        if args.copy_tmp:
            copy_datasets_to_tmp()
        success, _ = run_yolo_train(models, stage, train_config)
    else:
        device = resolve_device(args.device) if args.device in PROCESSING_DEVICES else args.device
        success, _ = run_yolo_predict(datasets, models, args.conf, args.iou, args.imgsz, device,
                                      input_override=args.input, output_override=args.output)

    elapsed = time.time() - start_time
    render_results_panel(args.mode, output_dirs, success, elapsed)
    sys.exit(0 if success else 1)


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description=f"{__app_name__} — Production CLI v{__version__}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Interactive mode (no args):
  python pipeline_cli.py

Direct mode:
  python pipeline_cli.py --sam --batch blurred,custom_capture_2026-08-14
  python pipeline_cli.py --yolo --model nano_detection,small_detection --stage 12
  python pipeline_cli.py --pred --batch blurred --model small_detection

Custom input/output paths (SAM/pred):
  python pipeline_cli.py --sam --input /data/my_images --output /data/my_labels
  python pipeline_cli.py --pred --input /data/new_batch --output /data/preds --model small_detection

Global flags:
  -v, --verbose    Increase output verbosity
  -q, --quiet      Suppress non-essential output
  --debug          Full tracebacks on error
  --dry-run        Preview actions without executing
  --format FMT     Output format: table, json, plain
  -V, --version    Show version and exit

Custom training (YOLO):
  python pipeline_cli.py --yolo --model nano_detection \\
    --device rocm --epochs 100 --batch-size 32 --optimizer AdamW --lr0 0.001
""",
    )
    # --- Global flags (processed before any command) ---
    parser.add_argument("-v", "--verbose", action="store_true", help="Increase output verbosity")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress non-essential output")
    parser.add_argument("--debug", action="store_true", help="Full tracebacks on error")
    parser.add_argument("--dry-run", action="store_true", help="Preview without executing")
    parser.add_argument("--format", choices=["table", "json", "plain"], default="table",
                        help="Output format")
    parser.add_argument("-V", "--version", action="store_true", help="Show version and exit")
    # --- Mode selection ---
    parser.add_argument("--sam", action="store_const", dest="mode", const="sam")
    parser.add_argument("--yolo", action="store_const", dest="mode", const="yolo")
    parser.add_argument("--pred", action="store_const", dest="mode", const="pred")
    # --- Mode-specific args ---
    parser.add_argument("--batch", help="dataset name(s), comma-separated (under data/raw/)")
    parser.add_argument("--input", help="custom input directory (overrides --batch for input)")
    parser.add_argument("--output", help="custom output directory (overrides default output path)")
    parser.add_argument("--model", help="model key(s), comma-separated")
    parser.add_argument("--stage", type=int, choices=[1, 2, 12], default=12, help="training stage")
    parser.add_argument("--conf", type=float, default=0.25, help="confidence threshold (pred)")
    parser.add_argument("--iou", type=float, default=0.45, help="IoU threshold (pred)")
    parser.add_argument("--imgsz", type=int, default=640, help="image size")
    parser.add_argument("--device", default="0",
                        help="device: rocm, cuda, apple, cpu, or raw (0, 1, mps, cpu)")
    # --- Custom training config (YOLO) ---
    parser.add_argument("--epochs", type=int, default=None, help="override epochs (both stages)")
    parser.add_argument("--batch-size", type=int, default=None, help="override batch size")
    parser.add_argument("--workers", type=int, default=None, help="dataloader workers")
    parser.add_argument("--optimizer", choices=OPTIMIZER_CHOICES, default=None, help="optimizer")
    parser.add_argument("--lr0", type=float, default=None, help="initial learning rate")
    parser.add_argument("--patience", type=int, default=None, help="early stopping patience")
    parser.add_argument("--fresh", action="store_true", help="SAM: start fresh")
    parser.add_argument("--resume", action="store_true", help="SAM: resume")
    parser.add_argument("--prepare", action="store_true", help="YOLO: prepare dataset first")
    parser.add_argument("--copy-tmp", action="store_true", help="YOLO: copy datasets to /tmp")
    args = parser.parse_args()

    # --- Handle --version (eager exit) ---
    if args.version:
        print(f"{__app_name__} v{__version__}")
        sys.exit(0)

    # --- Set global state from flags ---
    global _verbosity, _output_format, _dry_run
    if args.debug:
        _verbosity = Verbosity.DEBUG
    elif args.quiet:
        _verbosity = Verbosity.QUIET
    elif args.verbose:
        _verbosity = Verbosity.VERBOSE
    _output_format = OutputFormat(args.format)
    _dry_run = args.dry_run

    if _dry_run and _verbosity != Verbosity.QUIET:
        console.print("\n  [yellow]🔍 DRY RUN — no actions will be executed[/yellow]\n")

    if args.mode:
        direct_mode(args)
    else:
        # Interactive mode requires a TTY
        if not sys.stdin.isatty():
            console.print("\n  [red]❌ Interactive mode requires a terminal (TTY).[/red]")
            console.print("  [dim]Use --help to see available commands, or run in a real terminal.[/dim]\n")
            sys.exit(1)
        interactive_mode()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n  [yellow]⛔ Cancelled by user.[/yellow]\n")
        sys.exit(130)
    except PipelineError as e:
        sys.exit(handle_pipeline_error(e))
    except Exception as e:
        if _verbosity == Verbosity.DEBUG:
            raise
        console.print(f"\n  [red]❌ Unexpected error: {e}[/red]")
        console.print(f"  [dim]Run with --debug for full traceback.[/dim]\n")
        sys.exit(1)
