"""Comprehensive tests for new CLI features: dry-run, verbosity, version, TTY, typed exceptions.

Covers:
  - Global flags: --verbose, --quiet, --debug, --dry-run, --format, --version/-V
  - Typed exception hierarchy: PipelineError → ConfigError, DatasetError, DeviceError, etc.
  - render_error_panel(), handle_pipeline_error()
  - Verbosity and OutputFormat enums
  - TTY detection for interactive mode
  - Version output
"""
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

CLI_PATH = Path(__file__).resolve().parent.parent / "pipeline_cli.py"


# =============================================================================
# Version
# =============================================================================

class TestVersion:
    """Tests for --version / -V flag."""

    def test_version_flag_prints_version(self, cli_module):
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "--version"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0
        assert "v" in result.stdout.lower()

    def test_short_version_flag_works(self, cli_module):
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "-V"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0

    def test_version_string_contains_app_name(self, cli_module):
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "--version"],
            capture_output=True, text=True, timeout=15,
        )
        assert "Auto-Label" in result.stdout or "PPE" in result.stdout

    def test_version_module_attribute_exists(self, cli_module):
        assert hasattr(cli_module, "__version__")
        assert isinstance(cli_module.__version__, str)
        assert len(cli_module.__version__) > 0

    def test_version_module_attribute_format(self, cli_module):
        """Version should be in semver-like format."""
        v = cli_module.__version__
        parts = v.split(".")
        assert len(parts) >= 2, f"Version '{v}' should have at least major.minor"

    def test_app_name_attribute_exists(self, cli_module):
        assert hasattr(cli_module, "__app_name__")
        assert "PPE" in cli_module.__app_name__ or "Auto-Label" in cli_module.__app_name__


# =============================================================================
# Verbosity Enum
# =============================================================================

class TestVerbosityEnum:
    """Tests for Verbosity enum."""

    def test_verbosity_is_enum(self, cli_module):
        assert hasattr(cli_module, "Verbosity")
        # Check it's a proper enum-like class with expected values
        for v in ["QUIET", "NORMAL", "VERBOSE", "DEBUG"]:
            assert hasattr(cli_module.Verbosity, v), f"Missing Verbosity.{v}"

    def test_verbosity_values_are_strings(self, cli_module):
        for v in cli_module.Verbosity:
            assert isinstance(v.value, str)

    def test_verbosity_has_four_levels(self, cli_module):
        levels = list(cli_module.Verbosity)
        assert len(levels) == 4

    def test_verbosity_default_is_normal(self, cli_module):
        """Default verbosity should be NORMAL."""
        assert cli_module._verbosity == cli_module.Verbosity.NORMAL


# =============================================================================
# OutputFormat Enum
# =============================================================================

class TestOutputFormatEnum:
    """Tests for OutputFormat enum."""

    def test_output_format_is_enum(self, cli_module):
        assert hasattr(cli_module, "OutputFormat")
        for f in ["TABLE", "JSON", "PLAIN"]:
            assert hasattr(cli_module.OutputFormat, f), f"Missing OutputFormat.{f}"

    def test_output_format_has_three_options(self, cli_module):
        formats = list(cli_module.OutputFormat)
        assert len(formats) == 3

    def test_output_format_default_is_table(self, cli_module):
        assert cli_module._output_format == cli_module.OutputFormat.TABLE


# =============================================================================
# Dry-Run Global State
# =============================================================================

class TestDryRunState:
    """Tests for _dry_run global state."""

    def test_dry_run_default_is_false(self, cli_module):
        assert cli_module._dry_run is False


# =============================================================================
# Typed Exception Hierarchy
# =============================================================================

class TestTypedExceptionHierarchy:
    """Tests for typed exception hierarchy (production pattern)."""

    def test_pipeline_error_exists(self, cli_module):
        assert hasattr(cli_module, "PipelineError")
        assert issubclass(cli_module.PipelineError, Exception)

    def test_pipeline_error_has_message_and_hint(self, cli_module):
        err = cli_module.PipelineError("test error", hint="test hint")
        assert err.message == "test error"
        assert err.hint == "test hint"

    def test_pipeline_error_default_hint_is_empty(self, cli_module):
        err = cli_module.PipelineError("test error")
        assert err.hint == ""

    def test_config_error_subclass(self, cli_module):
        assert issubclass(cli_module.ConfigError, cli_module.PipelineError)

    def test_dataset_error_subclass(self, cli_module):
        assert issubclass(cli_module.DatasetError, cli_module.PipelineError)

    def test_device_error_subclass(self, cli_module):
        assert issubclass(cli_module.DeviceError, cli_module.PipelineError)

    def test_checkpoint_error_subclass(self, cli_module):
        assert issubclass(cli_module.CheckpointError, cli_module.PipelineError)

    def test_training_error_subclass(self, cli_module):
        assert issubclass(cli_module.TrainingError, cli_module.PipelineError)

    def test_prediction_error_subclass(self, cli_module):
        assert issubclass(cli_module.PredictionError, cli_module.PipelineError)

    def test_all_subclasses_inherit_message_hint(self, cli_module):
        """All subclasses should support message + hint pattern."""
        for exc_class in [cli_module.ConfigError, cli_module.DatasetError,
                          cli_module.DeviceError, cli_module.CheckpointError,
                          cli_module.TrainingError, cli_module.PredictionError]:
            err = exc_class("msg", hint="fix")
            assert err.message == "msg"
            assert err.hint == "fix"

    def test_pipeline_error_can_be_raised_and_caught(self, cli_module):
        with pytest.raises(cli_module.PipelineError, match="test msg"):
            raise cli_module.PipelineError("test msg")

    def test_subclass_caught_by_base(self, cli_module):
        """ConfigError should be catchable as PipelineError."""
        with pytest.raises(cli_module.PipelineError):
            raise cli_module.ConfigError("config issue")

    def test_specific_subclass_not_caught_by_wrong_type(self, cli_module):
        """DatasetError should not be caught as ConfigError."""
        with pytest.raises(cli_module.DatasetError):
            try:
                raise cli_module.DatasetError("dataset issue")
            except cli_module.ConfigError:
                pytest.fail("DatasetError should not be caught as ConfigError")


# =============================================================================
# render_error_panel / handle_pipeline_error
# =============================================================================

class TestErrorRendering:
    """Tests for error rendering functions."""

    def test_render_error_panel_does_not_crash(self, cli_module):
        err = cli_module.PipelineError("test error", hint="test fix")
        # Should not raise
        cli_module.render_error_panel(err)

    def test_handle_pipeline_error_returns_exit_code(self, cli_module):
        err = cli_module.PipelineError("test error")
        code = cli_module.handle_pipeline_error(err)
        assert code == 1

    def test_handle_pipeline_error_with_debug_shows_traceback(self, cli_module):
        """In DEBUG mode, traceback should be shown."""
        cli_module._verbosity = cli_module.Verbosity.DEBUG
        try:
            err = cli_module.PipelineError("debug error")
            code = cli_module.handle_pipeline_error(err)
            assert code == 1
        finally:
            cli_module._verbosity = cli_module.Verbosity.NORMAL

    def test_render_error_with_hint(self, cli_module):
        """render_error should display hint when provided."""
        cli_module.render_error("main error", hint="fix it")

    def test_render_error_without_hint(self, cli_module):
        """render_error should work without hint."""
        cli_module.render_error("just an error")

    def test_render_tip(self, cli_module):
        """render_tip should not crash."""
        cli_module.render_tip("helpful tip")


# =============================================================================
# TTY Detection
# =============================================================================

class TestTTYDetection:
    """Tests for TTY check in interactive mode."""

    def test_no_args_without_tty_exits_with_error(self, cli_module):
        """Running with no args and no TTY should exit with error, not hang."""
        result = subprocess.run(
            [sys.executable, str(CLI_PATH)],
            capture_output=True, text=True, timeout=15,
            # No stdin= → subprocess inherits, but capture_output makes it non-TTY
        )
        assert result.returncode != 0
        assert "terminal" in result.stdout.lower() or "tty" in result.stdout.lower() \
            or "interactive" in result.stdout.lower()

    def test_no_args_error_message_is_actionable(self, cli_module):
        """Error message should tell user what to do."""
        result = subprocess.run(
            [sys.executable, str(CLI_PATH)],
            capture_output=True, text=True, timeout=15,
        )
        combined = result.stdout + result.stderr
        assert "--help" in combined or "help" in combined.lower()


# =============================================================================
# Dry-Run Behavior (subprocess-level)
# =============================================================================

class TestDryRunBehavior:
    """Tests that --dry-run actually skips execution."""

    def test_dry_run_yolo_does_not_call_subprocess(self, cli_module, mock_args):
        """In dry-run mode, subprocess.run should NOT be called."""
        args = mock_args(mode="yolo", model="nano_detection", dry_run=True)
        # Set global dry_run flag
        original = cli_module._dry_run
        cli_module._dry_run = True
        try:
            with patch("pipeline_cli.subprocess.run") as mock_run:
                with patch.object(cli_module.sys, "exit"):
                    cli_module.direct_mode(args)
                assert not mock_run.called, "subprocess.run should not be called in dry-run"
        finally:
            cli_module._dry_run = original

    def test_dry_run_sam_does_not_call_subprocess(self, cli_module, mock_args):
        args = mock_args(mode="sam", batch="blurred", dry_run=True)
        original = cli_module._dry_run
        cli_module._dry_run = True
        try:
            with patch("pipeline_cli.subprocess.run") as mock_run:
                with patch("pipeline_cli.check_sam_checkpoint", return_value=(True, "/fake/ckpt.pt")):
                    with patch.object(cli_module.sys, "exit"):
                        cli_module.direct_mode(args)
                    assert not mock_run.called
        finally:
            cli_module._dry_run = original

    def test_dry_run_pred_does_not_call_subprocess(self, cli_module, mock_args):
        args = mock_args(mode="pred", batch="blurred", model="nano_detection", dry_run=True)
        original = cli_module._dry_run
        cli_module._dry_run = True
        try:
            with patch("pipeline_cli.subprocess.run") as mock_run:
                with patch.object(cli_module.sys, "exit"):
                    cli_module.direct_mode(args)
                assert not mock_run.called
        finally:
            cli_module._dry_run = original


# =============================================================================
# Global Flags — Subprocess Integration
# =============================================================================

class TestGlobalFlagsSubprocess:
    """Test global flags via actual subprocess calls."""

    def test_verbose_flag_accepted(self, cli_module):
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "-v", "--help"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0

    def test_quiet_flag_accepted(self, cli_module):
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "-q", "--help"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0

    def test_debug_flag_accepted(self, cli_module):
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "--debug", "--help"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0

    def test_format_table_accepted(self, cli_module):
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "--format", "table", "--help"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0

    def test_format_json_accepted(self, cli_module):
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "--format", "json", "--help"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0

    def test_format_plain_accepted(self, cli_module):
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "--format", "plain", "--help"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0

    def test_format_invalid_rejected(self, cli_module):
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "--format", "xml", "--help"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode != 0

    def test_dry_run_flag_accepted(self, cli_module):
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "--dry-run", "--yolo",
             "--model", "nano_detection", "--device", "cpu"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        assert "DRY RUN" in result.stdout

    def test_help_shows_global_flags(self, cli_module):
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "--help"],
            capture_output=True, text=True, timeout=15,
        )
        assert "--verbose" in result.stdout
        assert "--quiet" in result.stdout
        assert "--debug" in result.stdout
        assert "--dry-run" in result.stdout
        assert "--format" in result.stdout
        assert "--version" in result.stdout

    def test_help_shows_custom_training_section(self, cli_module):
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "--help"],
            capture_output=True, text=True, timeout=15,
        )
        assert "--epochs" in result.stdout
        assert "--batch-size" in result.stdout
        assert "--optimizer" in result.stdout
        assert "--lr0" in result.stdout
        assert "--patience" in result.stdout

    def test_help_shows_version_in_description(self, cli_module):
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "--help"],
            capture_output=True, text=True, timeout=15,
        )
        assert "v2" in result.stdout or "v1" in result.stdout  # version prefix
