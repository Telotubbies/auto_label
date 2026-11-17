"""T-1301: liveness that touches nothing, readiness that names the check that failed.

`/api/health` stays the cheap alias the runbooks quote; `/api/healthz` answers "is the process
alive" and `/api/readyz` answers "can it serve": database, data directory, secret, worker. The
payload is four booleans — no DSN, no path, no exception text, so a probe can be public.
"""
import logging
import os
import time
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import config, ratelimit
from app.db import SessionLocal
from app.main import app
from app.models import Worker, now
from app.routers import health
from app.services import heartbeat

REPO = Path(__file__).resolve().parents[3]
COMPOSE = REPO / "deploy" / "docker-compose.yml"
ALL_OK = {"ok": True, "checks": {"db": True, "data_dir": True, "secret": True, "worker": True}}


def _fresh_heartbeat() -> None:
    """Stamp this process's own worker row, as the embedded worker does on every poll."""
    deadline = time.time() + 10
    while time.time() < deadline:
        with SessionLocal() as db:
            row = db.get(Worker, heartbeat.worker_id())
            if row is not None:
                row.last_seen = now()
                db.commit()
                return
        time.sleep(0.05)
    raise AssertionError("the embedded worker never wrote its heartbeat row")


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        _fresh_heartbeat()
        yield client


def _failing(name: str, c, also: frozenset[str] = frozenset()) -> None:
    """Readiness is 503 and the broken dependency is named; every other check stays green."""
    r = c.get("/api/readyz")
    assert r.status_code == 503, r.text
    body = r.json()
    assert body["ok"] is False
    assert set(body["checks"]) == {"db", "data_dir", "secret", "worker"}
    assert {k for k, v in body["checks"].items() if v is False} == {name, *also}, body


def test_healthz_touches_no_database(monkeypatch, c):
    def boom(*_a, **_k):
        raise AssertionError("/api/healthz opened a database session")

    monkeypatch.setattr(health, "SessionLocal", boom)
    r = c.get("/api/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_healthz_is_200_when_the_app_is_up(c):
    r = c.get("/api/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_readyz_is_200_when_every_check_passes(c):
    _fresh_heartbeat()
    r = c.get("/api/readyz")
    assert r.status_code == 200, r.text
    assert r.json() == ALL_OK


def test_readyz_is_503_for_a_database_on_a_closed_port(c, monkeypatch):
    dead = create_engine("postgresql+psycopg2://labeldesk:x@127.0.0.1:1/labeldesk",
                         connect_args={"connect_timeout": 1})
    monkeypatch.setattr(health, "SessionLocal", sessionmaker(bind=dead))
    try:
        # the worker heartbeat lives in the same database, so it is honestly false too
        _failing("db", c, also=frozenset({"worker"}))
    finally:
        dead.dispose()


@pytest.mark.skipif(os.name == "nt", reason="Windows ignores the read-only directory mode bit")
def test_readyz_is_503_when_the_data_dir_is_read_only(tmp_path, c, monkeypatch):
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o500)
    monkeypatch.setattr(config, "DATA_DIR", ro)
    try:
        _failing("data_dir", c)
    finally:
        ro.chmod(0o700)


def test_readyz_is_503_without_a_secret(c, monkeypatch):
    monkeypatch.setattr(config, "SECRET", "")
    _failing("secret", c)


def test_readyz_is_503_with_a_stale_worker_row(c):
    try:
        with SessionLocal() as db:
            row = db.get(Worker, heartbeat.worker_id())
            assert row is not None, "the embedded worker never wrote its heartbeat row"
            row.last_seen = now() - config.WORKER_STALE_S - 60
            db.commit()
        _failing("worker", c)
    finally:
        _fresh_heartbeat()


def test_readyz_never_leaks_internals(c, monkeypatch, caplog):
    dead = create_engine("postgresql+psycopg2://labeldesk:x@127.0.0.1:1/labeldesk",
                         connect_args={"connect_timeout": 1})
    monkeypatch.setattr(health, "SessionLocal", sessionmaker(bind=dead))
    try:
        with caplog.at_level(logging.DEBUG, logger="labeldesk.health"):
            r = c.get("/api/readyz")
    finally:
        dead.dispose()
    assert r.status_code == 503
    body = r.text.lower()
    logs = " ".join(rec.getMessage() for rec in caplog.records if rec.name == "labeldesk.health").lower()
    for forbidden in ("postgresql", "127.0.0.1", "traceback", "operationalerror",
                      str(config.DATA_DIR).lower(), ".db"):
        assert forbidden not in body, f"the payload leaks {forbidden!r}"
        assert forbidden not in logs, f"the log line leaks {forbidden!r}"
    assert "db" in logs, "the failing check must name itself in the log too"


def test_health_still_answers_the_documented_payload(c):
    r = c.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "service": "labeldesk"}


def test_readyz_is_rate_limited():
    was = ratelimit.ENABLED
    ratelimit.ENABLED = True
    ratelimit._hits.clear()
    try:
        with TestClient(app) as client:
            codes = [client.get("/api/readyz").status_code for _ in range(31)]
    finally:
        ratelimit.ENABLED = was
    assert codes[:30] == [200] * 30, codes
    assert codes[30] == 429, codes


def test_compose_api_has_a_readyz_healthcheck():
    services = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]
    check = services["api"]["healthcheck"]
    assert check["test"][0] == "CMD"
    assert "/api/readyz" in " ".join(str(part) for part in check["test"])
    assert check["interval"] == "10s"
    assert check["timeout"] == "4s"
    assert check["retries"] == 6
    assert check["start_period"] == "30s"
    assert services["web"]["depends_on"]["api"]["condition"] == "service_healthy", (
        "web must start only after the API reports ready")
