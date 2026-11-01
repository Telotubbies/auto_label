"""Auto-label v2: model_ref, SAM refinement, VLM verify, prompt parsing, preview and `source`."""
import io
import os
import tempfile
import time
import uuid

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-test-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import select

from app.adapters import ADAPTERS, Availability
from app.db import SessionLocal
from app.main import app
from app.models import User
from app.security import issue_access

WS = "labeldesk-demo"
THAI = "หมวกนิรภัย"


@pytest.fixture(scope="module")
def c():
    # Mint the token directly instead of spending one of the shared login rate-limit slots
    # the other test modules need (all of them log in as the same demo user).
    with TestClient(app) as client:
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
        client.headers["Authorization"] = f"Bearer {issue_access(user.id)}"
        yield client


def jpeg(color=(200, 50, 50)) -> bytes:
    b = io.BytesIO(); PImage.new("RGB", (320, 240), color).save(b, "JPEG"); return b.getvalue()


def wait_job(c, base, jid, timeout=90):
    t = time.time()
    while time.time() - t < timeout:
        j = c.get(f"{base}/jobs/{jid}").json()
        if j["status"] in ("done", "failed", "cancelled"):
            return j
        time.sleep(0.25)
    raise TimeoutError(jid)


def run_job(c, base, payload):
    r = c.post(f"{base}/autolabel", json=payload)
    assert r.status_code == 200, r.text
    return wait_job(c, base, r.json()["id"])


@pytest.fixture(scope="module")
def scratch(c):
    """A throwaway detection project with 4 fresh images — seeded images are never touched."""
    name = f"autolabel-v2-{uuid.uuid4().hex[:8]}"
    p = c.post(f"/api/ws/{WS}/projects", json={"name": name, "type": "object-detection",
                                               "classes": ["person", THAI, "safety vest"]}).json()
    base = f"/api/ws/{WS}/projects/{p['slug']}"
    files = [("files", (f"v2-{i}.jpg", jpeg((10 + i * 40, 60, 90)))) for i in range(4)]
    up = c.post(f"{base}/upload", files=files, data={"split": "train", "batch_name": "autolabel v2"})
    assert up.status_code == 200 and up.json()["uploaded"] == 4, up.text
    classes = {x["name"]: x["id"] for x in c.get(f"{base}/classes").json()}
    yield {"id": p["id"], "slug": p["slug"], "base": base, "images": [x["id"] for x in up.json()["images"]],
           "classes": classes}
    c.delete(base)


def _usage(c):
    return c.get(f"/api/ws/{WS}/usage").json()["credits_used"]


def _saved(project_id):
    from app.db import SessionLocal
    from app.models import Image
    with SessionLocal() as s:
        return [a for img in s.scalars(select(Image).where(Image.project_id == project_id)) for a in img.annotations or []]


def _saved_for(image_id):
    from app.db import SessionLocal
    from app.models import Image
    with SessionLocal() as s:
        return list(s.get(Image, image_id).annotations or [])


# --- fakes -----------------------------------------------------------------------------

def box(cls="person", conf=0.9):
    return {"class": cls, "class_id": 0, "confidence": conf, "x": 50.0, "y": 40.0,
            "width": 30.0, "height": 20.0}


class FakeDetector:
    family = "ultralytics"

    def __init__(self, preds=None):
        self.preds = [box()] if preds is None else preds

    def probe(self):
        return Availability(True)

    def capabilities(self, variant):
        return {"detect"}

    def predict(self, variant, im, *, classes=None, prompt=None, weights=None, conf=0.4, iou=0.5):
        return {"predictions": [dict(p) for p in self.preds], "time": 0.0,
                "image": {"width": im.width, "height": im.height}}


class FakeSam:
    family = "sam3"

    def __init__(self):
        self.prompts = []

    def probe(self):
        return Availability(True)

    def capabilities(self, variant):
        return {"segment"}

    def segment_box(self, im, box_xyxy):
        return [0.1, 0.1, 0.9, 0.1, 0.9, 0.9, 0.1, 0.9], 0.8

    def predict(self, variant, im, *, classes=None, prompt=None, weights=None, conf=0.4, iou=0.5):
        self.prompts = list(classes or [])
        return {"model": f"sam3:{variant}", "predictions": [], "time": 0.0,
                "image": {"width": im.width, "height": im.height}}


class FakeVlm:
    family = "vlm"
    url = "http://localhost:8000/v1"

    def __init__(self, preds=None, phrases=None, fail_after=None, verify_result=True, echo_classes=False):
        self.preds = [box()] if preds is None else preds
        self.phrases = phrases or []
        self.fail_after = fail_after
        self.verify_result = verify_result
        self.echo_classes = echo_classes
        self.ground_classes = []
        self.calls = 0

    def probe(self):
        return Availability(True)

    def capabilities(self, variant):
        return {"detect", "open-vocab"}

    def ground(self, im, classes):
        self.calls += 1
        self.ground_classes = list(classes)
        if self.fail_after is not None and self.calls > self.fail_after:
            raise httpx.ConnectError("vLLM went away")
        preds = ([{**box(), "class": c, "class_id": i} for i, c in enumerate(classes)]
                 if self.echo_classes else [dict(p) for p in self.preds])
        return {"model": "vlm:qwen2.5-vl-7b", "predictions": preds, "time": 0.0,
                "image": {"width": im.width, "height": im.height}}

    def verify(self, im, box_xyxy, cls):
        return self.verify_result

    def parse_prompt(self, text):
        return list(self.phrases)


# --- tests -----------------------------------------------------------------------------

def test_vlm_ref_without_sam_is_rejected(c, scratch):
    r = c.post(f"{scratch['base']}/autolabel", json={"model_ref": "vlm:qwen2.5-vl-7b"})
    assert r.status_code == 400 and "SAM" in r.json()["detail"]


def test_preview_writes_nothing_and_charges_nothing(c, scratch, monkeypatch):
    monkeypatch.setitem(ADAPTERS, "ultralytics", FakeDetector())
    before, saved_before = _usage(c), _saved(scratch["id"])
    r = c.post(f"{scratch['base']}/autolabel/preview",
               json={"model_ref": "ultralytics:yolo26n", "sample": 4, "only_unannotated": False,
                     "image_ids": scratch["images"]})
    assert r.status_code == 200, r.text
    out = r.json()
    assert len(out["images"]) == 4 and all(x["annotations"] for x in out["images"])
    assert all(x["url"] for x in out["images"])
    assert sum(out["counts"].values()) == sum(len(x["annotations"]) for x in out["images"])
    assert _saved(scratch["id"]) == saved_before
    assert _usage(c) == before


def test_vlm_confidence_is_fixed_half(c, scratch, monkeypatch):
    monkeypatch.setitem(ADAPTERS, "vlm", FakeVlm(preds=[box(conf=0.9)]))
    monkeypatch.setitem(ADAPTERS, "sam3", FakeSam())
    img_id = scratch["images"][0]
    j = run_job(c, scratch["base"], {"model_ref": "vlm:qwen2.5-vl-7b", "confidence": 0.95,
                                     "only_unannotated": False, "image_ids": [img_id]})
    assert j["status"] == "done", j
    anns = _saved_for(img_id)
    assert anns and all(a["source"] == "vlm+sam3" for a in anns)
    assert all(a["confidence"] == 0.5 for a in anns)          # no calibrated score, threshold not applied


def test_vlm_verify_drops_rejected_boxes(c, scratch, monkeypatch):
    monkeypatch.setitem(ADAPTERS, "ultralytics", FakeDetector())
    monkeypatch.setitem(ADAPTERS, "vlm", FakeVlm(verify_result=False))
    j = run_job(c, scratch["base"], {"model_ref": "ultralytics:yolo26n", "vlm_verify": True,
                                     "only_unannotated": False, "image_ids": [scratch["images"][3]]})
    assert j["status"] == "done" and j["result"]["annotations"] == 0
    assert _saved_for(scratch["images"][3]) == []


def test_annotations_carry_source(c, scratch, monkeypatch):
    monkeypatch.setitem(ADAPTERS, "ultralytics", FakeDetector())
    ids = scratch["images"][1:3]
    j = run_job(c, scratch["base"], {"model_ref": "ultralytics:yolo26n", "only_unannotated": False, "image_ids": ids})
    assert j["status"] == "done", j
    anns = [a for i in ids for a in _saved_for(i)]
    assert anns and all(a["source"] == "ultralytics:yolo26n" for a in anns)


def test_zero_annotations_not_charged(c, scratch, monkeypatch):
    monkeypatch.setitem(ADAPTERS, "ultralytics", FakeDetector(preds=[]))
    before = _usage(c)
    j = run_job(c, scratch["base"], {"model_ref": "ultralytics:yolo26n", "only_unannotated": False,
                                     "image_ids": [scratch["images"][3]]})
    assert j["status"] == "done" and j["result"]["annotations"] == 0
    assert _usage(c) == before


def test_vlm_ground_keeps_thai_and_multiword_labels(c, scratch, monkeypatch):
    vlm = FakeVlm(echo_classes=True)
    monkeypatch.setitem(ADAPTERS, "vlm", vlm)
    monkeypatch.setitem(ADAPTERS, "sam3", FakeSam())
    ids = [scratch["classes"][THAI], scratch["classes"]["safety vest"]]
    img_id = scratch["images"][3]
    j = run_job(c, scratch["base"], {"model_ref": "vlm:qwen2.5-vl-7b", "class_ids": ids,
                                     "only_unannotated": False, "image_ids": [img_id]})
    assert j["status"] == "done", j
    assert vlm.ground_classes == [THAI, "safety vest"]          # enum goes out verbatim
    assert {a["classId"] for a in _saved_for(img_id)} == set(ids)   # and maps back to the right classes


def test_vlm_down_mid_batch_fails_readably(c, scratch, monkeypatch):
    ids = scratch["images"][:2]
    monkeypatch.setitem(ADAPTERS, "vlm", FakeVlm(fail_after=1))
    monkeypatch.setitem(ADAPTERS, "sam3", FakeSam())
    before = _usage(c)
    j = run_job(c, scratch["base"], {"model_ref": "vlm:qwen2.5-vl-7b", "only_unannotated": False,
                                     "image_ids": ids})
    assert j["status"] == "failed"
    assert "vLLM not reachable" in j["error"] and "Traceback" not in j["error"]
    assert any(a["source"] == "vlm+sam3" for a in _saved(scratch["id"]))
    # the one image labeled before the failure is still billed
    assert _usage(c) - before == pytest.approx(0.01)


def test_thai_class_names_reach_sam_prompts(c, scratch, monkeypatch):
    sam = FakeSam()
    monkeypatch.setitem(ADAPTERS, "sam3", sam)
    j = run_job(c, scratch["base"], {"model_ref": "sam3:sam3.1", "class_ids": [scratch["classes"][THAI]],
                                     "only_unannotated": False, "image_ids": scratch["images"][:1]})
    assert j["status"] == "done", j
    assert sam.prompts == [THAI]


def test_prompt_parser_feeds_sam(c, scratch, monkeypatch):
    sam = FakeSam()
    monkeypatch.setitem(ADAPTERS, "sam3", sam)
    monkeypatch.setitem(ADAPTERS, "vlm", FakeVlm(phrases=["workers", "helmets"]))
    j = run_job(c, scratch["base"], {"model_ref": "sam3:sam3.1", "prompt": "workers without helmets",
                                     "class_ids": [scratch["classes"][THAI]],
                                     "only_unannotated": False, "image_ids": scratch["images"][:1]})
    assert j["status"] == "done", j
    assert sam.prompts == ["workers", "helmets"]


def test_ready_trained_model_in_registry(c, scratch):
    from app.db import SessionLocal
    from app.models import TrainedModel, Version, Workspace
    with SessionLocal() as s:
        ws = s.scalar(select(Workspace).where(Workspace.slug == WS))
        v = Version(project_id=scratch["id"], number=1, name="registry test")
        s.add(v); s.flush()
        m = TrainedModel(workspace_id=ws.id, project_id=scratch["id"], version_id=v.id, name="v2 registry",
                         arch="yolo26n", task="detect", status="ready", family="ultralytics", variant="yolo26n")
        s.add(m); s.commit()
        mid = m.id
    try:
        refs = {i["ref"] for i in c.get(f"/api/ws/{WS}/registry").json()}
        assert f"trained:{mid}" in refs
    finally:
        with SessionLocal() as s:
            s.delete(s.get(TrainedModel, mid)); s.commit()


def test_review_sort_paginates_with_offset(c, scratch):
    cid = scratch["classes"]["person"]
    shape = {"kind": "bbox", "x": .1, "y": .1, "w": .3, "h": .3}
    # low-confidence AI, then vlm+sam3, then two plain detections
    for k, (img_id, conf, source) in enumerate(zip(
            scratch["images"], (0.2, 0.5, 0.9, 0.9), ("ultralytics:yolo26n", "vlm+sam3",
                                                      "ultralytics:yolo26n", "ultralytics:yolo26n"))):
        ann = [{"id": f"pg{k}", "classId": cid, "shape": shape, "confidence": conf, "source": source}]
        assert c.put(f"/api/images/{img_id}/annotations", json={"annotations": ann}).status_code == 200
    url = f"{scratch['base']}/images"
    page1 = c.get(url, params={"sort": "review", "limit": 2, "offset": 0}).json()["items"]
    page2 = c.get(url, params={"sort": "review", "limit": 2, "offset": 2}).json()["items"]
    ids = [x["id"] for x in page1 + page2]
    assert ids[:2] == scratch["images"][:2]              # low confidence, then vlm+sam3
    assert len(ids) == 4 and set(ids) == set(scratch["images"])
