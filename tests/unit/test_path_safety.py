"""TC-03: Path traversal blocked.

Verifies that `_sanitize_path()` and `resolve_input_dir()` reject paths that
escape the allowed base directory, preventing directory-traversal attacks
(ISO 27001 A.14.1.2).
"""
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


class TestSanitizePath:
    """Direct tests for the `_sanitize_path` pure function."""

    def test_rejects_dotdot_traversal(self, pipeline_cli, tmp_path):
        base = tmp_path / "safe"
        base.mkdir()
        # Classic traversal attempt
        with pytest.raises(ValueError, match="escapes base directory"):
            pipeline_cli._sanitize_path("../../../etc/passwd", base)

    def test_rejects_absolute_path_outside_base(self, pipeline_cli, tmp_path):
        base = tmp_path / "safe"
        base.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        with pytest.raises(ValueError):
            pipeline_cli._sanitize_path(str(outside / "secret.txt"), base)

    def test_accepts_path_inside_base(self, pipeline_cli, tmp_path):
        base = tmp_path / "safe"
        base.mkdir()
        target = base / "subdir" / "file.txt"
        target.parent.mkdir(parents=True)
        target.touch()
        result = pipeline_cli._sanitize_path(str(target), base)
        assert result.resolve().is_relative_to(base.resolve())

    def test_accepts_path_without_base(self, pipeline_cli, tmp_path):
        """When base_dir is None, any resolvable path is accepted (no containment check)."""
        target = tmp_path / "free.txt"
        target.touch()
        result = pipeline_cli._sanitize_path(str(target), None)
        assert result == target.resolve()

    def test_rejects_symlink_escape(self, pipeline_cli, tmp_path):
        base = tmp_path / "safe"
        base.mkdir()
        outside = tmp_path / "outside" / "secret.txt"
        outside.parent.mkdir(parents=True)
        outside.touch()
        link = base / "link"
        link.symlink_to(outside)
        with pytest.raises(ValueError):
            pipeline_cli._sanitize_path(str(link), base)


class TestResolveInputDir:
    """Tests for `resolve_input_dir` — the user-facing path resolver."""

    def test_rejects_traversal_via_input_path(self, pipeline_cli, tmp_path):
        base = tmp_path / "data" / "raw"
        base.mkdir(parents=True)
        with pytest.raises(ValueError):
            pipeline_cli.resolve_input_dir(
                batch=None, input_path="../../../etc/passwd", base_dir=base
            )

    def test_rejects_traversal_via_batch(self, pipeline_cli, tmp_path):
        base = tmp_path / "data" / "raw"
        base.mkdir(parents=True)
        with pytest.raises(ValueError):
            pipeline_cli.resolve_input_dir(
                batch="../../etc", input_path=None, base_dir=base
            )

    def test_requires_batch_or_input(self, pipeline_cli):
        with pytest.raises(ValueError, match="Must specify"):
            pipeline_cli.resolve_input_dir(batch=None, input_path=None)

    def test_accepts_valid_batch(self, pipeline_cli, tmp_path):
        base = tmp_path / "data" / "raw"
        batch_dir = base / "mybatch"
        batch_dir.mkdir(parents=True)
        result = pipeline_cli.resolve_input_dir(
            batch="mybatch", input_path=None, base_dir=base
        )
        assert result.resolve().is_relative_to(base.resolve())


class TestResolveOutputDir:
    """Tests for `resolve_output_dir`."""

    def test_rejects_traversal_in_sam_mode(self, pipeline_cli, tmp_path):
        with pytest.raises(ValueError):
            pipeline_cli.resolve_output_dir(
                mode="sam", batch="../../../etc", output_path=None
            )

    def test_requires_batch_when_no_output(self, pipeline_cli):
        with pytest.raises(ValueError, match="batch name required"):
            pipeline_cli.resolve_output_dir(mode="sam", batch=None, output_path=None)

    def test_unknown_mode_raises(self, pipeline_cli):
        with pytest.raises(ValueError, match="Unknown mode"):
            pipeline_cli.resolve_output_dir(mode="invalid", batch="x", output_path=None)
