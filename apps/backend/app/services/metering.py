"""Metering: monthly allowances for GPU time, stream hours and AI calls, plus current storage.

`record` only adds a row; the caller commits with whatever else it writes. GPU/stream/AI usage is
summed from the start of the local month, storage is the current all-time total (rows are deltas).
"""

import time
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import PLANS
from ..models import METRICS, UsageEvent, Workspace

LABELS = {"gpu_seconds": "GPU time", "stream_hours": "Stream hours", "ai_calls": "AI calls", "storage_bytes": "Storage"}
_TOTAL_METRICS = ("storage_bytes",)


def _check_metric(metric: str) -> str:
    if metric not in METRICS:
        raise ValueError("unknown usage metric")
    return metric


def record(
    db: Session, workspace_id: str, metric: str, quantity: float, project_id: str | None = None, **meta
) -> UsageEvent:
    """Add one metered quantity (uncommitted); the caller owns the transaction."""
    _check_metric(metric)
    if quantity < 0:
        raise ValueError("quantity must be >= 0")
    event = UsageEvent(
        workspace_id=workspace_id, project_id=project_id, metric=metric, quantity=float(quantity), meta=meta
    )
    db.add(event)
    return event


def adjust(
    db: Session, ws: Workspace, metric: str, quantity: float, project_id: str | None = None, **meta
) -> UsageEvent | None:
    """Add a signed delta to a total meter (storage), floored so usage never goes below zero.

    Deletes use a negative `quantity`; monthly meters are not adjustable because the window is history.
    """
    _check_metric(metric)
    if metric not in _TOTAL_METRICS:
        raise ValueError(f"{metric} is not a total meter")
    floor = max(float(quantity), -used(db, ws, metric))
    if floor == 0:
        return None
    event = UsageEvent(
        workspace_id=ws.id,
        project_id=project_id,
        metric=metric,
        quantity=floor,
        meta={**meta, "adjustment": True},
    )
    db.add(event)
    return event


def month_start(ts: float | None = None) -> float:
    """Timestamp of 00:00 on the first day of the local month containing `ts` (default: now)."""
    local = datetime.fromtimestamp(ts if ts is not None else time.time())
    return datetime(local.year, local.month, 1).timestamp()


def used(db: Session, ws: Workspace, metric: str, since: float | None = None) -> float:
    """Summed quantity for `metric`; `since=None` means all time (the storage total)."""
    _check_metric(metric)
    q = select(func.coalesce(func.sum(UsageEvent.quantity), 0.0)).where(
        UsageEvent.workspace_id == ws.id, UsageEvent.metric == metric
    )
    if since is not None:
        q = q.where(UsageEvent.created >= since)
    return float(db.scalar(q) or 0.0)


def project_used(db: Session, project_id: str, metric: str = "storage_bytes") -> float:
    """Summed quantity metered against one project (all time); used to refund a purge exactly."""
    _check_metric(metric)
    q = select(func.coalesce(func.sum(UsageEvent.quantity), 0.0)).where(
        UsageEvent.project_id == project_id, UsageEvent.metric == metric
    )
    return float(db.scalar(q) or 0.0)


def quota_for(ws: Workspace, metric: str) -> float:
    """Per-workspace override when set, else the plan allowance (unknown plans fall back to Free)."""
    _check_metric(metric)
    overrides = ws.quotas or {}
    if overrides.get(metric) is not None:
        return float(overrides[metric])
    return float(PLANS.get(ws.plan, PLANS["free"])[metric])


def check(db: Session, ws: Workspace, metric: str, amount: float = 1.0) -> None:
    """402 before the next unit would exceed the allowance; storage is checked against its total."""
    _check_metric(metric)
    since = None if metric in _TOTAL_METRICS else month_start()
    if used(db, ws, metric, since=since) + amount > quota_for(ws, metric):
        label = PLANS.get(ws.plan, PLANS["free"])["label"]
        raise HTTPException(402, f"{LABELS[metric]} quota reached on the {label} plan")


def remaining(db: Session, ws: Workspace, metric: str) -> float:
    """Allowance left in the current window; long jobs read this before each billable step."""
    _check_metric(metric)
    since = None if metric in _TOTAL_METRICS else month_start()
    return max(0.0, quota_for(ws, metric) - used(db, ws, metric, since=since))


def summary(db: Session, ws: Workspace) -> dict:
    """Current usage for every metric, shaped for the plan & usage page."""
    out = {}
    for metric in METRICS:
        total = metric in _TOTAL_METRICS
        out[metric] = {
            "used": used(db, ws, metric, since=None if total else month_start()),
            "quota": quota_for(ws, metric),
            "period": "total" if total else "month",
            "label": LABELS[metric],
        }
    return out


def daily(db: Session, ws: Workspace, days: int = 30) -> list[dict]:
    """Zero-filled per-day totals for the chart, oldest first; `date` is local YYYY-MM-DD.

    Storage rows are per-day deltas here (the summary is the running total), matching the meter.
    """
    if days <= 0:
        return []
    today = date.today()
    first = today - timedelta(days=days - 1)
    since = datetime(first.year, first.month, first.day).timestamp()
    events = db.scalars(select(UsageEvent).where(UsageEvent.workspace_id == ws.id, UsageEvent.created >= since)).all()
    buckets: dict[date, dict[str, float]] = {
        first + timedelta(days=i): dict.fromkeys(METRICS, 0.0) for i in range(days)
    }
    for event in events:
        day = datetime.fromtimestamp(event.created).date()
        if day in buckets and event.metric in buckets[day]:
            buckets[day][event.metric] += float(event.quantity or 0.0)
    return [{"date": day.isoformat(), **totals} for day, totals in sorted(buckets.items())]
