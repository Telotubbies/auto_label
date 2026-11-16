"""Hand a committed stream event to the alert dispatcher without blocking the stream worker.

`notify` only queues; one daemon thread opens its own session, so a slow provider (or a dead
one) can never stall capture or the rules loop. Failures are logged and dropped — an alert is
a side effect, never a reason to lose an event.
"""

from __future__ import annotations

import logging
import queue
import threading

from ..db import session_scope
from ..services import alerts

log = logging.getLogger("labeldesk.streams.alerts")

_queue: queue.Queue = queue.Queue(maxsize=100)
_lock = threading.Lock()
_started = False


def _run() -> None:
    while True:
        workspace_id, event = _queue.get()
        try:
            with session_scope() as db:
                alerts.dispatch(db, workspace_id, event)
        except Exception:
            log.exception("stream event %s: alert dispatch failed", event.get("event_id"))
        finally:
            _queue.task_done()


def _start() -> None:
    global _started
    with _lock:
        if _started:
            return
        threading.Thread(target=_run, name="alert-bridge", daemon=True).start()
        _started = True


def notify(workspace_id: str, event: dict) -> None:
    """Queue one committed event. Callers have already persisted the `StreamEvent` row."""
    _start()
    try:
        _queue.put_nowait((workspace_id, dict(event)))
    except queue.Full:  # alerting backpressure must not slow the camera
        log.warning("alert queue is full — dropped event %s", event.get("event_id"))


def wait_idle() -> None:
    """Block until the dispatcher has finished the events queued so far (tests, shutdown)."""
    _queue.join()
