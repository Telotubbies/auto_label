"""Task 10b contract tests: stream CRUD, live views, rules, events and shutdown behaviour."""
import io
import os
import secrets
import tempfile
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

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


def test_unreadable_video_reports_error_instead_of_reconnecting_forever(c):
    """Finding M4: a corrupt upload is a fatal file error, not an endless 'reconnecting'."""
    (DATA_DIR / "videos").mkdir(parents=True, exist_ok=True)
    bad = DATA_DIR / "videos" / f"corrupt-{uuid.uuid4().hex[:8]}.mp4"
    bad.write_bytes(b"this is not an mp4 container" * 64)
    try:
        sid = create_stream(c, source=f"file:videos/{bad.name}")
        assert c.post(f"{BASE}/{sid}/start").status_code == 200
        j = _poll(_status_is(c, sid, "error"), timeout=20)
        assert bad.name in j["lastError"]
        time.sleep(1.5)
        assert c.get(f"{BASE}/{sid}").json()["status"] == "error"
    finally:
        _unlink(bad)


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
    expired = f"exp={int(time.time()) - 60}&sig=deadbeef&viewer=x"
    assert c.get(f"{BASE}/{sid}/frame?{expired}").status_code == 403


def test_view_urls_are_signed_for_the_viewing_user(c):
    """Finding 1: the minted footage URL names its viewer and verifies only for that viewer."""
    from app.security import check_signature

    me = c.get("/api/me").json()["id"]
    sid = create_stream(c, name="Signed view")
    body = c.get(f"{BASE}/{sid}").json()
    for kind in ("mjpeg", "frame"):
        query = dict(parse_qsl(urlsplit(body[kind]).query))
        assert query.get("viewer") == me, (kind, body[kind])
        assert query.get("exp") and query.get("sig"), (kind, body[kind])
        rel = f"ws/{WS}/projects/{PR}/streams/{sid}/{kind}"
        assert check_signature(rel, int(query["exp"]), query["sig"], me)
        assert not check_signature(rel, int(query["exp"]), query["sig"], "someone-else")
        assert not check_signature(rel.replace(sid, "other-stream"), int(query["exp"]), query["sig"], me)


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
                           summary="person in zone z1", snapshot_path=f"streams/{sid}/{eid}.jpg",
                           predictions=[], rule_index=0, rule_kind="zone", rule_label="person in z1",
                           classes="|person|"))
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


def _sql_spy():
    """Collect SELECT statements issued against stream_events (Finding I4 is about SQL, not Python)."""
    from sqlalchemy import event

    from app.db import engine
    seen: list[str] = []

    def spy(_conn, _cursor, statement, _params, _context, _many):
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", spy)
    return seen, lambda: event.remove(engine, "before_cursor_execute", spy)


def test_events_page_query_uses_sql_limit_and_offset(c, fake_event):
    base = f"{BASE}/{fake_event['sid']}/events"
    seen, stop = _sql_spy()
    try:
        assert c.get(base, params={"limit": 10, "offset": 5}).status_code == 200
    finally:
        stop()
    pages = [s for s in seen if "stream_events" in s and "ORDER BY" in s.upper()]
    assert pages, seen
    assert all("LIMIT" in s.upper() and "OFFSET" in s.upper() for s in pages), pages


def test_events_paginate_without_gaps_or_duplicates(c, fake_event):
    from app.db import SessionLocal
    from app.models import StreamEvent
    sid = fake_event["sid"]
    now = time.time()
    with SessionLocal() as db:
        for n in range(24):
            db.add(StreamEvent(stream_id=sid, ts=now - n, rule={"index": 0, "kind": "zone", "class": "person"},
                               summary=f"e{n}", predictions=[]))
        db.commit()
    base = f"{BASE}/{sid}/events"
    first = c.get(base, params={"limit": 10}).json()
    second = c.get(base, params={"limit": 10, "offset": 10}).json()
    third = c.get(base, params={"limit": 10, "offset": 20}).json()
    assert first["total"] == second["total"] == third["total"] == 25
    ids = [e["id"] for e in first["items"] + second["items"] + third["items"]]
    assert len(ids) == 25 and len(set(ids)) == 25
    stamps = [e["ts"] for e in first["items"]]
    assert stamps == sorted(stamps, reverse=True)


def test_stream_events_index_covers_stream_and_ts():
    from sqlalchemy import inspect as sa_inspect

    from app.db import engine
    indexes = [tuple(i["column_names"]) for i in sa_inspect(engine).get_indexes("stream_events")]
    assert ("stream_id", "ts") in indexes, indexes


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
    from app.db import SessionLocal
    from app.models import StreamEvent
    with SessionLocal() as db:
        row = db.get(StreamEvent, ev["id"])
        assert row.clean_path and (DATA_DIR / row.clean_path).is_file()
        assert row.clean_path != row.snapshot_path
    # the status panel must show the demo video at its real rate (the window needs a couple of seconds)
    _poll(lambda: (j if (j := c.get(f"{BASE}/{sid}").json())["fps"] >= 5 else None), timeout=10)
    # events recorded by the real pipeline are filterable in SQL (rule index, kind, label, classes)
    for params in ({"kind": "line"}, {"class": "person"}, {"rule": 0}, {"rule": "line"}):
        page = c.get(f"{BASE}/{sid}/events", params=params).json()
        assert any(e["id"] == ev["id"] for e in page["items"]), (params, page)
    assert c.post(f"{BASE}/{sid}/stop").status_code == 200
    assert c.get(f"{BASE}/{sid}").json()["status"] == "stopped"


def test_frame_view_is_attributed_to_the_signed_viewer(c, monkeypatch, video):
    """Finding 1 end to end: a watched frame is audited to the user its URL was signed for."""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Audit

    monkeypatch.setattr("app.streams.manager.resolve", _fake_resolve)
    me = c.get("/api/me").json()["id"]
    sid = create_stream(c, source=video, sample_fps=10, name="Attributed view")
    assert c.post(f"{BASE}/{sid}/start").status_code == 200
    _poll(_status_is(c, sid, "live"), timeout=10)
    _poll(lambda: c.get(f"{BASE}/{sid}").json()["frames"] > 0, timeout=10)
    frame = c.get(f"{BASE}/{sid}").json()["frame"]
    auth = c.headers.pop("Authorization")                # the URL alone must identify the viewer
    try:
        assert c.get(frame).status_code == 200
        swapped = frame.replace(f"viewer={me}", "viewer=someone-else")
        assert c.get(swapped).status_code == 403         # a swapped viewer no longer verifies
    finally:
        c.headers["Authorization"] = auth
    with SessionLocal() as db:
        row = db.scalar(select(Audit).where(Audit.action == "stream.view", Audit.target == sid)
                        .order_by(Audit.created.desc()))
        assert row is not None and row.user_id == me, row
        assert row.meta["via"] == "frame"
    assert c.post(f"{BASE}/{sid}/stop").status_code == 200


def test_event_snapshots_live_under_the_project_folder(c, monkeypatch, video):
    """Finding 2: footage lives under snapshots/<project id>/ so retention can attribute and delete it."""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Project, StreamEvent

    monkeypatch.setattr("app.streams.manager.resolve", _fake_resolve)
    rule = {"kind": "count", "class": "person", "op": ">=", "k": 1, "for_s": 0}
    sid = create_stream(c, source=video, sample_fps=10, name="Scoped snapshots", rules=[rule])
    assert c.post(f"{BASE}/{sid}/start").status_code == 200
    evs = _poll(lambda: c.get(f"{BASE}/{sid}/events").json()["items"] or None, timeout=25)
    with SessionLocal() as db:
        pid = db.scalar(select(Project.id).where(Project.slug == PR))
        row = db.get(StreamEvent, evs[0]["id"])
        assert row.snapshot_path.startswith(f"snapshots/{pid}/"), row.snapshot_path
        assert row.clean_path.startswith(f"snapshots/{pid}/"), row.clean_path
        assert Path(row.snapshot_path).parent == Path(row.clean_path).parent
        written = [DATA_DIR / row.snapshot_path, DATA_DIR / row.clean_path]
        assert all(p.is_file() for p in written)
    assert c.post(f"{BASE}/{sid}/stop").status_code == 200
    assert c.delete(f"{BASE}/{sid}").status_code == 200
    assert not any(p.exists() for p in written)          # deleting the stream takes its footage with it


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


class _WorldModel:
    """Mirrors ultralytics_ad: open-vocabulary models refuse to run without a vocabulary."""

    variant = "yolov8s-worldv2"

    def __init__(self):
        self.calls = 0
        self.vocab: list[list[str] | None] = []

    def predict(self, im, **kw):
        self.calls += 1
        self.vocab.append(kw.get("classes"))
        if not kw.get("classes"):
            raise ValueError("YOLO-World needs classes")
        return {"predictions": [], "image": {"width": im.width, "height": im.height}, "time": 0.0}


def test_world_stream_without_class_rules_fails_fast(c, monkeypatch, video):
    """Finding I2: a live-but-blind World stream must report a clear error, not zero detections."""
    fake = _WorldModel()
    monkeypatch.setattr("app.streams.manager.resolve", lambda *a, **k: fake)
    sid = create_stream(c, source=video, model_ref="ultralytics:yolov8s-worldv2", rules=[])
    assert c.post(f"{BASE}/{sid}/start").status_code == 200
    j = _poll(_status_is(c, sid, "error"), timeout=10)
    assert j["lastError"] == "YOLO-World needs at least one rule with a class"
    assert fake.calls == 0                          # it must not spin on a predictable ValueError
    time.sleep(0.5)
    assert c.get(f"{BASE}/{sid}").json()["status"] == "error"


def test_world_stream_passes_the_rule_vocabulary(c, monkeypatch, video):
    fake = _WorldModel()
    monkeypatch.setattr("app.streams.manager.resolve", lambda *a, **k: fake)
    sid = create_stream(c, source=video, model_ref="ultralytics:yolov8s-worldv2", sample_fps=10, rules=[LINE_RULE])
    assert c.post(f"{BASE}/{sid}/start").status_code == 200
    _poll(_status_is(c, sid, "live"), timeout=10)
    _poll(lambda: fake.vocab or None, timeout=10)
    assert fake.vocab[0] == ["person"]
    assert c.post(f"{BASE}/{sid}/stop").status_code == 200


class _FakeVlm:
    """Task 13: the stream only needs the yes/no question and the sleep probe."""

    def __init__(self, sleeping: bool = False, answer: bool = True):
        self.sleeping, self.answer = sleeping, answer
        self.asked: list[str] = []

    def is_sleeping(self) -> bool:
        return self.sleeping

    def ask_yes_no(self, im, question: str) -> bool:
        self.asked.append(question)
        return self.answer


def test_vlm_rule_fires_on_yes_and_skips_while_sleeping(c, monkeypatch, video):
    from app.adapters import ADAPTERS
    fake = _FakeVlm(sleeping=True)
    monkeypatch.setitem(ADAPTERS, "vlm", fake)
    monkeypatch.setattr("app.streams.manager.resolve", _fake_resolve)
    question = "Is anyone without a helmet?"
    sid = create_stream(c, source=video, sample_fps=10,
                        rules=[{"kind": "vlm", "question": question, "every_s": 1}])
    assert c.post(f"{BASE}/{sid}/start").status_code == 200
    _poll(_status_is(c, sid, "live"), timeout=10)
    time.sleep(2.5)                                 # two full intervals while vLLM sleeps
    assert fake.asked == []                         # asleep: the question is skipped, not queued
    assert c.get(f"{BASE}/{sid}/events").json()["total"] == 0

    fake.sleeping, fake.answer = False, True
    events = _poll(lambda: c.get(f"{BASE}/{sid}/events").json()["items"] or None, timeout=8)
    ev = events[0]
    assert ev["rule"]["kind"] == "vlm"
    assert ev["summary"] == f"{question} → yes"
    assert fake.asked[0] == question          # a later interval may already have asked again
    assert c.post(f"{BASE}/{sid}/stop").status_code == 200


def test_vlm_rule_ignores_a_no_answer(c, monkeypatch, video):
    from app.adapters import ADAPTERS
    fake = _FakeVlm(answer=False)
    monkeypatch.setitem(ADAPTERS, "vlm", fake)
    monkeypatch.setattr("app.streams.manager.resolve", _fake_resolve)
    sid = create_stream(c, source=video, sample_fps=10,
                        rules=[{"kind": "vlm", "question": "Is the gate clear?", "every_s": 1}])
    assert c.post(f"{BASE}/{sid}/start").status_code == 200
    _poll(lambda: fake.asked or None, timeout=10)   # it did ask
    time.sleep(1.5)
    assert c.get(f"{BASE}/{sid}/events").json()["total"] == 0   # only "yes" creates an event
    assert c.post(f"{BASE}/{sid}/stop").status_code == 200


def test_internal_exception_text_never_reaches_last_error(c, monkeypatch, video):
    """Finding I3: only our own ValueError text is user-facing; everything else is logged."""
    def broken(*_a, **_k):
        raise RuntimeError(r"CUDA error at C:\secret\weights.pt")
    monkeypatch.setattr("app.streams.manager.resolve", broken)
    sid = create_stream(c, source=video, sample_fps=10)
    assert c.post(f"{BASE}/{sid}/start").status_code == 200
    j = _poll(_status_is(c, sid, "error"), timeout=10)
    assert j["lastError"] == "model unavailable"


def test_inference_failure_is_a_fixed_user_message(c, monkeypatch, video):
    class _Boom(_FakeModel):
        def predict(self, im, **kw):
            raise RuntimeError("socket closed by 10.1.2.3 /opt/weights/x.pt")
    monkeypatch.setattr("app.streams.manager.resolve", lambda *a, **k: _Boom())
    sid = create_stream(c, source=video, sample_fps=10)
    assert c.post(f"{BASE}/{sid}/start").status_code == 200
    j = _poll(lambda: (j if (j := c.get(f"{BASE}/{sid}").json())["lastError"] else None), timeout=10)
    assert j["lastError"] == "inference failed"
    assert c.post(f"{BASE}/{sid}/stop").status_code == 200


def test_set_ignores_live_after_a_fatal_error():
    """Finding M3: a grabber 'live' write must not land after the processor marked the worker fatal."""
    from app.models import Stream
    from app.streams.manager import _Worker
    row = Stream(id="race", workspace_id="w", project_id="p", name="race",
                 source="file:videos/race.mp4", model_ref="ultralytics:yolo11n")
    w = _Worker(row)
    w.fatal = True
    w._set("live", "")
    assert w.status != "live"


def test_patch_zones_cannot_orphan_rules(c):
    zones = [{"id": "z1", "points": [0, 0, .5, 0, .5, .5, 0, .5]}]
    sid = create_stream(c, zones=zones, rules=[{"kind": "zone", "class": "person", "zone_id": "z1"}])
    r = c.patch(f"{BASE}/{sid}", json={"zones": [{"id": "z2", "points": [0, 0, .4, 0, .4, .4]}]})
    assert r.status_code == 400 and "z1" in r.json()["detail"]
    assert c.get(f"{BASE}/{sid}").json()["zones"][0]["id"] == "z1"


def test_patch_moves_a_zone_rule_to_a_new_zone_atomically(c):
    """Finding I1: zones and rules in one PATCH are one atomic edit, not old-rules-against-new-zones."""
    zones = [{"id": "z1", "points": [0, 0, .5, 0, .5, .5, 0, .5]}]
    sid = create_stream(c, zones=zones, rules=[{"kind": "zone", "class": "person", "zone_id": "z1"}])
    r = c.patch(f"{BASE}/{sid}", json={
        "zones": [{"id": "z2", "points": [0, 0, .4, 0, .4, .4]}],
        "rules": [{"kind": "zone", "class": "person", "zone_id": "z2"}],
    })
    assert r.status_code == 200, r.text
    body = c.get(f"{BASE}/{sid}").json()
    assert body["zones"][0]["id"] == "z2"
    assert body["rules"][0]["zone_id"] == "z2"


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
    # Finding M1: a raw @ inside the password must not survive the mask either
    assert display_source("rtsp://user:p@ss@host/live") == "rtsp://***@host/live"
    assert "ss@" not in c.post(BASE, json={"name": "At sign", "source": "rtsp://user:p@ss@host/live",
                                           "model_ref": "ultralytics:yolo11n"}).json()["source"]


def test_file_source_cannot_escape_data_dir(c):
    r = c.post(BASE, json={"name": "Escape", "source": "file:../../outside.mp4",
                           "model_ref": "ultralytics:yolo11n"})
    assert r.status_code == 400 and "file:videos" in r.json()["detail"]


def test_frame_is_scoped_and_token_bound(c):
    sid = create_stream(c)
    other = create_stream(c, name="Other")
    frame = c.get(f"{BASE}/{sid}").json()["frame"]
    assert c.get(frame).status_code == 503              # signed + scoped, but stopped: no frame
    query = frame.split("?", 1)[1]
    wrong_project = frame.replace(f"/ws/{WS}/projects/{PR}/", f"/ws/{WS}/projects/other-project/")
    assert c.get(wrong_project).status_code == 403      # the signature covers the whole route path
    assert c.get(f"{BASE}/{other}/frame?{query}").status_code == 403   # bound to its stream


@pytest.mark.parametrize("source", [
    "rtsp://cam.local/stream", "rtsps://cam.local/stream", "http://cam.local/s.mjpg",
    "https://cam.local/s.mjpg", "file:videos/demo.mp4", "RTSP://cam.local/stream",
    "FILE:VIDEOS/demo.mp4",
])
def test_allows_allowlisted_sources(c, source):
    sid = create_stream(c, source=source)
    stored = c.get(f"{BASE}/{sid}").json()["source"]
    assert stored.split(":")[0] in ("rtsp", "rtsps", "http", "https", "file")
    if source.lower().startswith("file:"):
        assert stored == "file:videos/demo.mp4"


@pytest.mark.parametrize("source", [
    "gopher://cam.local/x",                       # not a stream protocol
    "ftp://cam.local/x",
    "file:///etc/passwd",                         # local file outside the videos dir
    "file:../../outside.mp4",
    "file:videos/../outside.mp4",
    "file:videos/%2e%2e/outside.mp4",             # encoded traversal
    "file:videos/sub/outside.mp4",                # nested path
    "file:videos/C:outside.mp4",                  # drive colon
    "file:videos/ outside.mp4",
    "file:videos/a|concat:b",                     # pipe/ffmpeg metacharacters
    "data:text/plain,hi",
    "concat:/tmp/a|/tmp/b",                       # ffmpeg protocol chaining
    "//cam.local/x",                              # scheme-relative
    "rtsp:///no-host",
    "http://",
    "rtsp://cam.local/x\nfile:///etc/passwd",     # control characters
])
def test_rejects_unallowlisted_sources(c, source):
    r = c.post(BASE, json={"name": "Bad source", "source": source, "model_ref": "ultralytics:yolo11n"})
    assert r.status_code == 400, (source, r.text)


def test_manager_rejects_a_source_that_bypassed_the_router(c, monkeypatch):
    """Defence in depth: every path into OpenCV goes through the allowlist, not just the router."""
    import app.streams.manager as mgr
    from app.db import SessionLocal
    from app.models import Project, Stream
    from sqlalchemy import select

    def boom(*_a, **_k):
        raise AssertionError("OpenCV must never see a rejected source")
    monkeypatch.setattr(mgr.cv2, "VideoCapture", boom)
    with SessionLocal() as db:
        p = db.scalar(select(Project).where(Project.slug == PR))
        row = Stream(workspace_id=p.workspace_id, project_id=p.id, name="bypass",
                     source="gopher://cam.local/x", model_ref="ultralytics:yolo11n")
        db.add(row)
        db.commit()
        sid = row.id
    try:
        mgr.manager.start(sid)
        j = _poll(_status_is(c, sid, "error"), timeout=5)
        assert "invalid source" in j["lastError"].lower()
    finally:
        mgr.manager.stop(sid)


def test_capture_is_released_only_by_its_own_grabber(c, monkeypatch, video):
    import app.streams.manager as mgr
    released: list[str] = []

    class FakeCap:
        def __init__(self, *_a, **_k):
            self.n = 0

        def isOpened(self):
            return True

        def read(self):
            self.n += 1
            return True, np.zeros((48, 64, 3), np.uint8)

        def get(self, _prop):
            return 10.0

        def set(self, *_a):
            return True

        def release(self):
            released.append(threading.current_thread().name)

    monkeypatch.setattr(mgr.cv2, "VideoCapture", FakeCap)
    monkeypatch.setattr(mgr, "resolve", _fake_resolve)
    sid = create_stream(c, source=video, sample_fps=10)
    assert c.post(f"{BASE}/{sid}/start").status_code == 200
    _poll(lambda: (mgr.manager.status(sid) or {}).get("frames", 0) > 0, timeout=10)
    assert c.post(f"{BASE}/{sid}/stop").status_code == 200
    assert released and all("grabber" in name for name in released), released


def test_to_dataset_ingests_the_clean_frame(c):
    """Finding 1: the annotated snapshot is for review; the dataset gets the untouched frame."""
    sid = create_stream(c, name="Clean frame")
    folder = DATA_DIR / "streams" / sid
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "ann.jpg").write_bytes(jpeg((220, 20, 20)))       # snapshot with red overlays
    (folder / "clean.jpg").write_bytes(jpeg((20, 20, 220)))     # clean blue frame
    from app.db import SessionLocal
    from app.models import StreamEvent
    with SessionLocal() as db:
        ev = StreamEvent(stream_id=sid, ts=time.time(), rule={"index": 0, "kind": "zone"},
                         summary="person in zone", snapshot_path=f"streams/{sid}/ann.jpg",
                         clean_path=f"streams/{sid}/clean.jpg", predictions=[])
        db.add(ev)
        db.commit()
        eid = ev.id
    r = c.post(f"{BASE}/{sid}/events/{eid}/to-dataset")
    assert r.status_code == 200 and r.json()["uploaded"] == 1, r.text
    img = c.get(f"{PROJECT}/images", params={"tag": "stream"}).json()["items"][0]   # newest
    body = c.get(img["url"]).content
    pixel = PImage.open(io.BytesIO(body)).convert("RGB").getpixel((32, 24))
    assert pixel[2] > pixel[0] + 50, pixel      # blue clean frame, not the red snapshot


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
