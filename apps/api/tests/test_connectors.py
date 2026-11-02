"""Read-only cloud storage connectors: validation, secret masking, listing, bucket sync.

No network or SDK install is needed: boto3 is faked through sys.modules and httpx.get is
replaced per test.
"""
import io
import json
import os
import sys
import types

os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"
os.environ["LD_EMBEDDED_WORKER"] = "0"

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image as PImage

from app.db import SessionLocal
from app.main import app
from app.models import Connector, Image, Project, User, Workspace
from app.services import connectors

WS, PR = "labeldesk-demo", "ppe-detection"
API = f"/api/ws/{WS}"


def jpeg(color=(30, 90, 150)):
    b = io.BytesIO()
    PImage.new("RGB", (32, 32), color).save(b, "JPEG")
    return b.getvalue()


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


# --- service validation -------------------------------------------------------------

@pytest.mark.parametrize("kind,config", [
    ("s3", {}),
    ("gcs", {}),
    ("gcs", {"bucket": ""}),
    ("azure", {}),
    ("azure", {"container": "c"}),
])
def test_validate_rejects_missing_required_fields(kind, config):
    with pytest.raises(ValueError):
        connectors.validate(kind, config)


def test_validate_rejects_unknown_kind():
    with pytest.raises(ValueError, match="s3"):
        connectors.validate("dropbox", {})


def test_validate_accepts_supported_configs(monkeypatch):
    monkeypatch.setattr(connectors, "_ensure_public", lambda url, field: None)   # no DNS in tests
    connectors.validate("s3", {"bucket": "b"})
    connectors.validate("gcs", {"bucket": "b"})
    connectors.validate("azure", {"container": "c", "account_name": "acct"})
    connectors.validate("azure", {"container": "c", "account_url": "https://acct.blob.core.windows.net"})


# --- API validation -----------------------------------------------------------------

@pytest.mark.parametrize("payload", [
    {"name": "no bucket", "kind": "s3", "config": {}},
    {"name": "no bucket", "kind": "gcs", "config": {}},
    {"name": "no container", "kind": "azure", "config": {"account_name": "acct"}},
    {"name": "no account", "kind": "azure", "config": {"container": "c"}},
    {"name": "unknown", "kind": "dropbox", "config": {"bucket": "b"}},
])
def test_api_rejects_invalid_config(admin, payload):
    r = admin.post(f"{API}/connectors", json=payload)
    assert r.status_code == 400, r.text


# --- secret masking -----------------------------------------------------------------

@pytest.mark.parametrize("payload,field,secret", [
    ({"name": "s3", "kind": "s3",
      "config": {"bucket": "b", "access_key": "AKIA", "secret_key": "s3-secret"}}, "secret_key", "s3-secret"),
    ({"name": "gcs", "kind": "gcs",
      "config": {"bucket": "b", "credentials_json": json.dumps({"private_key": "gcs-secret"})}},
     "credentials_json", "gcs-secret"),
    ({"name": "azure", "kind": "azure",
      "config": {"container": "c", "account_name": "acct", "sas_token": "azure-secret"}}, "sas_token", "azure-secret"),
])
def test_secrets_masked_in_post_and_list(admin, monkeypatch, payload, field, secret):
    monkeypatch.setattr(connectors, "_ensure_public", lambda url, field: None)   # no DNS in tests
    r = admin.post(f"{API}/connectors", json=payload)
    assert r.status_code == 200, r.text
    created = r.json()
    assert created["config"][field] == "***"
    assert secret not in r.text

    listed = admin.get(f"{API}/connectors")
    assert listed.status_code == 200, listed.text
    row = next(x for x in listed.json() if x["id"] == created["id"])
    assert row["config"][field] == "***"
    assert secret not in listed.text

    assert admin.delete(f"{API}/connectors/{created['id']}").status_code == 200


def test_connectors_are_admin_only(admin):
    rev = login("reviewer@labeldesk.dev")
    ann = login("labeler@labeldesk.dev")
    for client in (rev, ann):
        assert client.get(f"{API}/connectors").status_code == 403
        assert client.post(f"{API}/connectors", json={"name": "nope", "kind": "s3",
                                                      "config": {"bucket": "b"}}).status_code == 403
    created = admin.post(f"{API}/connectors", json={"name": "admin conn", "kind": "s3",
                                                   "config": {"bucket": "b"}}).json()
    assert rev.get(f"{API}/connectors/{created['id']}/objects").status_code == 403
    assert rev.post(f"{API}/projects/{PR}/connectors/{created['id']}/sync", json={}).status_code == 403
    admin.delete(f"{API}/connectors/{created['id']}")


# --- listing ------------------------------------------------------------------------

class FakeS3:
    """Just enough boto3 S3 surface for list_objects / fetch_bytes."""

    def __init__(self, contents):
        self.contents = contents
        self.list_calls = []

    def list_objects_v2(self, **kwargs):
        self.list_calls.append(kwargs)
        return {"Contents": self.contents, "KeyCount": len(self.contents)}

    def generate_presigned_url(self, op, Params, ExpiresIn):
        assert op == "get_object"
        assert ExpiresIn == 900
        return f"https://s3.example/{Params['Bucket']}/{Params['Key']}?X-Amz-Signature=fake"


def install_fake_boto3(monkeypatch, client):
    mod = types.ModuleType("boto3")
    mod.client = lambda *a, **kw: client
    monkeypatch.setitem(sys.modules, "boto3", mod)
    return mod


def s3_conn():
    return types.SimpleNamespace(kind="s3", config={
        "bucket": "bucket", "region": "us-east-1", "access_key": "AKIA", "secret_key": "s3-secret"})


def test_list_objects_returns_presigned_get_url(monkeypatch):
    fake = FakeS3([{"Key": "photos/a.jpg", "Size": 1234}])
    install_fake_boto3(monkeypatch, fake)

    objs = connectors.list_objects(s3_conn(), prefix="photos/", limit=10)

    assert len(objs) == 1
    assert objs[0]["key"] == "photos/a.jpg"
    assert objs[0]["size"] == 1234
    assert objs[0]["url"].startswith("https://")
    assert "X-Amz-Signature=fake" in objs[0]["url"]
    assert fake.list_calls == [{"Bucket": "bucket", "Prefix": "photos/", "MaxKeys": 10}]


def test_list_without_sdk_returns_501(monkeypatch):
    monkeypatch.setitem(sys.modules, "boto3", None)          # force ImportError on `import boto3`

    with pytest.raises(HTTPException) as exc:
        connectors.list_objects(s3_conn())

    assert exc.value.status_code == 501
    assert "boto3" in exc.value.detail


# --- sync job -----------------------------------------------------------------------

def seed_sync_connector(name="bucket sync"):
    with SessionLocal() as db:
        ws = db.query(Workspace).filter_by(slug=WS).one()
        project = db.query(Project).filter_by(workspace_id=ws.id, slug=PR).one()
        admin = db.query(User).filter_by(email="demo@labeldesk.dev").one()
        before = db.query(Image).filter_by(project_id=project.id, deleted_at=None).count()
        conn = Connector(workspace_id=ws.id, kind="s3", name=name,
                         config={"bucket": "bucket", "access_key": "AKIA", "secret_key": "s3-secret"},
                         created_by=admin.id)
        db.add(conn)
        db.commit()
        return conn.id, project.id, admin.id, before


class FakeStream:
    """Context-manager stand-in for `httpx.stream("GET", ...)`."""

    def __init__(self, data, status_code=200, location=""):
        self.status_code, self._data = status_code, data
        self._location = location

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def iter_bytes(self, chunk_size=None):
        yield self._data


def sync_job(connector_id, project_id, user_id, **params):
    return types.SimpleNamespace(
        id="job-connector", kind="connector_sync", created_by=user_id,
        params={"connector_id": connector_id, "project_id": project_id, **params})


def test_sync_job_uploads_images_skips_non_images_and_counts_failures(admin, monkeypatch):
    cid, pid, uid, before = seed_sync_connector()
    fake = FakeS3([
        {"Key": "shots/bus.jpg", "Size": 100},
        {"Key": "shots/notes.txt", "Size": 10},
        {"Key": "shots/broken.png", "Size": 100},
    ])
    install_fake_boto3(monkeypatch, fake)
    fetched = []

    def fake_stream(method, url, **kwargs):
        fetched.append(url)
        if "broken.png" in url:
            raise RuntimeError("connection reset")
        return FakeStream(jpeg())

    monkeypatch.setattr(connectors.httpx, "stream", fake_stream)

    result = connectors.sync_job(sync_job(cid, pid, uid, prefix="shots/", split="train",
                                          batch_name="cloud import", limit=50))

    assert result["connector_id"] == cid
    assert result["listed"] == 3
    assert result["uploaded"] == 1
    assert result["failed_files"] == 1
    assert len(fetched) == 2                         # only image objects are downloaded
    assert all(url.startswith("https://") for url in fetched)

    with SessionLocal() as db:
        conn = db.get(Connector, cid)
        assert conn.last_sync is not None and conn.last_status == "ok"
        assert db.query(Image).filter_by(project_id=pid, deleted_at=None).count() == before + 1


def test_sync_job_raises_when_no_images(admin, monkeypatch):
    cid, pid, uid, _ = seed_sync_connector(name="empty bucket")
    install_fake_boto3(monkeypatch, FakeS3([{"Key": "docs/readme.txt", "Size": 5}]))

    with pytest.raises(RuntimeError, match="no image"):
        connectors.sync_job(sync_job(cid, pid, uid, prefix="docs/"))

    with SessionLocal() as db:
        conn = db.get(Connector, cid)
        assert conn.last_status == "error"
        assert conn.last_sync is not None


def test_azure_sas_must_be_read_only():
    base = {"container": "frames", "account_url": "https://acct.blob.core.windows.net"}
    with pytest.raises(ValueError, match="read-only"):
        connectors.validate("azure", {**base, "sas_token": "sv=2024&sp=rwdl&sig=x"})
    connectors.validate("azure", {**base, "sas_token": "sv=2024&sp=rl&sig=x"})


def test_public_config_masks_credentials_in_urls():
    conn = types.SimpleNamespace(config={
        "bucket": "b", "access_key": "AKIAEXAMPLE", "secret_key": "shh",
        "endpoint_url": "https://user:pass@minio.internal:9000",
        "account_url": "https://acct.blob.core.windows.net?sig=abc",
    })

    out = connectors.public_config(conn)

    assert out["access_key"] == "***" and out["secret_key"] == "***"
    assert out["endpoint_url"] == "https://minio.internal:9000"
    assert out["account_url"] == "https://acct.blob.core.windows.net"


def test_fetch_bytes_does_not_follow_redirects(monkeypatch):
    install_fake_boto3(monkeypatch, FakeS3([]))

    def fake_stream(method, url, **kwargs):
        assert kwargs["follow_redirects"] is False
        return FakeStream(b"", status_code=302, location="http://10.0.0.5/internal")

    monkeypatch.setattr(connectors.httpx, "stream", fake_stream)
    with pytest.raises(RuntimeError, match="redirect"):
        connectors.fetch_bytes(s3_conn(), "photos/a.jpg")
