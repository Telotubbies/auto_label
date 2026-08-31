"""Dry-run integration tests — verify --dry-run works for all combinations.

Tests every combination of:
  - Mode: SAM, YOLO train, PRED
  - Model: nano_detection, small_detection, nano_segmentation, small_segmentation
  - Device: rocm, cuda, apple, cpu, 0, 1, mps
  - Stage: 1, 2, 12
  - Training config: epochs, batch-size, workers, optimizer, lr0, patience
  - Multi-model, multi-dataset
  - Flags: --prepare, --copy-tmp, --fresh, --resume
"""
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

CLI_PATH = Path(__file__).resolve().parent.parent / "pipeline_cli.py"

ALL_MODELS = ["nano_detection", "small_detection", "nano_segmentation", "small_segmentation"]
ALL_DEVICES = ["rocm", "cuda", "apple", "cpu", "0", "1", "mps"]
ALL_STAGES = [1, 2, 12]
ALL_OPTIMIZERS = ["SGD", "Adam", "AdamW", "RMSProp"]


def run_dry_run(args, timeout=30):
    """Run CLI with --dry-run and return (returncode, stdout)."""
    cmd = [sys.executable, str(CLI_PATH), "--dry-run"] + args
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


# =============================================================================
# YOLO Train — Every Model × Every Device
# =============================================================================

class TestDryRunYoloAllModelsAllDevices:
    """Dry-run YOLO train for every model × device combination."""

    @pytest.mark.parametrize("model", ALL_MODELS)
    @pytest.mark.parametrize("device", ALL_DEVICES)
    def test_yolo_train_model_device(self, cli_module, model, device):
        code, out, err = run_dry_run([
            "--yolo", "--model", model, "--device", device, "--epochs", "1",
        ])
        assert code == 0, f"model={model} device={device} failed: {err}"


# =============================================================================
# YOLO Train — Every Stage × Every Model
# =============================================================================

class TestDryRunYoloAllStages:
    """Dry-run YOLO train for every stage × model combination."""

    @pytest.mark.parametrize("model", ALL_MODELS)
    @pytest.mark.parametrize("stage", ALL_STAGES)
    def test_yolo_train_stage_model(self, cli_module, model, stage):
        code, out, err = run_dry_run([
            "--yolo", "--model", model, "--stage", str(stage),
            "--device", "cpu", "--epochs", "1",
        ])
        assert code == 0, f"model={model} stage={stage} failed: {err}"


# =============================================================================
# YOLO Train — Every Optimizer
# =============================================================================

class TestDryRunYoloAllOptimizers:
    """Dry-run YOLO train with every optimizer choice."""

    @pytest.mark.parametrize("optimizer", ALL_OPTIMIZERS)
    def test_yolo_train_optimizer(self, cli_module, optimizer):
        code, out, err = run_dry_run([
            "--yolo", "--model", "nano_detection",
            "--device", "cpu", "--optimizer", optimizer, "--epochs", "1",
        ])
        assert code == 0, f"optimizer={optimizer} failed: {err}"


# =============================================================================
# YOLO Train — Every Advanced Config Option
# =============================================================================

class TestDryRunYoloAdvancedConfig:
    """Dry-run YOLO train with each advanced config option individually."""

    def test_custom_epochs(self, cli_module):
        code, _, _ = run_dry_run(["--yolo", "--model", "nano_detection", "--epochs", "50"])
        assert code == 0

    def test_custom_batch_size(self, cli_module):
        code, _, _ = run_dry_run(["--yolo", "--model", "nano_detection", "--batch-size", "16"])
        assert code == 0

    def test_custom_workers(self, cli_module):
        code, _, _ = run_dry_run(["--yolo", "--model", "nano_detection", "--workers", "4"])
        assert code == 0

    def test_custom_lr0(self, cli_module):
        code, _, _ = run_dry_run(["--yolo", "--model", "nano_detection", "--lr0", "0.01"])
        assert code == 0

    def test_custom_patience(self, cli_module):
        code, _, _ = run_dry_run(["--yolo", "--model", "nano_detection", "--patience", "30"])
        assert code == 0

    def test_custom_imgsz(self, cli_module):
        code, _, _ = run_dry_run(["--yolo", "--model", "nano_detection", "--imgsz", "1280"])
        assert code == 0

    def test_all_config_combined(self, cli_module):
        code, _, _ = run_dry_run([
            "--yolo", "--model", "nano_detection",
            "--epochs", "100", "--batch-size", "32", "--workers", "8",
            "--optimizer", "AdamW", "--lr0", "0.001", "--patience", "20",
            "--imgsz", "640", "--device", "cpu",
        ])
        assert code == 0


# =============================================================================
# YOLO Train — Flags
# =============================================================================

class TestDryRunYoloFlags:
    """Dry-run YOLO train with various flags."""

    def test_prepare_flag(self, cli_module):
        code, _, _ = run_dry_run(["--yolo", "--model", "nano_detection", "--prepare"])
        assert code == 0

    def test_copy_tmp_flag(self, cli_module):
        code, _, _ = run_dry_run(["--yolo", "--model", "nano_detection", "--copy-tmp"])
        assert code == 0

    def test_prepare_and_copy_tmp(self, cli_module):
        code, _, _ = run_dry_run(["--yolo", "--model", "nano_detection", "--prepare", "--copy-tmp"])
        assert code == 0


# =============================================================================
# YOLO Train — Multi-Model
# =============================================================================

class TestDryRunYoloMultiModel:
    """Dry-run YOLO train with multiple models."""

    def test_two_models(self, cli_module):
        code, _, _ = run_dry_run([
            "--yolo", "--model", "nano_detection,small_detection",
            "--device", "cpu", "--epochs", "1",
        ])
        assert code == 0

    def test_all_four_models(self, cli_module):
        code, _, _ = run_dry_run([
            "--yolo", "--model", ",".join(ALL_MODELS),
            "--device", "cpu", "--epochs", "1",
        ])
        assert code == 0

    def test_models_with_whitespace(self, cli_module):
        code, _, _ = run_dry_run([
            "--yolo", "--model", " nano_detection , small_detection ",
            "--device", "cpu", "--epochs", "1",
        ])
        assert code == 0


# =============================================================================
# PRED — Every Model × Available Datasets
# =============================================================================

class TestDryRunPredAllModels:
    """Dry-run PRED for every model."""

    @pytest.mark.parametrize("model", ALL_MODELS)
    def test_pred_each_model(self, cli_module, model):
        code, _, _ = run_dry_run([
            "--pred", "--batch", "flip_flops", "--model", model, "--device", "cpu",
        ])
        assert code == 0, f"PRED model={model} failed"

    def test_pred_multi_model(self, cli_module):
        code, _, _ = run_dry_run([
            "--pred", "--batch", "flip_flops",
            "--model", ",".join(ALL_MODELS), "--device", "cpu",
        ])
        assert code == 0

    def test_pred_custom_conf(self, cli_module):
        code, _, _ = run_dry_run([
            "--pred", "--batch", "flip_flops", "--model", "nano_detection",
            "--conf", "0.5", "--device", "cpu",
        ])
        assert code == 0

    def test_pred_custom_iou(self, cli_module):
        code, _, _ = run_dry_run([
            "--pred", "--batch", "flip_flops", "--model", "nano_detection",
            "--iou", "0.6", "--device", "cpu",
        ])
        assert code == 0

    def test_pred_custom_imgsz(self, cli_module):
        code, _, _ = run_dry_run([
            "--pred", "--batch", "flip_flops", "--model", "nano_detection",
            "--imgsz", "1280", "--device", "cpu",
        ])
        assert code == 0

    def test_pred_all_params(self, cli_module):
        code, _, _ = run_dry_run([
            "--pred", "--batch", "flip_flops", "--model", "nano_detection",
            "--conf", "0.3", "--iou", "0.5", "--imgsz", "960", "--device", "cpu",
        ])
        assert code == 0


# =============================================================================
# PRED — Multi-Dataset
# =============================================================================

class TestDryRunPredMultiDataset:
    """Dry-run PRED with multiple datasets."""

    def test_pred_multi_dataset(self, cli_module):
        code, _, _ = run_dry_run([
            "--pred", "--batch", "blurred,flip_flops",
            "--model", "nano_detection", "--device", "cpu",
        ])
        assert code == 0

    def test_pred_three_datasets(self, cli_module):
        code, _, _ = run_dry_run([
            "--pred", "--batch", "blurred,custom_capture_2026-08-14,flip_flops",
            "--model", "nano_detection", "--device", "cpu",
        ])
        assert code == 0


# =============================================================================
# SAM — All Datasets
# =============================================================================

class TestDryRunSamAllDatasets:
    """Dry-run SAM for all available datasets."""

    @pytest.mark.parametrize("dataset", ["blurred", "custom_capture_2026-08-14", "flip_flops"])
    def test_sam_each_dataset(self, cli_module, dataset):
        code, _, _ = run_dry_run(["--sam", "--batch", dataset])
        assert code == 0, f"SAM dataset={dataset} failed"

    def test_sam_multi_dataset(self, cli_module):
        code, _, _ = run_dry_run([
            "--sam", "--batch", "blurred,custom_capture_2026-08-14,flip_flops",
        ])
        assert code == 0

    def test_sam_fresh_flag(self, cli_module):
        code, _, _ = run_dry_run(["--sam", "--batch", "blurred", "--fresh"])
        assert code == 0

    def test_sam_resume_flag(self, cli_module):
        code, _, _ = run_dry_run(["--sam", "--batch", "blurred", "--resume"])
        assert code == 0


# =============================================================================
# Dry-Run Output Verification
# =============================================================================

class TestDryRunOutput:
    """Verify dry-run output contains expected information."""

    def test_dry_run_shows_dry_run_message(self, cli_module):
        code, out, _ = run_dry_run(["--yolo", "--model", "nano_detection", "--device", "cpu"])
        assert "DRY RUN" in out

    def test_dry_run_shows_execution_skipped(self, cli_module):
        code, out, _ = run_dry_run(["--yolo", "--model", "nano_detection", "--device", "cpu"])
        assert "skipped" in out.lower() or "skip" in out.lower()

    def test_dry_run_shows_plan(self, cli_module):
        code, out, _ = run_dry_run(["--yolo", "--model", "nano_detection", "--device", "cpu"])
        assert "Execution Plan" in out or "Plan" in out

    def test_dry_run_shows_would_execute(self, cli_module):
        code, out, _ = run_dry_run(["--yolo", "--model", "nano_detection", "--device", "cpu"])
        assert "Would execute" in out or "would" in out.lower()

    def test_dry_run_yolo_shows_model_name(self, cli_module):
        code, out, _ = run_dry_run(["--yolo", "--model", "nano_detection", "--device", "cpu"])
        assert "nano_detection" in out or "Nano" in out or "YOLO26n" in out

    def test_dry_run_sam_shows_dataset(self, cli_module):
        code, out, _ = run_dry_run(["--sam", "--batch", "blurred"])
        assert "blurred" in out

    def test_dry_run_pred_shows_dataset_and_model(self, cli_module):
        code, out, _ = run_dry_run([
            "--pred", "--batch", "flip_flops", "--model", "small_detection", "--device", "cpu",
        ])
        assert "flip_flops" in out
        assert "small_detection" in out or "Small" in out or "YOLO26s" in out


# =============================================================================
# Error Cases — Dry-Run Should Still Validate
# =============================================================================

class TestDryRunErrorCases:
    """Dry-run should still validate arguments before showing plan."""

    def test_dry_run_sam_without_batch_fails(self, cli_module):
        code, _, _ = run_dry_run(["--sam"])
        assert code != 0

    def test_dry_run_pred_without_batch_fails(self, cli_module):
        code, _, _ = run_dry_run(["--pred"])
        assert code != 0

    def test_dry_run_invalid_model_fails(self, cli_module):
        code, _, _ = run_dry_run(["--yolo", "--model", "invalid"])
        assert code != 0

    def test_dry_run_missing_dataset_fails(self, cli_module):
        code, _, _ = run_dry_run(["--sam", "--batch", "nonexistent_xyz"])
        assert code != 0
