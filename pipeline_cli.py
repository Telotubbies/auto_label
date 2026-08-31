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
from rich.live import Live
from rich.text import Text
from rich.align import Align
from rich.columns import Columns
from rich.rule import Rule
from rich import box
from rich.layout import Layout
from rich.padding import Padding

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
REPO_ROOT = Path("/mnt/e/02_Projects/auto_label")
SAM_DIR = REPO_ROOT / "sam3_auto_label"
YOLO_DIR = REPO_ROOT / "yolo26_ppe"
RAW_DIR = REPO_ROOT / "data" / "raw"
SAM_OUTPUTS_DIR = REPO_ROOT / "data" / "sam_outputs_ground_truth"
PREDICTIONS_DIR = YOLO_DIR / "data" / "predictions"
SAM_PYTHON = "/opt/sam3_venv/bin/python"
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
}

CLASS_NAMES = ["person", "helmet", "boots", "shoes", "harness"]

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


def resolve_input_dir(batch: Optional[str], input_path: Optional[str], base_dir: Optional[Path] = None) -> Path:
    """Resolve input directory from --batch or --input."""
    if input_path:
        return Path(input_path)
    if batch:
        return (base_dir or RAW_DIR) / batch
    raise ValueError("Must specify either batch or input_path")


def resolve_output_dir(mode: str, batch: Optional[str], output_path: Optional[str]) -> Path:
    """Resolve output directory based on mode and batch name."""
    if output_path:
        return Path(output_path)
    if not batch:
        raise ValueError("batch name required to resolve output directory")
    if mode == "sam":
        return SAM_OUTPUTS_DIR / batch
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


def validate_mode_args(mode: str, batch: Optional[str], model: Optional[str]) -> List[str]:
    """Validate that required args are present for the given mode.
    Returns list of error messages (empty if valid).
    """
    errors = []
    if not mode:
        errors.append("No mode specified. Use --sam, --yolo, or --pred.")
    if mode in ("sam", "pred") and not batch:
        errors.append(f"--batch is required for --{mode} mode.")
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

def run_sam_batch(datasets: List[str], fresh=False, resume=False) -> Tuple[bool, Dict]:
    """Run SAM 3.1 on multiple datasets sequentially."""
    results = {}
    for ds_name in datasets:
        input_dir = RAW_DIR / ds_name
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
            "-c", "config/ppe_6class.yaml",
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

    det_src = YOLO_DIR / "data" / "yolo_detection_dataset_version_2"
    seg_src = YOLO_DIR / "data" / "yolo_segmentation_dataset_version_2"

    # Create target directories first
    cmds = []
    if det_src.exists():
        cmds.append(("Detection", f"mkdir -p /tmp/yolo_detect_data && cp -rL {det_src}/* /tmp/yolo_detect_data/"))
    if seg_src.exists():
        cmds.append(("Segmentation", f"mkdir -p /tmp/yolo_seg_data && cp -rL {seg_src}/* /tmp/yolo_seg_data/"))

    if not cmds:
        render_error("No prepared datasets found to copy",
                    "Run dataset preparation first (01_prepare_dataset.py)")
        return False

    for label, cmd in cmds:
        console.print(f"    [dim]{label}: {cmd}[/dim]")
        proc = subprocess.run(cmd, shell=True)
        if proc.returncode != 0:
            render_error(f"Copy failed for {label}")
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


def run_yolo_predict(datasets: List[str], models: List[str], conf, iou, imgsz, device) -> Tuple[bool, Dict]:
    """Run YOLO26 inference on multiple datasets."""
    results = {}

    for ds_name in datasets:
        input_dir = RAW_DIR / ds_name
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
        else:
            for m, cfg in MODELS.items():
                if not cfg["best"].exists():
                    render_error(f"Missing: {cfg['best']}", "Train the model first with --yolo")
            console.print(f"    [dim]$ {' '.join(cmd)}[/dim]\n")
            proc = subprocess.run(cmd, cwd=str(YOLO_DIR))

        results[ds_name] = True

    return all(results.values()), results


# =============================================================================
# Interactive Flow
# =============================================================================

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

    datasets = discover_datasets()
    if not datasets:
        render_error(f"No datasets found in {RAW_DIR}",
                    f"Place images in subdirectories under {RAW_DIR}/<batch_name>/")
        sys.exit(1)

    ds_choices = [
        questionary.Choice(f"{name}   ({count} images)", value=name)
        for name, count in datasets
    ]

    if mode == "sam":
        prompt = "Select datasets to auto-label  (SPACE to select multiple)"
    elif mode == "yolo":
        prompt = "Select raw datasets to include in training  (SPACE to select multiple)"
    else:
        prompt = "Select datasets for inference  (SPACE to select multiple)"

    selected_datasets = questionary.checkbox(
        f"{prompt}\n  Press ENTER to use all if none selected.",
        choices=ds_choices,
        style=QSTYLE,
    ).ask()

    if not selected_datasets:
        selected_datasets = [name for name, _ in datasets]
        console.print(f"\n  [green]✓[/green] Selected: [bold]All datasets[/bold]")
    else:
        render_selection_summary(selected_datasets, "Selected datasets")

    # --- Step 3: Mode-specific options ---
    selected_models = None
    stage = 12
    conf, iou, imgsz, device = 0.25, 0.45, 640, "0"
    do_prepare = False
    do_copy = False
    train_config = {}

    if mode == "yolo":
        render_step(3, 5, "Select Models to Train")

        model_choices = [
            questionary.Choice(
                f"{MODELS[k]['label']}   —   {MODELS[k]['desc']}",
                value=k,
            )
            for k in MODELS
        ]

        selected_models = questionary.checkbox(
            "Which models to train?\n  SPACE to toggle, ENTER to confirm (empty = all 4)",
            choices=model_choices,
            style=QSTYLE,
        ).ask()

        if not selected_models:
            selected_models = list(MODELS.keys())
            console.print(f"\n  [green]✓[/green] Selected: [bold]All 4 models[/bold]")
        else:
            render_selection_summary([MODELS[m]["label"] for m in selected_models], "Selected models")

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

        model_choices = []
        for k in MODELS:
            trained = MODELS[k]["best"].exists()
            status = "[green]✓ trained[/green]" if trained else "[red]✗ not trained[/red]"
            model_choices.append(
                questionary.Choice(
                    f"{MODELS[k]['label']}   —   {MODELS[k]['desc']}   ({status})",
                    value=k,
                )
            )

        selected_models = questionary.checkbox(
            "Which models to run?\n  SPACE to toggle, ENTER to confirm (empty = all available)",
            choices=model_choices,
            style=QSTYLE,
        ).ask()

        if not selected_models:
            selected_models = [k for k in MODELS if MODELS[k]["best"].exists()]
            if not selected_models:
                render_error("No trained models found!", "Train models first with --yolo mode")
                sys.exit(1)
            console.print(f"\n  [green]✓[/green] Selected: [bold]All trained models ({len(selected_models)})[/bold]")
        else:
            render_selection_summary([MODELS[m]["label"] for m in selected_models], "Selected models")

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
        output_dirs = [str(SAM_OUTPUTS_DIR / d) for d in selected_datasets]
    elif mode == "yolo":
        output_dirs = [str(YOLO_DIR / "models" / "production" / m) for m in selected_models]
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
        success, details = run_sam_batch(selected_datasets)
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
        success, details = run_yolo_predict(selected_datasets, selected_models, conf, iou, imgsz, device)

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
    errors = validate_mode_args(args.mode, args.batch, args.model)
    if errors:
        for e in errors:
            render_error(e)
        sys.exit(1)

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
        total_images = sum(count_images(RAW_DIR / d) for d in datasets)
        eta_s = estimate_eta_sam(total_images)
        output_dirs = [str(SAM_OUTPUTS_DIR / d) for d in datasets]
    else:  # pred
        try:
            models = parse_model_list(args.model)
        except ValueError as e:
            render_error(str(e))
            sys.exit(1)
        stage = None
        train_config = {}
        total_images = sum(count_images(RAW_DIR / d) for d in datasets)
        eta_s = estimate_eta_yolo_pred(total_images, len(models))
        output_dirs = [str(PREDICTIONS_DIR / d) for d in datasets]

    render_plan_panel(args.mode, datasets, models, stage, eta_s, output_dirs)

    console.print("  [bold cyan]🚀 Starting...[/bold cyan]\n")
    start_time = time.time()

    if args.mode == "sam":
        success, _ = run_sam_batch(datasets, fresh=args.fresh, resume=args.resume)
    elif args.mode == "yolo":
        if args.prepare:
            run_prepare_dataset()
        if args.copy_tmp:
            copy_datasets_to_tmp()
        success, _ = run_yolo_train(models, stage, train_config)
    else:
        device = resolve_device(args.device) if args.device in PROCESSING_DEVICES else args.device
        success, _ = run_yolo_predict(datasets, models, args.conf, args.iou, args.imgsz, device)

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
    parser.add_argument("--batch", help="dataset name(s), comma-separated")
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
