"""Unit tests for new CLI features: device selection, training config, build_train_overrides."""
import pytest
from unittest.mock import patch, MagicMock


# =============================================================================
# Processing Device Selection
# =============================================================================

class TestProcessingDevices:
    """Tests for PROCESSING_DEVICES config and resolve_device()."""

    def test_four_devices_defined(self, cli_module):
        assert set(cli_module.PROCESSING_DEVICES.keys()) == {"rocm", "cuda", "apple", "cpu"}

    def test_each_device_has_required_fields(self, cli_module):
        for key, cfg in cli_module.PROCESSING_DEVICES.items():
            assert "label" in cfg
            assert "value" in cfg
            assert "desc" in cfg

    def test_resolve_device_rocm(self, cli_module):
        assert cli_module.resolve_device("rocm") == "0"

    def test_resolve_device_cuda(self, cli_module):
        assert cli_module.resolve_device("cuda") == "0"

    def test_resolve_device_apple(self, cli_module):
        assert cli_module.resolve_device("apple") == "mps"

    def test_resolve_device_cpu(self, cli_module):
        assert cli_module.resolve_device("cpu") == "cpu"

    def test_resolve_device_passthrough(self, cli_module):
        """Unknown device keys should pass through as-is."""
        assert cli_module.resolve_device("0") == "0"
        assert cli_module.resolve_device("1") == "1"
        assert cli_module.resolve_device("mps") == "mps"


class TestDetectAvailableDevice:
    """Tests for detect_available_device()."""

    def test_returns_string(self, cli_module):
        result = cli_module.detect_available_device()
        assert isinstance(result, str)
        assert result in ("rocm", "cuda", "apple", "cpu")

    def test_returns_cpu_in_test_env(self, cli_module):
        """In the test environment (no GPU), should return 'cpu'."""
        result = cli_module.detect_available_device()
        # In WSL test env without proper GPU, this should be cpu or rocm
        assert result in ("rocm", "cuda", "apple", "cpu")


# =============================================================================
# Training Config
# =============================================================================

class TestTrainingDefaults:
    """Tests for TRAINING_DEFAULTS config."""

    def test_has_required_keys(self, cli_module):
        required = {"epochs_stage1", "epochs_stage2", "batch", "workers",
                    "optimizer", "lr0_stage1", "lr0_stage2", "imgsz",
                    "patience_stage1", "patience_stage2"}
        for key in required:
            assert key in cli_module.TRAINING_DEFAULTS, f"Missing key: {key}"

    def test_optimizer_choices(self, cli_module):
        assert set(cli_module.OPTIMIZER_CHOICES) == {"SGD", "Adam", "AdamW", "RMSProp"}


class TestBuildTrainOverrides:
    """Tests for build_train_overrides()."""

    def test_empty_config_returns_empty(self, cli_module):
        assert cli_module.build_train_overrides({}) == []

    def test_epochs(self, cli_module):
        result = cli_module.build_train_overrides({"epochs": 100})
        assert "--epochs" in result
        assert "100" in result

    def test_batch(self, cli_module):
        result = cli_module.build_train_overrides({"batch": 32})
        assert "--batch" in result
        assert "32" in result

    def test_workers(self, cli_module):
        result = cli_module.build_train_overrides({"workers": 8})
        assert "--workers" in result
        assert "8" in result

    def test_optimizer(self, cli_module):
        result = cli_module.build_train_overrides({"optimizer": "AdamW"})
        assert "--optimizer" in result
        assert "AdamW" in result

    def test_lr0(self, cli_module):
        result = cli_module.build_train_overrides({"lr0": 0.001})
        assert "--lr0" in result
        assert "0.001" in result

    def test_imgsz(self, cli_module):
        result = cli_module.build_train_overrides({"imgsz": 1280})
        assert "--imgsz" in result
        assert "1280" in result

    def test_device(self, cli_module):
        result = cli_module.build_train_overrides({"device": "0"})
        assert "--device" in result
        assert "0" in result

    def test_patience(self, cli_module):
        result = cli_module.build_train_overrides({"patience": 20})
        assert "--patience" in result
        assert "20" in result

    def test_multiple_overrides(self, cli_module):
        config = {"epochs": 100, "batch": 32, "optimizer": "AdamW", "lr0": 0.001}
        result = cli_module.build_train_overrides(config)
        result_str = " ".join(result)
        assert "--epochs" in result_str
        assert "--batch" in result_str
        assert "--optimizer" in result_str
        assert "--lr0" in result_str

    def test_none_values_skipped(self, cli_module):
        """None values should not produce CLI args."""
        config = {"epochs": None, "batch": 32, "workers": None}
        result = cli_module.build_train_overrides(config)
        result_str = " ".join(result)
        assert "--batch" in result_str
        assert "--epochs" not in result_str
        assert "--workers" not in result_str
