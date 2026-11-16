"""Alert channels (LINE Messaging API, Slack, email): validation, delivery, throttling, seam.

No real network: `alerts._post`, `alerts.check_url` and `mailer.send` are replaced in every
test that could reach a provider. Snapshot files are written under the test DATA_DIR.
"""

import json
import os
import tempfile
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp())
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import delete, inspect, select

from app import bootstrap
from app.config import DATA_DIR
from app.db import SessionLocal, engine
from app.main import app
from app.models import AlertChannel, AlertDelivery, Audit, Project, Stream, StreamEvent, Workspace, now
from app.routers.alerts import _get
from app.services import alerts, safefetch
from app.streams import alert_bridge
from app.streams import manager as stream_manager
from app.streams.manager import _Worker

WS = "labeldesk-demo"
BASE = f"/api/ws/{WS}/alerts"
BANGKOK = ZoneInfo("Asia/Bangkok")


def login(email="demo@labeldesk.dev", pw="demo1234"):
    # unique client host: the login limiter is keyed by ip+email and every module logs in
    c = TestClient(app, client=("alerts-test", 50001))
    r = c.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return c


@pytest.fixture(scope="module")
def admin():
    with TestClient(app, client=("alerts-test", 50001)):
        yield login()


@pytest.fixture(scope="module")
def ws_id(admin):
    with SessionLocal() as db:
        return db.scalar(select(Workspace.id).where(Workspace.slug == WS))


@pytest.fixture(scope="module")
def labeler():
    return login("labeler@labeldesk.dev")


@pytest.fixture(autouse=True)
def clean(ws_id, monkeypatch):
    monkeypatch.setenv("LD_FLAGS_ON", "task_33")
    with SessionLocal() as db:
        db.execute(delete(AlertDelivery).where(AlertDelivery.workspace_id == ws_id))
        db.execute(delete(AlertChannel).where(AlertChannel.workspace_id == ws_id))
        db.commit()
    yield
    with SessionLocal() as db:
        db.execute(delete(AlertDelivery).where(AlertDelivery.workspace_id == ws_id))
        db.execute(delete(AlertChannel).where(AlertChannel.workspace_id == ws_id))
        db.commit()


def _channel(ws_id, kind="line", config=None, settings=None, active=True) -> str:
    defaults = {
        "line": {"channel_token": "line-token-secret", "to": "U1234567890"},
        "slack": {"webhook_url": "https://hooks.slack.com/services/T/B/SECRET"},
        "email": {"recipients": ["ops@example.com"]},
    }
    with SessionLocal() as db:
        ch = AlertChannel(
            workspace_id=ws_id,
            kind=kind,
            name=f"{kind} alerts",
            config=config if config is not None else defaults[kind],
            settings=settings or {},
            active=active,
            created=now(),
        )
        db.add(ch)
        db.commit()
        return ch.id


def _event(snapshot_path=""):
    return {
        "title": "Helmet missing",
        "summary": "2 people without a helmet",
        "stream_name": "Gate 3",
        "stream_id": "s1",
        "project_id": "p1",
        "event_id": "e1",
        "created": now(),
        "snapshot_path": snapshot_path,
    }


def _fake_net(monkeypatch, status=200, seen=None):
    monkeypatch.setattr(alerts, "check_url", lambda url: url)

    def post(url, content, headers, timeout):
        if seen is not None:
            seen.update(url=url, content=content, headers=headers, timeout=timeout)
        return status

    monkeypatch.setattr(alerts, "_post", post)


def _snapshot(name="alert.jpg") -> tuple[str, str]:
    folder = DATA_DIR / "snapshots" / "p1"
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / name
    f.write_bytes(b"\xff\xd8\xff\xd9")
    return f"snapshots/p1/{name}", str(f)


# --- schema --------------------------------------------------------------------------


def test_alert_tables_are_created_on_an_existing_database():
    """create_all adds the two new tables to a database that already holds the rest."""
    with engine.begin() as cn:
        cn.exec_driver_sql("DROP TABLE IF EXISTS alert_deliveries")
        cn.exec_driver_sql("DROP TABLE IF EXISTS alert_channels")
    assert not inspect(engine).has_table("alert_channels")
    bootstrap.init_db()
    assert inspect(engine).has_table("alert_channels")
    assert inspect(engine).has_table("alert_deliveries")


# --- validation ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind,config",
    [
        ("line", {}),
        ("line", {"to": "U1"}),
        ("slack", {}),
        ("email", {}),
        ("email", {"recipients": []}),
        ("email", {"recipients": "ops@example.com"}),
    ],
)
def test_validate_rejects_missing_fields(kind, config):
    with pytest.raises(ValueError):
        alerts.validate(kind, config)


def test_validate_rejects_unknown_kind():
    with pytest.raises(ValueError, match="line"):
        alerts.validate("telegram", {})


def test_validate_accepts_supported_configs(monkeypatch):
    monkeypatch.setattr(alerts, "check_url", lambda url: url)
    alerts.validate("line", {"channel_token": "tok", "to": "U123"})
    alerts.validate("slack", {"webhook_url": "https://hooks.slack.com/services/T/B/S"})
    alerts.validate("email", {"recipients": ["a@example.com", "b@example.com"]})


def test_validate_rejects_private_or_plain_http_slack(monkeypatch):
    monkeypatch.setattr(
        alerts,
        "check_url",
        lambda url: (_ for _ in ()).throw(safefetch.BlockedURL("private address")),
    )
    with pytest.raises(ValueError, match="url"):
        alerts.validate("slack", {"webhook_url": "https://hooks.slack.com/services/T/B/S"})
    with pytest.raises(ValueError, match="https"):
        alerts.validate("slack", {"webhook_url": "http://hooks.slack.com/services/T/B/S"})


def test_validate_rejects_control_characters_in_secrets(monkeypatch):
    monkeypatch.setattr(alerts, "check_url", lambda url: url)
    with pytest.raises(ValueError, match="control"):
        alerts.validate("line", {"channel_token": "tok\r\nX-Injected: 1", "to": "U1"})
    with pytest.raises(ValueError, match="control"):
        alerts.validate(
            "slack",
            {"webhook_url": "https://hooks.slack.com/services/T/B/S\r\nX-Injected: 1"},
        )


def test_validate_settings_normalises_limits():
    assert alerts.validate_settings({})["throttle_s"] == alerts.DEFAULT_THROTTLE_S
    s = alerts.validate_settings({"throttle_s": 0, "quiet_hours": {"start": "22:00", "end": "07:00"}})
    assert s["throttle_s"] == 0 and s["quiet_hours"]["tz"] == "Asia/Bangkok"
    for bad in (
        {"throttle_s": -1},
        {"throttle_s": "60"},
        {"quiet_hours": {"start": "25:00", "end": "07:00"}},
        {"quiet_hours": {"start": "22:00", "end": "07:00", "tz": "Mars/Base"}},
    ):
        with pytest.raises(ValueError):
            alerts.validate_settings(bad)


def test_public_config_never_leaks_secrets():
    line = alerts.public_config("line", {"channel_token": "line-token-secret", "to": "U1"})
    assert line["to"] == "U1" and "line-token-secret" not in json.dumps(line)
    slack = alerts.public_config("slack", {"webhook_url": "https://hooks.slack.com/services/T/B/SECRET"})
    assert "SECRET" not in json.dumps(slack)


# --- snapshots -----------------------------------------------------------------------


def test_snapshot_url_signs_only_files_inside_data_dir(monkeypatch):
    monkeypatch.setattr(alerts, "PUBLIC_URL", "https://labeldesk.example")
    rel, _ = _snapshot()
    url = alerts.snapshot_url(rel)
    assert url and url.startswith("https://labeldesk.example/api/files/snapshots/p1/")
    assert "exp=" in url and "sig=" in url
    assert alerts.snapshot_url("../outside.jpg") is None
    assert alerts.snapshot_url(str(DATA_DIR / "snapshots" / "p1" / "alert.jpg")) is None
    assert alerts.snapshot_url("snapshots/p1/nope.png") is None
    assert alerts.snapshot_url("snapshots/p1/alert.txt") is None


# --- delivery ------------------------------------------------------------------------


def test_line_push_uses_messaging_api_with_bearer_and_image(ws_id, monkeypatch):
    seen = {}
    _fake_net(monkeypatch, seen=seen)
    monkeypatch.setattr(alerts, "PUBLIC_URL", "https://labeldesk.example")
    rel, _ = _snapshot()
    ch_id = _channel(ws_id, "line")
    with SessionLocal() as db:
        d = alerts.send(db, db.get(AlertChannel, ch_id), _event(rel))
        assert d.status == "ok"
    body = json.loads(seen["content"])
    assert seen["url"] == "https://api.line.me/v2/bot/message/push"
    assert seen["headers"]["Authorization"] == "Bearer line-token-secret"
    assert body["to"] == "U1234567890"
    assert body["messages"][0]["type"] == "text"
    assert "Helmet missing" in body["messages"][0]["text"]
    assert body["messages"][1]["type"] == "image"
    assert body["messages"][1]["originalContentUrl"].startswith("https://labeldesk.example/api/files/")
    assert body["messages"][1]["previewImageUrl"] == body["messages"][1]["originalContentUrl"]


def test_line_omits_image_message_when_public_url_is_not_https(ws_id, monkeypatch):
    seen = {}
    _fake_net(monkeypatch, seen=seen)
    monkeypatch.setattr(alerts, "PUBLIC_URL", "http://localhost:5173")
    rel, _ = _snapshot()
    ch_id = _channel(ws_id, "line")
    with SessionLocal() as db:
        d = alerts.send(db, db.get(AlertChannel, ch_id), _event(rel))
    assert d.status == "ok"
    body = json.loads(seen["content"])
    assert [m["type"] for m in body["messages"]] == ["text"]
    assert "http://localhost:5173/api/files/" in body["messages"][0]["text"]


def test_slack_posts_text_and_snapshot_attachment(ws_id, monkeypatch):
    seen = {}
    _fake_net(monkeypatch, seen=seen)
    monkeypatch.setattr(alerts, "PUBLIC_URL", "https://labeldesk.example")
    rel, _ = _snapshot()
    ch_id = _channel(ws_id, "slack")
    with SessionLocal() as db:
        d = alerts.send(db, db.get(AlertChannel, ch_id), _event(rel))
    assert d.status == "ok"
    body = json.loads(seen["content"])
    assert seen["url"].startswith("https://hooks.slack.com/")
    assert "Helmet missing" in body["text"]
    assert body["attachments"][0]["image_url"].startswith("https://labeldesk.example/api/files/")


def test_slack_text_cannot_inject_mentions_or_markup(ws_id, monkeypatch):
    seen = {}
    _fake_net(monkeypatch, seen=seen)
    ch_id = _channel(ws_id, "slack")
    event = _event()
    event["summary"] = "<!channel> & <https://evil.example|click>"
    with SessionLocal() as db:
        assert alerts.send(db, db.get(AlertChannel, ch_id), event).status == "ok"
    text = json.loads(seen["content"])["text"]
    assert "<!channel>" not in text and "<https://evil.example" not in text
    assert "&lt;!channel&gt;" in text and "&amp;" in text


def test_email_sends_to_every_recipient_with_snapshot(ws_id, monkeypatch):
    monkeypatch.setattr(alerts, "PUBLIC_URL", "https://labeldesk.example")
    sent = []
    monkeypatch.setattr(
        alerts.mailer,
        "send",
        lambda to, subject, text, **kw: sent.append({"to": to, "subject": subject, "text": text, **kw}) or True,
    )
    rel, _ = _snapshot()
    ch_id = _channel(ws_id, "email", {"recipients": ["a@example.com", "b@example.com"]})
    with SessionLocal() as db:
        d = alerts.send(db, db.get(AlertChannel, ch_id), _event(rel))
    assert d.status == "ok"
    assert {m["to"] for m in sent} == {"a@example.com", "b@example.com"}
    assert sent[0]["subject"] == "[LabelDesk] Helmet missing"
    assert "2 people without a helmet" in sent[0]["text"]
    assert "<img" in sent[0]["html_body"]


def test_failed_delivery_records_status_without_channel_body(ws_id, monkeypatch):
    _fake_net(monkeypatch, status=500)
    ch_id = _channel(ws_id, "slack")
    with SessionLocal() as db:
        d = alerts.send(db, db.get(AlertChannel, ch_id), _event())
        assert d.status == "failed" and d.last_status == 500
        assert d.reason == "HTTP 500"
        assert db.get(AlertChannel, ch_id).last_sent is None


def test_throttle_skips_second_alert(ws_id, monkeypatch):
    seen = {}
    _fake_net(monkeypatch, seen=seen)
    ch_id = _channel(ws_id, "slack", settings={"throttle_s": 3600})
    with SessionLocal() as db:
        ch = db.get(AlertChannel, ch_id)
        assert alerts.send(db, ch, _event()).status == "ok"
        db.commit()
        second = alerts.send(db, ch, _event())
        assert second.status == "skipped" and second.reason == "throttled"
    assert seen["url"].startswith("https://hooks.slack.com/")


def test_quiet_hours_skip_delivery(ws_id, monkeypatch):
    seen = {}
    _fake_net(monkeypatch, seen=seen)
    local = datetime.now(BANGKOK)
    start = (local.hour - 1) % 24
    end = (local.hour + 2) % 24
    ch_id = _channel(
        ws_id,
        "slack",
        settings={
            "quiet_hours": {
                "start": f"{start:02d}:00",
                "end": f"{end:02d}:00",
                "tz": "Asia/Bangkok",
            }
        },
    )
    with SessionLocal() as db:
        d = alerts.send(db, db.get(AlertChannel, ch_id), _event())
    assert d.status == "skipped" and d.reason == "quiet_hours"
    assert seen == {}


def test_dispatch_only_active_channels_and_respects_flag(ws_id, monkeypatch):
    _fake_net(monkeypatch)
    active = _channel(ws_id, "slack")
    inactive = _channel(ws_id, "slack", active=False)
    with SessionLocal() as db:
        rows = alerts.dispatch(db, ws_id, _event())
        db.commit()
        assert [d.channel_id for d in rows] == [active]
        assert db.scalar(select(AlertDelivery).where(AlertDelivery.channel_id == inactive)) is None
    monkeypatch.delenv("LD_FLAGS_ON", raising=False)
    with SessionLocal() as db:
        assert alerts.dispatch(db, ws_id, _event()) == []


# --- stream worker seam --------------------------------------------------------------


def test_bridge_forwards_a_committed_event(ws_id, monkeypatch):
    seen = []
    monkeypatch.setattr(alert_bridge.alerts, "dispatch", lambda db, w, ev: seen.append((w, ev)))
    alert_bridge.notify(ws_id, _event())
    alert_bridge.wait_idle()
    assert seen and seen[0][0] == ws_id and seen[0][1]["title"] == "Helmet missing"


def test_bridge_swallows_dispatch_failures(ws_id, monkeypatch):
    def boom(db, w, ev):
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(alert_bridge.alerts, "dispatch", boom)
    alert_bridge.notify(ws_id, _event())
    alert_bridge.wait_idle()  # no exception escapes the worker thread


def test_stream_worker_notifies_only_after_the_event_is_committed(ws_id, monkeypatch):
    seen = []

    def fake_notify(w, ev):
        with SessionLocal() as db:  # a fresh session must see the row
            assert db.get(StreamEvent, ev["event_id"]) is not None
        seen.append((w, ev))

    monkeypatch.setattr(stream_manager.alert_bridge, "notify", fake_notify)
    with SessionLocal() as db:
        project = db.scalar(select(Project).where(Project.workspace_id == ws_id))
        row = Stream(
            workspace_id=ws_id,
            project_id=project.id,
            name="Gate 3",
            source="file:videos/missing.mp4",
            model_ref="trained:x",
            rules=[{"kind": "count", "class": "person", "max": 0}],
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        worker = _Worker(row)
        worker._record({"rule": 0, "kind": "count", "summary": "3 people in frame"}, now(), [], None)
    assert seen and seen[0][0] == ws_id
    assert seen[0][1]["title"] and seen[0][1]["stream_name"] == "Gate 3"
    assert seen[0][1]["summary"] == "3 people in frame"


# --- API -----------------------------------------------------------------------------


def test_api_create_masks_and_encrypts_secrets(admin, ws_id, monkeypatch):
    monkeypatch.setattr(alerts, "check_url", lambda url: url)
    r = admin.post(
        BASE,
        json={
            "kind": "line",
            "name": "Factory LINE",
            "config": {"channel_token": "line-token-secret", "to": "U123"},
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "line-token-secret" not in json.dumps(body)
    with SessionLocal() as db:
        ch = db.get(AlertChannel, body["id"])
        assert ch.config["channel_token"].startswith("enc:v1:")
    listed = admin.get(BASE)
    assert "line-token-secret" not in listed.text


def test_api_update_with_masked_secret_keeps_the_stored_token(admin, ws_id, monkeypatch):
    """A read-modify-write client echoes the mask back; that must not clobber the secret."""
    monkeypatch.setattr(alerts, "check_url", lambda url: url)
    created = admin.post(
        BASE,
        json={
            "kind": "line",
            "name": "Factory LINE",
            "config": {"channel_token": "line-token-secret", "to": "U1"},
        },
    ).json()
    mask = created["config"]["channel_token"]
    assert mask != "line-token-secret"
    r = admin.patch(
        f"{BASE}/{created['id']}",
        json={"config": {"channel_token": mask, "to": "U2"}},
    )
    assert r.status_code == 200, r.text
    seen = {}
    _fake_net(monkeypatch, seen=seen)
    with SessionLocal() as db:
        assert alerts.send(db, db.get(AlertChannel, created["id"]), _event()).status == "ok"
    assert seen["headers"]["Authorization"] == "Bearer line-token-secret"


def test_api_audit_rows_never_contain_channel_secrets(admin, ws_id, monkeypatch):
    monkeypatch.setattr(alerts, "check_url", lambda url: url)
    r = admin.post(
        BASE,
        json={
            "kind": "line",
            "name": "Audited LINE",
            "config": {"channel_token": "line-token-secret", "to": "U1"},
        },
    )
    assert r.status_code == 200, r.text
    with SessionLocal() as db:
        rows = db.scalars(select(Audit).where(Audit.workspace_id == ws_id)).all()
    assert "alert.create" in [row.action for row in rows]
    assert "line-token-secret" not in json.dumps([row.meta for row in rows])


@pytest.mark.parametrize(
    "method,suffix,body",
    [
        ("get", "", None),
        ("patch", "/{ch}", {"active": False}),
        ("delete", "/{ch}", None),
        ("post", "/{ch}/test", None),
        ("get", "/{ch}/deliveries", None),
    ],
)
def test_api_non_admin_is_denied_on_every_route(labeler, ws_id, method, suffix, body):
    url = BASE + suffix.replace("{ch}", _channel(ws_id, "slack"))
    call = getattr(labeler, method)
    r = call(url) if body is None else call(url, json=body)
    assert r.status_code == 403


def test_slack_send_revets_the_webhook_and_never_posts_when_blocked(ws_id, monkeypatch):
    ch_id = _channel(ws_id, "slack")
    vetted, posted = [], []

    def block(url):
        vetted.append(url)
        raise safefetch.BlockedURL("private address")

    monkeypatch.setattr(alerts, "check_url", block)
    monkeypatch.setattr(alerts, "_post", lambda *a, **k: posted.append(a) or 200)
    with SessionLocal() as db:
        d = alerts.send(db, db.get(AlertChannel, ch_id), _event())
    assert vetted == ["https://hooks.slack.com/services/T/B/SECRET"]
    assert posted == []
    assert d.status == "failed" and d.reason == "channel URL is not allowed"


def test_api_crud_and_role_checks(admin, labeler, monkeypatch):
    monkeypatch.setattr(alerts, "check_url", lambda url: url)
    r = admin.post(
        BASE,
        json={
            "kind": "slack",
            "name": "Ops",
            "config": {"webhook_url": "https://hooks.slack.com/services/T/B/S"},
        },
    )
    assert r.status_code == 200, r.text
    ch = r.json()
    assert ch["settings"]["throttle_s"] == alerts.DEFAULT_THROTTLE_S

    assert (
        labeler.post(
            BASE,
            json={
                "kind": "email",
                "name": "x",
                "config": {"recipients": ["x@example.com"]},
            },
        ).status_code
        == 403
    )

    r = admin.patch(
        f"{BASE}/{ch['id']}",
        json={"name": "Ops on-call", "active": False, "settings": {"throttle_s": 0}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Ops on-call" and r.json()["active"] is False
    assert r.json()["settings"]["throttle_s"] == 0

    assert admin.delete(f"{BASE}/{ch['id']}").status_code == 200
    assert admin.get(BASE).json() == []


def test_api_rejects_invalid_config(admin, monkeypatch):
    monkeypatch.setattr(alerts, "check_url", lambda url: url)
    assert admin.post(BASE, json={"kind": "line", "name": "L", "config": {"to": "U1"}}).status_code == 400
    assert admin.post(BASE, json={"kind": "nope", "name": "N", "config": {}}).status_code == 400


def test_api_test_endpoint_bypasses_quiet_hours(admin, ws_id, monkeypatch):
    seen = {}
    _fake_net(monkeypatch, seen=seen)
    local = datetime.now(BANGKOK)
    ch_id = _channel(
        ws_id,
        "slack",
        settings={
            "throttle_s": 3600,
            "quiet_hours": {
                "start": f"{local.hour:02d}:00",
                "end": f"{(local.hour + 1) % 24:02d}:00",
            },
        },
    )
    r = admin.post(f"{BASE}/{ch_id}/test")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ok"
    assert seen["url"].startswith("https://hooks.slack.com/")


def test_api_lists_delivery_history(admin, ws_id, monkeypatch):
    _fake_net(monkeypatch)
    ch_id = _channel(ws_id, "slack")
    with SessionLocal() as db:
        d = alerts.send(db, db.get(AlertChannel, ch_id), _event())
        db.add(d)
        db.commit()
    r = admin.get(f"{BASE}/{ch_id}/deliveries")
    assert r.status_code == 200, r.text
    assert r.json()[0]["status"] == "ok"
    assert r.json()[0]["event"]["title"] == "Helmet missing"


def test_api_flag_off_returns_404(admin, monkeypatch):
    monkeypatch.delenv("LD_FLAGS_ON", raising=False)
    assert admin.get(BASE).status_code == 404


def test_channel_lookup_is_workspace_scoped(ws_id):
    ch_id = _channel(ws_id, "slack")
    with SessionLocal() as db:
        c = SimpleNamespace(ws=SimpleNamespace(id="another-workspace"), db=db)
        with pytest.raises(HTTPException) as exc:
            _get(c, ch_id)
        assert exc.value.status_code == 404


def test_dispatch_is_workspace_scoped(ws_id, monkeypatch):
    _fake_net(monkeypatch)
    _channel(ws_id, "slack")
    with SessionLocal() as db:
        assert alerts.dispatch(db, "another-workspace", _event()) == []
