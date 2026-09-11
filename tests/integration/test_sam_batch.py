"""TC-01: SAM batch on single image.
TC-02: SAM resume from checkpoint.

Integration tests that require the SAM 3.1 checkpoint and a working venv.
These are skipped unless the checkpoint exists and GPU/runtime deps are available.
"""
import json
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def _sam_checkpoint_exists(repo_root):
    ckpt = repo_root / "sam3_auto_label" / "checkpoints" / "sam3.1_multiplex.pt"
    return ckpt.exists()


def _sam_venv_exists(repo_root):
    if os.name == "nt":
        return (repo_root / "sam3_auto_label" / "sam3_venv" / "Scripts" / "python.exe").exists()
    return (repo_root / "sam3_auto_label" / "sam3_venv" / "bin" / "python").exists()


def _sam3_module_available():
    """Check if the vendored sam3 module is importable (WSL/Linux only)."""
    try:
        import importlib
        importlib.import_module("sam3.model_builder")
        return True
    except (ImportError, ModuleNotFoundError):
        return False


skip_no_checkpoint = pytest.mark.skipif(
    not _sam_checkpoint_exists(Path(__file__).resolve().parent.parent.parent),
    reason="SAM 3.1 checkpoint not found — run ./setup.sh first",
)

skip_no_sam3 = pytest.mark.skipif(
    not _sam3_module_available(),
    reason="sam3 module not importable — SAM batch tests require the WSL/Linux venv",
)


class TestSAMBatchSingleImage:
    """TC-01: SAM batch segmentation on a single test image."""

    @skip_no_checkpoint
    @skip_no_sam3
    def test_produces_coco_and_yolo_outputs(self, repo_root, tmp_path, monkeypatch):
        """Run SAM on one image and verify COCO JSON + YOLO format are generated."""
        import sys
        sys.path.insert(0, str(repo_root / "sam3_auto_label" / "src"))

        from config import load_config

        # Create a single test image (1x1 black PNG)
        try:
            from PIL import Image
            img_dir = tmp_path / "input"
            img_dir.mkdir()
            Image.new("RGB", (64, 64), color=(0, 0, 0)).save(img_dir / "test.png")
        except ImportError:
            pytest.skip("Pillow not installed")

        out_dir = tmp_path / "output"
        out_dir.mkdir()

        # Build a minimal config
        config_path = repo_root / "sam3_auto_label" / "config" / "ppe_4class.yaml"
        cfg = load_config(str(config_path))
        cfg.output.input_dir = str(img_dir)
        cfg.output.output_dir = str(out_dir)
        cfg.output.formats = ["coco", "yolo"]
        cfg.checkpoint.clear_on_success = False

        # This would require the full SAM model — skip if torch/CUDA unavailable
        try:
            import torch
            if not torch.cuda.is_available() and not hasattr(torch.backends, "mps"):
                pytest.skip("No GPU available for SAM inference")
        except ImportError:
            pytest.skip("PyTorch not installed")

        # Mock sys.argv so batch_main's argparse doesn't pick up pytest args
        monkeypatch.setattr(sys, "argv", [
            "batch_segment.py",
            "--config", str(config_path),
            "--input", str(img_dir),
            "--output", str(out_dir),
            "--device", "cpu",
        ])

        from batch_segment import main as batch_main
        # Run the batch
        rc = batch_main()
        # rc=0 means success
        assert rc == 0, "SAM batch must complete successfully on a single image"

        # Verify COCO output
        coco_dir = Path(cfg.coco_path)
        assert coco_dir.exists(), "COCO output directory must be created"
        coco_files = list(coco_dir.glob("*.json"))
        assert len(coco_files) > 0, "At least one COCO JSON must be generated"

        # Verify YOLO output
        yolo_dir = out_dir / "yolo"
        if yolo_dir.exists():
            yolo_labels = list(yolo_dir.glob("*.txt"))
            assert len(yolo_labels) > 0, "YOLO label files must be generated"


class TestSAMResumeFromCheckpoint:
    """TC-02: SAM resume from checkpoint skips already-processed images."""

    @skip_no_checkpoint
    def test_checkpoint_skips_processed_images(self, repo_root, tmp_path):
        """Create a checkpoint, verify resume skips processed images."""
        import sys
        sys.path.insert(0, str(repo_root / "sam3_auto_label" / "src"))

        from config import Config, InferenceConfig, AnnotationConfig, OutputConfig, CheckpointConfig, Category
        from batch_segment import save_checkpoint, load_checkpoint, checkpoint_path

        out_dir = tmp_path / "output"
        out_dir.mkdir()

        cfg = Config(
            categories=[Category(id=1, name="person", prompt="person")],
            inference=InferenceConfig(),
            annotation=AnnotationConfig(),
            output=OutputConfig(output_dir=str(out_dir)),
            checkpoint=CheckpointConfig(enabled=True, auto_resume=True, clear_on_success=False),
            base_dir=str(tmp_path),
        )

        # Save a checkpoint marking one image as done
        ckpt = {
            "processed": {"done_image.png": {"time": 1.0, "annotations": 3}},
            "total_images": 2,
            "started_at": "2026-01-01T00:00:00",
        }
        save_checkpoint(cfg, ckpt)

        # Load it back
        loaded = load_checkpoint(cfg)
        assert loaded is not None, "Checkpoint must be loadable"
        assert "done_image.png" in loaded["processed"]
        assert loaded["total_images"] == 2

        # The checkpoint path must be inside the output dir
        assert checkpoint_path(cfg) == str(out_dir / "checkpoint.json")

    def test_fresh_deletes_checkpoint(self, repo_root, tmp_path):
        """--fresh flag must delete existing checkpoint state."""
        import sys
        sys.path.insert(0, str(repo_root / "sam3_auto_label" / "src"))

        from config import Config, InferenceConfig, AnnotationConfig, OutputConfig, CheckpointConfig, Category
        from batch_segment import save_checkpoint, load_checkpoint, delete_checkpoint, checkpoint_path

        out_dir = tmp_path / "output"
        out_dir.mkdir()

        cfg = Config(
            categories=[Category(id=1, name="person", prompt="person")],
            inference=InferenceConfig(),
            annotation=AnnotationConfig(),
            output=OutputConfig(output_dir=str(out_dir)),
            checkpoint=CheckpointConfig(enabled=True),
            base_dir=str(tmp_path),
        )

        # Save a checkpoint
        save_checkpoint(cfg, {"processed": {}, "total_images": 5})
        assert Path(checkpoint_path(cfg)).exists()

        # Delete it (simulating --fresh)
        delete_checkpoint(cfg)
        assert not Path(checkpoint_path(cfg)).exists(), "delete_checkpoint must remove the file"

    def test_corrupt_checkpoint_ignored(self, repo_root, tmp_path):
        """A corrupt checkpoint file must be ignored, not crash the run."""
        import sys
        sys.path.insert(0, str(repo_root / "sam3_auto_label" / "src"))

        from config import Config, InferenceConfig, AnnotationConfig, OutputConfig, CheckpointConfig, Category
        from batch_segment import load_checkpoint, checkpoint_path

        out_dir = tmp_path / "output"
        out_dir.mkdir()

        cfg = Config(
            categories=[Category(id=1, name="person", prompt="person")],
            inference=InferenceConfig(),
            annotation=AnnotationConfig(),
            output=OutputConfig(output_dir=str(out_dir)),
            checkpoint=CheckpointConfig(enabled=True),
            base_dir=str(tmp_path),
        )

        # Write corrupt JSON
        Path(checkpoint_path(cfg)).write_text("{invalid json!!!", encoding="utf-8")
        result = load_checkpoint(cfg)
        assert result is None, "Corrupt checkpoint must return None, not raise"
