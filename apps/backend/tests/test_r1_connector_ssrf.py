"""I12: connector downloads must use the pinned-IP safefetch path, not a second DNS resolution."""
import os
import sys
import types

os.environ.setdefault("LD_WORKER_TOKEN", "test-worker-token-0123456789abcdef")

import pytest
from fastapi import HTTPException

from app.services import connectors, safefetch


def test_fetch_bytes_uses_safefetch(monkeypatch):
    class Conn:
        kind = "s3"

    monkeypatch.setattr(connectors, "_signed_url", lambda conn, key: "https://example.com/x")
    seen = {}

    def fake(url, max_bytes, timeout):
        seen.update(url=url, max_bytes=max_bytes, timeout=timeout)
        return b"object-bytes"

    monkeypatch.setattr(safefetch, "fetch_bytes", fake)
    assert connectors.fetch_bytes(Conn(), "x.jpg") == b"object-bytes"
    assert seen["url"] == "https://example.com/x"
    assert seen["max_bytes"] == connectors.MAX_FETCH_BYTES


def test_safefetch_bytes_blocks_private_hosts():
    with pytest.raises(safefetch.BlockedURL):
        safefetch.fetch_bytes("http://127.0.0.1/x.jpg", max_bytes=10, timeout=1)


def test_safefetch_resolves_once(monkeypatch):
    """A host that flips between a public and a private address gets exactly one lookup."""
    public = [(2, 1, 6, "", ("93.184.216.34", 80))]
    private = [(2, 1, 6, "", ("127.0.0.1", 80))]
    calls = []

    def fake_getaddrinfo(host, port, **kw):
        calls.append(host)
        return public if len(calls) == 1 else private

    monkeypatch.setattr(safefetch.socket, "getaddrinfo", fake_getaddrinfo)

    def refuse(*a, **kw):
        raise OSError("connection refused")

    monkeypatch.setattr(safefetch.socket, "create_connection", refuse)
    with pytest.raises(OSError):
        safefetch.fetch_bytes("http://example.com/x.jpg", max_bytes=10, timeout=1)
    assert calls == ["example.com"]


class _FakeS3:
    def list_objects_v2(self, **kwargs):
        return {"Contents": [{"Key": "a.jpg", "Size": 1}], "KeyCount": 1}

    def generate_presigned_url(self, op, Params, ExpiresIn):
        return f"https://s3.example/{Params['Bucket']}/{Params['Key']}?X-Amz-Signature=fake"


def _s3_conn(endpoint: str = "https://s3.example"):
    return types.SimpleNamespace(kind="s3", id="c1", config={"bucket": "bucket", "endpoint_url": endpoint})


def test_list_objects_rechecks_the_public_endpoint(monkeypatch):
    """The SDK resolves the endpoint a second time: re-check it right before the SDK call."""
    monkeypatch.setattr(connectors, "MULTI_TENANT", False, raising=False)   # custom endpoint opt-in
    monkeypatch.setitem(sys.modules, "boto3", types.SimpleNamespace(client=lambda *a, **kw: _FakeS3()))
    monkeypatch.setattr(connectors, "_ensure_public", lambda url, field: None)   # no DNS in tests
    seen = []
    monkeypatch.setattr(connectors, "_recheck_public", lambda cfg: seen.append(cfg["endpoint_url"]))

    connectors.list_objects(_s3_conn(), limit=1)

    assert seen == ["https://s3.example"]


def test_signed_url_rechecks_the_public_endpoint(monkeypatch):
    monkeypatch.setattr(connectors, "MULTI_TENANT", False, raising=False)
    monkeypatch.setitem(sys.modules, "boto3", types.SimpleNamespace(client=lambda *a, **kw: _FakeS3()))
    monkeypatch.setattr(connectors, "_ensure_public", lambda url, field: None)
    seen = []
    monkeypatch.setattr(connectors, "_recheck_public", lambda cfg: seen.append(cfg["endpoint_url"]))

    url = connectors._signed_url(_s3_conn(), "a.jpg")

    assert "X-Amz-Signature=fake" in url
    assert seen == ["https://s3.example"]


def test_recheck_public_rejects_a_private_endpoint():
    with pytest.raises(HTTPException) as exc:
        connectors._recheck_public({"endpoint_url": "http://127.0.0.1:9000"})
    assert exc.value.status_code == 400


def test_custom_s3_endpoint_is_rejected_in_multi_tenant_mode(monkeypatch):
    """I12: the SDK resolves again, so a hosted deployment cannot pin a custom endpoint."""
    monkeypatch.setattr(connectors, "MULTI_TENANT", True, raising=False)
    monkeypatch.setattr(connectors, "_ensure_public", lambda url, field: None)
    with pytest.raises(ValueError, match="multi-tenant"):
        connectors.validate("s3", {"bucket": "b", "endpoint_url": "https://s3.example"})


def test_custom_s3_endpoint_is_allowed_on_a_self_hosted_deployment(monkeypatch):
    monkeypatch.setattr(connectors, "MULTI_TENANT", False, raising=False)
    monkeypatch.setattr(connectors, "_ensure_public", lambda url, field: None)
    connectors.validate("s3", {"bucket": "b", "endpoint_url": "https://s3.example"})


def test_custom_azure_account_url_is_rejected_in_multi_tenant_mode(monkeypatch):
    monkeypatch.setattr(connectors, "MULTI_TENANT", True, raising=False)
    monkeypatch.setattr(connectors, "_ensure_public", lambda url, field: None)
    with pytest.raises(ValueError, match="multi-tenant"):
        connectors.validate("azure", {"container": "c", "account_url": "https://minio.example"})
    # the standard Azure host needs no custom endpoint and stays usable
    connectors.validate("azure", {"container": "c", "account_url": "https://acct.blob.core.windows.net"})
