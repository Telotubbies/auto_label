"""Outbound webhooks: HMAC signing, delivery/retry/backoff, admin API.

No real network: every test that can reach `deliver` patches `webhooks._post`.
`LD_WEBHOOK_FLUSH=0` (conftest) keeps the embedded worker's retry loop from racing these assertions.
"""
import os
import secrets
import tempfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-wh-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import User, Webhook, WebhookDelivery, Workspace, now
from app.services import webhooks

WS = "labeldesk-demo"
BASE = f"/api/ws/{WS}/webhooks"


def login(email, pw="demo1234"):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return c


@pytest.fixture(scope="module")
def admin():
    with TestClient(app):
        yield login("demo@labeldesk.dev")


@pytest.fixture(scope="module")
def ws_id(admin):
    with SessionLocal() as db:
        return db.scalar(select(Workspace.id).where(Workspace.slug == WS))


# --- helpers -------------------------------------------------------------------------

def _webhook(ws_id, events=("job.done",), active=True, url=None) -> str:
    with SessionLocal() as db:
        w = Webhook(workspace_id=ws_id, url=url or f"https://example.test/hook/{secrets.token_hex(4)}",
                    secret="whsec_" + secrets.token_urlsafe(24), events=list(events), active=active)
        db.add(w)
        db.commit()
        return w.id


def _delivery(wh_id, event="job.done", data=None) -> str:
    with SessionLocal() as db:
        w = db.get(Webhook, wh_id)
        d = webhooks.delivery_for(w, event, data if data is not None else {"job_id": "j-test"})
        db.add(d)
        db.commit()
        return d.id


def _deliveries(wh_id):
    with SessionLocal() as db:
        return db.scalars(select(WebhookDelivery).where(WebhookDelivery.webhook_id == wh_id)).all()


class Resp:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


# --- signing -------------------------------------------------------------------------

def test_sign_and_verify_roundtrip():
    body = b'{"hello":"world"}'
    ts = 1_700_000_000
    sig = webhooks.sign("whsec_secret", body, ts)
    assert sig.startswith("sha256=")
    assert webhooks.verify("whsec_secret", body, ts, sig)
    assert not webhooks.verify("whsec_secret", b'{"hello":"tampered"}', ts, sig)
    assert not webhooks.verify("whsec_secret", body, ts + 1, sig)
    assert not webhooks.verify("other_secret", body, ts, sig)
    assert not webhooks.verify("whsec_secret", body, ts, "sha256=é")            # garbage header stays a bool
    assert webhooks.verify("whsec_secret", body, ts, sig.removeprefix("sha256="))   # header without prefix


def test_canonical_is_sorted_and_compact():
    assert webhooks.canonical({"b": 1, "a": "é"}) == '{"a":"é","b":1}'.encode("utf-8")


# --- emit ----------------------------------------------------------------------------

def test_emit_creates_pending_delivery_per_active_subscriber(ws_id):
    sub_a = _webhook(ws_id, ["job.done"])
    sub_b = _webhook(ws_id, ["job.done", "model.ready"])
    inactive = _webhook(ws_id, ["job.done"], active=False)
    unsubscribed = _webhook(ws_id, ["model.ready"])

    before = now()
    with SessionLocal() as db:
        assert webhooks.emit(db, ws_id, "job.done", {"job_id": "j1"}) == 2
        db.commit()

    for wh_id in (sub_a, sub_b):
        rows = _deliveries(wh_id)
        assert len(rows) == 1
        d = rows[0]
        assert d.status == "pending" and d.attempts == 0
        assert d.event == "job.done" and d.workspace_id == ws_id
        assert d.next_attempt >= before
        assert d.payload["id"] == d.id
        assert d.payload["event"] == "job.done"
        assert d.payload["data"] == {"job_id": "j1"}
        assert d.payload["created"] >= before
    assert _deliveries(inactive) == [] and _deliveries(unsubscribed) == []


def test_emit_rejects_unknown_event(ws_id):
    with SessionLocal() as db:
        with pytest.raises(ValueError):
            webhooks.emit(db, ws_id, "not.an.event", {})


def test_job_done_payload_matches_worker_wiring(ws_id):
    wh_id = _webhook(ws_id, ["job.done"])
    data = {"job_id": "job-42", "kind": "train", "status": "done", "project_id": "p1", "error": ""}
    with SessionLocal() as db:
        # subscriptions left by earlier tests would widen the fan-out; this test pins one
        db.execute(Webhook.__table__.update().where(Webhook.workspace_id == ws_id,
                                                    Webhook.id != wh_id).values(active=False))
        assert webhooks.emit(db, ws_id, "job.done", data) == 1
        db.commit()

    (d,) = _deliveries(wh_id)
    assert d.payload["event"] == "job.done"
    assert d.payload["data"] == data


# --- deliver -------------------------------------------------------------------------

def test_deliver_success_signs_request(ws_id, monkeypatch):
    wh_id = _webhook(ws_id, ["job.done"])
    d_id = _delivery(wh_id)
    seen = {}

    def fake_post(url, content, headers, timeout):
        seen.update(url=url, content=content, headers=headers, timeout=timeout)
        return Resp(200)

    monkeypatch.setattr(webhooks, "_post", fake_post)
    with SessionLocal() as db:
        d = db.get(WebhookDelivery, d_id)
        assert webhooks.deliver(db, d) is True
        db.commit()
        assert d.status == "ok" and d.attempts == 1 and d.last_status == 200

    with SessionLocal() as db:
        w = db.get(Webhook, wh_id)
    assert seen["url"] == w.url
    h = seen["headers"]
    assert h["Content-Type"] == "application/json"
    assert h["X-LabelDesk-Event"] == "job.done"
    assert h["X-LabelDesk-Delivery"] == d_id
    assert webhooks.verify(w.secret, seen["content"], int(h["X-LabelDesk-Timestamp"]), h["X-LabelDesk-Signature"])
    assert seen["timeout"] == webhooks.TIMEOUT_S


def test_deliver_500_backs_off_then_marks_failed(ws_id, monkeypatch):
    wh_id = _webhook(ws_id, ["job.done"])
    d_id = _delivery(wh_id)
    monkeypatch.setattr(webhooks, "_post", lambda *a, **k: Resp(500, "boom"))

    with SessionLocal() as db:
        d = db.get(WebhookDelivery, d_id)
        t0 = now()
        assert webhooks.deliver(db, d) is False
        assert d.status == "pending" and d.attempts == 1 and d.last_status == 500
        assert d.next_attempt > t0 + webhooks.RETRY_DELAYS[0] - 1
        assert "500" in d.last_error

        assert webhooks.deliver(db, d) is False
        assert d.status == "pending" and d.attempts == 2 and d.last_status == 500
        assert d.next_attempt > t0 + webhooks.RETRY_DELAYS[1] - 1

        assert webhooks.deliver(db, d) is False
        assert d.status == "failed" and d.attempts == webhooks.MAX_ATTEMPTS
        db.commit()


def test_deliver_transport_error_keeps_pending(ws_id, monkeypatch):
    wh_id = _webhook(ws_id, ["job.done"])
    d_id = _delivery(wh_id)

    def boom(url, content, headers, timeout):
        raise TimeoutError("connect timed out " + "x" * 600)

    monkeypatch.setattr(webhooks, "_post", boom)
    with SessionLocal() as db:
        d = db.get(WebhookDelivery, d_id)
        assert webhooks.deliver(db, d) is False
        assert d.status == "pending" and d.attempts == 1
        assert d.last_status is None
        assert "timed out" in d.last_error
        assert len(d.last_error) <= 500
        db.commit()


# --- flush_due -----------------------------------------------------------------------

def test_flush_due_only_takes_due_pending_rows(ws_id, monkeypatch):
    wh_id = _webhook(ws_id, ["job.done"])
    due_id = _delivery(wh_id)
    future_id = _delivery(wh_id)
    ok_id = _delivery(wh_id)
    with SessionLocal() as db:
        # isolate: nothing else in this (fresh) db is due, and the future row must stay untouched
        db.execute(WebhookDelivery.__table__.update().where(
            WebhookDelivery.id != due_id).values(next_attempt=now() + 3600))
        db.execute(WebhookDelivery.__table__.update().where(WebhookDelivery.id == ok_id).values(
            status="ok", next_attempt=now() + 3600))
        db.commit()

    monkeypatch.setattr(webhooks, "_post", lambda *a, **k: Resp(200))
    assert webhooks.flush_due() == 1

    with SessionLocal() as db:
        due = db.get(WebhookDelivery, due_id)
        future = db.get(WebhookDelivery, future_id)
        ok = db.get(WebhookDelivery, ok_id)
        assert due.status == "ok" and due.attempts == 1
        assert future.status == "pending" and future.attempts == 0
        assert ok.status == "ok" and ok.attempts == 0


def test_flush_due_survives_transport_errors(ws_id, monkeypatch):
    wh_id = _webhook(ws_id, ["job.done"])
    d_id = _delivery(wh_id)
    with SessionLocal() as db:
        db.execute(WebhookDelivery.__table__.update().where(
            WebhookDelivery.id != d_id).values(next_attempt=now() + 3600))
        db.commit()

    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(webhooks, "_post", boom)
    assert webhooks.flush_due() == 1
    with SessionLocal() as db:
        d = db.get(WebhookDelivery, d_id)
        assert d.status == "pending" and d.attempts == 1 and "network down" in d.last_error


def test_flush_due_fails_deliveries_of_a_disabled_webhook(ws_id):
    wh_id = _webhook(ws_id, ["job.done"])
    d_id = _delivery(wh_id)
    with SessionLocal() as db:
        db.execute(Webhook.__table__.update().where(Webhook.id == wh_id).values(active=False))
        db.execute(WebhookDelivery.__table__.update().where(
            WebhookDelivery.id != d_id).values(next_attempt=now() + 3600))
        db.commit()

    assert webhooks.flush_due() == 1                      # no network: disabled is rejected before _post
    with SessionLocal() as db:
        d = db.get(WebhookDelivery, d_id)
        assert d.status == "failed" and d.last_error == "webhook disabled" and d.attempts == 0


# --- API -----------------------------------------------------------------------------

def test_webhook_api_requires_admin():
    annotator = login("labeler@labeldesk.dev")
    assert annotator.get(BASE).status_code == 403
    assert annotator.post(BASE, json={"url": "https://example.test/x", "events": ["job.done"]}).status_code == 403


def test_create_validates_url_and_events(admin):
    assert admin.post(BASE, json={"url": "ftp://example.test/x", "events": ["job.done"]}).status_code == 400
    assert admin.post(BASE, json={"url": "https://example.test/x", "events": []}).status_code == 400
    assert admin.post(BASE, json={"url": "https://example.test/x", "events": ["nope"]}).status_code == 400
    assert admin.post(BASE, json={"url": "https://" + "a" * 1100, "events": ["job.done"]}).status_code == 400


def test_secret_only_returned_on_create(admin):
    r = admin.post(BASE, json={"url": "https://example.test/secret-once", "events": ["job.done", "model.ready"]})
    assert r.status_code == 200, r.text
    created = r.json()
    assert created["secret"].startswith("whsec_")
    assert created["url"] == "https://example.test/secret-once"
    assert created["events"] == ["job.done", "model.ready"] and created["active"] is True

    listing = admin.get(BASE).json()
    row = next(w for w in listing if w["id"] == created["id"])
    assert "secret" not in row
    assert row["secret_preview"].startswith("whsec_") and row["secret_preview"].endswith("…")
    assert all("secret" not in w for w in listing)


def test_patch_and_delete(admin):
    created = admin.post(BASE, json={"url": "https://example.test/patch", "events": ["job.done"]}).json()
    wid = created["id"]

    r = admin.patch(f"{BASE}/{wid}", json={"url": "https://example.test/patched", "events": ["model.ready"],
                                           "active": False})
    assert r.status_code == 200, r.text
    row = next(w for w in admin.get(BASE).json() if w["id"] == wid)
    assert row["url"] == "https://example.test/patched"
    assert row["events"] == ["model.ready"] and row["active"] is False

    assert admin.patch(f"{BASE}/{wid}", json={"url": "ftp://nope"}).status_code == 400
    assert admin.patch(f"{BASE}/nope", json={"active": True}).status_code == 404
    assert admin.delete(f"{BASE}/{wid}").json() == {"ok": True}
    assert admin.patch(f"{BASE}/{wid}", json={"active": True}).status_code == 404


def test_cross_workspace_webhook_is_invisible(admin):
    own = admin.post(BASE, json={"url": "https://example.test/own", "events": ["job.done"]})
    assert own.status_code == 200, own.text
    assert admin.patch(f"{BASE}/{own.json()['id']}", json={"active": False}).status_code == 200

    with SessionLocal() as db:
        owner = db.scalar(select(User.id).where(User.email == "demo@labeldesk.dev"))
        other = Workspace(slug=f"other-{secrets.token_hex(3)}", name="Other", owner_id=owner)
        db.add(other)
        db.flush()
        w = Webhook(workspace_id=other.id, url="https://example.test/other", secret="whsec_other",
                    events=["job.done"])
        db.add(w)
        db.commit()
        other_id = w.id
    assert admin.patch(f"{BASE}/{other_id}", json={"active": False}).status_code == 404
    assert admin.delete(f"{BASE}/{other_id}").status_code == 404
    assert admin.get(f"{BASE}/{other_id}/deliveries").status_code == 404


def test_test_endpoint_records_delivery(admin, monkeypatch):
    created = admin.post(BASE, json={"url": "https://example.test/test-endpoint", "events": ["job.done"]}).json()
    seen = {}

    def fake_post(url, content, headers, timeout):
        seen.update(url=url, content=content)
        return Resp(200)

    monkeypatch.setattr(webhooks, "_post", fake_post)
    r = admin.post(f"{BASE}/{created['id']}/test")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["event"] == "stream.event"
    assert body["status"] == "ok" and body["attempts"] == 1
    assert body["payload"]["data"] == {"source": "test", "message": "LabelDesk webhook test"}

    rows = admin.get(f"{BASE}/{created['id']}/deliveries").json()
    assert [d["id"] for d in rows] == [body["id"]]
    assert rows[0]["status"] == "ok" and rows[0]["last_status"] == 200
    assert seen["url"] == "https://example.test/test-endpoint"


def test_test_endpoint_is_offline_safe(admin, monkeypatch):
    created = admin.post(BASE, json={"url": "https://example.test/down", "events": ["job.done"]}).json()

    def boom(*a, **k):
        raise OSError("host unreachable")

    monkeypatch.setattr(webhooks, "_post", boom)
    r = admin.post(f"{BASE}/{created['id']}/test")
    assert r.status_code == 200, r.text
    assert r.json()["status"] in ("pending", "failed")
    assert r.json()["last_status"] is None


def test_worker_notify_emits_job_done(monkeypatch):
    """The worker must fan terminal jobs out; losing this call would silently disable job.done."""
    from types import SimpleNamespace

    from app.worker import _notify

    calls = []
    monkeypatch.setattr(webhooks, "emit", lambda db, ws, ev, data: calls.append((ws, ev, data)) or 0)
    job = SimpleNamespace(id="j1", workspace_id=WS, kind="export", project_id="p1")

    _notify(job, "done")

    assert calls == [(WS, "job.done", {"job_id": "j1", "kind": "export", "status": "done",
                                       "project_id": "p1", "error": ""})]
