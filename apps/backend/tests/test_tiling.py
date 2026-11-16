"""SAHI-style tiling: tile grid, annotation remap, stitch, and sliced prediction."""
import itertools
import os

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

from types import SimpleNamespace

import pytest
from PIL import Image as PImage

from app.services.tiling import Tiling, sliced_predict, stitch, tile_annotations, tile_boxes


def test_parse_accepts_dict_and_disables_on_false():
    t = Tiling.parse({"tile_size": 512, "overlap": 0.25})
    assert (t.tile_size, t.overlap) == (512, 0.25)
    assert Tiling.parse(None) is None
    assert Tiling.parse(False) is None
    assert Tiling.parse({}) is None
    assert Tiling.parse(0) is None
    assert Tiling.parse(True).tile_size == 640


@pytest.mark.parametrize("raw", [{"tile_size": 32}, {"tile_size": 640, "overlap": 0.95}, {"overlap": 0.2}])
def test_parse_rejects_tiles_that_cannot_work(raw):
    with pytest.raises(ValueError, match="tiling"):
        Tiling.parse(raw)


def test_tiles_cover_every_edge_once():
    boxes = tile_boxes(1000, 600, Tiling(400, 0.2))
    assert boxes[0][:2] == (0, 0)
    assert max(b[2] for b in boxes) == 1000
    assert max(b[3] for b in boxes) == 600
    assert all(b[2] - b[0] == 400 and b[3] - b[1] == 400 for b in boxes)
    for lo, hi in ((0, 2), (1, 3)):
        spans = sorted({(b[lo], b[hi]) for b in boxes})
        assert spans[0][0] == 0
        assert all(a[1] >= b[0] for a, b in itertools.pairwise(spans))


def test_annotation_is_remapped_into_the_tile_and_clipped():
    anns = [
        {"id": "in", "shape": {"kind": "bbox", "x": 0.55, "y": 0.1, "w": 0.1, "h": 0.2}},
        {"id": "out", "shape": {"kind": "bbox", "x": 0.05, "y": 0.1, "w": 0.1, "h": 0.2}},
    ]
    local = tile_annotations(anns, (500, 0, 1000, 500), 1000, 500)
    assert [a["id"] for a in local] == ["in"]
    s = local[0]["shape"]
    assert (round(s["x"], 3), round(s["y"], 3), round(s["w"], 3), round(s["h"], 3)) == (0.1, 0.1, 0.2, 0.2)


def _pred(x, y, conf=0.9, cls="helmet", cid=0):
    return {"x": x, "y": y, "width": 100, "height": 100, "confidence": conf, "class": cls, "class_id": cid}


def _out(preds, w, h):
    return {"predictions": preds, "time": 0.01, "image": {"width": w, "height": h}}


def test_stitch_shifts_boxes_and_drops_overlap_duplicates():
    tiles = [
        ((0, 0, 400, 400), _out([_pred(350, 200, 0.6)], 400, 400)),
        ((300, 0, 700, 400), _out([_pred(50, 200, 0.9)], 400, 400)),  # same object after shifting
    ]
    preds = stitch(tiles, 700, 400)
    assert len(preds) == 1
    assert (preds[0]["x"], preds[0]["y"]) == (350, 200)
    assert preds[0]["confidence"] == 0.9


def test_stitch_keeps_different_classes_and_polygons_in_global_coords():
    poly = _pred(200, 200, cid=1, cls="vest")
    poly["points"] = [{"x": 150, "y": 150}, {"x": 250, "y": 150}, {"x": 200, "y": 250}]
    tiles = [
        ((0, 0, 400, 400), _out([_pred(200, 200, cid=0, cls="helmet")], 400, 400)),
        ((300, 0, 700, 400), _out([poly], 400, 400)),
    ]
    preds = stitch(tiles, 700, 400)
    assert {p["class"] for p in preds} == {"helmet", "vest"}
    vest = next(p for p in preds if p["class"] == "vest")
    assert vest["points"][0] == {"x": 450.0, "y": 150.0}


class _FakeModel:
    ref = "trained:fake"

    def __init__(self, caps=("detect",)):
        self.caps = set(caps)
        self.calls = []
        self.adapter = SimpleNamespace(family="ultralytics", capabilities=lambda _v: self.caps)

    def predict(self, im, **kw):
        self.calls.append((im.size, kw))
        return _out([_pred(im.width / 2, im.height / 2)], im.width, im.height)


def test_sliced_predict_runs_each_tile_and_returns_global_boxes():
    model = _FakeModel()
    im = PImage.new("RGB", (800, 800))
    out = sliced_predict(model, im, Tiling(400, 0), conf=0.3)
    assert len(model.calls) == 4
    assert model.calls[0][1] == {"conf": 0.3}
    assert out["image"] == {"width": 800, "height": 800}
    assert out["model"] == "trained:fake"
    assert {p["x"] for p in out["predictions"]} == {200.0, 600.0}


def test_sliced_predict_rejects_models_without_boxes():
    with pytest.raises(ValueError, match="detection"):
        sliced_predict(_FakeModel({"classify"}), PImage.new("RGB", (800, 800)), Tiling(400, 0))
