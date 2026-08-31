"""Tests for 01_prepare_dataset.py — dataset preparation logic.

Covers:
  - v1 fallback when v2 images are missing
  - sandals → shoes merge (6 → 5 classes)
  - Flatten file_name (remove subdirectory prefix)
  - Split ratios (80/10/10)
  - Oversampling for rare classes (harness)
  - COCO → YOLO conversion (bbox, polygon)
  - data.yaml generation
  - Error handling for missing annotations
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PREPARE_SCRIPT = Path(__file__).resolve().parent.parent / "yolo26_ppe" / "scripts" / "pipeline" / "01_prepare_dataset.py"


@pytest.fixture(scope="session")
def prepare_module():
    """Load 01_prepare_dataset.py as a module."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("prepare_dataset", str(PREPARE_SCRIPT))
    module = importlib.util.module_from_spec(spec)
    sys.modules["prepare_dataset"] = module
    spec.loader.exec_module(module)
    return module


# =============================================================================
# Config Constants
# =============================================================================

class TestPrepareConfig:
    """Tests for configuration constants."""

    def test_class_names_has_five_classes(self, prepare_module):
        assert len(prepare_module.CLASS_NAMES) == 5

    def test_class_names_order(self, prepare_module):
        assert prepare_module.CLASS_NAMES == ["person", "helmet", "boots", "shoes", "harness"]

    def test_coco_to_yolo_v2_mapping(self, prepare_module):
        """v2: 1=person, 2=helmet, 3=boots, 4=shoes, 5=harness."""
        assert prepare_module.COCO_TO_YOLO == {1: 0, 2: 1, 3: 2, 4: 3, 5: 4}

    def test_coco_to_yolo_v1_mapping_merges_sandals(self, prepare_module):
        """v1: sandals (5) → shoes (YOLO 3), harness (6) → harness (YOLO 4)."""
        m = prepare_module.COCO_TO_YOLO_V1
        assert m[5] == 3  # sandals → shoes
        assert m[6] == 4  # harness → harness
        assert m[4] == 3  # shoes → shoes

    def test_split_ratios_sum_to_one(self, prepare_module):
        total = sum(prepare_module.SPLIT_RATIOS.values())
        assert abs(total - 1.0) < 0.01

    def test_split_ratios_are_80_10_10(self, prepare_module):
        assert prepare_module.SPLIT_RATIOS["train"] == 0.8
        assert prepare_module.SPLIT_RATIOS["val"] == 0.1
        assert prepare_module.SPLIT_RATIOS["test"] == 0.1

    def test_random_seed_is_set(self, prepare_module):
        assert prepare_module.RANDOM_SEED == 42

    def test_oversample_targets_harness(self, prepare_module):
        assert 4 in prepare_module.OVERSAMPLE_TARGETS  # harness = YOLO class 4


# =============================================================================
# bbox_to_yolo Conversion
# =============================================================================

class TestBboxToYolo:
    """Tests for bbox_to_yolo()."""

    def test_basic_conversion(self, prepare_module):
        # COCO [x, y, w, h] → YOLO [cx, cy, w, h] normalized
        result = prepare_module.bbox_to_yolo([100, 100, 50, 50], 200, 200)
        # cx = (100 + 25) / 200 = 0.625
        # cy = (100 + 25) / 200 = 0.625
        # w = 50 / 200 = 0.25
        # h = 50 / 200 = 0.25
        assert abs(result[0] - 0.625) < 0.001
        assert abs(result[1] - 0.625) < 0.001
        assert abs(result[2] - 0.25) < 0.001
        assert abs(result[3] - 0.25) < 0.001

    def test_zero_origin(self, prepare_module):
        result = prepare_module.bbox_to_yolo([0, 0, 100, 100], 200, 200)
        assert abs(result[0] - 0.25) < 0.001
        assert abs(result[1] - 0.25) < 0.001

    def test_full_image(self, prepare_module):
        result = prepare_module.bbox_to_yolo([0, 0, 200, 200], 200, 200)
        assert abs(result[0] - 0.5) < 0.001
        assert abs(result[1] - 0.5) < 0.001
        assert abs(result[2] - 1.0) < 0.001
        assert abs(result[3] - 1.0) < 0.001

    def test_clipping(self, prepare_module):
        """Values should be clipped to [0, 1]."""
        result = prepare_module.bbox_to_yolo([-50, -50, 300, 300], 200, 200)
        assert 0 <= result[0] <= 1
        assert 0 <= result[1] <= 1
        assert 0 <= result[2] <= 1
        assert 0 <= result[3] <= 1

    def test_min_width_not_zero(self, prepare_module):
        """Width should not be zero even for tiny boxes."""
        result = prepare_module.bbox_to_yolo([100, 100, 0.001, 0.001], 200, 200)
        assert result[2] >= 0.001


# =============================================================================
# mask_to_polygons
# =============================================================================

class TestMaskToPolygons:
    """Tests for mask_to_polygons()."""

    def test_polygon_format_passthrough(self, prepare_module):
        """Already-polygon segmentation should be normalized and returned."""
        seg = [[10, 20, 30, 40, 50, 60]]  # 3 points
        result = prepare_module.mask_to_polygons(seg, 100, 100)
        assert len(result) == 1
        # Check normalization
        poly = result[0]
        assert all(0 <= v <= 1 for v in poly)

    def test_too_few_points_skipped(self, prepare_module):
        """Polygons with < 3 points (6 coords) should be skipped."""
        seg = [[10, 20, 30, 40]]  # 2 points = 4 coords
        result = prepare_module.mask_to_polygons(seg, 100, 100)
        assert result == []

    def test_none_segmentation_returns_none(self, prepare_module):
        result = prepare_module.mask_to_polygons(None, 100, 100)
        assert result is None

    def test_empty_list_returns_empty(self, prepare_module):
        result = prepare_module.mask_to_polygons([], 100, 100)
        assert result == []


# =============================================================================
# v1 Fallback Logic
# =============================================================================

class TestV1Fallback:
    """Tests for v1 fallback when v2 images are missing."""

    def test_v1_paths_exist(self, prepare_module):
        """v1 fallback paths should be defined."""
        assert hasattr(prepare_module, "V1_DIR")
        assert hasattr(prepare_module, "V1_ANN_PATH")
        assert hasattr(prepare_module, "V1_IMG_DIR")

    def test_v1_coco_mapping_has_six_entries(self, prepare_module):
        """v1 has 6 COCO categories (including sandals)."""
        assert len(prepare_module.COCO_TO_YOLO_V1) == 6

    def test_v1_sandals_maps_to_shoes(self, prepare_module):
        """sandals (COCO 5) should map to shoes (YOLO 3)."""
        assert prepare_module.COCO_TO_YOLO_V1[5] == 3

    def test_v1_harness_maps_correctly(self, prepare_module):
        """harness (COCO 6 in v1) should map to harness (YOLO 4)."""
        assert prepare_module.COCO_TO_YOLO_V1[6] == 4


# =============================================================================
# Output Directory Structure
# =============================================================================

class TestOutputDirectories:
    """Tests for output directory paths."""

    def test_det_dir_path(self, prepare_module):
        assert "yolo_detection_dataset_version_2" in str(prepare_module.DET_DIR)

    def test_seg_dir_path(self, prepare_module):
        assert "yolo_segmentation_dataset_version_2" in str(prepare_module.SEG_DIR)

    def test_det_and_seg_are_different(self, prepare_module):
        assert prepare_module.DET_DIR != prepare_module.SEG_DIR


# =============================================================================
# Integration — Full Prepare Run (with temp data)
# =============================================================================

class TestPrepareIntegration:
    """Integration tests with temporary COCO data."""

    @pytest.fixture
    def tmp_coco_dataset(self, tmp_path):
        """Create a minimal COCO dataset with real images."""
        img_dir = tmp_path / "images" / "batch1"
        img_dir.mkdir(parents=True)
        # Create 10 fake images
        for i in range(10):
            (img_dir / f"img_{i:04d}.jpg").write_bytes(b"fake_jpg")

        annotations = {
            "info": {"description": "test"},
            "licenses": [{"id": 1, "name": "test", "url": ""}],
            "categories": [
                {"id": 1, "name": "person"},
                {"id": 2, "name": "helmet"},
                {"id": 3, "name": "boots"},
                {"id": 4, "name": "shoes"},
                {"id": 5, "name": "harness"},
            ],
            "images": [
                {"id": i, "file_name": f"batch1/img_{i:04d}.jpg", "width": 640, "height": 480}
                for i in range(10)
            ],
            "annotations": [
                {"id": i, "image_id": i, "category_id": 1,
                 "bbox": [10, 10, 100, 100], "area": 10000, "iscrowd": 0,
                 "segmentation": [[10, 10, 110, 10, 110, 110, 10, 110]]}
                for i in range(10)
            ],
        }
        ann_path = tmp_path / "annotations.json"
        ann_path.write_text(json.dumps(annotations))
        return tmp_path, ann_path, img_dir

    def test_prepare_creates_split_directories(self, prepare_module, tmp_coco_dataset, tmp_path):
        """Prepare should create train/val/test directories."""
        tmp_data, ann_path, img_dir = tmp_coco_dataset
        det_out = tmp_path / "det_out"
        seg_out = tmp_path / "seg_out"

        with patch.object(prepare_module, "ANN_PATH", ann_path):
            with patch.object(prepare_module, "IMG_DIR", img_dir.parent):
                with patch.object(prepare_module, "DET_DIR", det_out):
                    with patch.object(prepare_module, "SEG_DIR", seg_out):
                        with patch.object(prepare_module, "COMBINED_DIR", tmp_data):
                            prepare_module.main()

        for split in ["train", "val", "test"]:
            assert (det_out / "images" / split).exists()
            assert (det_out / "labels" / split).exists()
            assert (seg_out / "images" / split).exists()
            assert (seg_out / "labels" / split).exists()

    def test_prepare_generates_data_yaml(self, prepare_module, tmp_coco_dataset, tmp_path):
        """Prepare should generate data.yaml files."""
        tmp_data, ann_path, img_dir = tmp_coco_dataset
        det_out = tmp_path / "det_out"
        seg_out = tmp_path / "seg_out"

        with patch.object(prepare_module, "ANN_PATH", ann_path):
            with patch.object(prepare_module, "IMG_DIR", img_dir.parent):
                with patch.object(prepare_module, "DET_DIR", det_out):
                    with patch.object(prepare_module, "SEG_DIR", seg_out):
                        with patch.object(prepare_module, "COMBINED_DIR", tmp_data):
                            prepare_module.main()

        assert (det_out / "data.yaml").exists()
        assert (seg_out / "data.yaml").exists()

    def test_data_yaml_contains_class_names(self, prepare_module, tmp_coco_dataset, tmp_path):
        """data.yaml should contain the 5 class names."""
        tmp_data, ann_path, img_dir = tmp_coco_dataset
        det_out = tmp_path / "det_out"
        seg_out = tmp_path / "seg_out"

        with patch.object(prepare_module, "ANN_PATH", ann_path):
            with patch.object(prepare_module, "IMG_DIR", img_dir.parent):
                with patch.object(prepare_module, "DET_DIR", det_out):
                    with patch.object(prepare_module, "SEG_DIR", seg_out):
                        with patch.object(prepare_module, "COMBINED_DIR", tmp_data):
                            prepare_module.main()

        yaml_content = (det_out / "data.yaml").read_text()
        assert "person" in yaml_content
        assert "helmet" in yaml_content
        assert "boots" in yaml_content
        assert "shoes" in yaml_content
        assert "harness" in yaml_content

    def test_prepare_creates_yolo_labels(self, prepare_module, tmp_coco_dataset, tmp_path):
        """Prepare should create YOLO format label files."""
        tmp_data, ann_path, img_dir = tmp_coco_dataset
        det_out = tmp_path / "det_out"
        seg_out = tmp_path / "seg_out"

        with patch.object(prepare_module, "ANN_PATH", ann_path):
            with patch.object(prepare_module, "IMG_DIR", img_dir.parent):
                with patch.object(prepare_module, "DET_DIR", det_out):
                    with patch.object(prepare_module, "SEG_DIR", seg_out):
                        with patch.object(prepare_module, "COMBINED_DIR", tmp_data):
                            prepare_module.main()

        # Check at least one label file exists
        train_labels = list((det_out / "labels" / "train").glob("*.txt"))
        assert len(train_labels) > 0

        # Check label format: class cx cy w h
        first_label = train_labels[0].read_text().strip()
        parts = first_label.split()
        assert len(parts) == 5  # class + 4 coords
        assert parts[0] == "0"  # person = class 0

    def test_split_ratios_correct(self, prepare_module, tmp_coco_dataset, tmp_path):
        """With 10 images: train=8, val=1, test=1."""
        tmp_data, ann_path, img_dir = tmp_coco_dataset
        det_out = tmp_path / "det_out"
        seg_out = tmp_path / "seg_out"

        with patch.object(prepare_module, "ANN_PATH", ann_path):
            with patch.object(prepare_module, "IMG_DIR", img_dir.parent):
                with patch.object(prepare_module, "DET_DIR", det_out):
                    with patch.object(prepare_module, "SEG_DIR", seg_out):
                        with patch.object(prepare_module, "COMBINED_DIR", tmp_data):
                            prepare_module.main()

        train_count = len(list((det_out / "images" / "train").glob("*")))
        val_count = len(list((det_out / "images" / "val").glob("*")))
        test_count = len(list((det_out / "images" / "test").glob("*")))
        # 10 images: 80% = 8, 10% = 1, 10% = 1
        assert train_count == 8
        assert val_count == 1
        assert test_count == 1
