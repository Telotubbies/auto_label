"""Liveness and readiness for orchestrators, Caddy and the recovery runbook.

`/api/healthz` answers "is the process alive" and touches nothing. `/api/readyz` answers "can it
serve": database, data directory, secret, worker. Each check is one function returning a bool, so a
failure names itself in the payload and the log line — and never leaks a DSN, a path or an exception.
"""
import logging
import tempfile
import threading

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .. import config
from ..db import SessionLocal
from ..models import Worker, now
from ..ratelimit import client_ip, limit
from ..services import heartbeat

log = logging.getLogger("labeldesk.health")
router = APIRouter(tags=["health"])

LIMIT_PER_MIN = 30
DB_BUDGET_S = 2.0


def _db_ok() -> bool:
    """`SELECT 1` through the session factory, bounded so a wedged connection cannot hang the probe."""
    ok = False

    def probe() -> None:
        nonlocal ok
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
            ok = True
        except Exception:  # noqa: S110  # the route names the check; the why would leak internals
            pass

    # shortcut: a wedged driver can leak one daemon thread per probe; upgrade to a connection-level
    # statement/connect timeout if that ever shows up in the field.
    t = threading.Thread(target=probe, daemon=True, name="readyz-db")
    t.start()
    t.join(DB_BUDGET_S)
    return ok


def _data_dir_ok() -> bool:
    """A one-byte write and delete: a full or read-only data volume fails here, not at upload time."""
    try:
        with tempfile.NamedTemporaryFile(dir=config.DATA_DIR, prefix=".readyz-") as f:
            f.write(b"x")
            f.flush()
        return True
    except Exception:
        return False


def _secret_ok() -> bool:
    """Present or not: never the length or the value."""
    return bool(config.SECRET)


def _worker_ok() -> bool:
    """A separate worker process reports itself; an embedded one must have beaten recently."""
    if not config.EMBEDDED_WORKER:
        return True
    try:
        with SessionLocal() as db:
            row = db.get(Worker, heartbeat.worker_id())
            return row is not None and row.last_seen >= now() - config.WORKER_STALE_S
    except Exception:
        return False


@router.get("/api/healthz")
def healthz(request: Request):
    limit(f"healthz:{client_ip(request)}", LIMIT_PER_MIN, 60)
    return {"ok": True}


@router.get("/api/readyz")
def readyz(request: Request):
    limit(f"readyz:{client_ip(request)}", LIMIT_PER_MIN, 60)
    checks = {
        "db": _db_ok(),
        "data_dir": _data_dir_ok(),
        "secret": _secret_ok(),
        "worker": _worker_ok(),
    }
    ok = all(checks.values())
    if not ok:
        log.warning("readyz failed: %s", ", ".join(k for k, passed in checks.items() if not passed))
    return JSONResponse(status_code=200 if ok else 503, content={"ok": ok, "checks": checks})
