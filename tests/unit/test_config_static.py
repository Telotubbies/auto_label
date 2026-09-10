"""TC-09: MLflow localhost only.
TC-12: Checkpoint location match.

Static checks on configuration files and source-code path constants.
No code execution of the pipeline is required.
"""
import os

import pytest
import yaml

pytestmark = pytest.mark.static


class TestMLflowLocalhost:
    """TC-09: MLflow must bind to 127.0.0.1, not 0.0.0.0 (ISO 27001 A.13.1.1)."""

    MLFLOW_CONFIG = "yolo26_ppe/configs/mlflow.yaml"

    def _load_mlflow_config(self, repo_root):
        config_path = repo_root / self.MLFLOW_CONFIG
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_host_is_localhost(self, repo_root):
        cfg = self._load_mlflow_config(repo_root)
        assert cfg["host"] == "127.0.0.1", (
            f"MLflow host must be 127.0.0.1, got {cfg['host']!r} — "
            "binding to 0.0.0.0 exposes the tracking server to the network"
        )

    def test_host_not_wildcard(self, repo_root):
        cfg = self._load_mlflow_config(repo_root)
        assert cfg["host"] != "0.0.0.0", "MLflow must not bind to 0.0.0.0"

    def test_port_is_int(self, repo_root):
        cfg = self._load_mlflow_config(repo_root)
        assert isinstance(cfg["port"], int)
        assert 1 <= cfg["port"] <= 65535


class TestCheckpointLocationMatch:
    """TC-12: setup.py and pipeline_cli.py must agree on the checkpoint path.

    Both must reference `checkpoints/sam3.1_multiplex.pt` relative to the
    sam3_auto_label directory.
    """

    EXPECTED_CKPT_NAME = "sam3.1_multiplex.pt"
    EXPECTED_CKPT_DIR = "checkpoints"

    def test_setup_py_uses_correct_path(self, repo_root):
        setup_path = repo_root / "sam3_auto_label" / "setup.py"
        content = setup_path.read_text(encoding="utf-8")
        assert self.EXPECTED_CKPT_NAME in content, (
            f"setup.py must reference {self.EXPECTED_CKPT_NAME}"
        )
        assert "CKPT_PATH" in content, "setup.py must define CKPT_PATH"
        assert self.EXPECTED_CKPT_DIR in content

    def test_pipeline_cli_uses_correct_path(self, repo_root):
        cli_path = repo_root / "pipeline_cli.py"
        content = cli_path.read_text(encoding="utf-8")
        assert self.EXPECTED_CKPT_NAME in content, (
            f"pipeline_cli.py must reference {self.EXPECTED_CKPT_NAME}"
        )
        assert self.EXPECTED_CKPT_DIR in content

    def test_check_sam_checkpoint_function_matches(self, pipeline_cli):
        """The runtime check function must point to the same checkpoint file."""
        ckpt = pipeline_cli.SAM_DIR / "checkpoints" / "sam3.1_multiplex.pt"
        exists, path = pipeline_cli.check_sam_checkpoint()
        assert "sam3.1_multiplex.pt" in path
        assert "checkpoints" in path

    def test_config_ckpt_path_property_matches(self, config_module):
        """The Config.ckpt_path property must produce the same relative path."""
        cfg = config_module.Config(base_dir="/fake/base")
        expected = os.path.join("/fake/base", "checkpoints", "sam3.1_multiplex.pt")
        assert cfg.ckpt_path == expected
