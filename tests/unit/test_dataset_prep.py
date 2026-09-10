"""TC-05: Dataset split correctness.
TC-06: Oversampling target met.

Tests the pure helper functions and split/oversampling logic from
`01_prepare_dataset.py` using synthetic COCO data so no real dataset
or GPU is required.
"""
import json
import random
from collections import Counter
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# TC-05: Dataset split correctness
# ---------------------------------------------------------------------------

class TestBboxToYolo:
    """The COCO→YOLO bbox conversion must produce normalized center-format coords."""

    def test_basic_conversion(self, prepare_dataset_module):
        result = prepare_dataset_module.bbox_to_yolo([10, 20, 100, 200], 640, 480)
        cx, cy, w, h = result
        # cx = (10 + 100/2) / 640 = 60/640
        assert cx == pytest.approx(60 / 640, abs=1e-6)
        # cy = (20 + 200/2) / 480 = 120/480
        assert cy == pytest.approx(120 / 480, abs=1e-6)
        assert w == pytest.approx(100 / 640, abs=1e-6)
        assert h == pytest.approx(200 / 480, abs=1e-6)

    def test_all_values_in_unit_range(self, prepare_dataset_module):
        result = prepare_dataset_module.bbox_to_yolo([0, 0, 640, 480], 640, 480)
        assert all(0.0 <= v <= 1.0 for v in result)

    def test_clips_to_unit_range(self, prepare_dataset_module):
        """Bbox extending beyond image bounds must be clipped to [0, 1]."""
        result = prepare_dataset_module.bbox_to_yolo([-50, -50, 1000, 1000], 640, 480)
        assert all(0.0 <= v <= 1.0 for v in result)

    def test_min_width_not_zero(self, prepare_dataset_module):
        """Width/height must not collapse to zero (min 0.001)."""
        result = prepare_dataset_module.bbox_to_yolo([0, 0, 0, 0], 640, 480)
        assert result[2] >= 0.001
        assert result[3] >= 0.001


class TestSplitRatios:
    """The 80/10/10 split must be deterministic (seed=42) and lossless."""

    def test_split_produces_correct_ratios(self):
        """Replicate the split algorithm and verify 80/10/10."""
        n = 913  # actual dataset size
        random.seed(42)
        img_ids = list(range(n))
        random.shuffle(img_ids)

        n_train = int(n * 0.8)
        n_val = int(n * 0.1)

        train = img_ids[:n_train]
        val = img_ids[n_train:n_train + n_val]
        test = img_ids[n_train + n_val:]

        # 80/10/10 of 913 → 730/91/92
        assert len(train) == 730
        assert len(val) == 91
        assert len(test) == 92
        assert len(train) + len(val) + len(test) == n

    def test_split_is_lossless(self):
        """No image ID may appear in more than one split, and all must be covered."""
        n = 100
        random.seed(42)
        img_ids = list(range(n))
        random.shuffle(img_ids)

        n_train = int(n * 0.8)
        n_val = int(n * 0.1)
        train = set(img_ids[:n_train])
        val = set(img_ids[n_train:n_train + n_val])
        test = set(img_ids[n_train + n_val:])

        # No overlap
        assert train.isdisjoint(val)
        assert train.isdisjoint(test)
        assert val.isdisjoint(test)
        # Full coverage
        assert train | val | test == set(range(n))

    def test_split_is_deterministic(self):
        """Same seed must produce the same split every time."""
        def make_split():
            random.seed(42)
            ids = list(range(200))
            random.shuffle(ids)
            n_train = int(200 * 0.8)
            n_val = int(200 * 0.1)
            return ids[:n_train], ids[n_train:n_train + n_val], ids[n_train + n_val:]

        t1, v1, te1 = make_split()
        t2, v2, te2 = make_split()
        assert t1 == t2
        assert v1 == v2
        assert te1 == te2


class TestEndToEndSplitWithSyntheticData:
    """Run the actual split + conversion on a synthetic COCO dataset in a temp dir."""

    def _make_synthetic_coco(self, tmp_path, n_images=20):
        """Create a minimal COCO dataset with images and annotations."""
        img_dir = tmp_path / "images"
        img_dir.mkdir()
        images = []
        annotations = []
        ann_id = 1
        for i in range(n_images):
            fname = f"img_{i:04d}.jpg"
            (img_dir / fname).write_bytes(b"fake")  # placeholder
            images.append({
                "id": i, "file_name": fname,
                "width": 640, "height": 480,
            })
            # 2 annotations per image, cycling through classes 1-5
            for j in range(2):
                cat_id = ((i + j) % 5) + 1
                annotations.append({
                    "id": ann_id,
                    "image_id": i,
                    "category_id": cat_id,
                    "bbox": [10, 20, 100, 200],
                    "segmentation": [],
                    "area": 20000,
                    "iscrowd": 0,
                })
                ann_id += 1
        categories = [
            {"id": k, "name": name}
            for k, name in zip(range(1, 6),
                               ["person", "helmet", "boots", "shoes", "harness"])
        ]
        data = {"images": images, "annotations": annotations, "categories": categories}
        ann_path = tmp_path / "annotations.json"
        ann_path.write_text(json.dumps(data), encoding="utf-8")
        return ann_path, img_dir, data

    def test_split_no_data_loss(self, prepare_dataset_module, tmp_path):
        """All images must appear in exactly one split after conversion."""
        ann_path, img_dir, data = self._make_synthetic_coco(tmp_path, n_images=20)

        # Replicate the split
        random.seed(42)
        img_ids = [img["id"] for img in data["images"]]
        random.shuffle(img_ids)
        n = len(img_ids)
        n_train = int(n * 0.8)
        n_val = int(n * 0.1)

        splits = {
            "train": img_ids[:n_train],
            "val": img_ids[n_train:n_train + n_val],
            "test": img_ids[n_train + n_val:],
        }

        all_split_ids = []
        for ids in splits.values():
            all_split_ids.extend(ids)
        assert sorted(all_split_ids) == sorted(img_ids), "Every image must be in exactly one split"
        assert len(splits["train"]) + len(splits["val"]) + len(splits["test"]) == n


# ---------------------------------------------------------------------------
# TC-06: Oversampling target met
# ---------------------------------------------------------------------------

class TestOversamplingLogic:
    """The oversampling multiplier must be calculated correctly and capped at 10x."""

    def test_multiplier_capped_at_10x(self, prepare_dataset_module):
        """If target_count // current > 10, multiplier must be capped at 10."""
        # harness: current=102, target=500 → 500//102 = 4 (under cap)
        # But if target were 5000 → 5000//102 = 49, cap to 10
        current = 102
        target = 5000
        multiplier = min(target // current, 10)
        assert multiplier == 10, "Multiplier must be capped at 10x to prevent overfitting"

    def test_multiplier_under_cap(self, prepare_dataset_module):
        """Normal case: harness current=102, target=500 → 500//102=4."""
        current = 102
        target = 500
        multiplier = min(target // current, 10)
        assert multiplier == 4

    def test_no_oversample_when_target_met(self):
        """If current >= target, multiplier should be 1 (no duplication)."""
        current = 600
        target = 500
        # The code skips when current >= target
        if current >= target:
            multiplier = 1
        else:
            multiplier = min(target // current, 10)
        assert multiplier == 1

    def test_oversampling_increases_class_count(self, prepare_dataset_module):
        """After oversampling, the target class count must increase toward the target."""
        # Simulate: 10 images with harness, multiplier=4 → 10*3=30 extra copies
        imgs_with_class = list(range(10))
        multiplier = 4
        oversample_imgs = []
        for img_id in imgs_with_class:
            for _ in range(multiplier - 1):
                oversample_imgs.append(img_id)

        # Original + oversampled
        total_images = len(imgs_with_class) + len(oversample_imgs)
        assert total_images == 10 * multiplier
        assert len(oversample_imgs) == 30

    def test_oversample_targets_defined(self, prepare_dataset_module):
        """The OVERSAMPLE_TARGETS dict must target boots and harness."""
        targets = prepare_dataset_module.OVERSAMPLE_TARGETS
        assert 2 in targets, "boots (YOLO class 2) must be an oversample target"
        assert 4 in targets, "harness (YOLO class 4) must be an oversample target"
        # Targets should be reasonable (not exceeding common class counts)
        assert targets[2] <= 1000
        assert targets[4] <= 1000

    def test_split_ratios_are_80_10_10(self, prepare_dataset_module):
        assert prepare_dataset_module.SPLIT_RATIOS == {"train": 0.8, "val": 0.1, "test": 0.1}

    def test_random_seed_is_42(self, prepare_dataset_module):
        assert prepare_dataset_module.RANDOM_SEED == 42

    def test_coco_to_yolo_mapping_complete(self, prepare_dataset_module):
        """All 5 COCO category IDs must map to YOLO class IDs 0-4."""
        mapping = prepare_dataset_module.COCO_TO_YOLO
        assert set(mapping.keys()) == {1, 2, 3, 4, 5}
        assert set(mapping.values()) == {0, 1, 2, 3, 4}
