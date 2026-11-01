"""Task 10b contract tests: stream CRUD, live views, rules, events and shutdown behaviour."""
import io
import os
import secrets
import tempfile
import threading
import time
import uuid

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-test-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage

from app.config import DATA_DIR
from app.main import app

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/ws/{WS}/projects/{PR}/streams"
PROJECT = f"/api/ws/{WS}/projects/{PR}"

LINE_RULE = {"kind": "line", "class": "person", "line": [0, .5, 1, .5], "direction": "both"}


@pytest.fixture(scope="module")
def c():
    # unique client host: the in-process login limiter is keyed by ip+email and every test
    # module logs in, so a shared host would starve later modules of their login budget
    with TestClient(app, client=("streams-test", 50000)) as client:
        tok = client.post("/api/auth/login", json={"email": "demo@labeldesk.dev", "password": "demo1234"}).json()["token"]
        client.headers["Authorization"] = f"Bearer {tok}"
        yield client
    from app.streams.manager import manager
    manager.stop_all()


def jpeg(color=None) -> bytes:
    """Solid-colour JPEG; random by default so it cannot dedupe against another module's upload."""
    if color is None:
        color = (secrets.randbelow(256), secrets.randbelow(256), secrets.randbelow(256))
    b = io.BytesIO()
    PImage.new("RGB", (320, 240), color).save(b, "JPEG")
    return b.getvalue()


def _poll(fn, timeout=10.0, interval=0.2):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        last = fn()
        if last:
            return last
        time.sleep(interval)
    raise AssertionError(f"condition not met within {timeout}s (last={last!r})")


def _status_is(c, sid, want):
    def check():
        j = c.get(f"{BASE}/{sid}").json()
        return j if j.get("status") == want else None
    return check


def create_stream(c, **kw) -> str:
    body = {"name": "Test stream", "source": "file:videos/none.mp4", "model_ref": "ultralytics:yolo11n"}
    body.update(kw)
    r = c.post(BASE, json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _write_video(name: str, seconds: float = 4.0, fps: int = 10, size=(160, 120)):
    (DATA_DIR / "videos").mkdir(parents=True, exist_ok=True)
    base = DATA_DIR / "videos" / name
    for suffix, fourcc in ((".avi", "MJPG"), (".mp4", "mp4v")):
        path = base.with_suffix(suffix)
        vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*fourcc), fps, size)
        if not vw.isOpened():
            vw.release()
            continue
        for i in range(int(seconds * fps)):
            frame = np.full((size[1], size[0], 3), 30, np.uint8)
            x = int((i / max(1, int(seconds * fps) - 1)) * (size[0] - 30))
            cv2.rectangle(frame, (x, 40), (x + 30, 100), (220, 60, 60), -1)
            vw.write(frame)
        vw.release()
        if path.stat().st_size > 0:
            return path
        path.unlink(missing_ok=True)
    raise RuntimeError("could not write a test video")


def _unlink(path):
    """Windows keeps a capture handle briefly after release; retry instead of failing teardown."""
    for _ in range(30):
        try:
            path.unlink(missing_ok=True)
            return
        except PermissionError:
            time.sleep(0.1)


@pytest.fixture
def video():
    path = _write_video(f"src-{uuid.uuid4().hex[:8]}")
    yield f"file:videos/{path.name}"
    _unlink(path)


class _FakeModel:
    variant = "yolo11n"

    def __init__(self):
        self.calls = 0

    def predict(self, im, **kw):
        self.calls += 1
        step = self.calls % 12
        y = .15 + .7 * step / 11
        return {"predictions": [{"class": "person", "confidence": .9, "x": im.width * .5, "y": im.height * y,
                                 "width": im.width * .2, "height": im.height * .2}],
                "image": {"width": im.width, "height": im.height}, "time": 0.0}


def _fake_resolve(ref, db=None, workspace_id=None):
    return _FakeModel()


def test_stop_returns_when_source_never_opens(c):
    sid = create_stream(c, source="rtsp://10.255.255.1/none")
    assert c.post(f"{BASE}/{sid}/start").status_code == 200
    # Review Focus 4: the bad source must be visible before stop, not just a final "stopped".
    j = _poll(_status_is(c, sid, "reconnecting"), timeout=20)
    assert "10.255.255.1" in j["lastError"]
    t = time.time()
    assert c.post(f"{BASE}/{sid}/stop").status_code == 200
    assert time.time() - t < 5
    assert c.get(f"{BASE}/{sid}").json()["status"] == "stopped"
    from app.streams.manager import manager
    assert manager.status(sid) is None
    _poll(lambda: not any(t.name.startswith(f"stream-{sid}-") for t in threading.enumerate()), timeout=5)


def test_deleted_video_reports_error(c):
    sid = create_stream(c, source="file:videos/definitely-missing.mp4")
    assert c.post(f"{BASE}/{sid}/start").status_code == 200
    j = _poll(_status_is(c, sid, "error"), timeout=10)
    assert "definitely-missing.mp4" in j["lastError"]


def test_rejects_sam_as_stream_model(c):
    for ref in ("sam3:sam3.1", "vlm:qwen2.5-vl-7b"):
        r = c.post(BASE, json={"name": "Bad", "source": "file:videos/none.mp4", "model_ref": ref})
        assert r.status_code == 400, (ref, r.text)


def test_rejects_malformed_rules(c):
    zones = [{"id": "z1", "points": [0, 0, .5, 0, .5, .5, 0, .5]}]
    for rules in ([{"kind": "line", "class": "person"}],
                  [{"kind": "nope"}],
                  [{"kind": "zone", "class": "person", "zone_id": "unknown"}]):
        r = c.post(BASE, json={"name": "Bad rules", "source": "file:videos/none.mp4",
                               "model_ref": "ultralytics:yolo11n", "zones": zones, "rules": rules})
        assert r.status_code == 400, (rules, r.text)


def test_mjpeg_requires_valid_token(c):
    sid = create_stream(c)
    assert c.get(f"{BASE}/{sid}/mjpeg").status_code == 403
    assert c.get(f"{BASE}/{sid}/mjpeg?token=garbage").status_code == 403
    assert c.get(f"{BASE}/{sid}/frame?token=garbage").status_code == 403


@pytest.fixture
def fake_event(c):
    sid = create_stream(c, name="Event stream")
    eid = "ev" + secrets.token_hex(4)
    folder = DATA_DIR / "streams" / sid
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{eid}.jpg").write_bytes(jpeg())

    from app.db import SessionLocal
    from app.models import StreamEvent
    with SessionLocal() as db:
        db.add(StreamEvent(id=eid, stream_id=sid, ts=time.time(),
                           rule={"index": 0, "kind": "zone", "class": "person", "label": "person in z1"},
                           summary="person in zone z1", snapshot_path=f"streams/{sid}/{eid}.jpg", predictions=[]))
        db.commit()
    yield {"sid": sid, "eid": eid}
    c.delete(f"{BASE}/{sid}")


def test_event_reviewed_toggle(c, fake_event):
    url = f"{BASE}/{fake_event['sid']}/events/{fake_event['eid']}"
    r = c.patch(url, json={"reviewed": True})
    assert r.status_code == 200 and r.json()["reviewed"] is True
    assert c.patch(url, json={"reviewed": False}).json()["reviewed"] is False
    evs = c.get(f"{BASE}/{fake_event['sid']}/events", params={"reviewed": "no"}).json()
    assert evs["total"] == 1 and any(e["id"] == fake_event["eid"] for e in evs["items"])


def test_event_filters_by_rule_class_and_reviewed(c, fake_event):
    base = f"{BASE}/{fake_event['sid']}/events"
    assert [e["id"] for e in c.get(base, params={"rule": 0}).json()["items"]] == [fake_event["eid"]]
    assert c.get(base, params={"rule": 1}).json()["items"] == []
    assert c.get(base, params={"rule": "person"}).json()["items"][0]["id"] == fake_event["eid"]
    assert c.get(base, params={"class": "person"}).json()["items"][0]["id"] == fake_event["eid"]
    assert c.get(base, params={"class": "helmet"}).json()["total"] == 0
    assert c.get(base, params={"reviewed": "no"}).json()["items"][0]["id"] == fake_event["eid"]
    c.patch(f"{base}/{fake_event['eid']}", json={"reviewed": True})
    assert c.get(base, params={"reviewed": "yes"}).json()["items"][0]["id"] == fake_event["eid"]
    assert c.get(base, params={"reviewed": "no"}).json()["total"] == 0
    assert c.get(base, params={"reviewed": "maybe"}).status_code == 400


def test_events_total_and_offset(c, fake_event):
    from app.db import SessionLocal
    from app.models import StreamEvent
    sid = fake_event["sid"]
    with SessionLocal() as db:
        for _ in range(2):
            db.add(StreamEvent(stream_id=sid, ts=time.time(), rule={"index": 1, "kind": "count"},
                               summary="count", predictions=[]))
        db.commit()
    base = f"{BASE}/{sid}/events"
    page = c.get(base, params={"offset": 1, "limit": 1}).json()
    assert page["total"] == 3 and len(page["items"]) == 1
    assert c.get(base, params={"limit": 2}).json()["total"] == 3


def test_event_to_dataset_creates_image(c, fake_event):
    before = c.get(f"{PROJECT}/images", params={"tag": "stream"}).json()["total"]
    url = f"{BASE}/{fake_event['sid']}/events/{fake_event['eid']}/to-dataset"
    r = c.post(url)
    assert r.status_code == 200, r.text
    assert r.json()["uploaded"] == 1
    after = c.get(f"{PROJECT}/images", params={"tag": "stream"}).json()["total"]
    assert after == before + 1
    assert c.post(url).json()["duplicates"] == 1


def test_upload_video_returns_file_source(c):
    path = _write_video(f"upload-{uuid.uuid4().hex[:8]}", seconds=1.0)
    try:
        data = path.read_bytes()
    finally:
        path.unlink(missing_ok=True)
    r = c.post(f"{BASE}/upload-video", files={"file": ("clip.avi", data, "video/x-msvideo")})
    assert r.status_code == 200, r.text
    source = r.json()["source"]
    assert source.startswith("file:videos/")
    assert (DATA_DIR / source[len("file:"):]).is_file()


def test_stream_end_to_end_line_crossing(c, monkeypatch, video):
    monkeypatch.setattr("app.streams.manager.resolve", _fake_resolve)
    sid = create_stream(c, source=video, sample_fps=10, rules=[LINE_RULE])
    assert c.post(f"{BASE}/{sid}/start").status_code == 200
    _poll(_status_is(c, sid, "live"), timeout=10)
    evs = _poll(lambda: c.get(f"{BASE}/{sid}/events").json()["items"] or None, timeout=25)
    ev = evs[0]
    assert ev["rule"]["kind"] == "line"
    assert ev["snapshot"]
    shot = c.get(ev["snapshot"])
    assert shot.status_code == 200 and shot.content[:2] == b"\xff\xd8"
    # the status panel must show the demo video at its real rate (the window needs a couple of seconds)
    _poll(lambda: (j if (j := c.get(f"{BASE}/{sid}").json())["fps"] >= 5 else None), timeout=10)
    assert c.post(f"{BASE}/{sid}/stop").status_code == 200
    assert c.get(f"{BASE}/{sid}").json()["status"] == "stopped"


class _GpuBusyOnce(_FakeModel):
    def __init__(self):
        super().__init__()
        self.busy = True

    def predict(self, im, **kw):
        if self.busy:
            self.busy = False
            from app.gpu import GpuBusy
            raise GpuBusy("GPU busy: train")
        return super().predict(im, **kw)


def test_gpu_busy_pauses_then_resumes(c, monkeypatch, video):
    monkeypatch.setattr("app.streams.manager.resolve", lambda *a, **k: _GpuBusyOnce())
    sid = create_stream(c, source=video, sample_fps=10)
    assert c.post(f"{BASE}/{sid}/start").status_code == 200
    j = _poll(_status_is(c, sid, "paused (GPU busy)"), timeout=10)
    assert "GPU busy" in j["lastError"]
    j = _poll(_status_is(c, sid, "live"), timeout=10)
    assert j["lastError"] == ""                     # the stale warning must clear on recovery
    assert c.post(f"{BASE}/{sid}/stop").status_code == 200


def test_pause_all_reports_gpu_busy(c, monkeypatch, video):
    monkeypatch.setattr("app.streams.manager.resolve", _fake_resolve)
    from app.gpu import scheduler
    from app.streams.manager import manager
    # Training takes the GPU through scheduler.exclusive, which must call these exact hooks.
    assert scheduler._pause == manager.pause_all and scheduler._resume == manager.resume_all
    sid = create_stream(c, source=video, sample_fps=10)
    assert c.post(f"{BASE}/{sid}/start").status_code == 200
    _poll(_status_is(c, sid, "live"), timeout=10)
    manager.pause_all()
    assert c.get(f"{BASE}/{sid}").json()["status"] == "paused (GPU busy)"
    manager.resume_all()
    _poll(_status_is(c, sid, "live"), timeout=10)
    assert c.post(f"{BASE}/{sid}/stop").status_code == 200


def test_tracker_never_shares_a_track_id_within_a_frame():
    from app.streams.manager import _Tracker
    tracker = _Tracker()
    boxes = [[.35, .5], [.40, .5], [.45, .5], [.50, .5]]
    for t in range(4):
        preds = [{"class": "person", "x": x, "y": y, "width": .2, "height": .2} for x, y in boxes]
        tracker.update(t, preds)
        assert len({p["track_id"] for p in preds}) == len(preds)


def test_model_unavailable_stays_error(c, monkeypatch, video):
    # Review Focus 4: a dead model must never be resurrected to "live" by the grabber.
    def broken(*_a, **_k):
        raise ValueError("unknown trained model 'gone'")
    monkeypatch.setattr("app.streams.manager.resolve", broken)
    sid = create_stream(c, source=video, sample_fps=10)
    assert c.post(f"{BASE}/{sid}/start").status_code == 200
    j = _poll(_status_is(c, sid, "error"), timeout=10)
    assert "unknown trained model" in j["lastError"]
    time.sleep(1.2)
    assert c.get(f"{BASE}/{sid}").json()["status"] == "error"
    assert c.post(f"{BASE}/{sid}/stop").json()["status"] == "stopped"


def test_patch_zones_cannot_orphan_rules(c):
    zones = [{"id": "z1", "points": [0, 0, .5, 0, .5, .5, 0, .5]}]
    sid = create_stream(c, zones=zones, rules=[{"kind": "zone", "class": "person", "zone_id": "z1"}])
    r = c.patch(f"{BASE}/{sid}", json={"zones": [{"id": "z2", "points": [0, 0, .4, 0, .4, .4]}]})
    assert r.status_code == 400 and "z1" in r.json()["detail"]
    assert c.get(f"{BASE}/{sid}").json()["zones"][0]["id"] == "z1"


def test_zone_ids_must_be_unique(c):
    z = [{"id": "z1", "points": [0, 0, .5, 0, .5, .5]}, {"id": "z1", "points": [0, 0, .4, 0, .4, .4]}]
    r = c.post(BASE, json={"name": "Dup", "source": "file:videos/none.mp4",
                           "model_ref": "ultralytics:yolo11n", "zones": z})
    assert r.status_code == 400 and "duplicate" in r.json()["detail"]


def test_rtsp_credentials_are_masked(c):
    sid = create_stream(c, source="rtsp://alice:s3cret@cam.local/live")
    body = c.get(f"{BASE}/{sid}").json()
    assert "s3cret" not in body["source"] and "***@" in body["source"]
    from app.streams.manager import display_source
    assert display_source("rtsp://alice:s3cret@cam.local/live") == "rtsp://***@cam.local/live"


def test_file_source_cannot_escape_data_dir(c):
    sid = create_stream(c, source="file:../../outside.mp4")
    assert c.post(f"{BASE}/{sid}/start").status_code == 200
    j = _poll(_status_is(c, sid, "error"), timeout=10)
    assert "outside.mp4" in j["lastError"]
    assert str(DATA_DIR) not in j["lastError"]          # no server paths in user-facing errors
    c.post(f"{BASE}/{sid}/stop")


def test_frame_is_scoped_and_token_bound(c):
    sid = create_stream(c)
    other = create_stream(c, name="Other")
    frame = c.get(f"{BASE}/{sid}").json()["frame"]
    assert c.get(frame).status_code == 503              # scoped + valid token, but stopped: no frame
    token = frame.split("token=", 1)[1]
    wrong_project = frame.replace(f"/ws/{WS}/projects/{PR}/", f"/ws/{WS}/projects/other-project/")
    assert c.get(wrong_project).status_code == 404
    other_path = f"{BASE}/{other}/frame?token={token}"
    assert c.get(other_path).status_code == 403         # token bound to its stream


def test_uploaded_video_is_removed_with_the_stream(c):
    path = _write_video(f"cleanup-{uuid.uuid4().hex[:8]}", seconds=1.0)
    try:
        data = path.read_bytes()
    finally:
        path.unlink(missing_ok=True)
    up = c.post(f"{BASE}/upload-video", files={"file": ("clip.avi", data, "video/x-msvideo")}).json()
    stored = DATA_DIR / up["source"][len("file:"):]
    sid = create_stream(c, source=up["source"])
    assert c.delete(f"{BASE}/{sid}").status_code == 200
    assert not stored.exists()
