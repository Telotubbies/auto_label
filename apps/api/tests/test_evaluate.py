"""Evaluation service: COCO metrics, confidence sweep, confusion matrix, per-image detail."""
import json
import os
from pathlib import Path

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from PIL import Image as PImage

from app.services import evaluate as evaluate_mod

CLASSES = ["helmet", "vest"]


def _ann(cls: int, x: float, y: float, w: float, h: float) -> dict:
    return {"cls": cls, "shape": {"kind": "bbox", "x": x, "y": y, "w": w, "h": h}}


def _tint(i: int) -> tuple[int, int, int]:
    return (20 + 40 * i, 80, 160)


def make_version(root: Path, items: list[dict]) -> Path:
    """Write manifest.json + one solid-colour JPEG per item under <root>/<split>/<name>."""
    root.mkdir(parents=True, exist_ok=True)
    for i, it in enumerate(items):
        p = root / it["file"]
        p.parent.mkdir(parents=True, exist_ok=True)
        PImage.new("RGB", (it["width"], it["height"]), _tint(i)).save(p, "JPEG")
    (root / "manifest.json").write_text(
        json.dumps({"classes": CLASSES, "type": "object-detection", "items": items}))
    return root


def _pred(cls: str, conf: float, x: float, y: float, w: float, h: float) -> dict:
    """Centre-based pixel prediction, the shape adapters return."""
    return {"class": cls, "class_id": CLASSES.index(cls), "confidence": conf,
            "x": x, "y": y, "width": w, "height": h}


class FakeModel:
    """Returns fixed predictions; the image's solid tint identifies which file it is."""

    def __init__(self, root: Path, preds: dict[str, list[dict]]):
        items = json.loads((root / "manifest.json").read_text())["items"]
        self.colors = {Path(it["file"]).name: _tint(i) for i, it in enumerate(items)}
        self.preds = preds
        self.calls = 0

    def predict(self, im, **kw):
        self.calls += 1
        px = im.convert("RGB").getpixel((0, 0))
        name = min(self.colors, key=lambda n: sum((a - b) ** 2 for a, b in zip(self.colors[n], px)))
        return {"predictions": [dict(p) for p in self.preds.get(name, [])],
                "image": {"width": im.width, "height": im.height}, "time": 0.001}


def _use_model(monkeypatch, model):
    monkeypatch.setattr(evaluate_mod, "resolve", lambda ref, db, workspace_id=None: model)


# Two classes, four test images, two exact matches, two wrong boxes, one extra, two missed.
REF_ITEMS = [
    {"file": "test/a.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [_ann(0, 0.10, 0.10, 0.20, 0.20), _ann(1, 0.60, 0.60, 0.20, 0.20)]},
    {"file": "test/b.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [_ann(0, 0.20, 0.20, 0.20, 0.20)]},
    {"file": "test/c.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [_ann(1, 0.30, 0.30, 0.20, 0.20), _ann(1, 0.70, 0.10, 0.10, 0.10)]},
    {"file": "test/d.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [_ann(0, 0.40, 0.40, 0.30, 0.30)]},
]
REF_PREDS = {
    "a.jpg": [_pred("helmet", 0.90, 40, 40, 40, 40), _pred("vest", 0.80, 140, 140, 40, 40)],
    "b.jpg": [_pred("helmet", 0.70, 40, 40, 40, 40)],          # IoU 0.25: wrong box
    "c.jpg": [_pred("vest", 0.60, 80, 80, 40, 40), _pred("helmet", 0.30, 50, 50, 20, 20)],
    "d.jpg": [],                                               # missed
}


def test_matches_pycocotools_reference(tmp_path, monkeypatch):
    root = make_version(tmp_path / "v1", REF_ITEMS)
    _use_model(monkeypatch, FakeModel(root, REF_PREDS))
    out = evaluate_mod.evaluate("ultralytics:yolo26n", root, "object-detection")
    # Reference produced once with pycocotools COCOeval(iouType="bbox") directly on this exact
    # export + these fixed predictions, with annotation ids renumbered to 1-based (pycocotools
    # treats gt id 0 as unmatched; the throwaway script was not kept). The two-class AP is the
    # mean of the per-class precision samples: helmet 34/101 = 0.3366 and vest 67/101 = 0.6634
    # (101 recall samples, interpolated precision) -> 0.5. A 0-based reference gives 0.3317.
    assert out["coco"]["AP"] == pytest.approx(0.5)
    assert out["coco"]["AP50"] == pytest.approx(0.5)
    helmet, vest = (c["AP"] for c in out["per_class"])
    assert helmet == pytest.approx(34 / 101, abs=1e-3)
    assert vest == pytest.approx(67 / 101, abs=1e-3)
    keys = {"AP", "AP50", "AP75", "APs", "APm", "APl", "AR1", "AR10", "AR100", "ARs", "ARm", "ARl"}
    assert set(out["coco"]) == keys
    assert all(isinstance(v, float) for v in out["coco"].values())


PERFECT_ITEMS = [
    {"file": "test/p1.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [_ann(0, 0.10, 0.10, 0.20, 0.20), _ann(1, 0.50, 0.50, 0.20, 0.20)]},
    {"file": "test/p2.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [_ann(1, 0.20, 0.40, 0.20, 0.10)]},
]
PERFECT_PREDS = {
    "p1.jpg": [_pred("helmet", 0.95, 40, 40, 40, 40), _pred("vest", 0.90, 120, 120, 40, 40)],
    "p2.jpg": [_pred("vest", 0.85, 60, 90, 40, 20)],
}


def test_perfect_predictions_ap_is_one(tmp_path, monkeypatch):
    root = make_version(tmp_path / "v1", PERFECT_ITEMS)
    _use_model(monkeypatch, FakeModel(root, PERFECT_PREDS))
    out = evaluate_mod.evaluate("ultralytics:yolo26n", root, "object-detection")
    assert out["coco"]["AP"] == pytest.approx(1.0)
    assert out["coco"]["AP50"] == pytest.approx(1.0)


VALID_ITEMS = [
    {"file": "valid/v1.jpg", "split": "valid", "width": 200, "height": 200,
     "anns": [_ann(0, 0.10, 0.10, 0.20, 0.20)]},
    {"file": "valid/v2.jpg", "split": "valid", "width": 200, "height": 200,
     "anns": [_ann(1, 0.50, 0.50, 0.20, 0.20)]},
]
VALID_PREDS = {
    "v1.jpg": [_pred("helmet", 0.90, 40, 40, 40, 40)],
    "v2.jpg": [_pred("vest", 0.90, 120, 120, 40, 40)],
}


def test_empty_test_split_falls_back_to_valid(tmp_path, monkeypatch):
    root = make_version(tmp_path / "v1", VALID_ITEMS)
    _use_model(monkeypatch, FakeModel(root, VALID_PREDS))
    out = evaluate_mod.evaluate("ultralytics:yolo26n", root, "object-detection")
    assert out["split"] == "valid"
    assert "empty" in out["note"].lower()
    assert "valid" in out["note"].lower()
    assert out["coco"]["AP"] > 0


def test_f1_best_conf_in_range(tmp_path, monkeypatch):
    root = make_version(tmp_path / "v1", REF_ITEMS)
    _use_model(monkeypatch, FakeModel(root, REF_PREDS))
    out = evaluate_mod.evaluate("ultralytics:yolo26n", root, "object-detection")
    assert 0 < out["f1_best"]["conf"] < 1
    assert 0 <= out["f1_best"]["f1"] <= 1
    assert out["confusion"]["labels"][-1] == "background"


CONFUSION_ITEMS = [
    {"file": "test/e.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [_ann(0, 0.10, 0.10, 0.20, 0.20)]},
]
# vest (wrong class) scores higher than the correct helmet, so the best F1 keeps both.
CONFUSION_PREDS = {
    "e.jpg": [_pred("vest", 0.95, 40, 40, 40, 40), _pred("helmet", 0.90, 40, 40, 40, 40)],
}


def test_confusion_cell_counts_and_images(tmp_path, monkeypatch):
    root = make_version(tmp_path / "v1", CONFUSION_ITEMS)
    _use_model(monkeypatch, FakeModel(root, CONFUSION_PREDS))
    out = evaluate_mod.evaluate("ultralytics:yolo26n", root, "object-detection")
    labels, matrix, images = out["confusion"]["labels"], out["confusion"]["matrix"], out["confusion"]["images"]
    i, j, bg = labels.index("helmet"), labels.index("vest"), labels.index("background")
    # the highest-scoring box (vest 0.95) claims the helmet GT, so the matrix shows real confusion
    assert matrix[i][j] == 1
    assert images[i][j] == ["e.jpg"]
    assert matrix[bg][i] == 1                # the correct-class box lost the GT to the higher-scoring one
    assert matrix[i][bg] == 0                # the gt was matched
    assert matrix[bg][j] == 0                # the vest box is not a background false positive


def test_classify_returns_note_without_coco(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluate_mod, "resolve", lambda *a, **k: None)
    out = evaluate_mod.evaluate("ultralytics:yolo26n-cls", tmp_path / "missing", "classify")
    assert "classification" in out["note"].lower()
    assert out["f1_best"]["conf"] == 0.4


def test_no_eval_data_does_not_crash(tmp_path, monkeypatch):
    root = make_version(tmp_path / "v1", [])
    monkeypatch.setattr(evaluate_mod, "resolve", lambda *a, **k: None)
    out = evaluate_mod.evaluate("ultralytics:yolo26n", root, "object-detection")
    assert "skipped" in out["note"].lower()
    assert all(v == 0.0 for v in out["coco"].values())
    assert out["f1_best"] == {"conf": 0.4, "f1": 0.0}
    assert out["detections"] == []
    assert out["tide"] == {k: 0.0 for k in ("cls", "loc", "both", "dupe", "bkg", "missed")}


SEG_ITEMS = [
    {"file": "test/s1.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [{"cls": 0, "shape": {"kind": "polygon",
                                   "points": [0.2, 0.2, 0.6, 0.2, 0.6, 0.6, 0.2, 0.6]}}]},
]
SEG_PREDS = {"s1.jpg": [{"class": "helmet", "class_id": 0, "confidence": 0.9,
                         "x": 80, "y": 80, "width": 80, "height": 80,
                         "points": [{"x": 40, "y": 40}, {"x": 120, "y": 40},
                                    {"x": 120, "y": 120}, {"x": 40, "y": 120}]}]}


def test_segmentation_uses_mask_iou(tmp_path, monkeypatch):
    root = make_version(tmp_path / "v1", SEG_ITEMS)
    _use_model(monkeypatch, FakeModel(root, SEG_PREDS))
    out = evaluate_mod.evaluate("ultralytics:yolo26n-seg", root, "segment")
    assert out["iou"] == "segm"
    assert out["coco"]["AP"] == pytest.approx(1.0)
    assert out["coco"]["AP50"] == pytest.approx(1.0)


THIN_ITEMS = [
    {"file": "test/t1.jpg", "split": "test", "width": 200, "height": 200,
     # a thin diagonal mask that still spans the full 80x80 box
     "anns": [{"cls": 0, "shape": {"kind": "polygon",
                                   "points": [0.2, 0.2, 0.22, 0.2, 0.6, 0.58, 0.58, 0.6]}}]},
]
FULL_BOX_PRED = {"t1.jpg": [{"class": "helmet", "class_id": 0, "confidence": 0.9,
                             "x": 80, "y": 80, "width": 80, "height": 80,
                             "points": [{"x": 40, "y": 40}, {"x": 120, "y": 40},
                                        {"x": 120, "y": 120}, {"x": 40, "y": 120}]}]}


def test_segm_and_bbox_disagree_when_masks_do(tmp_path, monkeypatch):
    """Same boxes (IoU 1.0), different masks (thin strip vs full square): only segm rejects it."""
    root = make_version(tmp_path / "v1", THIN_ITEMS)
    _use_model(monkeypatch, FakeModel(root, FULL_BOX_PRED))
    seg = evaluate_mod.evaluate("ultralytics:yolo26n-seg", root, "segment")
    box = evaluate_mod.evaluate("ultralytics:yolo26n", root, "object-detection")
    assert seg["iou"] == "segm" and box["iou"] == "bbox"
    assert seg["coco"]["AP50"] == 0.0
    assert box["coco"]["AP50"] == pytest.approx(1.0)


WORST_ITEMS = [
    {"file": "test/good.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [_ann(0, 0.10, 0.10, 0.20, 0.20)]},
    {"file": "test/miss.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [_ann(0, 0.40, 0.40, 0.20, 0.20)]},
]
WORST_PREDS = {"good.jpg": [_pred("helmet", 0.9, 40, 40, 40, 40)], "miss.jpg": []}


def test_worst_lists_only_images_with_errors(tmp_path, monkeypatch):
    root = make_version(tmp_path / "v1", WORST_ITEMS)
    _use_model(monkeypatch, FakeModel(root, WORST_PREDS))
    out = evaluate_mod.evaluate("ultralytics:yolo26n", root, "object-detection")
    assert out["worst"] == ["miss.jpg"]


def test_pr_curve_sorted_by_recall(tmp_path, monkeypatch):
    root = make_version(tmp_path / "v1", REF_ITEMS)
    _use_model(monkeypatch, FakeModel(root, REF_PREDS))
    out = evaluate_mod.evaluate("ultralytics:yolo26n", root, "object-detection")
    recalls = [p["recall"] for p in out["pr_curve"]]
    assert recalls == sorted(recalls)
    assert all(0 <= p["precision"] <= 1 for p in out["pr_curve"])
    assert len(recalls) == 19


TIDE_KEYS = ("cls", "loc", "both", "dupe", "bkg", "missed")

# gt box (20,20,40,40) vs predicted box (30,30,40,40): IoU 900/2300 = 0.391, a pure loc error
LOC_ITEMS = [
    {"file": "test/loc1.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [_ann(0, 0.10, 0.10, 0.20, 0.20)]},
    {"file": "test/loc2.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [_ann(0, 0.10, 0.10, 0.20, 0.20)]},
    {"file": "test/loc3.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [_ann(0, 0.10, 0.10, 0.20, 0.20)]},
]
LOC_PREDS = {name: [_pred("helmet", 0.9, 50, 50, 40, 40)]
             for name in ("loc1.jpg", "loc2.jpg", "loc3.jpg")}


def test_tide_loc_dominates_when_all_errors_are_localisation(tmp_path, monkeypatch):
    root = make_version(tmp_path / "v1", LOC_ITEMS)
    _use_model(monkeypatch, FakeModel(root, LOC_PREDS))
    out = evaluate_mod.evaluate("ultralytics:yolo26n", root, "object-detection")
    tide = out["tide"]
    assert set(tide) == set(TIDE_KEYS)
    assert tide["loc"] == pytest.approx(1.0)
    assert all(tide[k] == 0.0 for k in TIDE_KEYS if k != "loc")
    assert tide["loc"] == max(tide.values())


def test_tide_is_zero_for_a_perfect_model(tmp_path, monkeypatch):
    root = make_version(tmp_path / "v1", PERFECT_ITEMS)
    _use_model(monkeypatch, FakeModel(root, PERFECT_PREDS))
    out = evaluate_mod.evaluate("ultralytics:yolo26n", root, "object-detection")
    assert out["tide"] == {k: 0.0 for k in TIDE_KEYS}


CLS_ITEMS = [
    {"file": "test/cls.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [_ann(0, 0.10, 0.10, 0.20, 0.20)]},
]
# identical box (40,40,40,40 pixels), wrong class: a pure classification error
CLS_PREDS = {"cls.jpg": [_pred("vest", 0.9, 40, 40, 40, 40)]}


def test_tide_cls_error_is_recovered(tmp_path, monkeypatch):
    root = make_version(tmp_path / "v1", CLS_ITEMS)
    _use_model(monkeypatch, FakeModel(root, CLS_PREDS))
    out = evaluate_mod.evaluate("ultralytics:yolo26n", root, "object-detection")
    tide = out["tide"]
    assert tide["cls"] == pytest.approx(1.0)
    assert all(tide[k] == 0.0 for k in TIDE_KEYS if k != "cls")


MISSED_ITEMS = [
    {"file": "test/missed.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [_ann(0, 0.10, 0.10, 0.20, 0.20)]},
    {"file": "test/found.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [_ann(1, 0.50, 0.50, 0.20, 0.20)]},
]
MISSED_PREDS = {"missed.jpg": [], "found.jpg": [_pred("vest", 0.9, 120, 120, 40, 40)]}


def test_tide_missed_error_is_recovered(tmp_path, monkeypatch):
    """Oracle missed fix removes the gt; one found class keeps AP50 measurable (0.5 -> 1.0)."""
    root = make_version(tmp_path / "v1", MISSED_ITEMS)
    _use_model(monkeypatch, FakeModel(root, MISSED_PREDS))
    out = evaluate_mod.evaluate("ultralytics:yolo26n", root, "object-detection")
    tide = out["tide"]
    assert tide["missed"] == pytest.approx(0.5)
    assert all(tide[k] == 0.0 for k in TIDE_KEYS if k != "missed")


BOTH_ITEMS = [
    {"file": "test/both.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [_ann(0, 0.10, 0.10, 0.20, 0.20)]},
]
# wrong class (vest) and a shifted box: IoU 0.391, so the fix needs both corrections
BOTH_PREDS = {"both.jpg": [_pred("vest", 0.9, 50, 50, 40, 40)]}


def test_tide_both_error_is_recovered(tmp_path, monkeypatch):
    root = make_version(tmp_path / "v1", BOTH_ITEMS)
    _use_model(monkeypatch, FakeModel(root, BOTH_PREDS))
    out = evaluate_mod.evaluate("ultralytics:yolo26n", root, "object-detection")
    tide = out["tide"]
    assert tide["both"] == pytest.approx(1.0)
    assert all(tide[k] == 0.0 for k in TIDE_KEYS if k != "both")


def test_tide_classification_labels_each_error_type():
    """One image with a TP, a duplicate, a background false positive and a second TP."""
    rec = {
        "file": "test/labels.jpg", "image_id": 1, "width": 200, "height": 200,
        "gt": [{"cls": "helmet", "bbox": [20, 20, 40, 40], "segm": None},
               {"cls": "vest", "bbox": [100, 100, 40, 40], "segm": None}],
        "pred": [{"cls": "helmet", "conf": 0.90, "bbox": [20, 20, 40, 40], "points": None},
                 {"cls": "helmet", "conf": 0.80, "bbox": [20, 20, 40, 40], "points": None},
                 {"cls": "vest", "conf": 0.70, "bbox": [130, 130, 40, 40], "points": None},
                 {"cls": "vest", "conf": 0.60, "bbox": [100, 100, 40, 40], "points": None}],
    }
    fixes, missed, _ = evaluate_mod._tide_classify(rec, "bbox")
    assert fixes == [None, ("dupe", 0), ("bkg", -1), None]
    assert missed == []


CROWDED_REC = {
    "file": "test/crowded.jpg", "image_id": 1, "width": 200, "height": 200,
    # two overlapping same-class gts, both matched by higher-scored predictions
    "gt": [{"cls": "helmet", "bbox": [20, 20, 40, 40], "segm": None},
           {"cls": "helmet", "bbox": [35, 20, 40, 40], "segm": None}],
    # the last box overlaps both gts (IoU 0.70 / 0.67): a duplicate of the first TP, not a loc
    "pred": [{"cls": "helmet", "conf": 0.90, "bbox": [20, 20, 40, 40], "points": None},
             {"cls": "helmet", "conf": 0.85, "bbox": [35, 20, 40, 40], "points": None},
             {"cls": "helmet", "conf": 0.80, "bbox": [27, 20, 40, 40], "points": None}],
}


def test_tide_crowded_duplicate_stays_dupe():
    fixes, missed, tps = evaluate_mod._tide_classify(CROWDED_REC, "bbox")
    assert fixes == [None, None, ("dupe", 0)]
    assert missed == []
    assert set(tps) == {0, 1}


STEAL_ITEMS = [
    {"file": "test/steal.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [_ann(0, 0.10, 0.10, 0.20, 0.20)]},
    # a second helmet gt found late, so a duplicate inserted at 0.95 would lower AP50
    {"file": "test/steal_other.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [_ann(0, 0.50, 0.50, 0.20, 0.20)]},
]
# a higher-scored wrong-class box on the same gt: the helmet box must still win the TP
STEAL_PREDS = {"steal.jpg": [_pred("vest", 0.95, 40, 40, 40, 40),
                             _pred("helmet", 0.90, 40, 40, 40, 40)],
               "steal_other.jpg": [_pred("helmet", 0.40, 120, 120, 40, 40)]}


def test_tide_wrong_class_box_does_not_steal_the_tp(tmp_path, monkeypatch):
    fixes, missed, _ = evaluate_mod._tide_classify(
        {"file": "steal.jpg", "image_id": 1, "width": 200, "height": 200,
         "gt": [{"cls": "helmet", "bbox": [20, 20, 40, 40], "segm": None}],
         "pred": [{"cls": "vest", "conf": 0.95, "bbox": [20, 20, 40, 40], "points": None},
                  {"cls": "helmet", "conf": 0.90, "bbox": [20, 20, 40, 40], "points": None}]},
        "bbox")
    assert fixes == [("cls", 0), None]
    assert missed == []
    root = make_version(tmp_path / "v1", STEAL_ITEMS)
    _use_model(monkeypatch, FakeModel(root, STEAL_PREDS))
    out = evaluate_mod.evaluate("ultralytics:yolo26n", root, "object-detection")
    assert out["coco"]["AP50"] == pytest.approx(1.0)
    # the cls oracle fix would duplicate the TP that already owns the gt, so nothing is recoverable
    assert out["tide"] == {k: 0.0 for k in TIDE_KEYS}


DUPE_ITEMS = [
    {"file": "test/dupe1.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [_ann(0, 0.10, 0.10, 0.20, 0.20)]},
    {"file": "test/dupe2.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [_ann(0, 0.10, 0.10, 0.20, 0.20)]},
    {"file": "test/dupe3.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [_ann(0, 0.10, 0.10, 0.20, 0.20)]},
]
# one image fires the same box twice (TP 0.90 + duplicate 0.80), the other two find their gt
# later and lower: base AP50 ~0.834, dropping the duplicate -> 1.0.
DUPE_PREDS = {
    "dupe1.jpg": [_pred("helmet", 0.90, 40, 40, 40, 40),
                  _pred("helmet", 0.80, 40, 40, 40, 40)],
    "dupe2.jpg": [_pred("helmet", 0.50, 40, 40, 40, 40)],
    "dupe3.jpg": [_pred("helmet", 0.40, 40, 40, 40, 40)],
}


def test_tide_dupe_dap_end_to_end(tmp_path, monkeypatch):
    root = make_version(tmp_path / "v1", DUPE_ITEMS)
    _use_model(monkeypatch, FakeModel(root, DUPE_PREDS))
    out = evaluate_mod.evaluate("ultralytics:yolo26n", root, "object-detection")
    tide = out["tide"]
    assert out["coco"]["AP50"] == pytest.approx(0.8342, abs=1e-3)
    assert tide["dupe"] == pytest.approx(0.1658, abs=1e-3)
    assert tide["dupe"] == max(tide.values())
    assert tide["bkg"] == 0.0


BKG_ITEMS = [
    {"file": "test/bkg_tp.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [_ann(0, 0.10, 0.10, 0.20, 0.20)]},
    {"file": "test/bkg_fp.jpg", "split": "test", "width": 200, "height": 200, "anns": []},
]
# a confident background box on an empty image outranks the only TP: base AP50 0.5 -> 1.0
BKG_PREDS = {
    "bkg_tp.jpg": [_pred("helmet", 0.50, 40, 40, 40, 40)],
    "bkg_fp.jpg": [_pred("helmet", 0.90, 150, 150, 30, 30)],
}


def test_tide_bkg_dap_end_to_end(tmp_path, monkeypatch):
    root = make_version(tmp_path / "v1", BKG_ITEMS)
    _use_model(monkeypatch, FakeModel(root, BKG_PREDS))
    out = evaluate_mod.evaluate("ultralytics:yolo26n", root, "object-detection")
    tide = out["tide"]
    assert out["coco"]["AP50"] == pytest.approx(0.5)
    assert tide["bkg"] == pytest.approx(0.5)
    assert all(tide[k] == 0.0 for k in TIDE_KEYS if k != "bkg")


SEG2_ITEMS = [
    {"file": "test/seg_thin.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [{"cls": 0, "shape": {"kind": "polygon",
                                   "points": [0.2, 0.2, 0.22, 0.2, 0.6, 0.58, 0.58, 0.6]}}]},
    {"file": "test/seg_box.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [{"cls": 1, "shape": {"kind": "polygon",
                                   "points": [0.2, 0.2, 0.6, 0.2, 0.6, 0.6, 0.2, 0.6]}}]},
]
SEG2_PREDS = {
    # boxes agree, masks do not: mask IoU ~0.07, so the helmet gt is missed and the box is bkg
    "seg_thin.jpg": [{"class": "helmet", "class_id": 0, "confidence": 0.9,
                      "x": 80, "y": 80, "width": 80, "height": 80,
                      "points": [{"x": 40, "y": 40}, {"x": 120, "y": 40},
                                 {"x": 120, "y": 120}, {"x": 40, "y": 120}]}],
    "seg_box.jpg": [{"class": "vest", "class_id": 1, "confidence": 0.9,
                     "x": 80, "y": 80, "width": 80, "height": 80,
                     "points": [{"x": 40, "y": 40}, {"x": 120, "y": 40},
                                {"x": 120, "y": 120}, {"x": 40, "y": 120}]}],
}


def test_tide_segm_uses_mask_iou(tmp_path, monkeypatch):
    """Boxes agree but masks do not: the mask-only error must reach a bucket, not read as zero."""
    root = make_version(tmp_path / "v1", SEG2_ITEMS)
    _use_model(monkeypatch, FakeModel(root, SEG2_PREDS))
    out = evaluate_mod.evaluate("ultralytics:yolo26n-seg", root, "segment")
    assert out["iou"] == "segm" and out["coco"]["AP50"] == pytest.approx(0.5)
    assert out["tide"]["missed"] == pytest.approx(0.5)
    assert all(out["tide"][k] == 0.0 for k in TIDE_KEYS if k != "missed")


MULTI_PART_REC = {
    "file": "test/multipart.jpg", "image_id": 1, "width": 200, "height": 200,
    # one gt mask in three vertical thirds: no single part reaches IoU 0.5, the union is exact
    "gt": [{"cls": "helmet", "bbox": [40, 40, 120, 120],
            "segm": [[40, 40, 80, 40, 80, 160, 40, 160],
                     [80, 40, 120, 40, 120, 160, 80, 160],
                     [120, 40, 160, 40, 160, 160, 120, 160]]}],
    "pred": [{"cls": "helmet", "conf": 0.9, "bbox": [40, 40, 120, 120],
              "points": [{"x": 40, "y": 40}, {"x": 160, "y": 40},
                         {"x": 160, "y": 160}, {"x": 40, "y": 160}]}],
}


def test_tide_mask_iou_merges_multi_part_gt():
    fixes, missed, _ = evaluate_mod._tide_classify(MULTI_PART_REC, "segm")
    assert fixes == [None]
    assert missed == []


def test_tide_mask_iou_accepts_rle_gt():
    from pycocotools import mask as mask_utils

    poly = [40, 40, 160, 40, 160, 160, 40, 160]
    rle = mask_utils.frPyObjects([poly], 200, 200)[0]
    rec = dict(MULTI_PART_REC)
    rec["gt"] = [{**MULTI_PART_REC["gt"][0], "segm": rle}]
    assert evaluate_mod._mask_iou(rle, poly, 200, 200) == pytest.approx(1.0)
    fixes, missed, _ = evaluate_mod._tide_classify(rec, "segm")
    assert fixes == [None]
    assert missed == []


EMPTY_GT_ITEMS = [
    {"file": "test/only_missed.jpg", "split": "test", "width": 200, "height": 200,
     "anns": [_ann(0, 0.20, 0.20, 0.20, 0.20)]},
]
# removing the only missed gt leaves an empty ground truth with a scored detection still present
EMPTY_GT_PREDS = {"only_missed.jpg": [_pred("helmet", 0.90, 150, 150, 30, 30)]}


def test_tide_missed_oracle_with_empty_ground_truth(tmp_path, monkeypatch):
    root = make_version(tmp_path / "v1", EMPTY_GT_ITEMS)
    _use_model(monkeypatch, FakeModel(root, EMPTY_GT_PREDS))
    out = evaluate_mod.evaluate("ultralytics:yolo26n", root, "object-detection")
    tide = out["tide"]
    assert tide["missed"] == 0.0
    assert all(tide[k] == 0.0 for k in TIDE_KEYS if k != "missed")


LOC_REC = {
    "file": "test/loc.jpg", "image_id": 1, "width": 200, "height": 200,
    "gt": [{"id": 1, "cls": "helmet", "bbox": [20, 20, 40, 40], "segm": None}],
    "pred": [{"cls": "helmet", "conf": 0.9, "bbox": [30, 30, 40, 40], "points": None}],
}


def test_tide_loc_error_covers_the_gt():
    """A loc error targets the gt, so that gt is not also reported as missed."""
    fixes, missed, tps = evaluate_mod._tide_classify(LOC_REC, "bbox")
    assert fixes == [("loc", 0)]
    assert missed == []
    assert tps == set()


def test_tide_fixed_segm_converts_uncompressed_rle_gt():
    """An uncompressed RLE gt must become a compressed RLE before it is reused as a fix."""
    rec = {"file": "test/rle_loc.jpg", "image_id": 1, "width": 4, "height": 4,
           # 2x2 block at rows 0-1 / cols 0-1, column-major run lengths
           "gt": [{"id": 1, "cls": "helmet", "bbox": [0, 0, 2, 2],
                   "segm": {"size": [4, 4], "counts": [0, 2, 2, 2, 10]}}],
           "pred": [{"cls": "helmet", "conf": 0.9, "bbox": [1, 0, 2, 2], "points": None}]}
    classified = evaluate_mod._tide_classify(rec, "segm")
    assert classified[0] == [("loc", 0)]
    out = evaluate_mod._tide_corrected([rec], [classified], {"helmet": 1}, "segm", "loc")
    seg = out[0]["segmentation"]
    assert isinstance(seg, dict)
    assert isinstance(seg["counts"], bytes)          # compressed, ready for COCO loadRes
