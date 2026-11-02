"""Adapter protocol, catalog and registry."""
import os
import time

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import create_engine, inspect, select

from app.adapters import ADAPTERS, parse_ref, validate_prediction
from app.bootstrap import ensure_columns
from app.main import app

WS = "labeldesk-demo"


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        tok = client.post("/api/auth/login", json={"email": "demo@labeldesk.dev", "password": "demo1234"}).json()["token"]
        client.headers["Authorization"] = f"Bearer {tok}"
        yield client


def test_parse_ref():
    assert parse_ref("ultralytics:rtdetr-l") == ("ultralytics", "rtdetr-l")
    assert parse_ref("trained:abc123") == ("trained", "abc123")
    with pytest.raises(ValueError):
        parse_ref("rtdetr")


def test_catalog_lists_families_with_license(c):
    items = c.get(f"/api/ws/{WS}/registry").json()
    refs = {i["ref"] for i in items}
    assert {"ultralytics:yolo26n", "ultralytics:rtdetr-l", "ultralytics:yolov8s-worldv2", "sam3:sam3.1", "vlm:qwen2.5-vl-7b"} <= refs
    assert all(i["license"] for i in items)
    sam = next(i for i in items if i["ref"] == "sam3:sam3.1")
    assert sam["available"] is False and "LD_SAM_ENABLED" in sam["reason"]
    vlm = next(i for i in items if i["ref"] == "vlm:qwen2.5-vl-7b")
    assert vlm["kind"] == "vlm" and vlm["license"] == "Apache-2.0"  # availability depends on a live vLLM
    assert "yolo26l" not in {i["variant"] for i in items}


def test_every_available_adapter_returns_valid_schema():
    im = PImage.new("RGB", (64, 48))
    for fam, ad in ADAPTERS.items():
        if ad.probe().ok and fam == "ultralytics":
            validate_prediction(ad.predict("yolo26n", im))


def test_validate_prediction_rejects_bad_payload():
    good = {"model": "x:y", "image": {"width": 1, "height": 1}, "time": 0.1, "predictions": []}
    validate_prediction(good)
    with pytest.raises(ValueError):
        validate_prediction({**good, "predictions": [{"class": "a"}]})
    with pytest.raises(ValueError):
        validate_prediction({k: v for k, v in good.items() if k != "model"})


def test_sam3_segment_box_without_sam():
    assert ADAPTERS["sam3"].segment_box(PImage.new("RGB", (64, 48)), (1, 1, 30, 30)) == (None, 0.0)


def test_ensure_columns_is_idempotent(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path/'x.db'}")
    with eng.begin() as cn:
        cn.exec_driver_sql("CREATE TABLE t (id TEXT)")
    ensure_columns(eng, "t", {"family": "VARCHAR(32) DEFAULT 'ultralytics'"})
    ensure_columns(eng, "t", {"family": "VARCHAR(32)"})
    assert "family" in [col["name"] for col in inspect(eng).get_columns("t")]


# --- resolve / Resolved / YOLO-World vocabulary ---------------------------------------

class _FakeModel:
    def __init__(self, log):
        self.log = log
        self.vocab = None

    def set_classes(self, classes):
        self.vocab = list(classes)


@pytest.fixture
def fake_loader(monkeypatch):
    from app.adapters import ultralytics_ad as ul
    calls, model = [], _FakeModel([])
    monkeypatch.setattr(ul, "_load", lambda weights, cls="YOLO": calls.append((weights, cls)) or model)
    monkeypatch.setattr(ul, "_run", lambda m, im, conf, iou: {
        "predictions": [], "time": 0.0, "image": {"width": im.width, "height": im.height}, "vocab": list(m.vocab or [])})
    return calls, model


class _FakeDb:
    """resolve() only needs db.get(TrainedModel, id)."""
    def __init__(self, row):
        self.row = row

    def get(self, _model, _id):
        return self.row


def _trained_db(**kw):
    from app.models import TrainedModel
    m = TrainedModel(id="abc123", workspace_id="w", project_id="p", version_id="v", name="t", arch="l",
                     task=kw.pop("task", "detect"), status="done", weights="models/x/best.pt", **kw)
    return _FakeDb(m)


def test_resolve_trained_rtdetr_keeps_variant_and_class(fake_loader):
    from app.adapters import resolve
    calls, _ = fake_loader
    r = resolve("trained:abc123", _trained_db(variant="rtdetr-l"))
    assert (r.variant, r.weights, r.ref) == ("rtdetr-l", "models/x/best.pt", "trained:abc123")
    out = r.predict(PImage.new("RGB", (8, 8)))
    assert calls[-1][1] == "RTDETR" and calls[-1][0].endswith("best.pt")
    assert out["model"] == "trained:abc123"


def test_resolve_old_trained_row_derives_variant_from_task():
    from app.adapters import resolve
    assert resolve("trained:abc123", _trained_db(variant="", task="segment")).variant == "yolo26n-seg"
    assert resolve("trained:abc123", _trained_db(variant="", task="classify")).variant == "yolo26n-cls"
    assert resolve("trained:abc123", _trained_db(variant="", task="detect")).variant == "yolo26n"


def test_resolve_zoo_ref_has_no_weights():
    from app.adapters import resolve
    r = resolve("ultralytics:rtdetr-l", _FakeDb(None))
    assert (r.variant, r.weights, r.ref) == ("rtdetr-l", None, "ultralytics:rtdetr-l")


def test_yolo_world_requires_classes(fake_loader):
    with pytest.raises(ValueError, match="YOLO-World needs classes"):
        ADAPTERS["ultralytics"].predict("yolov8s-worldv2", PImage.new("RGB", (8, 8)))


def test_yolo_world_calls_see_their_own_vocabulary(fake_loader):
    ad, im = ADAPTERS["ultralytics"], PImage.new("RGB", (8, 8))
    assert ad.predict("yolov8s-worldv2", im, classes=["cat"])["vocab"] == ["cat"]
    assert ad.predict("yolov8s-worldv2", im, classes=["dog", "car"])["vocab"] == ["dog", "car"]


# --- Task 2: train families, run cap, resume ----------------------------------------------

PR = "ppe-detection"
BASE = f"/api/ws/{WS}/projects/{PR}"


def wait_job(c, jid, timeout=900):
    t = time.time()
    while time.time() - t < timeout:
        j = c.get(f"{BASE}/jobs/{jid}").json()
        if j["status"] in ("done", "failed", "cancelled"):
            assert j["status"] == "done", j
            return j
        time.sleep(1)
    raise TimeoutError(jid)


@pytest.fixture(scope="module")
def version_id(c):
    imgs = c.get(f"{BASE}/images", params={"status": "review"}).json()["items"]
    if imgs:    # approve the seeded batch so a version has data (standalone-safe)
        cls = c.get(f"{BASE}/classes").json()[0]
        ann = [{"id": "x1", "classId": cls["id"], "shape": {"kind": "bbox", "x": .1, "y": .1, "w": .3, "h": .3}}]
        c.put(f"/api/images/{imgs[0]['id']}/annotations", json={"annotations": ann})
        c.post(f"/api/images/{imgs[0]['id']}/review", json={"approved": True})
        c.post(f"{BASE}/board/move", json={"batch_id": imgs[0]["batchId"], "from_status": "review", "to_status": "done"})
    v = c.post(f"{BASE}/versions", json={"settings": {
        "split": {"train": 70, "valid": 20, "test": 10},
        "preprocessing": {"resize": {"width": 320, "height": 320, "mode": "fit"}},
        "augmentation": {"outputs": 1}}}).json()
    wait_job(c, v["job"]["id"])
    yield v["id"]
    if imgs:    # hand the seeded batch back to review so other modules see the original state
        c.post(f"{BASE}/board/move", json={"batch_id": imgs[0]["batchId"], "from_status": "done", "to_status": "review"})


def test_train_options_groups_families(c):
    o = c.get(f"{BASE}/train/options").json()
    fams = {f["family"]: f for f in o["families"]}
    assert {"yolo", "rtdetr", "yolo-world"} <= set(fams)
    assert fams["rtdetr"]["license"] == "AGPL-3.0"
    assert all({"label", "available", "reason", "variants"} <= set(f) for f in fams.values())
    assert fams["rtdetr"]["variants"][0]["id"] == "rtdetr-l"


@pytest.mark.slow
def test_train_rtdetr_one_epoch_cpu(c, version_id, tmp_path, monkeypatch):
    if os.environ.get("LD_SLOW_TESTS") != "1":
        pytest.skip("slow: set LD_SLOW_TESTS=1 to run (downloads rtdetr-l.pt, trains on CPU)")
    monkeypatch.chdir(tmp_path)
    try:
        from ultralytics.utils.downloads import attempt_download_asset
        attempt_download_asset("rtdetr-l.pt")
    except Exception as e:
        pytest.skip(f"rtdetr-l.pt unavailable offline: {e}")
    if not (tmp_path / "rtdetr-l.pt").exists():
        pytest.skip("rtdetr-l.pt could not be downloaded (offline)")
    m = c.post(f"{BASE}/train", json={"version_id": version_id, "family": "ultralytics", "variant": "rtdetr-l",
                                      "epochs": 1, "imgsz": 160, "batch": 2}).json()
    assert m["arch"] == "rtdetr-l"
    wait_job(c, m["jobId"])
    assert c.get(f"{BASE}/models/{m['id']}").json()["status"] == "ready"


def test_max_minutes_stops_and_keeps_best(c, version_id, monkeypatch):
    from app.adapters import ultralytics_ad as ul
    ticks = iter([0.0])
    monkeypatch.setattr(ul, "_now", lambda: next(ticks, 1e9))      # deadline set at t=0, passed by the first check
    m = c.post(f"{BASE}/train", json={"version_id": version_id, "variant": "yolo26n", "epochs": 3, "imgsz": 160,
                                      "batch": 4, "max_minutes": 1}).json()
    wait_job(c, m["jobId"])
    got = c.get(f"{BASE}/models/{m['id']}").json()
    assert got["status"] == "ready" and [h["epoch"] for h in got["history"]] == [1] and got["weightsUrl"]


def test_old_size_field_still_works(c, version_id):
    m = c.post(f"{BASE}/train", json={"version_id": version_id, "size": "n", "epochs": 1, "imgsz": 160, "batch": 4}).json()
    assert m["variant"] == "yolo26n" and m["family"] == "ultralytics" and m["license"] == "AGPL-3.0"
    wait_job(c, m["jobId"])


def test_resume_from_continues_from_last_weights(c, version_id):
    parent = c.post(f"{BASE}/train", json={"version_id": version_id, "epochs": 1, "imgsz": 160, "batch": 4}).json()
    wait_job(c, parent["jobId"])
    child = c.post(f"{BASE}/train", json={"version_id": version_id, "epochs": 1, "imgsz": 160, "batch": 4,
                                          "resume_from": parent["id"]}).json()
    wait_job(c, child["jobId"])
    assert c.get(f"{BASE}/models/{child['id']}").json()["status"] == "ready"
    assert c.post(f"{BASE}/train", json={"version_id": version_id, "resume_from": "nope"}).status_code == 400


def test_bad_variant_and_max_minutes_rejected(c, version_id):
    assert c.post(f"{BASE}/train", json={"version_id": version_id, "variant": "gpt-9"}).status_code == 400
    assert c.post(f"{BASE}/train", json={"version_id": version_id, "max_minutes": 0}).status_code == 400


def test_remote_worker_mode_rejects_unsupported_options(c, version_id, monkeypatch):
    from app.routers import training
    monkeypatch.setattr(training, "LOCAL_JOB_KINDS", ["version", "export", "autolabel"])
    for body in ({"variant": "rtdetr-l"}, {"variant": "yolov8s-worldv2"}, {"variant": "yolo11s"},
                 {"max_minutes": 5}, {"resume_from": "any-model"}):
        r = c.post(f"{BASE}/train", json={"version_id": version_id, **body})
        assert r.status_code == 400 and r.json()["detail"] == "not supported on remote GPU workers yet", body


def test_remote_worker_mode_queues_size_for_yolo26(c, version_id, monkeypatch):
    from app import worker
    from app.routers import training
    off = ["version", "export", "autolabel"]
    monkeypatch.setattr(training, "LOCAL_JOB_KINDS", off)
    monkeypatch.setattr(worker, "LOCAL_JOB_KINDS", off)      # keep the embedded worker off this job
    m = c.post(f"{BASE}/train", json={"version_id": version_id, "variant": "yolo26s", "epochs": 1, "imgsz": 160,
                                      "batch": 4}).json()
    j = c.get(f"{BASE}/jobs/{m['jobId']}").json()
    assert j["params"]["options"]["variant"] == "yolo26s" and j["params"]["options"]["size"] == "s"
    assert c.post(f"{BASE}/jobs/{m['jobId']}/cancel").json()["status"] == "cancelled"


def test_resume_from_rejects_other_project_and_workspace(c, version_id):
    from app.db import SessionLocal
    from app.models import Project, TrainedModel, Workspace, new_id
    with SessionLocal() as s:
        ws = s.scalar(select(Workspace).where(Workspace.slug == WS))
        other = Project(workspace_id=ws.id, slug=f"other-{new_id()}", name="Other")
        ws2 = Workspace(id=new_id(), slug=f"ws-{new_id()}", name="Other WS", owner_id=ws.owner_id)
        s.add_all([other, ws2]); s.flush()
        common = dict(task="detect", status="ready", arch="yolo26n", family="ultralytics", variant="yolo26n",
                      license="AGPL-3.0", classes=[], version_id=version_id)
        foreign_project = TrainedModel(workspace_id=ws.id, project_id=other.id, name="other-project", **common)
        foreign_ws = TrainedModel(workspace_id=ws2.id, project_id=other.id, name="other-workspace", **common)
        s.add_all([foreign_project, foreign_ws]); s.commit()
        ids = (foreign_project.id, foreign_ws.id)
    for mid in ids:
        assert c.post(f"{BASE}/train", json={"version_id": version_id, "resume_from": mid}).status_code == 400

