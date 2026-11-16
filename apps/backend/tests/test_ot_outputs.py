"""PLC / OT outputs: config validation, fail-safe pulse dispatch, latency budget, API and flag.

No network and no equipment: every driver call is a recorder. The dispatch contract is
"assert the reject signal once, always return the line to its de-energised state, and never
raise into the stream worker".
"""
import ipaddress
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import models
from app.db import SessionLocal
from app.main import app
from app.ot import drivers
from app.services import flags, ot
from app.streams.rules import Engine

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/ws/{WS}/projects/{PR}/ot-outputs"
PW = "demo1234"

COIL = {"host": "127.0.0.1", "port": 502, "unit_id": 1, "register": "coil", "address": 10}


@pytest.fixture(autouse=True)
def _ot_net(monkeypatch):
    """Loopback only: OT_ALLOW_CIDR is empty in production, so every target is refused by default."""
    monkeypatch.setattr(ot.config, "OT_ALLOW_CIDR", (ipaddress.ip_network("127.0.0.0/8"),))



class Recorder:
    """Fake transport: records every level and timeout, and can fail selected writes."""

    def __init__(self, fail_on: str = ""):
        self.writes: list[bool] = []
        self.timeouts: list[float | None] = []
        self.fail_on = fail_on

    def __call__(self, protocol, endpoint, value, timeout=None):
        self.writes.append(value)
        self.timeouts.append(timeout)
        if self.fail_on == "on" and value:
            raise drivers.DriverError("transport down")
        if self.fail_on == "off" and not value:
            raise drivers.DriverError("transport down")


class Mono:
    def __init__(self, *values):
        self.values = list(values)

    def __call__(self):
        return self.values.pop(0) if self.values else 0.0


def _login(client: TestClient, email: str) -> dict:
    r = client.post("/api/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def admin(client):
    return _login(client, "demo@labeldesk.dev")


@pytest.fixture(scope="module")
def ids(client):
    with SessionLocal() as db:
        ws = db.scalar(select(models.Workspace).where(models.Workspace.slug == WS))
        project = db.scalar(select(models.Project).where(models.Project.slug == PR))
        return ws.id, project.id


@pytest.fixture()
def enabled_flag(monkeypatch):
    monkeypatch.setenv("LD_FLAGS_ON", "task_40")


def _output(ws_id, project_id, **over):
    data = dict(id=models.new_id(), workspace_id=ws_id, project_id=project_id, name="Reject gate",
                protocol="modbus", endpoint=dict(COIL), event_filter={"kinds": ["zone"], "classes": ["defect"]},
                latency_budget_ms=200, pulse_ms=50, enabled=True)
    data.update(over)
    return models.OtOutput(**data)


# --- validation ------------------------------------------------------------------

def test_endpoint_validation_normalises_and_rejects_bad_values():
    assert ot.validate_endpoint("modbus", dict(COIL)) == {**COIL}
    store = ot.validate_endpoint("modbus", {**COIL, "register": "holding", "address": 0})
    assert store["port"] == 502                       # default filled in

    for endpoint in ({"host": "", "port": 502, "unit_id": 1, "register": "coil", "address": 1},
                     {**COIL, "port": 0}, {**COIL, "unit_id": 248}, {**COIL, "address": 65536},
                     {**COIL, "register": "input"}):
        with pytest.raises(ValueError):
            ot.validate_endpoint("modbus", endpoint)
    with pytest.raises(ValueError):
        ot.validate_endpoint("carrier-pigeon", dict(COIL))

    with pytest.raises(ValueError):
        ot.validate_endpoint("mqtt", {"host": "h", "port": 1883, "topic": "bad/#"})
    with pytest.raises(ValueError):
        ot.validate_endpoint("opcua", {"endpoint_url": "http://h", "node_id": "ns=2;s=x"})
    with pytest.raises(ValueError):
        ot.validate_endpoint("gpio", {"line": 2048})


def test_event_filter_validation():
    assert ot.validate_event_filter({}) == {"kinds": [], "classes": []}
    assert ot.validate_event_filter({"kinds": ["line", "zone"], "classes": [" defect "]}) == {
        "kinds": ["line", "zone"], "classes": ["defect"]}
    for bad in ({"kinds": ["motion"]}, {"classes": "defect"}, {"extra": 1}):
        with pytest.raises(ValueError):
            ot.validate_event_filter(bad)


def test_limits_are_bounded():
    assert ot.check_limits(name=" Gate ", latency_budget_ms=250, pulse_ms=100) == ("Gate", 250, 100)
    for name, budget, pulse in (("", 250, 100), ("x" * 121, 250, 100), ("ok", 9, 100),
                                ("ok", 10_001, 100), ("ok", 250, 9), ("ok", 250, 5_001)):
        with pytest.raises(ValueError):
            ot.check_limits(name=name, latency_budget_ms=budget, pulse_ms=pulse)
    with pytest.raises(ValueError):
        ot.check_limits(name="bad\x00name", latency_budget_ms=250, pulse_ms=100)


def test_opcua_endpoint_must_not_embed_credentials():
    with pytest.raises(ValueError, match="credentials"):
        ot.validate_endpoint("opcua", {"endpoint_url": "opc.tcp://user:secret@plc:4840", "node_id": "ns=2;s=x"})


# --- pulse contract --------------------------------------------------------------

def test_deliver_pulses_then_returns_to_fail_safe():
    rec, mono = Recorder(), Mono(0.0, 0.02)
    slept = []
    result = ot.deliver("modbus", COIL, budget_ms=200, pulse_ms=50, event_ts=1000.0, write=rec,
                        wall=lambda: 1000.05, mono=mono, sleep=slept.append)
    assert rec.writes == [True, False]                 # reject asserted, then de-energised
    assert slept == [0.05]
    assert (result.status, result.latency_ms, result.detail) == ("ok", 70, "")


def test_a_late_event_does_not_assert_the_reject_signal():
    rec = Recorder()
    result = ot.deliver("modbus", COIL, budget_ms=200, pulse_ms=50, event_ts=1000.0, write=rec,
                        wall=lambda: 1000.5, mono=Mono(0.0), sleep=lambda _s: None)
    assert rec.writes == [False]                       # safe level only; the part has already passed
    assert result.status == "late"
    assert result.latency_ms == 500


def test_an_over_budget_write_is_de_asserted_and_reported_late():
    rec = Recorder()
    result = ot.deliver("modbus", COIL, budget_ms=200, pulse_ms=50, event_ts=1000.0, write=rec,
                        wall=lambda: 1000.05, mono=Mono(0.0, 0.3), sleep=lambda _s: None)
    assert rec.writes == [True, False]
    assert result.status == "late"
    assert result.latency_ms == 350


def test_a_failed_assert_still_forces_the_safe_state():
    rec = Recorder(fail_on="on")
    result = ot.deliver("modbus", COIL, budget_ms=200, pulse_ms=50, event_ts=1000.0, write=rec,
                        wall=lambda: 1000.0, mono=Mono(0.0, 0.0), sleep=lambda _s: None)
    assert rec.writes == [True, False]
    assert result.status == "failed"
    assert "transport down" in result.detail


def test_a_failed_fail_safe_write_is_reported():
    rec = Recorder(fail_on="off")
    result = ot.deliver("modbus", COIL, budget_ms=200, pulse_ms=50, event_ts=1000.0, write=rec,
                        wall=lambda: 1000.0, mono=Mono(0.0, 0.0), sleep=lambda _s: None)
    assert result.status == "failed"
    assert "fail-safe" in result.detail


def test_unexpected_driver_errors_are_not_leaked_verbatim(caplog):
    def explode(_protocol, _endpoint, _value, timeout=None):
        raise RuntimeError("password=hunter2 in payload")

    result = ot.deliver("modbus", COIL, budget_ms=200, pulse_ms=50, event_ts=1000.0, write=explode,
                        wall=lambda: 1000.0, mono=Mono(0.0, 0.0), sleep=lambda _s: None)
    assert result.status == "failed"
    assert result.detail.startswith("driver error") and "fail-safe write failed" in result.detail
    assert "hunter2" not in result.detail
    assert "hunter2" not in caplog.text


def test_a_failed_release_after_an_over_budget_write_is_failed_not_late():
    rec = Recorder(fail_on="off")
    result = ot.deliver("modbus", COIL, budget_ms=200, pulse_ms=50, event_ts=1000.0, write=rec,
                        wall=lambda: 1000.05, mono=Mono(0.0, 0.3), sleep=lambda _s: None)
    assert rec.writes == [True, False]
    assert result.status == "failed"
    assert "fail-safe" in result.detail


def test_a_failed_release_on_a_late_event_is_failed_not_late():
    rec = Recorder(fail_on="off")
    result = ot.deliver("modbus", COIL, budget_ms=200, pulse_ms=50, event_ts=1000.0, write=rec,
                        wall=lambda: 1000.5, mono=Mono(0.0), sleep=lambda _s: None)
    assert result.status == "failed"
    assert "fail-safe" in result.detail


def test_the_assert_timeout_is_bounded_by_the_remaining_budget():
    rec = Recorder()
    ot.deliver("modbus", COIL, budget_ms=250, pulse_ms=50, event_ts=1000.0, write=rec,
               wall=lambda: 1000.2, mono=Mono(0.0, 0.01), sleep=lambda _s: None)
    assert rec.timeouts[0] == pytest.approx(0.05)      # 250 ms budget - 200 ms already elapsed


# --- event mapping ---------------------------------------------------------------

def test_event_filter_matches_kind_and_class(ids):
    ws_id, project_id = ids
    out = _output(ws_id, project_id)
    assert ot.matches(out, {"kind": "zone", "class": "defect"})
    assert not ot.matches(out, {"kind": "line", "class": "defect"})
    assert not ot.matches(out, {"kind": "zone", "class": "person"})
    assert not ot.matches(out, {"kind": "zone"})       # unknown class never fires a reject
    out.event_filter = {}
    assert ot.matches(out, {"kind": "line", "class": "person"})


def test_dispatch_records_a_delivery_and_updates_status(ids, monkeypatch):
    ws_id, project_id = ids
    rec = Recorder()
    monkeypatch.setattr(drivers, "write", rec)
    monkeypatch.setattr(ot, "_mono", Mono(0.0, 0.01))
    monkeypatch.setattr(ot, "_sleep", lambda _s: None)
    with SessionLocal() as db:
        out = _output(ws_id, project_id, pulse_ms=10)
        db.add(out)
        db.commit()
        rows = ot.dispatch_event(db, project_id, {"kind": "zone", "class": "defect", "summary": "defect in zone"},
                                 event_ts=ot._now(), stream_id="stream-test", workspace_id=ws_id)
        db.commit()
        assert len(rows) == 1
        delivery = rows[0]
        assert delivery.status == "ok"
        assert delivery.output_id == out.id
        assert delivery.stream_id == "stream-test"
        assert delivery.rule_kind == "zone"
        row = db.get(models.OtOutput, out.id)
        assert row.last_status == "ok" and row.last_latency_ms is not None
        db.delete(row)
        db.delete(delivery)
        db.commit()
    assert rec.writes == [True, False]


def test_dispatch_skips_disabled_outputs_and_filter_misses(ids, monkeypatch):
    ws_id, project_id = ids
    rec = Recorder()
    monkeypatch.setattr(drivers, "write", rec)
    with SessionLocal() as db:
        disabled = _output(ws_id, project_id, name="off", enabled=False)
        other_class = _output(ws_id, project_id, name="person only",
                              event_filter={"kinds": ["zone"], "classes": ["person"]})
        db.add_all([disabled, other_class])
        db.commit()
        rows = ot.dispatch_event(db, project_id, {"kind": "zone", "class": "defect"}, event_ts=ot._now(),
                                 workspace_id=ws_id)
        db.commit()
        assert rows == []
        db.delete(disabled)
        db.delete(other_class)
        db.commit()
    assert rec.writes == []


def test_dispatch_never_reaches_another_workspace(ids, monkeypatch):
    """A truncated or replayed event must never fire another tenant's actuator."""
    ws_id, project_id = ids
    rec = Recorder()
    monkeypatch.setattr(drivers, "write", rec)
    with SessionLocal() as db:
        out = _output(ws_id, project_id)
        db.add(out)
        db.commit()
        rows = ot.dispatch_event(db, project_id, {"kind": "zone", "class": "defect"},
                                 event_ts=ot._now(), workspace_id="another-workspace")
        db.commit()
        db.delete(db.get(models.OtOutput, out.id))       # cascades any wrongly created delivery
        db.commit()
    assert rows == []
    assert rec.writes == []


def test_rule_engine_events_flow_into_the_same_dispatcher(ids, monkeypatch):
    """The stream worker's Engine output is the input contract; no second event shape."""
    ws_id, project_id = ids
    rec = Recorder()
    monkeypatch.setattr(drivers, "write", rec)
    monkeypatch.setattr(ot, "_mono", Mono(0.0, 0.01))
    monkeypatch.setattr(ot, "_sleep", lambda _s: None)
    engine = Engine([{"kind": "zone", "class": "defect", "zone_id": "z"}],
                    [{"id": "z", "points": [0, 0, 1, 0, 1, 1, 0, 1]}])
    preds = [{"class": "defect", "x": 0.5, "y": 0.4, "width": 0.1, "height": 0.1, "track_id": 1}]
    events = engine.step(100.0, preds)
    assert events and events[0]["kind"] == "zone"
    event = {**engine.rules[events[0]["rule"]], **events[0], "index": events[0]["rule"]}
    with SessionLocal() as db:
        out = _output(ws_id, project_id, pulse_ms=10)
        db.add(out)
        db.commit()
        rows = ot.dispatch_event(db, project_id, event, event_ts=ot._now(), stream_id="cam-1", workspace_id=ws_id)
        db.commit()
        assert [r.status for r in rows] == ["ok"]
        db.delete(rows[0])
        db.delete(db.get(models.OtOutput, out.id))
        db.commit()
    assert rec.writes == [True, False]


def test_stream_bridge_merges_the_rule_into_engine_events(ids, monkeypatch):
    """Task 10b only has to pass the firing and the stream: the bridge adds the rule class."""
    from types import SimpleNamespace

    from app.streams import ot_bridge

    ws_id, project_id = ids
    rec = Recorder()
    monkeypatch.setattr(drivers, "write", rec)
    monkeypatch.setattr(ot, "_mono", Mono(0.0, 0.01))
    monkeypatch.setattr(ot, "_sleep", lambda _s: None)
    stream = SimpleNamespace(id="cam-9", workspace_id=ws_id, project_id=project_id,
                             rules=[{"kind": "zone", "class": "defect", "zone_id": "z"}])
    events = [{"rule": 0, "kind": "zone", "summary": "defect in zone"}]
    with SessionLocal() as db:
        out = _output(ws_id, project_id, pulse_ms=10)
        db.add(out)
        db.commit()
        rows = ot_bridge.dispatch_rule_events(db, stream, events, ot._now())
        db.commit()
        assert [r.status for r in rows] == ["ok"]
        assert rows[0].stream_id == "cam-9" and rows[0].rule_kind == "zone"
        db.delete(rows[0])
        db.delete(db.get(models.OtOutput, out.id))
        db.commit()
    assert rec.writes == [True, False]


def test_async_dispatcher_records_in_the_background_and_honours_the_flag(ids, monkeypatch):
    """The stream worker must never block on a PLC; the actuator thread owns its session."""
    ws_id, project_id = ids
    rec = Recorder()
    monkeypatch.setattr(drivers, "write", rec)
    monkeypatch.setenv("LD_FLAGS_ON", "task_40")
    with SessionLocal() as db:
        out = _output(ws_id, project_id, pulse_ms=10)
        db.add(out)
        db.commit()
        out_id = out.id

    dispatcher = ot.AsyncDispatcher()
    assert dispatcher.submit(ws_id, project_id, {"kind": "zone", "class": "defect"}, ot._now(), "cam-q")
    dispatcher.join()
    assert rec.writes == [True, False]
    with SessionLocal() as db:
        rows = db.scalars(select(models.OtDelivery).where(models.OtDelivery.output_id == out_id)).all()
        assert [r.status for r in rows] == ["ok"]
        db.delete(rows[0])
        db.delete(db.get(models.OtOutput, out_id))
        db.commit()


def test_a_disabled_flag_drops_the_firing(ids, monkeypatch):
    """An admin switching task_40 off stops actuation even while a stream keeps running."""
    ws_id, project_id = ids
    rec = Recorder()
    monkeypatch.setattr(drivers, "write", rec)
    monkeypatch.setenv("LD_FLAGS_ON", "task_10b,task_20c,task_22,task_23,task_33")
    with SessionLocal() as db:
        flags.set_flag(db, ws_id, "task_40", False)
        out = _output(ws_id, project_id, pulse_ms=10)
        db.add(out)
        db.commit()
        out_id = out.id

    dispatcher = ot.AsyncDispatcher()
    assert dispatcher.submit(ws_id, project_id, {"kind": "zone", "class": "defect"}, ot._now(), "cam-off")
    dispatcher.join()
    with SessionLocal() as db:
        statuses = [r.status for r in db.scalars(
            select(models.OtDelivery).where(models.OtDelivery.output_id == out_id)).all()]
        db.delete(db.get(models.OtOutput, out_id))
        db.commit()
    assert statuses == []
    assert rec.writes == []


def test_async_dispatcher_drops_when_full_and_does_not_actuate(ids, monkeypatch):
    ws_id, project_id = ids
    rec = Recorder()
    monkeypatch.setattr(drivers, "write", rec)
    dispatcher = ot.AsyncDispatcher(maxsize=1)
    # Pretend the consumer is alive but busy: a full bounded queue must drop, never assert.
    dispatcher._thread = SimpleNamespace(is_alive=lambda: True)
    dispatcher._queue.put_nowait((ws_id, project_id, {}, 0.0, ""))
    assert dispatcher.submit(ws_id, project_id, {"kind": "zone"}, ot._now(), "") is False
    assert rec.writes == []
    dispatcher._queue.get_nowait()


def test_worker_record_enqueues_the_rule_for_the_actuator(monkeypatch):
    """Task 10b's manager is the live call site; this guards the wiring."""
    from contextlib import contextmanager
    from types import SimpleNamespace

    from app.streams import manager

    stream = SimpleNamespace(id="cam-1", workspace_id="ws-1", project_id="p-1", name="Cam", source="rtsp://x",
                             model_ref="trained:x", sample_fps=5.0, zones=[],
                             rules=[{"kind": "zone", "class": "defect", "zone_id": "z"}])
    worker = manager._Worker(stream)
    worker._save_frames = lambda *_args: ("", "")
    sent = []

    class FakeScope:
        """Just enough session for feat's `_record`: the project exists, nothing is written."""

        def get(self, model, _key):
            return SimpleNamespace(deleted_at=None) if model is models.Project else None

        def add(self, _row):
            pass

    @contextmanager
    def fake_scope():
        yield FakeScope()

    monkeypatch.setattr(manager, "session_scope", fake_scope)
    monkeypatch.setattr(manager.alert_bridge, "notify", lambda *_args: None)
    monkeypatch.setattr(manager.ot_bridge, "enqueue_rule_events",
                        lambda stream_, events, ts: sent.append((stream_, events, ts)))
    event = {"rule": 0, "kind": "zone", "summary": "defect in zone"}
    worker._record(event, 123.0, [], None)
    assert sent and sent[0][0] is worker and sent[0][1] == [event] and sent[0][2] == 123.0


def test_concurrent_dispatches_do_not_interleave_one_output(ids, monkeypatch):
    """Two streams (or a stream and a manual test) must not cut each other's pulse short."""
    ws_id, project_id = ids
    start = threading.Barrier(2)
    guard = threading.Lock()
    concurrent = peak = 0

    def write(protocol, endpoint, value, timeout=None):
        nonlocal concurrent, peak
        with guard:
            concurrent += 1
            peak = max(peak, concurrent)
        time.sleep(0.05)
        with guard:
            concurrent -= 1
        rec(protocol, endpoint, value, timeout)

    rec = Recorder()
    monkeypatch.setattr(drivers, "write", write)
    with SessionLocal() as db:
        out = _output(ws_id, project_id, pulse_ms=40)
        db.add(out)
        db.commit()
        out_id = out.id

    def fire():
        start.wait(timeout=2)
        with SessionLocal() as db:
            rows = ot.dispatch_event(db, project_id, {"kind": "zone", "class": "defect"}, event_ts=ot._now(),
                                     workspace_id=ws_id)
            db.commit()
            return [r.id for r in rows]

    with ThreadPoolExecutor(max_workers=2) as pool:
        deliveries = [f.result() for f in [pool.submit(fire), pool.submit(fire)]]
    assert peak == 1                                     # serialised per output
    assert rec.writes == [True, False, True, False]
    with SessionLocal() as db:
        for row_id in [r for pair in deliveries for r in pair]:
            db.delete(db.get(models.OtDelivery, row_id))
        db.delete(db.get(models.OtOutput, out_id))
        db.commit()


# --- API -------------------------------------------------------------------------

def test_route_is_hidden_while_the_flag_is_off(client, admin, monkeypatch):
    monkeypatch.delenv("LD_FLAGS_ON", raising=False)
    assert client.get(BASE, headers=admin).status_code == 404


def test_admin_can_toggle_the_flag_for_one_workspace(client, admin, monkeypatch):
    monkeypatch.delenv("LD_FLAGS_ON", raising=False)
    listed = client.get(f"/api/ws/{WS}/flags", headers=admin)
    assert listed.status_code == 200
    assert "task_40" in [f["key"] for f in listed.json()["flags"]]
    assert "task_40" not in listed.json()["enabled"]

    reviewer = _login(client, "reviewer@labeldesk.dev")
    assert client.put(f"/api/ws/{WS}/flags/task_40", headers=reviewer, json={"enabled": True}).status_code == 403

    try:
        put = client.put(f"/api/ws/{WS}/flags/task_40", headers=admin, json={"enabled": True})
        assert put.status_code == 200 and put.json()["enabled"] is True
        assert client.get(BASE, headers=admin).status_code == 200
    finally:
        client.put(f"/api/ws/{WS}/flags/task_40", headers=admin, json={"enabled": False})
    assert client.get(BASE, headers=admin).status_code == 404


def test_create_list_update_and_test_output(client, admin, ids, enabled_flag, monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(drivers, "write", rec)
    created = client.post(BASE, headers=admin, json={
        "name": "Reject gate", "protocol": "modbus", "endpoint": dict(COIL),
        "event_filter": {"kinds": ["zone"], "classes": ["defect"]},
        "latency_budget_ms": 300, "pulse_ms": 10,
    })
    assert created.status_code == 200, created.text
    out = created.json()
    assert out["name"] == "Reject gate" and out["last_status"] == "never"
    assert out["workspace_id"] == ids[0]

    listed = client.get(BASE, headers=admin).json()
    assert any(o["id"] == out["id"] for o in listed)

    tested = client.post(f"{BASE}/{out['id']}/test", headers=admin)
    assert tested.status_code == 200, tested.text
    body = tested.json()
    assert body["status"] == "ok" and body["latency_ms"] is not None
    assert rec.writes == [True, False]

    patched = client.patch(f"{BASE}/{out['id']}", headers=admin, json={"enabled": False, "pulse_ms": 20})
    assert patched.status_code == 200, patched.text
    assert patched.json()["enabled"] is False and patched.json()["pulse_ms"] == 20

    deliveries = client.get(f"{BASE}/{out['id']}/deliveries", headers=admin).json()
    assert [d["id"] for d in deliveries] == [body["id"]]
    assert client.delete(f"{BASE}/{out['id']}", headers=admin).status_code == 200
    assert client.get(f"{BASE}/{out['id']}", headers=admin).status_code == 404


def test_invalid_config_is_a_400(client, admin, enabled_flag):
    r = client.post(BASE, headers=admin, json={"name": "bad", "protocol": "modbus",
                                               "endpoint": {**COIL, "port": 0}})
    assert r.status_code == 400
    r = client.post(BASE, headers=admin, json={"name": "bad", "protocol": "mqtt",
                                               "endpoint": {"host": "h", "port": 1883, "topic": "a/#"}})
    assert r.status_code == 400
    r = client.post(BASE, headers=admin, json={"name": "bad", "protocol": "modbus", "endpoint": dict(COIL),
                                               "latency_budget_ms": 0})
    assert r.status_code == 400


def test_an_unlisted_private_target_is_refused(client, admin, enabled_flag, monkeypatch):
    """Empty LD_OT_ALLOW_CIDR means no OT target is reachable: the save is a 400, not a probe.

    Without this, an admin-supplied host:port makes the API open a TCP connection anywhere and
    report reachability through last_status/last_error — a blind SSRF oracle into the LAN.
    """
    monkeypatch.setattr(ot.config, "OT_ALLOW_CIDR", ())
    r = client.post(BASE, headers=admin, json={"name": "lan", "protocol": "modbus", "endpoint": dict(COIL)})
    assert r.status_code == 400
    assert "LD_OT_ALLOW_CIDR" in r.json()["detail"]
    assert not [o for o in client.get(BASE, headers=admin).json() if o["name"] == "lan"]   # nothing stored
    r = client.post(BASE, headers=admin, json={"name": "ua", "protocol": "opcua",
                                               "endpoint": {"endpoint_url": "opc.tcp://127.0.0.1:4840",
                                                            "node_id": "ns=2;s=Reject"}})
    assert r.status_code == 400


def test_unknown_request_fields_are_rejected(client, admin, enabled_flag):
    """A typo must not silently leave the latency budget at its default."""
    r = client.post(BASE, headers=admin, json={"name": "typo", "protocol": "modbus", "endpoint": dict(COIL),
                                               "latency_budget": 5})
    assert r.status_code == 422


def test_a_disabled_output_cannot_be_pulsed_by_the_test_endpoint(client, admin, enabled_flag, monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(drivers, "write", rec)
    out = client.post(BASE, headers=admin, json={"name": "disabled", "protocol": "modbus",
                                                 "endpoint": dict(COIL), "enabled": False}).json()
    try:
        r = client.post(f"{BASE}/{out['id']}/test", headers=admin)
        assert r.status_code == 400
        assert rec.writes == []
    finally:
        client.delete(f"{BASE}/{out['id']}", headers=admin)


def test_another_workspace_cannot_reach_an_output(client, admin, enabled_flag, ids):
    ws_id, _project_id = ids
    with SessionLocal() as db:
        owner = db.scalar(select(models.User).where(models.User.email == "demo@labeldesk.dev"))
        other = models.Workspace(slug=f"other-{models.new_id()}", name="Other", owner_id=owner.id)
        db.add(other)
        db.flush()
        project = models.Project(workspace_id=other.id, slug="other-project", name="Other",
                                 type="object-detection", settings={})
        db.add(project)
        db.flush()
        foreign = _output(other.id, project.id)
        db.add(foreign)
        db.commit()
        foreign_id = foreign.id
        try:
            assert client.get(f"{BASE}/{foreign_id}", headers=admin).status_code == 404
            assert client.patch(f"{BASE}/{foreign_id}", headers=admin, json={"name": "x"}).status_code == 404
            assert client.delete(f"{BASE}/{foreign_id}", headers=admin).status_code == 404
            assert client.post(f"{BASE}/{foreign_id}/test", headers=admin).status_code == 404
        finally:
            db.delete(db.get(models.OtOutput, foreign_id))
            db.delete(project)
            db.delete(other)
            db.commit()


def test_project_settings_permission_is_required(client, enabled_flag):
    reviewer = _login(client, "reviewer@labeldesk.dev")
    created = client.post(BASE, headers=reviewer, json={"name": "nope", "protocol": "modbus",
                                                        "endpoint": dict(COIL)})
    assert created.status_code == 403
    assert client.get(BASE, headers=reviewer).status_code == 200      # read stays open to members
