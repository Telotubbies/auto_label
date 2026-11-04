"""Metering: usage rows, monthly windows, quotas, and the daily chart series."""

import os
import secrets
import tempfile
import time
from datetime import datetime

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-meter-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import PLANS
from app.db import SessionLocal
from app.main import app
from app.models import METRICS, UsageEvent, User, Workspace
from app.services import metering

GB = 1024**3


@pytest.fixture(scope="module", autouse=True)
def _schema():
    """The TestClient lifespan creates the schema; each test then uses its own workspace."""
    with TestClient(app):
        yield


def make_ws(db, plan: str = "free", **kw) -> Workspace:
    user = User(email=f"meter-{secrets.token_hex(4)}@labeldesk.dev", name="Meter")
    db.add(user)
    db.flush()
    ws = Workspace(slug=f"meter-{secrets.token_hex(4)}", name="Metering", owner_id=user.id, plan=plan, **kw)
    db.add(ws)
    db.commit()
    return ws


def test_record_and_used_sum():
    with SessionLocal() as db:
        ws = make_ws(db)
        ev = metering.record(db, ws.id, "gpu_seconds", 120, project_id="p1", job_id="j1")
        assert isinstance(ev, UsageEvent)
        assert ev.meta["job_id"] == "j1" and ev.project_id == "p1"
        metering.record(db, ws.id, "gpu_seconds", 30.5)
        db.commit()

        assert metering.used(db, ws, "gpu_seconds", since=metering.month_start()) == 150.5
        assert metering.used(db, ws, "gpu_seconds") == 150.5
        assert metering.used(db, ws, "ai_calls") == 0.0


def test_previous_month_excluded_but_storage_all_time():
    with SessionLocal() as db:
        ws = make_ws(db)
        old = metering.month_start() - 20 * 86400
        assert old < metering.month_start()

        stale_gpu = metering.record(db, ws.id, "gpu_seconds", 75)
        stale_gpu.created = old
        stale_storage = metering.record(db, ws.id, "storage_bytes", 2 * GB)
        stale_storage.created = old
        metering.record(db, ws.id, "gpu_seconds", 10)
        metering.record(db, ws.id, "storage_bytes", 0.5 * GB)
        db.commit()

        since = metering.month_start()
        assert metering.used(db, ws, "gpu_seconds", since=since) == 10
        assert metering.used(db, ws, "gpu_seconds") == 85
        assert metering.used(db, ws, "storage_bytes") == 2.5 * GB

        summary = metering.summary(db, ws)
        assert summary["gpu_seconds"]["used"] == 10 and summary["gpu_seconds"]["period"] == "month"
        assert summary["storage_bytes"]["used"] == 2.5 * GB and summary["storage_bytes"]["period"] == "total"


def test_quota_check_raises_402():
    with SessionLocal() as db:
        ws = make_ws(db)
        metering.record(db, ws.id, "gpu_seconds", PLANS["free"]["gpu_seconds"] - 5)
        db.commit()
        metering.check(db, ws, "gpu_seconds", 5)  # exactly at the limit is still allowed
        with pytest.raises(HTTPException) as err:
            metering.check(db, ws, "gpu_seconds", 6)
        assert err.value.status_code == 402
        assert err.value.detail == "GPU time quota reached on the Free plan"


def test_monthly_window_applies_to_check():
    with SessionLocal() as db:
        ws = make_ws(db, quotas={"gpu_seconds": 20})
        stale = metering.record(db, ws.id, "gpu_seconds", 100)
        stale.created = metering.month_start() - 40 * 86400
        metering.record(db, ws.id, "gpu_seconds", 15)
        db.commit()
        metering.check(db, ws, "gpu_seconds", 5)  # last month's 100 does not count
        with pytest.raises(HTTPException):
            metering.check(db, ws, "gpu_seconds", 6)


def test_workspace_quota_override_wins():
    with SessionLocal() as db:
        ws = make_ws(db, quotas={"gpu_seconds": "7", "ai_calls": 3})
        assert metering.quota_for(ws, "gpu_seconds") == 7.0
        assert metering.quota_for(ws, "ai_calls") == 3.0
        assert metering.quota_for(ws, "stream_hours") == float(PLANS["free"]["stream_hours"])

        metering.record(db, ws.id, "gpu_seconds", 7)
        db.commit()
        with pytest.raises(HTTPException):
            metering.check(db, ws, "gpu_seconds", 1)
        metering.check(db, ws, "ai_calls", 2)  # its own override, unrelated to GPU


def test_summary_and_daily_series():
    with SessionLocal() as db:
        ws = make_ws(db)
        metering.record(db, ws.id, "ai_calls", 4)
        yesterday = metering.record(db, ws.id, "stream_hours", 1.5)
        yesterday.created = time.time() - 86400
        metering.record(db, ws.id, "storage_bytes", GB)
        db.commit()

        summary = metering.summary(db, ws)
        assert set(summary) == set(METRICS)
        assert summary["gpu_seconds"]["label"] == "GPU time"
        assert summary["gpu_seconds"]["quota"] == float(PLANS["free"]["gpu_seconds"])
        assert summary["stream_hours"]["label"] == "Stream hours"
        assert summary["ai_calls"]["label"] == "AI calls"
        assert summary["storage_bytes"]["label"] == "Storage"

        rows = metering.daily(db, ws, days=7)
        assert len(rows) == 7
        assert [r["date"] for r in rows] == sorted(r["date"] for r in rows)
        assert set(rows[0]) == {"date", *METRICS}
        assert rows[-1]["date"] == datetime.fromtimestamp(time.time()).date().isoformat()
        assert rows[-1]["ai_calls"] == 4 and rows[-1]["storage_bytes"] == GB
        assert rows[-2]["stream_hours"] == 1.5


def test_month_start_is_local_first_day():
    start = datetime.fromtimestamp(metering.month_start())
    assert (start.day, start.hour, start.minute, start.second, start.microsecond) == (1, 0, 0, 0, 0)


def test_remaining_and_adjust_floor_at_zero():
    """I2: deletes release storage, and usage never goes below zero."""
    with SessionLocal() as db:
        ws = make_ws(db, quotas={"storage_bytes": 1000})
        metering.record(db, ws.id, "storage_bytes", 800)
        db.commit()
        assert metering.remaining(db, ws, "storage_bytes") == pytest.approx(200)

        metering.adjust(db, ws, "storage_bytes", -500)
        db.commit()
        assert metering.used(db, ws, "storage_bytes") == pytest.approx(300)

        metering.adjust(db, ws, "storage_bytes", -5000)
        db.commit()
        assert metering.used(db, ws, "storage_bytes") == 0.0

        with pytest.raises(ValueError):
            metering.adjust(db, ws, "gpu_seconds", -1)


def test_invalid_metric_and_negative_quantity():
    with SessionLocal() as db:
        ws = make_ws(db)
        with pytest.raises(ValueError):
            metering.record(db, ws.id, "tokens", 1)
        with pytest.raises(ValueError):
            metering.record(db, ws.id, "gpu_seconds", -0.5)
        n = db.scalar(select(func.count()).select_from(UsageEvent).where(UsageEvent.workspace_id == ws.id))
        assert n == 0
