"""Shared test environment.

Set once, before any test module imports `app`, so the whole session shares one temp data dir.
The suite logs in once per module, which is more than the 8-per-5-minutes login allowance, so the
in-process rate limiter is off by default; only the test that exercises it turns it on. The autouse
fixture restores the default and clears the hit counters after every test so one limiter test
cannot poison the next module. Webhook retries are driven explicitly (no background flush loop).
"""
import os
import tempfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-tests-"))
os.environ.setdefault("LD_EMBEDDED_WORKER", "1")
os.environ.setdefault("LD_WORKER_TOKEN", "test-worker-token-0123456789abcdef")
os.environ.setdefault("LD_SAM_ENABLED", "0")
os.environ.setdefault("LD_RATE_LIMIT", "0")
os.environ.setdefault("LD_WEBHOOK_FLUSH", "0")

import pytest


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    yield
    from app import ratelimit
    ratelimit.ENABLED = os.environ.get("LD_RATE_LIMIT", "1") != "0"
    ratelimit._hits.clear()
