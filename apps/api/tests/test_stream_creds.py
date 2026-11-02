"""RTSP credentials at rest: sealed URLs never expose the password, masked URLs stay usable in the UI."""

import os
import tempfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-test-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

from app import models
from app.services import secretbox
from app.streams import creds

RTSP = "rtsp://viewer:S3cretPassw0rd@cam.example.test:554/live"


def test_seal_and_open_round_trip():
    sealed = creds.seal_source(RTSP)
    assert sealed != RTSP
    assert creds.is_sealed(sealed)
    assert sealed.startswith(secretbox.PREFIX)
    assert "S3cretPassw0rd" not in sealed
    assert creds.open_source(sealed) == RTSP
    assert creds.seal_source(sealed) == sealed  # already sealed: untouched


def test_credential_free_url_is_untouched():
    plain = "rtsp://cam.example.test/live"
    assert creds.seal_source(plain) == plain
    assert creds.open_source(plain) == plain
    assert creds.mask_source(plain) == plain


def test_mask_hides_the_password_but_keeps_the_user():
    sealed = creds.seal_source(RTSP)
    masked = creds.mask_source(sealed)
    assert "S3cretPassw0rd" not in masked
    assert secretbox.PREFIX not in masked
    assert "viewer" in masked
    assert "****" in masked
    assert "cam.example.test" in masked
    assert creds.mask_source(RTSP) == masked


def test_mask_never_leaks_ciphertext(monkeypatch):
    sealed = creds.seal_source(RTSP)

    def broken(value):
        raise ValueError("cannot decrypt")

    monkeypatch.setattr(secretbox, "decrypt", broken)
    assert creds.mask_source(sealed) == ""


def test_seal_existing_is_a_noop_without_stream_model(monkeypatch):
    monkeypatch.setattr(models, "Stream", None)   # a build that predates Task 10b
    assert creds.seal_existing(None) == 0
