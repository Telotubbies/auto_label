"""Shared plumbing for the Insights Studio aggregations: data signature, TTL cache, model lookup."""

from __future__ import annotations

import hashlib
import json
import threading
import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Image, TrainedModel

CACHE_TTL = 1800  # signed file URLs live 6 h; a 30 min cache keeps them fresh
CACHE_MAX = 64

_CACHE: dict[str, tuple[str, float, dict]] = {}
_CACHE_LOCK = threading.Lock()


def signature(m: TrainedModel) -> str:
    """Stable hash of everything an evaluation payload is derived from."""
    payload = {
        "metrics": m.metrics or {},
        "history": m.history or [],
        "classes": m.classes or [],
        "version": m.version_id,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]


def data_stamp(db: Session, project_id: str) -> str:
    """Cheap dataset stamp: slices read live tags/batch/split/label source, so they must not go stale."""
    updated = (
        db.scalar(select(func.max(Image.updated)).where(Image.project_id == project_id))
        or 0.0
    )
    return hashlib.sha256(str(updated).encode()).hexdigest()[:8]


def cached(key: str, sig: str, build) -> tuple[dict, bool]:
    """Return (payload, hit). Entries expire after CACHE_TTL and evict in LRU order."""
    now = time.monotonic()
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if entry and entry[0] == sig and now - entry[1] < CACHE_TTL:
            _CACHE[key] = _CACHE.pop(key)  # refresh LRU order
            return entry[2], True
    payload = build()
    with _CACHE_LOCK:
        _CACHE[key] = (sig, now, payload)
        while len(_CACHE) > CACHE_MAX:
            _CACHE.pop(next(iter(_CACHE)))
    return payload, False


def clear_cache() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()


def model_in_project(db: Session, project_id: str, mid: str) -> TrainedModel:
    m = db.get(TrainedModel, mid)
    if not m or m.project_id != project_id:
        raise LookupError("model not found")
    return m
