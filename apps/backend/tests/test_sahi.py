"""SAHI-style slice inference: post-processing types, match metrics, slice grids and the auto rule.

Boxes use the API's centre format: x, y, width, height (pixels), confidence, class_id.
"""
import pytest

from app.services import sahi


def box(x, y, w, h, conf, cls=0, **extra):
    return {"x": x, "y": y, "width": w, "height": h, "confidence": conf, "class_id": cls, "class": f"c{cls}", **extra}


# --- match metrics --------------------------------------------------------------------------------

def test_iou_and_ios_differ_when_one_box_sits_inside_another():
    big, small = box(50, 50, 100, 100, .9), box(50, 50, 20, 20, .8)

    assert sahi.match_value(big, small, "IOU") == pytest.approx(400 / 10000)
    assert sahi.match_value(big, small, "IOS") == pytest.approx(1.0)


def test_unknown_metric_or_postprocess_is_refused():
    with pytest.raises(ValueError):
        sahi.match_value(box(0, 0, 1, 1, 1), box(0, 0, 1, 1, 1), "DICE")
    with pytest.raises(ValueError):
        sahi.postprocess([box(0, 0, 1, 1, 1)], kind="SOFTNMS")


# --- post-processing types ------------------------------------------------------------------------

TWO_HALVES = [box(40, 50, 80, 100, .9), box(80, 50, 80, 100, .6)]      # one object cut by a tile edge


def test_nms_keeps_the_stronger_box_and_drops_the_overlap():
    out = sahi.postprocess(TWO_HALVES, kind="NMS", metric="IOU", threshold=0.3)

    assert len(out) == 1 and out[0]["confidence"] == .9 and out[0]["width"] == 80


def test_nmm_merges_the_overlap_into_one_union_box():
    out = sahi.postprocess(TWO_HALVES, kind="NMM", metric="IOU", threshold=0.3)

    assert len(out) == 1
    assert out[0]["confidence"] == .9                      # the stronger score wins
    assert (out[0]["x"], out[0]["width"]) == (60, 120)     # union spans 0..120


def test_greedynmm_chains_through_the_growing_box():
    chain = [box(30, 50, 60, 100, .9), box(70, 50, 60, 100, .8), box(110, 50, 60, 100, .7)]

    nmm = sahi.postprocess(chain, kind="NMM", metric="IOU", threshold=0.1)
    greedy = sahi.postprocess(chain, kind="GREEDYNMM", metric="IOU", threshold=0.1)

    assert len(nmm) == 2          # the third box never overlaps the original first box
    assert len(greedy) == 1       # but it overlaps the box that already absorbed the second


def test_lsnms_gives_the_same_boxes_as_nms():
    boxes = TWO_HALVES + [box(300, 50, 40, 40, .7)]

    assert sahi.postprocess(boxes, kind="LSNMS", metric="IOU", threshold=0.3) == \
        sahi.postprocess(boxes, kind="NMS", metric="IOU", threshold=0.3)


def test_postprocess_is_class_aware_unless_agnostic():
    cats = [box(50, 50, 80, 80, .9, cls=0), box(50, 50, 80, 80, .8, cls=1)]

    assert len(sahi.postprocess(cats, kind="NMS", metric="IOU", threshold=0.5)) == 2
    assert len(sahi.postprocess(cats, kind="NMS", metric="IOU", threshold=0.5, class_agnostic=True)) == 1


def test_ios_threshold_removes_a_small_box_inside_a_big_one_that_iou_keeps():
    nested = [box(50, 50, 100, 100, .9), box(50, 50, 20, 20, .8)]

    assert len(sahi.postprocess(nested, kind="NMS", metric="IOU", threshold=0.5)) == 2
    assert len(sahi.postprocess(nested, kind="NMS", metric="IOS", threshold=0.5)) == 1


def test_a_merged_box_keeps_the_polygon_of_its_strongest_member():
    strong = box(40, 50, 80, 100, .9, points=[{"x": 1, "y": 1}, {"x": 9, "y": 1}, {"x": 5, "y": 9}])
    weak = box(80, 50, 80, 100, .6, points=[{"x": 2, "y": 2}, {"x": 3, "y": 3}, {"x": 4, "y": 4}])

    out = sahi.postprocess([weak, strong], kind="NMM", metric="IOU", threshold=0.3)

    assert out[0]["points"] == strong["points"]


# --- slice grid -----------------------------------------------------------------------------------

def test_slices_use_separate_width_height_and_overlap_ratios():
    cfg = sahi.SliceConfig(slice_width=200, slice_height=100, overlap_width_ratio=0.5, overlap_height_ratio=0.0)

    grid = cfg.resolve(400, 200).boxes(400, 200)

    assert all(b[2] - b[0] == 200 and b[3] - b[1] == 100 for b in grid)
    assert sorted({b[0] for b in grid}) == [0, 100, 200]       # 50% horizontal overlap
    assert sorted({b[1] for b in grid}) == [0, 100]            # no vertical overlap


def test_a_slice_never_exceeds_the_cap_so_one_request_cannot_fan_out():
    cfg = sahi.SliceConfig(slice_width=64, slice_height=64, overlap_width_ratio=0.5, overlap_height_ratio=0.5)

    with pytest.raises(ValueError, match="slices"):
        cfg.resolve(8000, 8000).boxes(8000, 8000)


def test_auto_slice_picks_a_bigger_slice_for_a_bigger_image():
    small = sahi.SliceConfig(auto=True).resolve(1280, 720)
    large = sahi.SliceConfig(auto=True).resolve(6000, 4000)

    assert large.slice_width > small.slice_width
    assert 0 < small.overlap_width_ratio < 0.5


def test_options_are_range_checked():
    for bad in ({"slice_width": 10}, {"overlap_width_ratio": 0.95}, {"postprocess_match_threshold": 1.5}):
        with pytest.raises(ValueError):
            sahi.parse_options(bad)


def test_default_options_turn_slicing_off():
    assert sahi.parse_options({}) is None
