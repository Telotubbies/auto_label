"""Bridge rule-engine firings to the PLC / OT outputs.

The stream worker owns the rule index; this helper merges the rule (a class may be needed
for the output filter) into the engine event and queues it for the actuator thread. The
manager calls it from ``_record`` after writing the event row:

    ot_bridge.enqueue_rule_events(self, [ev], ts)

``dispatch_rule_events`` is the synchronous variant for tests and callers that already own
a session. Keeping the bridge duck-typed means the stream module can be merged independently
of the OT feature.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..services import ot


def _merged(stream, event: dict) -> dict:
    """The engine event plus the rule that fired, so class/zone filters can be applied."""
    rules = list(getattr(stream, "rules", []) or [])
    index = event.get("rule")
    rule = rules[index] if isinstance(index, int) and 0 <= index < len(rules) else {}
    return {**rule, **event, "index": index}


def dispatch_rule_events(db: Session, stream, events: list[dict], event_ts: float) -> list:
    """Dispatch each firing synchronously (tests and callers that already own a session)."""
    deliveries = []
    for event in events or []:
        deliveries.extend(ot.dispatch_event(
            db, getattr(stream, "project_id", ""), _merged(stream, event), event_ts=event_ts,
            stream_id=getattr(stream, "id", ""), workspace_id=getattr(stream, "workspace_id", "")))
    return deliveries


def enqueue_rule_events(stream, events: list[dict], event_ts: float) -> int:
    """Queue each firing for the actuator thread; returns how many were accepted.

    This is what the stream processor calls: no database session, no socket, no sleep on the
    capture thread. A disabled workspace flag is re-checked by the actuator before it writes.
    """
    accepted = 0
    for event in events or []:
        if ot.enqueue(getattr(stream, "workspace_id", ""), getattr(stream, "project_id", ""),
                      _merged(stream, event), event_ts, getattr(stream, "id", "")):
            accepted += 1
    return accepted
