"""Shared test environment.

Set once, before any test module imports `app`, so the whole session shares one temp data dir.
The base directory is created under `LD_TEST_TMP` when set, else under the system temp dir, and
is removed when the session finishes. Test modules must not create their own temp dirs.
The suite logs in once per module, which is more than the 8-per-5-minutes login allowance, so the
in-process rate limiter is off by default; only the test that exercises it turns it on. The autouse
fixture restores the default and clears the hit counters after every test so one limiter test
cannot poison the next module. Webhook retries are driven explicitly (no background flush loop).
"""
import gc
import os
import shutil
import tempfile
import time

_OWN_DATA_DIR = "LD_DATA_DIR" not in os.environ
if _OWN_DATA_DIR:
    _TMP_ROOT = os.environ.get("LD_TEST_TMP") or tempfile.gettempdir()
    os.makedirs(_TMP_ROOT, exist_ok=True)
    TEST_TMP = tempfile.mkdtemp(prefix="ld-tests-", dir=_TMP_ROOT)
    os.environ["LD_DATA_DIR"] = TEST_TMP
else:
    TEST_TMP = os.environ["LD_DATA_DIR"]
os.environ.setdefault("LD_EMBEDDED_WORKER", "1")
os.environ.setdefault("LD_WORKER_TOKEN", "test-worker-token-0123456789abcdef")
os.environ.setdefault("LD_SAM_ENABLED", "0")
os.environ.setdefault("LD_CLIP", "0")              # optional CLIP: keep the cheap deterministic features
os.environ.setdefault("LD_RATE_LIMIT", "0")
os.environ.setdefault("LD_WEBHOOK_FLUSH", "0")
# Values read once at `app` import: pin them here, not in the module that happens to import first,
# or a mixed pytest selection freezes the wrong ones for every later module (I15).
os.environ["LD_ENV"] = "dev"
os.environ["LD_MAIL_DEV"] = "1"
os.environ["LD_PUBLIC_URL"] = "http://localhost:5173"   # the dev inbox also requires a localhost origin
os.environ["LD_SEED_DEMO"] = "1"
# The suite exercises the shipped surfaces; a workspace turns them off through the same flag API.
os.environ["LD_FLAGS_ON"] = "task_10b,task_20c,task_22,task_23"

import pytest


def pytest_sessionfinish(session, exitstatus):
    if not _OWN_DATA_DIR:
        return
    try:
        from app.db import engine
        engine.dispose()                 # close pooled SQLite handles or Windows blocks the delete
    except Exception:
        pass
    gc.collect()
    for _ in range(20):                  # a worker thread may still be finishing its last write
        shutil.rmtree(TEST_TMP, ignore_errors=True)
        if not os.path.exists(TEST_TMP):
            return
        time.sleep(0.1)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    yield
    from app import ratelimit
    ratelimit.ENABLED = os.environ.get("LD_RATE_LIMIT", "1") != "0"
    ratelimit._hits.clear()


@pytest.fixture(scope="session", autouse=True)
def _seeded_database():
    """Create the schema and demo account once, before any module inserts its own rows.

    Production seeding is disabled on a non-empty or production database (M7); tests must not
    depend on that production behaviour, so they ask for the seed explicitly here.
    """
    from app import bootstrap
    bootstrap.init_db()
