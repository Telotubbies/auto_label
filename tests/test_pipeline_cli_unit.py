"""Unit tests for pipeline_cli.py — pure logic functions.

Tests path resolution, dataset discovery, ETA estimation, model config
validation, and argument parsing. No GPU or terminal required.
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# =============================================================================
# Dataset Discovery
# =============================================================================

class TestDiscoverDatasets:
    """Tests for discover_datasets()."""

    def test_finds_datasets_with_images(self, cli_module, tmp_raw_dir):
        """Should find only directories that contain image files."""
        result = cli_module.discover_datasets(base_dir=tmp_raw_dir)
        names = [d[0] for d in result]
        assert "batch_a" in names
        assert "batch_b" in names
        assert "empty_batch" not in names  # no images → excluded

    def test_returns_correct_image_counts(self, cli_module, tmp_raw_dir):
        """Should count images correctly per dataset."""
        result = dict(cli_module.discover_datasets(base_dir=tmp_raw_dir))
        assert result["batch_a"] == 3
        assert result["batch_b"] == 5

    def test_ignores_non_image_files(self, cli_module, tmp_raw_dir):
        """Should not count .txt or other non-image files."""
        result = dict(cli_module.discover_datasets(base_dir=tmp_raw_dir))
        assert result["batch_a"] == 3  # readme.txt excluded

    def test_returns_empty_for_missing_dir(self, cli_module, tmp_path):
        """Should return empty list if directory doesn't exist."""
        result = cli_module.discover_datasets(base_dir=tmp_path / "nonexistent")
        assert result == []

    def test_sorted_by_name(self, cli_module, tmp_raw_dir):
        """Results should be sorted alphabetically."""
        result = cli_module.discover_datasets(base_dir=tmp_raw_dir)
        names = [d[0] for d in result]
        assert names == sorted(names)


class TestCountImages:
    """Tests for count_images()."""

    def test_counts_jpg(self, cli_module, tmp_path):
        (tmp_path / "a.jpg").write_bytes(b"x")
        (tmp_path / "b.jpg").write_bytes(b"x")
        assert cli_module.count_images(tmp_path) == 2

    def test_counts_png(self, cli_module, tmp_path):
        (tmp_path / "a.png").write_bytes(b"x")
        assert cli_module.count_images(tmp_path) == 1

    def test_counts_mixed_extensions(self, cli_module, tmp_path):
        for ext in [".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif"]:
            (tmp_path / f"img{ext}").write_bytes(b"x")
        assert cli_module.count_images(tmp_path) == 7

    def test_ignores_non_images(self, cli_module, tmp_path):
        (tmp_path / "a.jpg").write_bytes(b"x")
        (tmp_path / "b.txt").write_text("x")
        (tmp_path / "c.json").write_text("{}")
        assert cli_module.count_images(tmp_path) == 1

    def test_returns_zero_for_empty_dir(self, cli_module, tmp_path):
        assert cli_module.count_images(tmp_path) == 0

    def test_returns_zero_for_missing_path(self, cli_module, tmp_path):
        assert cli_module.count_images(tmp_path / "nope") == 0

    def test_single_file(self, cli_module, tmp_path):
        f = tmp_path / "single.jpg"
        f.write_bytes(b"x")
        assert cli_module.count_images(f) == 1


# =============================================================================
# Path Resolution
# =============================================================================

class TestResolveInputDir:
    """Tests for resolve_input_dir()."""

    def test_from_batch(self, cli_module, tmp_path):
        result = cli_module.resolve_input_dir("my_batch", None, base_dir=tmp_path)
        assert result == tmp_path / "my_batch"

    def test_from_input_path(self, cli_module, tmp_path):
        result = cli_module.resolve_input_dir(None, "/some/explicit/path")
        assert result == Path("/some/explicit/path")

    def test_input_overrides_batch(self, cli_module, tmp_path):
        result = cli_module.resolve_input_dir("batch", "/explicit/path", base_dir=tmp_path)
        assert result == Path("/explicit/path")

    def test_raises_when_neither_given(self, cli_module):
        with pytest.raises(ValueError, match="batch or input_path"):
            cli_module.resolve_input_dir(None, None)


class TestResolveOutputDir:
    """Tests for resolve_output_dir()."""

    def test_sam_mode(self, cli_module):
        result = cli_module.resolve_output_dir("sam", "my_batch", None)
        assert "sam_outputs_ground_truth" in str(result)
        assert "my_batch" in str(result)

    def test_pred_mode(self, cli_module):
        result = cli_module.resolve_output_dir("pred", "my_batch", None)
        assert "predictions" in str(result)
        assert "my_batch" in str(result)

    def test_yolo_mode(self, cli_module):
        result = cli_module.resolve_output_dir("yolo", "my_batch", None)
        assert "predictions" in str(result)

    def test_explicit_output_overrides(self, cli_module):
        result = cli_module.resolve_output_dir("sam", "batch", "/custom/output")
        assert result == Path("/custom/output")

    def test_raises_without_batch(self, cli_module):
        with pytest.raises(ValueError, match="batch name required"):
            cli_module.resolve_output_dir("sam", None, None)

    def test_raises_for_unknown_mode(self, cli_module):
        with pytest.raises(ValueError, match="Unknown mode"):
            cli_module.resolve_output_dir("unknown", "batch", None)


# =============================================================================
# Model List Parsing
# =============================================================================

class TestParseModelList:
    """Tests for parse_model_list()."""

    def test_returns_all_when_none(self, cli_module):
        result = cli_module.parse_model_list(None)
        assert set(result) == {"nano_detection", "small_detection", "nano_segmentation", "small_segmentation"}

    def test_returns_all_when_empty(self, cli_module):
        result = cli_module.parse_model_list("")
        assert len(result) == 4

    def test_single_model(self, cli_module):
        result = cli_module.parse_model_list("nano_detection")
        assert result == ["nano_detection"]

    def test_multiple_models(self, cli_module):
        result = cli_module.parse_model_list("nano_detection,small_detection")
        assert result == ["nano_detection", "small_detection"]

    def test_strips_whitespace(self, cli_module):
        result = cli_module.parse_model_list(" nano_detection , small_detection ")
        assert result == ["nano_detection", "small_detection"]

    def test_raises_for_unknown_model(self, cli_module):
        with pytest.raises(ValueError, match="Unknown model"):
            cli_module.parse_model_list("invalid_model")

    def test_raises_for_partial_invalid(self, cli_module):
        with pytest.raises(ValueError, match="Unknown model"):
            cli_module.parse_model_list("nano_detection,invalid_model")


# =============================================================================
# Batch List Parsing
# =============================================================================

class TestParseBatchList:
    """Tests for parse_batch_list()."""

    def test_single_batch(self, cli_module, tmp_raw_dir):
        result = cli_module.parse_batch_list("batch_a", base_dir=tmp_raw_dir)
        assert result == ["batch_a"]

    def test_multiple_batches(self, cli_module, tmp_raw_dir):
        result = cli_module.parse_batch_list("batch_a,batch_b", base_dir=tmp_raw_dir)
        assert result == ["batch_a", "batch_b"]

    def test_strips_whitespace(self, cli_module, tmp_raw_dir):
        result = cli_module.parse_batch_list(" batch_a , batch_b ", base_dir=tmp_raw_dir)
        assert result == ["batch_a", "batch_b"]

    def test_empty_string_returns_empty(self, cli_module, tmp_raw_dir):
        result = cli_module.parse_batch_list("", base_dir=tmp_raw_dir)
        assert result == []

    def test_none_returns_empty(self, cli_module, tmp_raw_dir):
        result = cli_module.parse_batch_list(None, base_dir=tmp_raw_dir)
        assert result == []

    def test_raises_for_missing_dataset(self, cli_module, tmp_raw_dir):
        with pytest.raises(ValueError, match="Dataset.*not found"):
            cli_module.parse_batch_list("nonexistent", base_dir=tmp_raw_dir)


# =============================================================================
# ETA Estimation
# =============================================================================

class TestEstimateEtaSam:
    """Tests for estimate_eta_sam()."""

    def test_basic_calculation(self, cli_module):
        assert cli_module.estimate_eta_sam(10) == 350  # 10 * 35

    def test_zero_images(self, cli_module):
        assert cli_module.estimate_eta_sam(0) == 0

    def test_large_batch(self, cli_module):
        assert cli_module.estimate_eta_sam(100) == 3500


class TestEstimateEtaYoloTrain:
    """Tests for estimate_eta_yolo_train()."""

    def test_both_stages(self, cli_module):
        # Stage 1: 45min, Stage 2: 15min → 60min per model
        result = cli_module.estimate_eta_yolo_train(1, stage=12)
        assert result == 60 * 60  # 3600s

    def test_stage1_only(self, cli_module):
        result = cli_module.estimate_eta_yolo_train(1, stage=1)
        assert result == 45 * 60  # 2700s

    def test_stage2_only(self, cli_module):
        result = cli_module.estimate_eta_yolo_train(1, stage=2)
        assert result == 15 * 60  # 900s

    def test_multiple_models(self, cli_module):
        result = cli_module.estimate_eta_yolo_train(4, stage=12)
        assert result == 4 * 60 * 60  # 14400s


class TestEstimateEtaYoloPred:
    """Tests for estimate_eta_yolo_pred()."""

    def test_basic(self, cli_module):
        # 4 models * 5s + 48 * 0.025 * 4 = 20 + 4.8 = 24 (int)
        result = cli_module.estimate_eta_yolo_pred(48, 4)
        assert result == 24

    def test_zero_images(self, cli_module):
        result = cli_module.estimate_eta_yolo_pred(0, 4)
        assert result == 20  # just model load time


class TestFormatEta:
    """Tests for format_eta()."""

    def test_seconds(self, cli_module):
        assert cli_module.format_eta(30) == "~30s"

    def test_minutes(self, cli_module):
        assert cli_module.format_eta(125) == "~2m 5s"

    def test_hours(self, cli_module):
        assert cli_module.format_eta(7380) == "~2h 3m"

    def test_zero(self, cli_module):
        assert cli_module.format_eta(0) == "~0s"

    def test_negative(self, cli_module):
        assert cli_module.format_eta(-1) == "—"


# =============================================================================
# Model Config
# =============================================================================

class TestModelConfig:
    """Tests for MODELS dict integrity."""

    def test_four_models_defined(self, cli_module):
        assert len(cli_module.MODELS) == 4

    def test_model_keys_are_descriptive(self, cli_module):
        keys = set(cli_module.MODELS.keys())
        assert keys == {"nano_detection", "small_detection", "nano_segmentation", "small_segmentation"}

    def test_each_model_has_required_fields(self, cli_module):
        required = {"weights", "task", "label", "desc", "project", "best", "data", "batch", "size"}
        for key, cfg in cli_module.MODELS.items():
            missing = required - set(cfg.keys())
            assert not missing, f"{key} missing fields: {missing}"

    def test_model_tasks_are_valid(self, cli_module):
        for cfg in cli_module.MODELS.values():
            assert cfg["task"] in ("detect", "segment")

    def test_model_sizes_are_valid(self, cli_module):
        for cfg in cli_module.MODELS.values():
            assert cfg["size"] in ("n", "s")

    def test_detection_models_use_detect_data(self, cli_module):
        for key, cfg in cli_module.MODELS.items():
            if cfg["task"] == "detect":
                assert "detect" in cfg["data"]

    def test_segmentation_models_use_seg_data(self, cli_module):
        for key, cfg in cli_module.MODELS.items():
            if cfg["task"] == "segment":
                assert "seg" in cfg["data"]

    def test_best_paths_use_production_structure(self, cli_module):
        for key, cfg in cli_module.MODELS.items():
            path_str = str(cfg["best"])
            assert "models/production" in path_str
            assert "stage_2_final_fine_tuning" in path_str
            assert "weights/best.pt" in path_str


# =============================================================================
# Validation
# =============================================================================

class TestValidateModeArgs:
    """Tests for validate_mode_args()."""

    def test_no_mode_returns_error(self, cli_module):
        errors = cli_module.validate_mode_args(None, "batch", None)
        assert any("No mode" in e for e in errors)

    def test_sam_without_batch_returns_error(self, cli_module):
        errors = cli_module.validate_mode_args("sam", None, None)
        assert any("--batch" in e for e in errors)

    def test_pred_without_batch_returns_error(self, cli_module):
        errors = cli_module.validate_mode_args("pred", None, None)
        assert any("--batch" in e for e in errors)

    def test_yolo_without_batch_is_ok(self, cli_module):
        errors = cli_module.validate_mode_args("yolo", None, None)
        assert not errors  # yolo doesn't require --batch

    def test_yolo_with_invalid_model_returns_error(self, cli_module):
        errors = cli_module.validate_mode_args("yolo", None, "invalid_model")
        assert any("Unknown model" in e for e in errors)

    def test_valid_args_return_no_errors(self, cli_module):
        errors = cli_module.validate_mode_args("sam", "blurred", None)
        assert not errors


# =============================================================================
# Environment Checks
# =============================================================================

class TestCheckSamCheckpoint:
    """Tests for check_sam_checkpoint()."""

    def test_returns_tuple(self, cli_module):
        result = cli_module.check_sam_checkpoint()
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)

    def test_path_contains_checkpoint_name(self, cli_module):
        _, path = cli_module.check_sam_checkpoint()
        assert "sam3.1_multiplex.pt" in path
        assert "checkpoints" in path


class TestCheckProductionModels:
    """Tests for check_production_models()."""

    def test_returns_count_and_list(self, cli_module):
        count, trained = cli_module.check_production_models()
        assert isinstance(count, int)
        assert isinstance(trained, list)
        assert 0 <= count <= 4

    def test_trained_models_are_valid_keys(self, cli_module):
        _, trained = cli_module.check_production_models()
        for key in trained:
            assert key in cli_module.MODELS


class TestCheckPythonVenv:
    """Tests for check_python_venv()."""

    def test_returns_bool(self, cli_module):
        result = cli_module.check_python_venv()
        assert isinstance(result, bool)
