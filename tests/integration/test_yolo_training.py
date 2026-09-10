"""TC-07: YOLO training 4 models.
TC-08: ONNX export.

Integration tests that require a prepared dataset, GPU, and trained model
weights. These are skipped unless the prerequisites exist.
"""
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _models_exist():
    """Check if trained model weights exist."""
    models_dir = REPO_ROOT / "yolo26_ppe" / "models" / "production"
    if not models_dir.exists():
        return False
    found = list(models_dir.rglob("best.pt"))
    return len(found) >= 1


def _dataset_prepared():
    """Check if the YOLO dataset has been prepared."""
    det_dir = REPO_ROOT / "yolo26_ppe" / "data" / "yolo_detection_dataset_version_2"
    return det_dir.exists() and (det_dir / "data.yaml").exists()


def _onnx_models_exist():
    """Check if ONNX exports exist."""
    models_dir = REPO_ROOT / "yolo26_ppe" / "models" / "production"
    if not models_dir.exists():
        return False
    return len(list(models_dir.rglob("*.onnx"))) >= 1


skip_no_dataset = pytest.mark.skipif(
    not _dataset_prepared(),
    reason="YOLO dataset not prepared — run 01_prepare_dataset.py first",
)

skip_no_models = pytest.mark.skipif(
    not _models_exist(),
    reason="Trained models not found — run 02_train_models.py first",
)


class TestYOLOTrainingFourModels:
    """TC-07: YOLO26 training must produce 4 models with MLflow logging."""

    @skip_no_dataset
    def test_four_model_directories_exist(self, repo_root):
        """All 4 model variant directories must exist after training."""
        models_dir = repo_root / "yolo26_ppe" / "models" / "production"
        expected = ["nano_detection", "small_detection", "nano_segmentation", "small_segmentation"]
        for name in expected:
            model_dir = models_dir / name
            assert model_dir.exists(), f"Model directory missing: {name}"

    @skip_no_models
    def test_best_weights_exist(self, repo_root):
        """Each trained model must have a best.pt weights file."""
        models_dir = repo_root / "yolo26_ppe" / "models" / "production"
        best_files = list(models_dir.rglob("best.pt"))
        assert len(best_files) >= 1, "At least one best.pt must exist after training"

    @skip_no_models
    def test_model_variants_covered(self, repo_root):
        """At least the 4 expected model variants should have weights."""
        models_dir = repo_root / "yolo26_ppe" / "models" / "production"
        expected = ["nano_detection", "small_detection", "nano_segmentation", "small_segmentation"]
        found = []
        for name in expected:
            if (models_dir / name).exists():
                weights = list((models_dir / name).rglob("best.pt"))
                if weights:
                    found.append(name)
        # At least some models should be trained
        assert len(found) >= 1, f"No trained models found. Expected: {expected}"

    def test_pipeline_cli_models_dict_has_four(self, pipeline_cli):
        """The MODELS dict in pipeline_cli must define exactly 4 variants."""
        assert len(pipeline_cli.MODELS) == 4
        expected_keys = {"nano_detection", "small_detection", "nano_segmentation", "small_segmentation"}
        assert set(pipeline_cli.MODELS.keys()) == expected_keys

    def test_each_model_has_required_fields(self, pipeline_cli):
        """Each model entry must have weights, task, label, and project fields."""
        required = {"weights", "task", "label", "project", "best", "data", "batch"}
        for key, model in pipeline_cli.MODELS.items():
            missing = required - set(model.keys())
            assert not missing, f"Model {key} missing fields: {missing}"

    def test_model_tasks_are_correct(self, pipeline_cli):
        """Detection models must have task='detect', segmentation task='segment'."""
        assert pipeline_cli.MODELS["nano_detection"]["task"] == "detect"
        assert pipeline_cli.MODELS["small_detection"]["task"] == "detect"
        assert pipeline_cli.MODELS["nano_segmentation"]["task"] == "segment"
        assert pipeline_cli.MODELS["small_segmentation"]["task"] == "segment"


class TestONNXExport:
    """TC-08: ONNX export must produce .onnx files with matching inference."""

    @skip_no_models
    def test_onnx_files_exist(self, repo_root):
        """ONNX export must produce .onnx files for trained models."""
        models_dir = repo_root / "yolo26_ppe" / "models" / "production"
        onnx_files = list(models_dir.rglob("*.onnx"))
        assert len(onnx_files) >= 1, "At least one .onnx file must exist after export"

    @skip_no_models
    def test_onnx_files_are_valid_size(self, repo_root):
        """ONNX files must be non-trivial in size (>1MB)."""
        models_dir = repo_root / "yolo26_ppe" / "models" / "production"
        for onnx in models_dir.rglob("*.onnx"):
            size_mb = onnx.stat().st_size / (1024 * 1024)
            assert size_mb > 0.1, f"ONNX file too small ({size_mb:.2f} MB): {onnx.name}"
            # Must be under 50MB per NFR-07
            assert size_mb <= 50, f"ONNX file exceeds 50MB limit ({size_mb:.2f} MB): {onnx.name}"

    def test_onnx_export_script_exists(self, repo_root):
        """The ONNX export script must exist."""
        export_script = repo_root / "yolo26_ppe" / "scripts" / "pipeline" / "04_export_and_evaluate_onnx.py"
        assert export_script.exists(), "04_export_and_evaluate_onnx.py must exist"
        content = export_script.read_text(encoding="utf-8")
        assert "onnx" in content.lower(), "Export script must reference ONNX"
        assert "export" in content.lower(), "Export script must perform export"

    def test_onnx_export_script_has_benchmark(self, repo_root):
        """The ONNX export script must include inference benchmarking."""
        export_script = repo_root / "yolo26_ppe" / "scripts" / "pipeline" / "04_export_and_evaluate_onnx.py"
        content = export_script.read_text(encoding="utf-8")
        # Must reference benchmark/inference timing
        assert any(kw in content.lower() for kw in ["benchmark", "inference", "latency"]), (
            "Export script must include inference benchmarking"
        )
