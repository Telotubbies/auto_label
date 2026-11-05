"""Workflow execution: model → filter → crop → second model/OCR → rule engine → sink."""
import os
import tempfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-wf-run-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from PIL import Image as PImage
from sqlalchemy import delete, select

from app.bootstrap import init_db
from app.config import DATA_DIR
from app.db import SessionLocal
from app.models import Image, LabelClass, Project, Workspace
from app.services import workflow_runner as runner
from app.services.workflows import validate_blocks

WS, PR = "labeldesk-demo", "ppe-detection"


@pytest.fixture(scope="module", autouse=True)
def _schema():
    init_db()
    yield


def _project(db) -> Project:
    ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
    return db.scalar(select(Project).where(Project.workspace_id == ws.id, Project.slug == PR))


class FakeResolved:
    def __init__(self, ref: str, fn, seen: list):
        self.ref, self.fn, self.seen = ref, fn, seen

    def predict(self, im, **kw):
        self.seen.append((self.ref, im.size, kw))
        return self.fn(self.ref, im, **kw)


def install(monkeypatch, fn):
    seen: list = []

    def fake_resolve(ref, db, *, workspace_id=None):
        seen.append(("resolve", ref, workspace_id))
        return FakeResolved(ref, fn, seen)

    monkeypatch.setattr(runner, "resolve", fake_resolve)
    return seen


def det(ref, cls, cx, cy, w, h, conf=0.9, size=(100, 100), points=None):
    W, H = size
    p = {"class": cls, "class_id": 0, "confidence": conf,
         "x": cx * W, "y": cy * H, "width": w * W, "height": h * H}
    if points:
        p["points"] = [{"x": x * W, "y": y * H} for x, y in points]
    return {"model": ref, "time": 0.01, "image": {"width": W, "height": H}, "predictions": [p]}


def test_filter_drops_other_classes_and_low_confidence(monkeypatch):
    def fn(ref, im, **kw):
        out = det(ref, "person", 0.2, 0.2, 0.1, 0.1, 0.9, im.size)
        out["predictions"] += det(ref, "person", 0.5, 0.5, 0.1, 0.1, 0.2, im.size)["predictions"]
        out["predictions"] += det(ref, "helmet", 0.8, 0.8, 0.1, 0.1, 0.9, im.size)["predictions"]
        return out

    install(monkeypatch, fn)
    blocks = validate_blocks([
        {"type": "model", "model_ref": "trained:a"},
        {"type": "filter", "classes": ["person"], "min_conf": 0.5},
        {"type": "sink", "kind": "response"},
    ])
    with SessionLocal() as db:
        out = runner.run(db, _project(db), blocks, PImage.new("RGB", (100, 100)))
    assert [d["class"] for d in out["detections"]] == ["person"]
    assert out["detections"][0]["confidence"] == pytest.approx(0.9)


def test_crop_runs_the_next_model_on_the_crop_and_maps_boxes_back(monkeypatch):
    def fn(ref, im, **kw):
        if ref == "trained:outer":
            return det(ref, "pallet", 0.5, 0.5, 0.4, 0.4, size=im.size)
        return det(ref, "box", 0.5, 0.5, 0.2, 0.2, size=im.size)

    seen = install(monkeypatch, fn)
    blocks = validate_blocks([
        {"type": "model", "model_ref": "trained:outer"},
        {"type": "crop", "expand": 0},
        {"type": "model", "model_ref": "trained:inner"},
        {"type": "sink", "kind": "response"},
    ])
    with SessionLocal() as db:
        out = runner.run(db, _project(db), blocks, PImage.new("RGB", (100, 100)))
    sizes = [(s[0], s[1]) for s in seen if s[0] != "resolve"]
    assert sizes == [("trained:outer", (100, 100)), ("trained:inner", (40, 40))]
    d = out["detections"][0]
    assert d["class"] == "box"
    assert d["x"] == pytest.approx(0.46) and d["y"] == pytest.approx(0.46)
    assert d["w"] == pytest.approx(0.08) and d["h"] == pytest.approx(0.08)
    assert out["detections"][0]["model"] == "trained:inner"


def test_a_second_crop_still_cuts_from_the_root_image(monkeypatch):
    def fn(ref, im, **kw):
        if ref == "trained:outer":
            return det(ref, "pallet", 0.5, 0.5, 0.4, 0.4, size=im.size)
        if ref == "trained:mid":
            return det(ref, "label", 0.5, 0.5, 0.5, 0.5, size=im.size)
        return det(ref, "line", 0.5, 0.5, 0.2, 0.2, size=im.size)

    seen = install(monkeypatch, fn)
    blocks = validate_blocks([
        {"type": "model", "model_ref": "trained:outer"},
        {"type": "crop", "expand": 0},
        {"type": "model", "model_ref": "trained:mid"},
        {"type": "crop", "expand": 0},
        {"type": "model", "model_ref": "trained:inner"},
        {"type": "sink", "kind": "response"},
    ])
    with SessionLocal() as db:
        runner.run(db, _project(db), blocks, PImage.new("RGB", (100, 100)))
    sizes = [(s[0], s[1]) for s in seen if s[0] != "resolve"]
    # The 40x40 crop holds a label at 0.4-0.6 of the root, so the next crop is 20x20 of the root.
    assert sizes == [("trained:outer", (100, 100)), ("trained:mid", (40, 40)), ("trained:inner", (20, 20))]


def test_ocr_block_collects_text(monkeypatch):
    def fn(ref, im, **kw):
        assert kw.get("prompt")
        return {"model": ref, "time": 0, "image": {"width": im.width, "height": im.height},
                "predictions": [], "text": "INV-0042"}

    install(monkeypatch, fn)
    blocks = validate_blocks([
        {"type": "ocr", "model_ref": "vlm:qwen2.5-vl-7b"},
        {"type": "sink", "kind": "response"},
    ])
    with SessionLocal() as db:
        out = runner.run(db, _project(db), blocks, PImage.new("RGB", (100, 100)))
    assert [t["text"] for t in out["texts"]] == ["INV-0042"]
    assert out["detections"] == []


def test_rule_count_uses_the_task10_engine(monkeypatch):
    def fn(ref, im, **kw):
        out = det(ref, "person", 0.2, 0.2, 0.1, 0.1, size=im.size)
        out["predictions"] += det(ref, "person", 0.6, 0.6, 0.1, 0.1, size=im.size)["predictions"]
        return out

    install(monkeypatch, fn)
    blocks = validate_blocks([
        {"type": "model", "model_ref": "trained:a"},
        {"type": "rule", "kind": "count", "class": "person", "k": 2, "op": ">=", "for_s": 0},
        {"type": "sink", "kind": "response"},
    ])
    with SessionLocal() as db:
        out = runner.run(db, _project(db), blocks, PImage.new("RGB", (100, 100)))
    assert out["events"] and out["events"][0]["kind"] == "count"
    assert "2 person" in out["events"][0]["summary"]


def test_rule_zone_fires_for_a_detection_inside_the_polygon(monkeypatch):
    install(monkeypatch, lambda ref, im, **kw: det(ref, "helmet", 0.5, 0.5, 0.1, 0.1, size=im.size))
    blocks = validate_blocks([
        {"type": "model", "model_ref": "trained:a"},
        {"type": "rule", "kind": "zone", "class": "helmet",
         "points": [0, 0, 1, 0, 1, 1, 0, 1]},
        {"type": "sink", "kind": "response"},
    ])
    with SessionLocal() as db:
        out = runner.run(db, _project(db), blocks, PImage.new("RGB", (100, 100)))
    assert out["events"][0]["kind"] == "zone"


def test_annotations_sink_writes_project_annotations(monkeypatch):
    install(monkeypatch, lambda ref, im, **kw: det(ref, "person", 0.5, 0.5, 0.2, 0.2, size=im.size))
    blocks = validate_blocks([
        {"type": "model", "model_ref": "trained:a"},
        {"type": "sink", "kind": "annotations"},
    ])
    rel = "workflow-test/frame.jpg"
    path = DATA_DIR / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    PImage.new("RGB", (100, 100)).save(path, "JPEG")
    with SessionLocal() as db:
        project = _project(db)
        person = db.scalar(select(LabelClass).where(LabelClass.project_id == project.id,
                                                    LabelClass.name == "person"))
        row = Image(project_id=project.id, name="frame.jpg", sha256="0" * 64, width=100, height=100,
                    path=rel, thumb=rel, size=10)
        db.add(row)
        db.commit()
        try:
            out = runner.run(db, project, blocks, PImage.open(path).convert("RGB"), image_row=row)
            assert out["annotations_added"] == 1
            db.expire_all()
            saved = db.get(Image, row.id)
            assert len(saved.annotations) == 1
            assert saved.annotations[0]["classId"] == person.id
            assert saved.annotations[0]["source"] == "trained:a"
        finally:
            db.execute(delete(Image).where(Image.id == row.id))
            db.commit()


def test_resolve_is_scoped_to_the_workspace(monkeypatch):
    seen = install(monkeypatch, lambda ref, im, **kw: det(ref, "person", 0.5, 0.5, 0.1, 0.1, size=im.size))
    blocks = validate_blocks([{"type": "model", "model_ref": "trained:a"},
                              {"type": "sink", "kind": "response"}])
    with SessionLocal() as db:
        project = _project(db)
        runner.run(db, project, blocks, PImage.new("RGB", (100, 100)))
        assert ("resolve", "trained:a", project.workspace_id) in seen


def test_annotations_sink_requires_a_project_image(monkeypatch):
    install(monkeypatch, lambda ref, im, **kw: det(ref, "person", 0.5, 0.5, 0.1, 0.1, size=im.size))
    blocks = validate_blocks([{"type": "model", "model_ref": "trained:a"},
                              {"type": "sink", "kind": "annotations"}])
    with SessionLocal() as db, pytest.raises(ValueError, match="project image"):
        runner.run(db, _project(db), blocks, PImage.new("RGB", (100, 100)))
