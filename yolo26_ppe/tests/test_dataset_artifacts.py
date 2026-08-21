"""Artifact integrity tests for the generated YOLO datasets.

These tests inspect the on-disk output of 01_prepare_data.py
(yolo26_ppe/data/yolo_detect + yolo_segment). They catch the C1 split
leakage on real artifacts, broken image/label pairing, and malformed labels.

Run AFTER `01_prepare_data.py` has been (re)generated with the fixed splitter.
"""
import json
import os
import re

import pytest
import yaml

PPE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASETS = ["yolo_detect", "yolo_segment"]
SPLITS = ["train", "val", "test"]
EXPECTED_CLASSES = ["person", "helmet", "boots", "shoes", "sandals", "harness"]

# Oversampled copies exist only in train and are named `<name>_os<idx>.jpg`
_OS_SUFFIX = re.compile(r"_os\d+$")


def _dataset_dir(name):
    return os.path.join(PPE_DIR, "data", name)


def _image_stems(dataset, split):
    img_dir = os.path.join(_dataset_dir(dataset), "images", split)
    return {os.path.splitext(f)[0] for f in os.listdir(img_dir)}


def _base_stems(stems):
    """Strip oversample suffix so copies map back to their source image."""
    return {_OS_SUFFIX.sub("", s) for s in stems}


pytestmark = [
    pytest.mark.skipif(
        not all(os.path.isdir(_dataset_dir(d)) for d in DATASETS),
        reason="dataset not generated yet — run 01_prepare_data.py first",
    )
]


class TestSplitLeakage:
    """Regression guard for CODE_REVIEW C1: no source image may appear in
    more than one split. Oversampled `_os*` copies are train-only and are
    reduced to their base name before comparison."""

    @pytest.mark.parametrize("dataset", DATASETS)
    @pytest.mark.parametrize("split_a,split_b", [("train", "val"), ("train", "test"), ("val", "test")])
    def test_no_overlap_between_splits(self, dataset, split_a, split_b):
        a = _base_stems(_image_stems(dataset, split_a))
        b = _base_stems(_image_stems(dataset, split_b))
        overlap = a & b
        assert not overlap, (
            f"{dataset}: {len(overlap)} image(s) leaked into both {split_a} and {split_b}, "
            f"e.g. {sorted(overlap)[:5]}. Regenerate data with the fixed 01_prepare_data.py."
        )

    @pytest.mark.parametrize("dataset", DATASETS)
    def test_oversample_copies_only_in_train(self, dataset):
        for split in ["val", "test"]:
            stems = _image_stems(dataset, split)
            leaked_copies = {s for s in stems if _OS_SUFFIX.search(s)}
            assert not leaked_copies, f"{dataset}/{split} has oversampled copies: {sorted(leaked_copies)[:5]}"


class TestImageLabelPairing:
    @pytest.mark.parametrize("dataset", DATASETS)
    @pytest.mark.parametrize("split", SPLITS)
    def test_every_image_has_exactly_one_label(self, dataset, split):
        img_stems = _image_stems(dataset, split)
        label_dir = os.path.join(_dataset_dir(dataset), "labels", split)
        label_stems = {os.path.splitext(f)[0] for f in os.listdir(label_dir)}
        missing_labels = img_stems - label_stems
        orphan_labels = label_stems - img_stems
        assert not missing_labels, f"{dataset}/{split}: images without labels: {sorted(missing_labels)[:5]}"
        assert not orphan_labels, f"{dataset}/{split}: labels without images: {sorted(orphan_labels)[:5]}"


class TestLabelFormat:
    @pytest.mark.parametrize("split", SPLITS)
    def test_detect_labels_wellformed(self, split):
        label_dir = os.path.join(_dataset_dir("yolo_detect"), "labels", split)
        for fname in os.listdir(label_dir):
            with open(os.path.join(label_dir, fname)) as f:
                for lineno, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split()
                    assert len(parts) == 5, f"{fname}:{lineno} expected 5 values, got {len(parts)}"
                    cls = int(parts[0])
                    assert 0 <= cls < len(EXPECTED_CLASSES), f"{fname}:{lineno} bad class id {cls}"
                    coords = [float(v) for v in parts[1:]]
                    assert all(0.0 <= v <= 1.0 for v in coords), f"{fname}:{lineno} coords out of [0,1]"

    @pytest.mark.parametrize("split", SPLITS)
    def test_segment_labels_wellformed(self, split):
        label_dir = os.path.join(_dataset_dir("yolo_segment"), "labels", split)
        for fname in os.listdir(label_dir):
            with open(os.path.join(label_dir, fname)) as f:
                for lineno, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split()
                    # class + at least 3 (x, y) points
                    assert len(parts) >= 7 and len(parts) % 2 == 1, (
                        f"{fname}:{lineno} malformed polygon ({len(parts)} tokens)"
                    )
                    cls = int(parts[0])
                    assert 0 <= cls < len(EXPECTED_CLASSES), f"{fname}:{lineno} bad class id {cls}"
                    coords = [float(v) for v in parts[1:]]
                    assert all(0.0 <= v <= 1.0 for v in coords), f"{fname}:{lineno} coords out of [0,1]"


class TestConfigFiles:
    @pytest.mark.parametrize("dataset", DATASETS)
    def test_data_yaml_valid(self, dataset):
        with open(os.path.join(_dataset_dir(dataset), "data.yaml")) as f:
            cfg = yaml.safe_load(f)
        assert cfg["nc"] == len(EXPECTED_CLASSES)
        assert list(cfg["names"]) == EXPECTED_CLASSES
        for key in ["train", "val", "test"]:
            assert key in cfg

    def test_analysis_json_has_required_keys(self):
        path = os.path.join(PPE_DIR, "data", "analysis", "data_analysis.json")
        with open(path) as f:
            analysis = json.load(f)
        for key in ["total_images", "splits", "before_balance",
                    "after_balance_detect", "class_names", "oversample_log"]:
            assert key in analysis, f"data_analysis.json missing key: {key}"
        assert analysis["class_names"] == EXPECTED_CLASSES
        assert set(analysis["splits"]) == set(SPLITS)
