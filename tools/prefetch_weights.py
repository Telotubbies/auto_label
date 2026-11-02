"""Prefetch every checkpoint the LabelDesk v2 demo needs before going on stage.

Run from the repo root on the demo box (CPU is enough for this step):

    python tools/prefetch_weights.py
    python tools/prefetch_weights.py --check
    python tools/prefetch_weights.py --dry-run
    python tools/prefetch_weights.py --pretrained-dir D:/labeldesk-weights --skip-vlm

Zoo checkpoints land in ``LD_PRETRAINED_DIR`` (default ``yolo26_ppe/models/pretrained``)
so ``UltralyticsAdapter`` finds them locally instead of hitting the hub during the demo.
Each world model gets one ``set_classes(["person"])`` call, which also pulls the CLIP
text encoder. The vLLM model is fetched with ``huggingface-cli download``, falling back
to the ``hf`` command. ``--check`` and ``--dry-run`` never touch the network.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRETRAINED_DIR = REPO_ROOT / "yolo26_ppe" / "models" / "pretrained"
WEIGHTS = (
    "rtdetr-l.pt",
    "yolov8s-worldv2.pt",
    "yolov8m-worldv2.pt",
    "yolo11n.pt",
    "yolo11s.pt",
)
WORLD_WEIGHTS = frozenset({"yolov8s-worldv2.pt", "yolov8m-worldv2.pt"})
CLIP_CLASSES = ("person",)
VLM_MODEL = "Qwen/Qwen2.5-VL-7B-Instruct-AWQ"

Loader = Callable[[str], object]
HfRunner = Callable[[list[str]], int]


@dataclass(frozen=True)
class Item:
    """One thing to prefetch, in ``build_plan`` order."""

    name: str
    kind: Literal["ultralytics", "vlm"]
    action: str


def build_plan(skip_vlm: bool = False) -> list[Item]:
    """The exact download plan: five Ultralytics checkpoints, then the vLLM model."""
    items: list[Item] = []
    for name in WEIGHTS:
        action = f"load {name} and copy its checkpoint to <pretrained>/{name}"
        if name in WORLD_WEIGHTS:
            action += ' after set_classes(["person"])'
        items.append(Item(name, "ultralytics", action))
    if not skip_vlm:
        items.append(Item(VLM_MODEL, "vlm", f"huggingface-cli download {VLM_MODEL}"))
    return items


def default_pretrained_dir() -> Path:
    """``LD_PRETRAINED_DIR`` when set, else the repo's local model directory."""
    override = os.environ.get("LD_PRETRAINED_DIR")
    return Path(override) if override else DEFAULT_PRETRAINED_DIR


def _hf_command() -> str | None:
    """``huggingface-cli`` then ``hf``, or ``None`` when neither is on PATH."""
    return shutil.which("huggingface-cli") or shutil.which("hf")


def _load_ultralytics(name: str) -> object:
    """Load a model through Ultralytics; imported late so this module works without torch."""
    from ultralytics import YOLO, YOLOWorld

    return YOLOWorld(name) if name in WORLD_WEIGHTS else YOLO(name)


def _run_hf(cmd: list[str]) -> int:
    """Run the HF CLI and return its exit code."""
    return int(subprocess.run(cmd, check=False).returncode)


def _fetch_weights(name: str, dest: Path, loader: Loader) -> None:
    """Load one checkpoint, build the CLIP encoder for world models, then copy it into ``dest``.

    Ultralytics downloads hub names into the process working directory, so the load runs from
    ``dest``: the demo box does not accumulate stray ``*.pt`` files at the repo root.
    """
    dest = Path(dest).resolve()
    previous = Path.cwd()
    os.chdir(dest)
    try:
        model = loader(name)
        if name in WORLD_WEIGHTS:
            model.set_classes(list(CLIP_CLASSES))  # type: ignore[attr-defined]
        source = Path(str(getattr(model, "ckpt_path", "") or "")).resolve()
        if not source.is_file():
            raise RuntimeError(f"loader produced no checkpoint file for {name}")
        target = dest / name
        if source != target:
            shutil.copyfile(source, target)
    finally:
        os.chdir(previous)


def vlm_cached(model: str = VLM_MODEL, hub_dir: Path | None = None) -> bool:
    """Whether the Hugging Face cache already holds ``model`` (no network access)."""
    if hub_dir is not None:
        root = hub_dir
    elif os.environ.get("HF_HUB_CACHE"):
        root = Path(os.environ["HF_HUB_CACHE"])
    else:
        hf_home = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
        root = hf_home / "hub"
    return (root / f"models--{model.replace('/', '--')}").is_dir()


def _reason(exc: BaseException) -> str:
    return str(exc).strip().replace("\n", " ") or type(exc).__name__


def run(
    *,
    pretrained_dir: Path | str | None = None,
    skip_vlm: bool = False,
    check: bool = False,
    dry_run: bool = False,
    loader: Loader | None = None,
    hf_runner: HfRunner | None = None,
    out: Callable[[str], None] = print,
) -> int:
    """Run, check or dry-run the prefetch plan. Returns a process exit code."""
    dest = Path(pretrained_dir) if pretrained_dir is not None else default_pretrained_dir()
    plan = build_plan(skip_vlm=skip_vlm)
    if dry_run:
        for item in plan:
            out(f"PLAN {item.name} ({item.action})")
        out(f"summary: planned {len(plan)} item(s), nothing downloaded")
        return 0
    if not check:
        dest.mkdir(parents=True, exist_ok=True)

    passed = 0
    failed = 0
    for item in plan:
        if item.kind == "ultralytics":
            target = dest / item.name
            if target.is_file():
                out(f"PASS {item.name} (present)")
                passed += 1
                continue
            if check:
                out(f"FAIL {item.name} (missing from {dest})")
                failed += 1
                continue
            try:
                _fetch_weights(item.name, dest, loader or _load_ultralytics)
            except Exception as exc:  # network and hub errors are per-item failures, not crashes
                out(f"FAIL {item.name} ({_reason(exc)})")
                failed += 1
            else:
                out(f"PASS {item.name} (downloaded)")
                passed += 1
            continue

        if vlm_cached(item.name):
            out(f"PASS {item.name} (present in Hugging Face cache)")
            passed += 1
            continue
        if check:
            out(f"FAIL {item.name} (not in Hugging Face cache)")
            failed += 1
            continue
        command = _hf_command()
        if command is None:
            out(f"FAIL {item.name} (neither huggingface-cli nor hf is on PATH)")
            failed += 1
            continue
        try:
            rc = (hf_runner or _run_hf)([command, "download", item.name])
        except Exception as exc:  # a missing CLI or a broken download must not abort the others
            out(f"FAIL {item.name} ({_reason(exc)})")
            failed += 1
            continue
        if rc == 0:
            out(f"PASS {item.name} (downloaded)")
            passed += 1
        else:
            out(f"FAIL {item.name} (huggingface-cli exited {rc})")
            failed += 1

    out(f"summary: {passed} ok, {failed} failed, {len(plan)} item(s)")
    return 0 if failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download the LabelDesk v2 demo checkpoints.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="report present/missing without downloading",
    )
    parser.add_argument("--dry-run", action="store_true", help="print the planned actions and exit")
    parser.add_argument("--skip-vlm", action="store_true", help="skip the vLLM model download")
    parser.add_argument("--pretrained-dir", type=Path, default=None, help="override LD_PRETRAINED_DIR")
    args = parser.parse_args(argv)
    return run(
        pretrained_dir=args.pretrained_dir,
        skip_vlm=args.skip_vlm,
        check=args.check,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    sys.exit(main())
