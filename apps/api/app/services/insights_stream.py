"""Stream analytics: event volume per rule/zone/class, dwell distribution, hourly heatmap, cameras.

Events carry a rule snapshot from the moment they fired, so the breakdown stays truthful even when
the stream's rules are edited later. Only the last `days` of project events are read, and the
payload is cached by (count, newest ts, reviewed count).
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Project, Stream, StreamEvent
from .insights_common import cached

DAY = 86400
DEFAULT_DAYS = 30
DWELL_BUCKETS = (
    ("0–5 s", 0.0, 5.0),
    ("5–15 s", 5.0, 15.0),
    ("15–30 s", 15.0, 30.0),
    ("30–60 s", 30.0, 60.0),
    ("60–120 s", 60.0, 120.0),
    ("120 s+", 120.0, float("inf")),
)
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_DWELL_RE = re.compile(r"dwelled\s+([\d.]+)s")


def _seconds(ev: StreamEvent) -> float | None:
    """Dwell duration: stored by current rules, parsed from the summary for older events."""
    raw = (ev.rule or {}).get("seconds")
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    if (ev.rule or {}).get("kind") != "dwell":
        return None
    match = _DWELL_RE.search(ev.summary or "")
    return float(match.group(1)) if match else None


def _class_tokens(ev: StreamEvent) -> list[str]:
    return [c for c in (ev.classes or "").split("|") if c]


def _rule_label(ev: StreamEvent) -> str:
    rule = ev.rule or {}
    return str(
        rule.get("label") or rule.get("kind") or f"Rule {rule.get('index', '')}"
    ).strip()


def _zone(ev: StreamEvent, zones: dict[str, list[dict]]) -> str | None:
    zone_id = (ev.rule or {}).get("zone_id")
    if not isinstance(zone_id, str) or not zone_id:
        return None
    zone = next(
        (z for z in zones.get(ev.stream_id, []) if z.get("id") == zone_id), None
    )
    return str((zone or {}).get("label") or zone_id)


def _day(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).date().isoformat()


def _hour(ts: float) -> int:
    return datetime.fromtimestamp(ts, timezone.utc).hour


def fetch(
    db: Session,
    project: Project,
    days: int = DEFAULT_DAYS,
    stream_id: str | None = None,
) -> tuple[list[dict], dict[str, Stream]]:
    """Project events in the window, flattened with their display labels (no credentials)."""
    since = time.time() - days * DAY
    stmt = (
        select(StreamEvent, Stream)
        .join(Stream, Stream.id == StreamEvent.stream_id)
        .where(Stream.project_id == project.id, StreamEvent.ts >= since)
    )
    if stream_id:
        stmt = stmt.where(StreamEvent.stream_id == stream_id)
    streams = {
        s.id: s
        for s in db.scalars(select(Stream).where(Stream.project_id == project.id)).all()
    }
    zones = {sid: s.zones or [] for sid, s in streams.items()}
    out: list[dict] = []
    for ev, stream in db.execute(stmt.order_by(StreamEvent.ts)).all():
        out.append(
            {
                "id": ev.id,
                "ts": ev.ts,
                "reviewed": bool(ev.reviewed),
                "stream_id": stream.id,
                "stream_name": stream.name,
                "rule": _rule_label(ev),
                "kind": (ev.rule or {}).get("kind") or "",
                "zone": _zone(ev, zones),
                "classes": _class_tokens(ev),
                "seconds": _seconds(ev),
                "day": _day(ev.ts),
                "hour": _hour(ev.ts),
            }
        )
    return out, streams


def _series(rows: list[dict], dates: list[str], key: str, top: int = 8) -> list[dict]:
    """Daily series for the largest `key` groups; the remainder folds into Other so totals hold."""
    totals: Counter = Counter()
    for row in rows:
        for value in row.get(key) if isinstance(row.get(key), list) else [row.get(key)]:
            if value:
                totals[value] += 1
    keep = {name for name, _n in totals.most_common(top)}
    index = {d: i for i, d in enumerate(dates)}
    buckets: dict[str, list[int]] = {name: [0] * len(dates) for name in keep}
    other = [0] * len(dates)
    for row in rows:
        values = row.get(key) if isinstance(row.get(key), list) else [row.get(key)]
        i = index.get(row["day"])
        if i is None:
            continue
        for value in values:
            if not value:
                continue
            if value in keep:
                buckets[value][i] += 1
            else:
                other[i] += 1
    series = [{"name": name, "values": buckets[name]} for name in sorted(keep)]
    if any(other):
        series.append({"name": "Other", "values": other})
    return series


def _breakdown(rows: list[dict], key: str) -> list[dict]:
    counts: Counter = Counter()
    for row in rows:
        for value in row.get(key) if isinstance(row.get(key), list) else [row.get(key)]:
            if value:
                counts[value] += 1
    return [
        {"key": name, "value": n}
        for name, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def _breakdown_from(rows: list[dict], read) -> list[dict]:
    counts: Counter = Counter()
    for row in rows:
        for value in read(row):
            if value:
                counts[value] += 1
    return [
        {"key": name, "value": n}
        for name, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def _hourly(rows: list[dict]) -> dict:
    cells: Counter = Counter()
    for row in rows:
        weekday = datetime.fromtimestamp(row["ts"], timezone.utc).weekday()
        cells[(weekday, row["hour"])] += 1
    return {
        "days": list(WEEKDAYS),
        "hours": [f"{h:02d}" for h in range(24)],
        "values": [[w, h, n] for (w, h), n in sorted(cells.items())],
    }


def analytics(db: Session, project: Project, days: int = DEFAULT_DAYS) -> dict:
    def compute() -> dict:
        rows, streams = fetch(db, project, days)
        since = time.time() - days * DAY
        today = datetime.fromtimestamp(time.time(), timezone.utc).date()
        dates = [
            (today - timedelta(days=days - 1 - i)).isoformat() for i in range(days)
        ]
        dwell = [r["seconds"] for r in rows if r["seconds"] is not None]
        buckets = []
        for label, lo, hi in DWELL_BUCKETS:
            buckets.append(sum(1 for s in dwell if lo <= s < hi))
        cameras: Counter = Counter(r["stream_id"] for r in rows)
        reviewed: Counter = Counter(r["stream_id"] for r in rows if r["reviewed"])
        last: dict[str, float] = {}
        for row in rows:
            last[row["stream_id"]] = max(last.get(row["stream_id"], 0.0), row["ts"])
        top = [
            {
                "id": sid,
                "name": streams[sid].name,
                "events": n,
                "reviewed": reviewed.get(sid, 0),
                "last_event": last.get(sid, 0.0),
            }
            for sid, n in cameras.most_common()
        ]
        return {
            "window": {"days": days, "since": since},
            "totals": {
                "events": len(rows),
                "reviewed": sum(1 for r in rows if r["reviewed"]),
                "cameras": len(cameras),
                "dwell_seconds": round(sum(dwell), 1),
                "last_event": max((r["ts"] for r in rows), default=0.0),
            },
            "top_cameras": top,
            "breakdown": {
                "rule": _breakdown(rows, "rule"),
                "zone": _breakdown(rows, "zone"),
                "class": _breakdown(rows, "classes"),
                "stream": _breakdown_from(rows, lambda r: [r["stream_name"]]),
            },
            "dwell": {
                "buckets": [b[0] for b in DWELL_BUCKETS],
                "counts": buckets,
                "samples": len(dwell),
                "max": max(dwell, default=0.0),
            },
            "hourly": _hourly(rows),
            "over_time": {
                "dates": dates,
                "by_rule": _series(rows, dates, "rule"),
                "by_zone": _series(rows, dates, "zone"),
                "by_class": _series(rows, dates, "classes"),
            },
        }

    stamp = _stamp(db, project, days)
    payload, _hit = cached(f"streams:{project.id}:{days}", stamp, compute)
    return payload


def _stamp(db: Session, project: Project, days: int) -> str:
    since = time.time() - days * DAY
    count, newest, reviewed = db.execute(
        select(
            func.count(StreamEvent.id),
            func.max(StreamEvent.ts),
            func.sum(StreamEvent.reviewed),
        )
        .join(Stream, Stream.id == StreamEvent.stream_id)
        .where(Stream.project_id == project.id, StreamEvent.ts >= since)
    ).one()
    # Names, zones and rules shape the labels in the payload, so a rename or edit must bust the cache.
    config = db.execute(
        select(Stream.id, Stream.name, Stream.zones, Stream.rules).where(
            Stream.project_id == project.id
        )
    ).all()
    digest = hashlib.sha256(
        json.dumps([list(row) for row in config], sort_keys=True, default=str).encode()
    ).hexdigest()[:12]
    return f"{count or 0}:{newest or 0}:{reviewed or 0}:{digest}"
