"""OBB and keypoint annotations: validation, imaging helpers and exporter/importer round-trips."""
import json
import math
import os
import tempfile
from pathlib import Path

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-test-"))
os.environ.setdefault("LD_EMBEDDED_WORKER", "1")
os.environ.setdefault("LD_WORKER_TOKEN", "test-worker-token-0123456789abcdef")
os.environ.setdefault("LD_SAM_ENABLED", "0")

import pytest
from fastapi import HTTPException
from PIL import Image as PImage

from app.routers.images import _check_ann
from app.routers.projects import _clean_skeleton
from app.services import exporters, imaging, importers

TOL = 1e-3


def _jpg(path: Path, size: tuple[int, int] = (200, 100)):
    path.parent.mkdir(parents=True, exist_ok=True)
    PImage.new("RGB", size, (30, 60, 90)).save(path, "JPEG")


def _export(version_dir: Path, fmt: str, out: Path) -> importers.Bundle:
    exporters.build_dir(fmt, version_dir, out)
    files = [(p.relative_to(out).as_posix(), p.read_bytes()) for p in sorted(out.rglob("*")) if p.is_file()]
    return importers.collect(files)


def _angle_diff(a: float, b: float) -> float:
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


def _ann(shape: dict, **extra) -> dict:
    return {"id": "a1", "classId": "c1", "shape": shape, **extra}


# --- geometry ---------------------------------------------------------------------------------

def test_obb_corners_use_pixel_space():
    s = {"kind": "obb", "cx": 0.5, "cy": 0.5, "w": 0.4, "h": 0.2, "angle": 0.0}

    assert imaging.obb_corners(s, 200, 100) == pytest.approx([(60, 40), (140, 40), (140, 60), (60, 60)])

    rotated = imaging.obb_corners({**s, "angle": math.pi / 2}, 200, 100)
    assert rotated[0] == pytest.approx((110, 10))


def test_bbox_of_handles_obb_and_keypoints():
    obb = {"shape": {"kind": "obb", "cx": 0.5, "cy": 0.5, "w": 0.4, "h": 0.2, "angle": 0.0}}
    assert imaging.bbox_of(obb) == pytest.approx((0.3, 0.4, 0.4, 0.2))

    kps = {"shape": {"kind": "keypoints",
                     "points": [0.1, 0.2, 2, 0.3, 0.4, 1, 0.9, 0.9, 0, 0.5, 0.6, 2]}}
    assert imaging.bbox_of(kps) == pytest.approx((0.1, 0.2, 0.4, 0.4))


# --- shape validation -------------------------------------------------------------------------

def test_check_ann_accepts_obb_and_keypoints_with_tracking():
    obb = _check_ann(_ann({"kind": "obb", "cx": 0.5, "cy": 0.5, "w": 0.2, "h": 0.1, "angle": 0.3},
                          keyframe=True, trackId="t" * 80))
    assert obb["shape"] == {"kind": "obb", "cx": 0.5, "cy": 0.5, "w": 0.2, "h": 0.1, "angle": 0.3}
    assert obb["keyframe"] is True
    assert obb["trackId"] == "t" * 64

    kps = _check_ann(_ann({"kind": "keypoints", "points": [0.1, 0.2, 0, 0.3, 0.4, 1, 0.5, 0.6, 2]},
                          keyframe=False, trackId="person-7"))
    assert kps["shape"]["kind"] == "keypoints"
    assert kps["shape"]["points"] == pytest.approx([0.1, 0.2, 0, 0.3, 0.4, 1, 0.5, 0.6, 2])
    assert kps["shape"]["points"][2] == 0 and isinstance(kps["shape"]["points"][2], int)
    assert kps["keyframe"] is False
    assert kps["trackId"] == "person-7"


@pytest.mark.parametrize("shape", [
    {"kind": "obb", "cx": 0.5, "cy": 0.5, "w": 0.2, "h": 0.1},                      # missing angle
    {"kind": "obb", "cx": 0.5, "cy": 0.5, "w": 0.2, "h": 0.1, "angle": 7.0},        # outside ±2π
    {"kind": "obb", "cx": 0.5, "cy": 0.5, "w": "wide", "h": 0.1, "angle": 0.0},     # non-numeric
    {"kind": "obb", "cx": 0.5, "cy": 0.5, "w": 0.2, "h": 0.1, "angle": float("nan")},
    {"kind": "keypoints", "points": [0.1, 0.2]},                                    # too short
    {"kind": "keypoints", "points": [0.1, 0.2, 2, 0.3]},                            # not triples
    {"kind": "keypoints", "points": [0.1, 0.2, 3]},                                 # visibility out of range
    {"kind": "keypoints", "points": ["x", 0.2, 2]},                                 # non-numeric
    {"kind": "keypoints", "points": [0.5] * 3003},                                  # > 1000 points
])
def test_check_ann_rejects_malformed_obb_and_keypoints(shape):
    with pytest.raises(HTTPException) as err:
        _check_ann(_ann(shape))
    assert err.value.status_code == 400


def test_clean_skeleton_strips_and_drops_unknown_keys():
    raw = {"names": ["nose", " eye ", "ear"], "edges": [[0, 1], [1, 2]], "flip_idx": [2, 1, 0], "extra": True}
    assert _clean_skeleton(raw) == {"names": ["nose", "eye", "ear"], "edges": [[0, 1], [1, 2]],
                                    "flip_idx": [2, 1, 0]}
    assert _clean_skeleton(None) is None


@pytest.mark.parametrize("raw", [
    {"names": []},
    {"names": ["a", "a"]},
    {"names": ["x" * 61]},
    {"names": ["a"], "edges": [[0, 0]]},
    {"names": ["a", "b"], "edges": [[0, 2]]},
    {"names": ["a", "b"], "edges": [[0]]},
    {"names": ["a", "b"], "flip_idx": [0]},
    {"names": ["a"], "edges": [[0, 1]]},
])
def test_clean_skeleton_rejects_bad_schema(raw):
    with pytest.raises(ValueError):
        _clean_skeleton(raw)


# --- export / import --------------------------------------------------------------------------

def test_new_formats_registered():
    assert exporters.FORMATS["yolo_obb"]["tasks"] == ["object-detection"]
    assert "keypoint-detection" in exporters.FORMATS["coco_keypoints"]["tasks"]
    assert exporters.EXPORTERS["yolo_obb"] is exporters.export_yolo_obb
    assert exporters.EXPORTERS["coco_keypoints"] is exporters.export_coco_keypoints


def test_yolo_obb_roundtrip(tmp_path):
    version_dir, out = tmp_path / "version", tmp_path / "out"
    _jpg(version_dir / "train" / "a.jpg")
    _jpg(version_dir / "valid" / "b.jpg", (100, 100))
    obb = {"kind": "obb", "cx": 0.55, "cy": 0.45, "w": 0.3, "h": 0.2, "angle": 0.4}
    (version_dir / "manifest.json").write_text(json.dumps({
        "classes": ["car"], "type": "object-detection", "skeletons": [None],
        "items": [
            {"file": "train/a.jpg", "split": "train", "width": 200, "height": 100,
             "anns": [{"cls": 0, "shape": obb}]},
            {"file": "valid/b.jpg", "split": "valid", "width": 100, "height": 100,
             "anns": [{"cls": 0, "shape": {"kind": "bbox", "x": 0.2, "y": 0.3, "w": 0.4, "h": 0.2}}]},
        ],
    }))

    bundle = _export(version_dir, "yolo_obb", out)

    assert bundle.task == "obb"
    assert (out / "data.yaml").read_text().splitlines()[-1] == "task: obb"

    got_a = importers.annotations_for(bundle, "train/images/a.jpg", 200, 100)
    assert [name for name, _ in got_a] == ["car"]
    shape = got_a[0][1]
    assert shape["kind"] == "obb"
    for key in ("cx", "cy", "w", "h"):
        assert shape[key] == pytest.approx(obb[key], abs=TOL)
    assert _angle_diff(shape["angle"], obb["angle"]) < TOL

    got_b = importers.annotations_for(bundle, "valid/images/b.jpg", 100, 100)
    assert got_b[0][1] == pytest.approx({"kind": "obb", "cx": 0.4, "cy": 0.4, "w": 0.4, "h": 0.2, "angle": 0.0})


def test_coco_keypoints_roundtrip(tmp_path):
    version_dir, out = tmp_path / "version", tmp_path / "out"
    _jpg(version_dir / "train" / "pose.jpg")
    points = [0.25, 0.3, 2, 0.5, 0.4, 1, 0.6, 0.5, 2]
    skeleton = {"names": ["nose", "eye", "ear"], "edges": [[0, 1], [1, 2]]}
    (version_dir / "manifest.json").write_text(json.dumps({
        "classes": ["person"], "type": "keypoint-detection", "skeletons": [skeleton],
        "items": [{"file": "train/pose.jpg", "split": "train", "width": 200, "height": 100,
                   "anns": [{"cls": 0, "shape": {"kind": "keypoints", "points": points}}]}],
    }))

    bundle = _export(version_dir, "coco_keypoints", out)

    coco = json.loads((out / "train" / "_annotations.coco.json").read_text())
    cat = coco["categories"][0]
    assert cat["keypoints"] == ["nose", "eye", "ear"]
    assert cat["skeleton"] == [[1, 2], [2, 3]]
    assert coco["annotations"][0]["num_keypoints"] == 3
    assert coco["annotations"][0]["bbox"] == pytest.approx([50, 30, 70, 20])

    got = importers.annotations_for(bundle, "train/pose.jpg", 200, 100)
    assert [(name, shape["kind"]) for name, shape in got] == [("person", "keypoints")]
    assert got[0][1]["points"] == pytest.approx(points, abs=TOL)
    assert bundle.skeletons["person"] == skeleton
