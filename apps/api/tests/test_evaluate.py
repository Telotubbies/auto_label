"""Evaluation service: COCO metrics, confidence sweep, confusion matrix, per-image detail."""
import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-test-"))
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
