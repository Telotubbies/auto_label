"""T-051: one unclamped xywh box-IoU helper, shared by the four callers that had a copy."""
import pytest

from app.services.boxes import box_iou


def test_identical_boxes_are_one():
    assert box_iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0


def test_disjoint_boxes_are_zero():
    assert box_iou((0, 0, 10, 10), (10, 0, 10, 10)) == 0.0  # touching edges, not negative
    assert box_iou((0, 0, 10, 10), (20, 20, 10, 10)) == 0.0


def test_half_overlap_is_one_third():
    assert box_iou((0, 0, 10, 10), (5, 0, 10, 10)) == pytest.approx(1 / 3, abs=1e-9)


def test_zero_area_box_is_zero():
    assert box_iou((0, 0, 0, 0), (0, 0, 0, 0)) == 0.0  # union > 0 guard: never raises
    assert box_iou((0, 0, 0, 0), (0, 0, 10, 10)) == 0.0


def test_symmetry():
    a, b = (3, 4, 10, 20), (6, 10, 12, 8)
    assert box_iou(a, b) == box_iou(b, a)


def test_the_four_callers_keep_no_private_copy():
    from app.services import evaluate, health, health_scan, insights_eval, suspects

    for mod in (evaluate, insights_eval, suspects):
        assert not hasattr(mod, "_iou"), mod.__name__
    assert not hasattr(health_scan, "iou")
    assert health.box_iou is box_iou
