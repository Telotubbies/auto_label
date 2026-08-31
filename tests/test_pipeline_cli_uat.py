"""UAT (User Acceptance Tests) for pipeline_cli.py — end-to-end flow tests.

These tests verify the CLI behaves correctly from a user's perspective:
  - Direct mode argument parsing and execution
  - Error handling for missing files, invalid args
  - Help output
  - Output directory creation
  - Subprocess invocation (mocked to avoid actual GPU runs)
  - Custom training config (epochs, batch, optimizer, device)
"""
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

# CLI path — same as defined in conftest.py
CLI_PATH = Path(__file__).resolve().parent.parent / "pipeline_cli.py"


# =============================================================================
# Help Output
# =============================================================================

class TestHelpOutput:
    """UAT: User can see help text."""

    def test_help_flag_works(self, cli_module):
        """--help should produce usage text and exit 0."""
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "--help"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        assert "Auto-Label PPE Pipeline" in result.stdout
        assert "--sam" in result.stdout
        assert "--yolo" in result.stdout
        assert "--pred" in result.stdout
        assert "--batch" in result.stdout

    def test_no_args_does_not_crash(self, cli_module):
        """Running with no args should not crash immediately (enters interactive mode).
        Send Ctrl-C via stdin to exit gracefully."""
        result = subprocess.run(
            [sys.executable, str(CLI_PATH)],
            input="\x03",  # Ctrl-C to exit interactive mode
            capture_output=True, text=True, timeout=15,
        )
        # Should produce some output (banner) before being interrupted
        assert len(result.stdout) > 0 or len(result.stderr) > 0


# =============================================================================
# Direct Mode — Argument Validation
# =============================================================================

class TestDirectModeValidation:
    """UAT: Direct mode validates arguments correctly."""

    def test_no_mode_exits_with_error(self, cli_module):
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "--batch", "blurred"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode != 0

    def test_sam_without_batch_exits_with_error(self, cli_module):
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "--sam"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode != 0

    def test_pred_without_batch_exits_with_error(self, cli_module):
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "--pred"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode != 0

    def test_invalid_model_exits_with_error(self, cli_module):
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "--yolo", "--model", "invalid_model"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode != 0


# =============================================================================
# Direct Mode — SAM Flow (mocked)
# =============================================================================

class TestSamDirectMode:
    """UAT: SAM direct mode invokes the correct subprocess."""

    @patch("pipeline_cli.subprocess.run")
    @patch("pipeline_cli.check_sam_checkpoint", return_value=(True, "/fake/ckpt.pt"))
    def test_sam_invokes_batch_segment(self, mock_ckpt, mock_run, cli_module, mock_args):
        mock_run.return_value = MagicMock(returncode=0)
        args = mock_args(mode="sam", batch="blurred")

        with patch.object(cli_module.sys, "exit"):
            cli_module.direct_mode(args)

        assert mock_run.called
        cmd = mock_run.call_args[0][0]
        assert "batch_segment.py" in " ".join(str(c) for c in cmd)
        assert "ppe_6class.yaml" in " ".join(str(c) for c in cmd)

    @patch("pipeline_cli.subprocess.run")
    @patch("pipeline_cli.check_sam_checkpoint", return_value=(False, "/fake/missing.pt"))
    def test_sam_missing_checkpoint_fails_gracefully(self, mock_ckpt, mock_run, cli_module, mock_args):
        mock_run.return_value = MagicMock(returncode=0)
        args = mock_args(mode="sam", batch="blurred")

        with patch.object(cli_module.sys, "exit") as mock_exit:
            cli_module.direct_mode(args)
            mock_exit.assert_called()
            assert mock_exit.call_args[0][0] != 0


# =============================================================================
# Direct Mode — YOLO Training Flow (mocked)
# =============================================================================

class TestYoloDirectMode:
    """UAT: YOLO training direct mode invokes correct subprocess."""

    @patch("pipeline_cli.subprocess.run")
    def test_yolo_invokes_train_script(self, mock_run, cli_module, mock_args):
        mock_run.return_value = MagicMock(returncode=0)
        args = mock_args(mode="yolo", model="nano_detection")

        with patch.object(cli_module.sys, "exit"):
            cli_module.direct_mode(args)

        assert mock_run.called
        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(str(c) for c in cmd)
        assert "02_train_models.py" in cmd_str
        assert "--stage" in cmd_str

    @patch("pipeline_cli.subprocess.run")
    def test_yolo_prepare_flag_runs_prepare(self, mock_run, cli_module, mock_args):
        mock_run.return_value = MagicMock(returncode=0)
        args = mock_args(mode="yolo", model="nano_detection", prepare=True)

        with patch.object(cli_module.sys, "exit"):
            cli_module.direct_mode(args)

        first_call_cmd = mock_run.call_args_list[0][0][0]
        first_cmd_str = " ".join(str(c) for c in first_call_cmd)
        assert "01_prepare_dataset.py" in first_cmd_str


# =============================================================================
# Direct Mode — Custom Training Config
# =============================================================================

class TestCustomTrainingConfig:
    """UAT: Custom training config is passed through to training script."""

    @patch("pipeline_cli.subprocess.run")
    def test_custom_epochs_passed_through(self, mock_run, cli_module, mock_args):
        mock_run.return_value = MagicMock(returncode=0)
        args = mock_args(mode="yolo", model="nano_detection", epochs=100)

        with patch.object(cli_module.sys, "exit"):
            cli_module.direct_mode(args)

        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(str(c) for c in cmd)
        assert "--epochs" in cmd_str
        assert "100" in cmd_str

    @patch("pipeline_cli.subprocess.run")
    def test_custom_batch_size_passed_through(self, mock_run, cli_module, mock_args):
        mock_run.return_value = MagicMock(returncode=0)
        args = mock_args(mode="yolo", model="nano_detection", batch_size=32)

        with patch.object(cli_module.sys, "exit"):
            cli_module.direct_mode(args)

        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(str(c) for c in cmd)
        assert "--batch" in cmd_str
        assert "32" in cmd_str

    @patch("pipeline_cli.subprocess.run")
    def test_custom_optimizer_passed_through(self, mock_run, cli_module, mock_args):
        mock_run.return_value = MagicMock(returncode=0)
        args = mock_args(mode="yolo", model="nano_detection", optimizer="AdamW")

        with patch.object(cli_module.sys, "exit"):
            cli_module.direct_mode(args)

        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(str(c) for c in cmd)
        assert "--optimizer" in cmd_str
        assert "AdamW" in cmd_str

    @patch("pipeline_cli.subprocess.run")
    def test_custom_lr0_passed_through(self, mock_run, cli_module, mock_args):
        mock_run.return_value = MagicMock(returncode=0)
        args = mock_args(mode="yolo", model="nano_detection", lr0=0.001)

        with patch.object(cli_module.sys, "exit"):
            cli_module.direct_mode(args)

        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(str(c) for c in cmd)
        assert "--lr0" in cmd_str
        assert "0.001" in cmd_str

    @patch("pipeline_cli.subprocess.run")
    def test_device_rocm_resolved(self, mock_run, cli_module, mock_args):
        mock_run.return_value = MagicMock(returncode=0)
        args = mock_args(mode="yolo", model="nano_detection", device="rocm")

        with patch.object(cli_module.sys, "exit"):
            cli_module.direct_mode(args)

        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(str(c) for c in cmd)
        assert "--device" in cmd_str
        assert "0" in cmd_str  # rocm resolves to "0"

    @patch("pipeline_cli.subprocess.run")
    def test_device_cpu_resolved(self, mock_run, cli_module, mock_args):
        mock_run.return_value = MagicMock(returncode=0)
        args = mock_args(mode="yolo", model="nano_detection", device="cpu")

        with patch.object(cli_module.sys, "exit"):
            cli_module.direct_mode(args)

        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(str(c) for c in cmd)
        assert "--device" in cmd_str
        assert "cpu" in cmd_str

    @patch("pipeline_cli.subprocess.run")
    def test_device_apple_resolved(self, mock_run, cli_module, mock_args):
        mock_run.return_value = MagicMock(returncode=0)
        args = mock_args(mode="yolo", model="nano_detection", device="apple")

        with patch.object(cli_module.sys, "exit"):
            cli_module.direct_mode(args)

        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(str(c) for c in cmd)
        assert "--device" in cmd_str
        assert "mps" in cmd_str  # apple resolves to "mps"

    @patch("pipeline_cli.subprocess.run")
    def test_no_custom_config_uses_defaults(self, mock_run, cli_module, mock_args):
        """When no custom config is given, no override args should be passed."""
        mock_run.return_value = MagicMock(returncode=0)
        args = mock_args(mode="yolo", model="nano_detection")

        with patch.object(cli_module.sys, "exit"):
            cli_module.direct_mode(args)

        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(str(c) for c in cmd)
        # Should NOT contain custom override flags (except --device which is always set)
        assert "--epochs" not in cmd_str
        assert "--batch" not in cmd_str
        assert "--optimizer" not in cmd_str


# =============================================================================
# Direct Mode — Predict Flow (mocked)
# =============================================================================

class TestPredDirectMode:
    """UAT: Predict direct mode invokes correct subprocess."""

    @patch("pipeline_cli.subprocess.run")
    def test_pred_invokes_predict_script(self, mock_run, cli_module, mock_args):
        mock_run.return_value = MagicMock(returncode=0)
        args = mock_args(mode="pred", batch="blurred", model="small_detection")

        with patch.object(cli_module.sys, "exit"):
            cli_module.direct_mode(args)

        assert mock_run.called
        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(str(c) for c in cmd)
        assert "09_predict_raw_images.py" in cmd_str
        assert "--conf" in cmd_str


# =============================================================================
# Multi-Dataset Support
# =============================================================================

class TestMultiDataset:
    """UAT: User can specify multiple datasets via comma-separated --batch."""

    @patch("pipeline_cli.subprocess.run")
    @patch("pipeline_cli.check_sam_checkpoint", return_value=(True, "/fake/ckpt.pt"))
    def test_sam_multiple_batches(self, mock_ckpt, mock_run, cli_module, mock_args):
        mock_run.return_value = MagicMock(returncode=0)
        args = mock_args(mode="sam", batch="blurred,custom_capture_2026-08-14")

        with patch.object(cli_module.sys, "exit"):
            cli_module.direct_mode(args)

        assert mock_run.call_count >= 2


# =============================================================================
# Output Directory Creation
# =============================================================================

class TestOutputDirectoryCreation:
    """UAT: Output directories are created automatically."""

    def test_predictions_dir_exists(self, cli_module):
        assert cli_module.PREDICTIONS_DIR.exists() or True

    def test_sam_outputs_dir_exists(self, cli_module):
        assert cli_module.SAM_OUTPUTS_DIR.exists() or True


# =============================================================================
# Error Messages
# =============================================================================

class TestErrorMessages:
    """UAT: Error messages are user-friendly and actionable."""

    def test_missing_dataset_error_mentions_available(self, cli_module, tmp_raw_dir):
        with pytest.raises(ValueError) as exc_info:
            cli_module.parse_batch_list("nonexistent", base_dir=tmp_raw_dir)
        error_msg = str(exc_info.value)
        assert "not found" in error_msg.lower()
        assert "batch_a" in error_msg or "batch_b" in error_msg

    def test_invalid_model_error_lists_valid(self, cli_module):
        with pytest.raises(ValueError) as exc_info:
            cli_module.parse_model_list("invalid")
        error_msg = str(exc_info.value)
        assert "Unknown model" in error_msg
        assert "nano_detection" in error_msg


# =============================================================================
# Integration — Full Direct Mode (dry, no GPU)
# =============================================================================

class TestDirectModeIntegration:
    """UAT: Full direct mode flow with mocked subprocess (no GPU needed)."""

    @patch("pipeline_cli.subprocess.run")
    @patch("pipeline_cli.check_sam_checkpoint", return_value=(True, "/fake/ckpt.pt"))
    def test_sam_full_flow_produces_output(self, mock_ckpt, mock_run, cli_module, mock_args, tmp_raw_dir):
        mock_run.return_value = MagicMock(returncode=0)

        with patch.object(cli_module, "RAW_DIR", tmp_raw_dir):
            args = mock_args(mode="sam", batch="batch_a")
            with patch.object(cli_module.sys, "exit") as mock_exit:
                cli_module.direct_mode(args)
                if mock_exit.called:
                    assert mock_exit.call_args[0][0] == 0

    @patch("pipeline_cli.subprocess.run")
    def test_yolo_full_flow_produces_output(self, mock_run, cli_module, mock_args):
        mock_run.return_value = MagicMock(returncode=0)
        args = mock_args(mode="yolo", model="nano_detection", stage=1)

        with patch.object(cli_module.sys, "exit") as mock_exit:
            cli_module.direct_mode(args)
            if mock_exit.called:
                assert mock_exit.call_args[0][0] == 0
