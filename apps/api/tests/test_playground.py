import io
import os
import tempfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp())
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage

from app.adapters import ADAPTERS, Availability, validate_prediction
from app.main import app

WS = "labeldesk-demo"
URL = f"/api/ws/{WS}/playground/predict"


class FakeAd:
    def __init__(self, family, fail=False, caps=("detect",), boom: Exception | None = None):
        self.family, self.fail, self.caps, self.calls, self.boom = family, fail, set(caps), [], boom

    def probe(self):
        return Availability(True)

    def capabilities(self, variant):
        return self.caps

    def predict(self, variant, im, *, classes=None, prompt=None, weights=None, conf=0.4, iou=0.5):
        self.calls.append({"classes": classes, "prompt": prompt, "conf": conf})
        if self.boom:
            raise self.boom
        if self.fail:
            raise RuntimeError("vLLM not reachable at http://x")
        base = {"model": f"{self.family}:{variant}", "time": 0.01, "image": {"width": im.width, "height": im.height}}
        if prompt:
            return {**base, "predictions": [], "text": "two helmets"}
        return {**base, "predictions": [{"class": "a", "class_id": 0, "confidence": 0.8, "x": 5, "y": 5,
                                         "width": 4, "height": 4}]}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as cl:     # one login per module: the login endpoint is rate limited
        tok = cl.post("/api/auth/login", json={"email": "demo@labeldesk.dev", "password": "demo1234"}).json()["token"]
        cl.headers["Authorization"] = f"Bearer {tok}"
        yield cl


@pytest.fixture
def c(client, monkeypatch):
    fakes = {"ok": FakeAd("ok"), "bad": FakeAd("bad", fail=True), "vlm": FakeAd("vlm", caps=("vlm", "detect"))}
    for k, v in fakes.items():
        monkeypatch.setitem(ADAPTERS, k, v)
    client.fakes = fakes
    return client


def img():
    b = io.BytesIO()
    PImage.new("RGB", (32, 32)).save(b, "PNG")
    return {"file": ("a.png", b.getvalue(), "image/png")}


def post(c, refs, **data):
    return c.post(URL, files=img(), data={"model_refs": refs, **data})


def test_rejects_more_than_three_refs(c):
    assert post(c, "ok:a,ok:b,ok:c,ok:d").status_code == 400
    assert post(c, "").status_code == 400


def test_one_failing_model_does_not_fail_others(c):
    r = post(c, "ok:det,bad:x")
    assert r.status_code == 200
    ok, bad = r.json()["results"]
    assert ok["error"] is None and len(ok["prediction"]["predictions"]) == 1 and ok["latency_ms"] >= 0
    assert bad["error"] == "model unavailable" and bad["prediction"] is None


def test_vlm_question_returns_text(c):
    res = post(c, "vlm:q", prompt="how many helmets?").json()["results"][0]
    assert res["prediction"]["text"] == "two helmets" and res["error"] is None
    assert c.fakes["vlm"].calls[-1]["prompt"] == "how many helmets?"


def test_vlm_grounding_needs_classes_and_gets_them(c):
    assert "classes" in post(c, "vlm:q").json()["results"][0]["error"]
    r = post(c, "vlm:q", classes="helmet, vest")
    assert r.json()["results"][0]["error"] is None
    assert c.fakes["vlm"].calls[-1]["classes"] == ["helmet", "vest"]


def test_unknown_ref_is_per_model_error(c):
    res = post(c, "nope:x,ok:det").json()["results"]
    assert res[0]["error"] == "model unavailable" and res[1]["error"] is None


def test_unexpected_failure_is_reported_generically(c, monkeypatch):
    monkeypatch.setitem(ADAPTERS, "boom", FakeAd("boom", boom=KeyError("/srv/secret/weights.pt")))
    res = post(c, "boom:x").json()["results"][0]
    assert res["error"] == "inference failed" and res["prediction"] is None


def test_duplicate_refs_are_deduped(c):
    res = post(c, "ok:det,ok:det").json()["results"]
    assert len(res) == 1 and res[0]["error"] is None


def test_upload_is_exif_oriented(c):
    im = PImage.new("RGB", (40, 20), "red")
    exif = im.getexif()
    exif[274] = 6                                  # rotate 90° CW on display
    buf = io.BytesIO()
    im.save(buf, "JPEG", exif=exif)
    r = c.post(URL, files={"file": ("a.jpg", buf.getvalue(), "image/jpeg")}, data={"model_refs": "ok:det"})
    assert r.json()["results"][0]["prediction"]["image"] == {"width": 20, "height": 40}


@pytest.fixture
def trained_rows():
    """A ready model in another workspace and a still-training one here; both removed afterwards."""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Project, TrainedModel, Version, Workspace

    with SessionLocal() as db:
        proj = db.scalar(select(Project).where(Project.slug == "ppe-detection"))
        demo = db.scalar(select(Workspace).where(Workspace.slug == WS))
        other = Workspace(slug="isolation-check", name="Isolation check", owner_id=demo.owner_id)
        ver = Version(project_id=proj.id, number=990001, name="isolation", status="ready")
        db.add_all([other, ver])
        db.flush()
        rows = [TrainedModel(id="isofix-foreign-ready-00000000001", workspace_id=other.id, project_id=proj.id,
                             version_id=ver.id, name="other workspace", arch="yolo26n", task="detect",
                             status="ready", family="ultralytics", variant="yolo26n", weights="models/o/best.pt"),
                TrainedModel(id="isofix-demo-training-00000000002", workspace_id=demo.id, project_id=proj.id,
                             version_id=ver.id, name="still training", arch="yolo26n", task="detect",
                             status="training", family="ultralytics", variant="yolo26n", weights="models/t/best.pt")]
        db.add_all(rows)
        db.commit()
        ids, ver_id, ws_id = [r.id for r in rows], ver.id, other.id
    yield ids
    with SessionLocal() as db:
        for mid in ids:
            row = db.get(TrainedModel, mid)
            if row:
                db.delete(row)
        db.commit()
        for row in (db.get(Version, ver_id), db.get(Workspace, ws_id)):
            if row:
                db.delete(row)
        db.commit()


def test_trained_model_from_another_workspace_is_not_resolved(c, monkeypatch, trained_rows):
    fake = FakeAd("ultralytics")
    monkeypatch.setitem(ADAPTERS, "ultralytics", fake)
    res = post(c, f"trained:{trained_rows[0]}").json()["results"][0]
    assert res["prediction"] is None and "unknown trained model" in res["error"]
    assert fake.calls == []


def test_model_that_is_not_ready_is_not_resolved(c, monkeypatch, trained_rows):
    fake = FakeAd("ultralytics")
    monkeypatch.setitem(ADAPTERS, "ultralytics", fake)
    res = post(c, f"trained:{trained_rows[1]}").json()["results"][0]
    assert res["prediction"] is None and "unknown trained model" in res["error"]
    assert fake.calls == []


def test_confidence_is_forwarded(c):
    post(c, "ok:det", confidence="0.6")
    assert c.fakes["ok"].calls[-1]["conf"] == 0.6


def test_world_model_without_classes_is_per_model_error(c):
    assert "classes" in post(c, "ok:yolov8s-worldv2").json()["results"][0]["error"]
    r = post(c, "ok:yolov8s-worldv2", classes="helmet, vest")
    assert r.json()["results"][0]["error"] is None
    assert c.fakes["ok"].calls[-1]["classes"] == ["helmet", "vest"]


def test_annotator_may_use_playground(c):     # the c fixture installs the fake adapters
    anon = TestClient(app)      # the login endpoint is rate limited: one login per user per module
    tok = anon.post("/api/auth/login", json={"email": "labeler@labeldesk.dev", "password": "demo1234"}).json()["token"]
    r = anon.post(URL, files=img(), data={"model_refs": "ok:det"},
                  headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, r.text


def test_playground_charges_no_credits(c):
    before = c.get(f"/api/ws/{WS}").json()["usage"]["credits_used"]
    post(c, "ok:det,vlm:q", classes="helmet", prompt="how many?")
    assert c.get(f"/api/ws/{WS}").json()["usage"]["credits_used"] == before


def test_classification_prediction_is_valid():
    d = {"model": "x:cls", "image": {"width": 1, "height": 1}, "time": 0.1,
         "predictions": [{"class": "cat", "class_id": 0, "confidence": 0.9}], "top": {"class": "cat"}}
    validate_prediction(d)
    with pytest.raises(ValueError):
        validate_prediction({k: v for k, v in d.items() if k != "top"})
