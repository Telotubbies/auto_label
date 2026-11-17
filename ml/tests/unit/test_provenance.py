"""TC-13: Provenance fields in experiment tracker.
TC-14: Retry on failure in batch segment.
TC-15: Label validator rejects invalid annotations.
TC-16: min_area filter drops small objects.
TC-17: SHA256 replaces MD5 for config hash.

Tests for the standard-compliance improvements (Group 1 + Group 2).
"""
import json
import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# TC-13: Provenance fields (model_version, prompt_version, annotation_source)
# ---------------------------------------------------------------------------

class TestProvenanceFields:
    """The experiments table must track model_version, prompt_version, and
    annotation_source so old annotations can be traced to their model/prompt."""

    def test_experiments_table_has_model_version_column(self, repo_root, tmp_path):
        """The SQLite schema must include a model_version column."""
        sys.path.insert(0, str(repo_root / "sam3_auto_label" / "src"))
        from config import Config, InferenceConfig, AnnotationConfig, OutputConfig, CheckpointConfig, Category
        from tracker import ExperimentTracker

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
        tracker = ExperimentTracker(cfg)

        import sqlite3
        with sqlite3.connect(tracker.db_path) as conn:
            c = conn.cursor()
            c.execute("PRAGMA table_info(experiments)")
            columns = [row[1] for row in c.fetchall()]
        assert "model_version" in columns, "experiments table must have model_version column"
        assert "prompt_version" in columns, "experiments table must have prompt_version column"

    def test_annotation_dict_has_source_field(self, repo_root):
        """Each annotation dict must include an annotation_source field."""
        sys.path.insert(0, str(repo_root / "sam3_auto_label" / "src"))
        from inference import build_annotation_dict
        ann = build_annotation_dict(
            ann_id=1, image_id=1, category_id=1,
            bbox=[10, 20, 100, 200], area=20000,
            score=0.95, segmentation=None,
            annotation_source="auto",
        )
        assert ann["annotation_source"] == "auto", "annotation must have annotation_source field"

    def test_annotation_dict_defaults_to_auto(self, repo_root):
        """If annotation_source is not provided, it defaults to 'auto'."""
        sys.path.insert(0, str(repo_root / "sam3_auto_label" / "src"))
        from inference import build_annotation_dict
        ann = build_annotation_dict(
            ann_id=1, image_id=1, category_id=1,
            bbox=[10, 20, 100, 200], area=20000,
            score=0.95, segmentation=None,
        )
        assert ann["annotation_source"] == "auto"


# ---------------------------------------------------------------------------
# TC-14: Retry on failure
# ---------------------------------------------------------------------------

class TestRetryOnFailure:
    """The batch loop must retry failed images up to max_retries times."""

    def test_retry_function_retries_on_failure(self, repo_root):
        """retry_segment should call segment_image up to max_retries times."""
        sys.path.insert(0, str(repo_root / "sam3_auto_label" / "src"))
        from batch_segment import retry_segment

        call_count = [0]

        def failing_segment(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise RuntimeError("transient OOM")
            return [{"id": 1}], 2

        annotations, ann_id, attempts = retry_segment(
            failing_segment, None, None, 1, 1, None, max_retries=3,
        )
        assert attempts == 3, "should retry until success"
        assert len(annotations) == 1

    def test_retry_gives_up_after_max_retries(self, repo_root):
        """After max_retries, retry_segment should return empty annotations."""
        sys.path.insert(0, str(repo_root / "sam3_auto_label" / "src"))
        from batch_segment import retry_segment

        def always_fail(*args, **kwargs):
            raise RuntimeError("permanent failure")

        annotations, ann_id, attempts = retry_segment(
            always_fail, None, None, 1, 1, None, max_retries=2,
        )
        assert attempts == 2, "should stop after max_retries"
        assert annotations == [], "should return empty on permanent failure"


# ---------------------------------------------------------------------------
# TC-15: Label validator
# ---------------------------------------------------------------------------

class TestLabelValidator:
    """The label validator must reject annotations with invalid data."""

    def test_rejects_nan_bbox(self, repo_root):
        """Bbox with NaN values must be rejected."""
        sys.path.insert(0, str(repo_root / "sam3_auto_label" / "src"))
        from inference import validate_annotation
        import math

        ann = {
            "id": 1, "image_id": 1, "category_id": 1,
            "bbox": [math.nan, 20, 100, 200],
            "area": 20000, "score": 0.9,
            "segmentation": None,
        }
        assert not validate_annotation(ann), "NaN bbox must be rejected"

    def test_rejects_zero_area(self, repo_root):
        """Annotations with zero area must be rejected."""
        sys.path.insert(0, str(repo_root / "sam3_auto_label" / "src"))
        from inference import validate_annotation

        ann = {
            "id": 1, "image_id": 1, "category_id": 1,
            "bbox": [10, 20, 0, 0],
            "area": 0, "score": 0.9,
            "segmentation": None,
        }
        assert not validate_annotation(ann), "zero area must be rejected"

    def test_rejects_negative_bbox(self, repo_root):
        """Bbox with negative width/height must be rejected."""
        sys.path.insert(0, str(repo_root / "sam3_auto_label" / "src"))
        from inference import validate_annotation

        ann = {
            "id": 1, "image_id": 1, "category_id": 1,
            "bbox": [10, 20, -100, 200],
            "area": 20000, "score": 0.9,
            "segmentation": None,
        }
        assert not validate_annotation(ann), "negative bbox must be rejected"

    def test_rejects_invalid_category_id(self, repo_root):
        """Category ID <= 0 must be rejected."""
        sys.path.insert(0, str(repo_root / "sam3_auto_label" / "src"))
        from inference import validate_annotation

        ann = {
            "id": 1, "image_id": 1, "category_id": 0,
            "bbox": [10, 20, 100, 200],
            "area": 20000, "score": 0.9,
            "segmentation": None,
        }
        assert not validate_annotation(ann), "category_id <= 0 must be rejected"

    def test_rejects_score_below_zero(self, repo_root):
        """Score < 0 or > 1 must be rejected."""
        sys.path.insert(0, str(repo_root / "sam3_auto_label" / "src"))
        from inference import validate_annotation

        ann = {
            "id": 1, "image_id": 1, "category_id": 1,
            "bbox": [10, 20, 100, 200],
            "area": 20000, "score": 1.5,
            "segmentation": None,
        }
        assert not validate_annotation(ann), "score > 1 must be rejected"

    def test_accepts_valid_annotation(self, repo_root):
        """A valid annotation must pass validation."""
        sys.path.insert(0, str(repo_root / "sam3_auto_label" / "src"))
        from inference import validate_annotation

        ann = {
            "id": 1, "image_id": 1, "category_id": 1,
            "bbox": [10, 20, 100, 200],
            "area": 20000, "score": 0.9,
            "segmentation": {"size": [100, 200], "counts": "abc"},
        }
        assert validate_annotation(ann), "valid annotation must pass"


# ---------------------------------------------------------------------------
# TC-16: min_area filter
# ---------------------------------------------------------------------------

class TestMinAreaFilter:
    """The min_area filter must drop annotations smaller than the threshold."""

    def test_filter_drops_small_annotations(self, repo_root):
        """Annotations with area < min_area must be filtered out."""
        sys.path.insert(0, str(repo_root / "sam3_auto_label" / "src"))
        from inference import filter_by_min_area

        annotations = [
            {"id": 1, "area": 50, "score": 0.9},
            {"id": 2, "area": 500, "score": 0.8},
            {"id": 3, "area": 100, "score": 0.7},
        ]
        filtered = filter_by_min_area(annotations, min_area=100)
        assert len(filtered) == 2, "only annotations with area >= 100 should remain"
        assert all(a["area"] >= 100 for a in filtered)

    def test_filter_with_zero_min_area_keeps_all(self, repo_root):
        """min_area=0 should keep all annotations (disabled)."""
        sys.path.insert(0, str(repo_root / "sam3_auto_label" / "src"))
        from inference import filter_by_min_area

        annotations = [
            {"id": 1, "area": 0, "score": 0.9},
            {"id": 2, "area": 500, "score": 0.8},
        ]
        filtered = filter_by_min_area(annotations, min_area=0)
        assert len(filtered) == 2, "min_area=0 should keep everything"

    def test_min_area_config_field_exists(self, repo_root):
        """InferenceConfig must have a min_area field."""
        sys.path.insert(0, str(repo_root / "sam3_auto_label" / "src"))
        from config import InferenceConfig
        cfg = InferenceConfig()
        assert hasattr(cfg, "min_area"), "InferenceConfig must have min_area field"
        assert cfg.min_area == 0, "default min_area should be 0 (disabled)"


# ---------------------------------------------------------------------------
# TC-17: SHA256 replaces MD5
# ---------------------------------------------------------------------------

class TestSHA256ConfigHash:
    """The config hash must use SHA256, not MD5 (collision safety)."""

    def test_config_hash_is_sha256(self, repo_root, tmp_path):
        """The _config_hash method must produce a SHA256-based hash."""
        sys.path.insert(0, str(repo_root / "sam3_auto_label" / "src"))
        from config import Config, InferenceConfig, AnnotationConfig, OutputConfig, CheckpointConfig, Category
        from tracker import ExperimentTracker

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
        tracker = ExperimentTracker(cfg)
        hash_val = tracker._config_hash(cfg)
        # SHA256 produces 64 hex chars; we take first 16 for a shorter ID
        assert len(hash_val) >= 16, "SHA256 hash should be at least 16 chars"
        assert all(c in "0123456789abcdef" for c in hash_val), "hash should be hex"

    def test_config_hash_not_md5_length(self, repo_root, tmp_path):
        """The hash must NOT be MD5 length (32 chars). SHA256 is 64 chars."""
        sys.path.insert(0, str(repo_root / "sam3_auto_label" / "src"))
        from config import Config, InferenceConfig, AnnotationConfig, OutputConfig, CheckpointConfig, Category
        from tracker import ExperimentTracker

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
        tracker = ExperimentTracker(cfg)
        hash_val = tracker._config_hash(cfg)
        # MD5 is 32 chars; we slice to 16, so 16 is ambiguous.
        # But the full hash before slicing must be SHA256 (64 chars).
        # We verify by checking the internal algorithm.
        import hashlib
        import json
        config_dict = {
            "threshold": cfg.inference.confidence_threshold,
            "resolution": cfg.inference.resolution,
            "device": cfg.inference.device,
            "categories": [(c.id, c.name, c.prompt) for c in cfg.categories],
        }
        sha256_full = hashlib.sha256(
            json.dumps(config_dict, sort_keys=True).encode()
        ).hexdigest()
        assert hash_val == sha256_full[:16], "hash must be SHA256-derived"
