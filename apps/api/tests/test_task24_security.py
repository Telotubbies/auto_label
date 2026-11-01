"""Task 24 security round: SSRF guards, encrypted secrets at rest, key handling, replay window."""
import os
import tempfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-t24sec-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Audit, Connector, Webhook, Workspace
from app.services import connectors, safefetch, secretbox, webhooks

WS = "labeldesk-demo"


def login(email="demo@labeldesk.dev", pw="demo1234"):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return c


@pytest.fixture(scope="module")
def admin():
    with TestClient(app):
        yield login()


def ws_id() -> str:
    with SessionLocal() as db:
        return db.scalar(select(Workspace.id).where(Workspace.slug == WS))


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/hook", "http://10.1.2.3/hook", "http://169.254.169.254/latest/meta-data/",
    "http://[::1]/hook", "http://192.168.1.5/hook",
])
def test_check_url_rejects_private_addresses(url):
    with pytest.raises(safefetch.BlockedURL):
        safefetch.check_url(url)


def test_webhook_api_rejects_private_urls(admin):
    for url in ("http://127.0.0.1/hook", "http://10.0.0.8/hook", "http://169.254.169.254/hook"):
        r = admin.post(f"/api/ws/{WS}/webhooks", json={"url": url, "events": ["job.done"]})
        assert r.status_code == 400, (url, r.text)


def test_webhook_delivery_rechecks_url_and_never_dials_private(admin, monkeypatch):
    with SessionLocal() as db:
        w = Webhook(workspace_id=ws_id(), url="http://127.0.0.1/now-private",
                    secret=secretbox.encrypt("whsec_x"), events=["job.done"], active=True)
        db.add(w)
        db.flush()
        d = webhooks.delivery_for(w, "job.done", {"n": 1})
        db.add(d)
        db.commit()
        d_id = d.id

    called = []
    monkeypatch.setattr(webhooks, "_post", lambda *a, **k: called.append(a) or 200)
    with SessionLocal() as db:
        d = db.get(webhooks.models.WebhookDelivery, d_id)
        assert webhooks.deliver(db, d) is False
        db.commit()
        assert d.status == "failed" and d.last_status is None
        assert "not allowed" in (d.last_error or "").lower()
    assert called == []                         # never opened a connection


def test_safefetch_post_does_not_follow_redirects(monkeypatch):
    class FakeConn:
        def request(self, *a, **k):
            pass

        def getresponse(self):
            class R:
                status = 302

                def getheader(self, name):
                    return "http://10.0.0.5/internal"

            return R()

        def close(self):
            pass

    hits = []

    def fake_addr(host, port):
        return "93.184.216.34"

    def fake_conn(*a, **k):
        hits.append(a)
        return FakeConn()

    monkeypatch.setattr(safefetch, "_public_ip", fake_addr)
    monkeypatch.setattr(safefetch.http.client, "HTTPConnection", fake_conn)
    with pytest.raises(safefetch.BlockedURL):
        safefetch.post("http://hooks.example.com/x", b"{}", {"X-Test": "1"}, 5)
    assert len(hits) == 1                       # one hop only; the private redirect is never dialled


@pytest.mark.parametrize("kind,config", [
    ("s3", {"bucket": "b", "endpoint_url": "http://127.0.0.1:9000"}),
    ("s3", {"bucket": "b", "endpoint_url": "http://169.254.169.254"}),
    ("azure", {"container": "c", "account_url": "http://10.0.0.5"}),
    ("azure", {"container": "c", "account_url": "http://127.0.0.1/devstoreaccount1"}),
])
def test_connector_validate_rejects_private_hosts(kind, config):
    with pytest.raises(ValueError, match="private|reserved|public"):
        connectors.validate(kind, config)


def test_connector_secrets_are_encrypted_at_rest(admin):
    before = None
    r = admin.post(f"/api/ws/{WS}/connectors", json={
        "name": "encrypted s3", "kind": "s3",
        "config": {"bucket": "b", "access_key": "AKIAEXAMPLE", "secret_key": "plain-s3-secret"}})
    assert r.status_code == 200, r.text
    assert "plain-s3-secret" not in r.text
    with SessionLocal() as db:
        row = db.get(Connector, r.json()["id"])
        stored = (row.config or {}).get("secret_key")
        assert stored and stored != "plain-s3-secret"
        assert stored.startswith(secretbox.PREFIX)
        # decrypt only for use
        assert connectors._config(row)["secret_key"] == "plain-s3-secret"
    assert before is None
    admin.delete(f"/api/ws/{WS}/connectors/{r.json()['id']}")


def test_webhook_secret_is_encrypted_at_rest(admin):
    created = admin.post(f"/api/ws/{WS}/webhooks",
                         json={"url": "https://93.184.216.34/hook", "events": ["job.done"]}).json()
    plain = created["secret"]
    assert plain.startswith("whsec_")
    with SessionLocal() as db:
        row = db.get(Webhook, created["id"])
        assert row.secret != plain and row.secret.startswith(secretbox.PREFIX)
        assert secretbox.decrypt(row.secret) == plain
    listed = admin.get(f"/api/ws/{WS}/webhooks").text
    assert plain not in listed
    admin.delete(f"/api/ws/{WS}/webhooks/{created['id']}")


def test_migration_encrypts_existing_plaintext_rows():
    with SessionLocal() as db:
        w = Webhook(workspace_id=ws_id(), url="https://93.184.216.34/legacy",
                    secret="whsec_legacy_plain", events=["job.done"], active=True)
        c = Connector(workspace_id=ws_id(), kind="s3", name="legacy-conn",
                      config={"bucket": "b", "secret_key": "legacy-secret"})
        db.add_all([w, c])
        db.commit()
        wid, cid = w.id, c.id

    secretbox.migrate()
    secretbox.migrate()                       # idempotent

    with SessionLocal() as db:
        assert db.get(Webhook, wid).secret.startswith(secretbox.PREFIX)
        assert db.get(Connector, cid).config["secret_key"].startswith(secretbox.PREFIX)
        assert secretbox.decrypt(db.get(Webhook, wid).secret) == "whsec_legacy_plain"


def test_query_string_key_only_for_publishable(admin):
    regular = admin.post(f"/api/ws/{WS}/keys", json={"name": "q-regular", "scopes": ["read"]}).json()
    pub = admin.post(f"/api/ws/{WS}/keys", json={"name": "q-pub", "publishable": True}).json()

    anon = TestClient(app)
    assert anon.get("/api/v1/projects", params={"api_key": regular["key"]}).status_code == 403
    # a publishable key authenticates, then fails the read scope (it is infer-only)
    assert anon.get("/api/v1/projects", params={"api_key": pub["key"]}).status_code == 403
    assert "read" in anon.get("/api/v1/projects", params={"api_key": pub["key"]}).text


def test_developer_calls_audit_key_prefix(admin):
    key = admin.post(f"/api/ws/{WS}/keys", json={"name": "audited", "scopes": ["read"]}).json()
    assert TestClient(app).get("/api/v1/projects", headers={"x-api-key": key["key"]}).status_code == 200
    with SessionLocal() as db:
        row = db.scalar(select(Audit).where(Audit.action == "apikey.use").order_by(Audit.created.desc()))
        assert row is not None and row.meta["prefix"] == key["prefix"]


def test_verify_rejects_stale_timestamps():
    import time

    body = b'{"x":1}'
    now = int(time.time())
    sig = webhooks.sign("whsec_s", body, now)
    assert webhooks.verify("whsec_s", body, now, sig) is True
    assert webhooks.verify("whsec_s", body, now - 301, webhooks.sign("whsec_s", body, now - 301)) is False
    assert webhooks.verify("whsec_s", body, now - 10, sig) is False       # body/signature mismatch


def test_azure_account_name_ssrf_bypass_is_rejected(admin):
    payload = {"name": "azure bypass", "kind": "azure",
               "config": {"container": "x", "account_name": "169.254.169.254#"}}
    with pytest.raises(ValueError, match="account_name"):
        connectors.validate("azure", payload["config"])
    assert admin.post(f"/api/ws/{WS}/connectors", json=payload).status_code == 400
    with pytest.raises(ValueError, match="account_name"):
        connectors.validate("azure", {"container": "x", "account_name": "Evil_Name"})


def test_check_url_blocks_nat64_embedded_ipv4():
    with pytest.raises(safefetch.BlockedURL):
        safefetch.check_url("http://[64:ff9b::a00:1]/hook")


def test_safefetch_post_host_header_strips_userinfo(monkeypatch):
    seen = {}

    class FakeConn:
        def request(self, method, path, body=None, headers=None):
            seen.update(method=method, path=path, headers=headers or {})

        def getresponse(self):
            return type("R", (), {"status": 204})()

        def close(self):
            pass

    monkeypatch.setattr(safefetch, "_public_ip", lambda host, port: "93.184.216.34")
    monkeypatch.setattr(safefetch.http.client, "HTTPConnection", lambda *a, **k: FakeConn())

    assert safefetch.post("http://user:pass@93.184.216.34:8080/hook", b"{}", {"X-Test": "1"}, 5) == 204
    assert seen["headers"]["Host"] == "93.184.216.34:8080"
    assert "user" not in seen["headers"]["Host"]


def test_apikey_use_audit_is_sampled_per_minute(admin):
    key = admin.post(f"/api/ws/{WS}/keys", json={"name": "sampled", "scopes": ["read"]}).json()
    c = TestClient(app)
    for _ in range(3):
        assert c.get("/api/v1/projects", headers={"x-api-key": key["key"]}).status_code == 200
    with SessionLocal() as db:
        rows = db.scalars(select(Audit).where(Audit.action == "apikey.use")
                          .order_by(Audit.created.desc()).limit(50)).all()
        assert sum(1 for r in rows if (r.meta or {}).get("prefix") == key["prefix"]) == 1
