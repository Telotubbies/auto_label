"""Unit tests for the split + conversion logic in 01_prepare_data.py.

Regression guard for CODE_REVIEW C1 (data leakage): calling the split
helper once per source must produce pairwise-disjoint train/val/test sets.
"""
import random

import pytest


def _fake_images(prefix, n):
    return [{"id": f"{prefix}_{i}", "file_name": f"{prefix}_{i:04d}.jpg"} for i in range(n)]


def _ids(split_dict):
    return {k: {img["id"] for img in v} for k, v in split_dict.items()}


class TestSplitImgs:
    def test_splits_are_pairwise_disjoint(self, prepare_module):
        """One call must partition the input — no image in two splits."""
        random.seed(42)
        splits = prepare_module.split_imgs(_fake_images("a", 100))
        ids = _ids(splits)
        assert ids["train"].isdisjoint(ids["val"])
        assert ids["train"].isdisjoint(ids["test"])
        assert ids["val"].isdisjoint(ids["test"])

    def test_splits_cover_all_images(self, prepare_module):
        """Union of splits must equal the input set (nothing lost/duplicated)."""
        random.seed(42)
        imgs = _fake_images("a", 100)
        splits = prepare_module.split_imgs(imgs)
        ids = _ids(splits)
        assert ids["train"] | ids["val"] | ids["test"] == {img["id"] for img in imgs}

    def test_split_ratios_approx_70_20_10(self, prepare_module):
        random.seed(42)
        splits = prepare_module.split_imgs(_fake_images("a", 100))
        assert len(splits["train"]) == 70
        assert len(splits["val"]) == 20
        assert len(splits["test"]) == 10

    def test_two_sources_each_split_once_stay_internally_disjoint(self, prepare_module):
        """Mirrors main(): one call per source, shared RNG — each source's
        splits must still be disjoint (the C1 bug pattern)."""
        random.seed(prepare_module.RANDOM_SEED)
        split_a = prepare_module.split_imgs(_fake_images("src2026", 432))
        split_b = prepare_module.split_imgs(_fake_images("srcblur", 48))
        for splits in (split_a, split_b):
            ids = _ids(splits)
            assert ids["train"].isdisjoint(ids["val"])
            assert ids["train"].isdisjoint(ids["test"])
            assert ids["val"].isdisjoint(ids["test"])


class TestBboxToYolo:
    def test_center_and_scale(self, prepare_module):
        # bbox [x, y, w, h] = [100, 50, 200, 100] in a 1000x500 image
        cx, cy, w, h = prepare_module.bbox_to_yolo([100, 50, 200, 100], 1000, 500)
        assert cx == pytest.approx(0.2)
        assert cy == pytest.approx(0.2)
        assert w == pytest.approx(0.2)
        assert h == pytest.approx(0.2)

    def test_full_image_bbox_maps_to_unit(self, prepare_module):
        cx, cy, w, h = prepare_module.bbox_to_yolo([0, 0, 640, 480], 640, 480)
        assert (cx, cy, w, h) == (pytest.approx(0.5), pytest.approx(0.5),
                                  pytest.approx(1.0), pytest.approx(1.0))


class TestBboxToPolygon:
    def test_returns_8_normalized_coords_in_range(self, prepare_module):
        poly = prepare_module.bbox_to_polygon([10, 20, 30, 40], 100, 200)
        assert len(poly) == 8
        assert all(0.0 <= v <= 1.0 for v in poly)

    def test_corner_order_clockwise_from_top_left(self, prepare_module):
        poly = prepare_module.bbox_to_polygon([0, 0, 50, 100], 100, 200)
        assert poly == [0.0, 0.0, 0.5, 0.0, 0.5, 0.5, 0.0, 0.5]


class TestRleToPolygon:
    def test_simple_square_mask(self, prepare_module):
        import numpy as np
        from pycocotools import mask as mask_util

        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:80, 30:70] = 1
        rle = mask_util.encode(np.asfortranarray(mask))
        poly = prepare_module.rle_to_polygon(rle, 100, 100)
        assert poly is not None
        assert len(poly) >= 6  # at least 3 points
        assert len(poly) % 2 == 0
        assert all(0.0 <= v <= 1.0 for v in poly)

    def test_empty_mask_returns_none(self, prepare_module):
        import numpy as np
        from pycocotools import mask as mask_util

        rle = mask_util.encode(np.asfortranarray(np.zeros((50, 50), dtype=np.uint8)))
        assert prepare_module.rle_to_polygon(rle, 50, 50) is None

    def test_none_input_returns_none(self, prepare_module):
        assert prepare_module.rle_to_polygon(None, 100, 100) is None
