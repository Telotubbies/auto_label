"""Worker liveness. One row per process; the admin console shows online/stale workers.

The loop beats on every poll but writes at most every few seconds, so an idle worker costs one
UPDATE per interval instead of one per 1.5 s tick.
"""
import os
import platform
import threading
import time

from sqlalchemy import select

from ..config import WORKER_STALE_S
from ..db import SessionLocal
from ..models import Worker, now

BEAT_EVERY_S = 5.0
_ID = f"{platform.node() or 'worker'}:{os.getpid()}"
_lock = threading.Lock()
_last = 0.0


def worker_id() -> str:
    return _ID


def beat(kinds: list[str] | None = None, current_job: str | None = None, force: bool = False) -> None:
    """Upsert this worker's heartbeat (throttled unless forced)."""
    global _last
    with _lock:
        t = time.monotonic()
        if not force and t - _last < BEAT_EVERY_S:
            return
        _last = t
    with SessionLocal() as db:
        w = db.get(Worker, _ID)
        if w is None:
            w = Worker(id=_ID, host=platform.node() or "", started=now())
            db.add(w)
        if kinds is not None:
            w.kinds = list(kinds)
        w.current_job = current_job
        w.last_seen = now()
        db.commit()


def workers(db, stale_after: float = WORKER_STALE_S) -> list[dict]:
    cutoff = now() - stale_after
    rows = db.scalars(select(Worker).order_by(Worker.last_seen.desc())).all()
    return [{"id": w.id, "host": w.host, "kinds": w.kinds or [], "started": w.started,
             "last_seen": w.last_seen, "current_job": w.current_job, "online": w.last_seen >= cutoff}
            for w in rows]
