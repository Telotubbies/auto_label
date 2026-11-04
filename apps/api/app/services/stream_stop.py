"""Bounded stream shutdown for project trash/purge and the flags kill switch (I-4).

A request must not join every camera worker inline: one slow ``read()``/``predict()`` per stream
would hold the HTTP call for seconds each. ``stop_streams`` signals every worker first, waits a
small shared budget, and audits any stream that is still draining. The threads themselves exit on
their own stop event and ``_Worker._record`` re-checks ``Project.deleted_at`` before writing, so
no snapshot or event row can land after the project was trashed or purged (C2).
"""
from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session

from ..deps import audit
from ..models import Stream
from ..streams.manager import manager

# Total synchronous wait per request, not per stream: 20 cameras cost 0.25 s, not 80 s.
STOP_BUDGET_S = 0.25


def stop_streams(
    db: Session,
    stream_ids: Iterable[str],
    *,
    workspace_id: str,
    user_id: str | None,
    reason: str,
    budget: float = STOP_BUDGET_S,
) -> list[str]:
    """Signal every worker, wait at most ``budget``, audit the ones still draining.

    Status writes and the audit row use the caller's session, so they commit atomically with each
    other and with the flag write; the trash commits ``deleted_at`` earlier, before the signal, so
    the worker guard sees it.
    """
    ids = [sid for sid in dict.fromkeys(stream_ids) if sid]
    if not ids:
        return []
    draining = manager.stop_many(ids, budget=budget)
    for sid in ids:
        row = db.get(Stream, sid)
        if row is not None:
            row.status = "stopping" if sid in draining else "stopped"
            row.last_error = ""
    if draining:
        audit(db, workspace_id, user_id, "stream.stop_draining", reason,
              streams=draining, count=len(draining))
    return draining
