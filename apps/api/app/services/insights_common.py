"""Shared plumbing for the Insights Studio aggregations: data signature, TTL cache, model lookup.

The cache is scoped per project (or per project+model/stream surface) and every scope is bounded,
so a burst of distinct widget specs from one project can neither grow the process without limit
nor evict every other project's entries (I11). TTL/LRU bookkeeping comes from ``cachetools``
(MIT) instead of a hand-rolled dict.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections import OrderedDict

from cachetools import TTLCache
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Image, TrainedModel

CACHE_TTL = 1800  # signed file URLs live 6 h; a 30 min cache keeps them fresh
CACHE_MAX = 256  # hard key ceiling for the process (all scopes together)
CACHE_MAX_PER_SCOPE = 16  # widget specs one project may keep resident

_SCOPES: "OrderedDict[str, TTLCache]" = OrderedDict()
_CACHE_LOCK = threading.Lock()
_MISSING = object()


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


def _scope_cache(scope: str) -> TTLCache:
    """The LRU scope for ``scope``, creating it and trimming the process ceiling when needed."""
    cache = _SCOPES.pop(scope, None)  # move-to-end keeps recently used scopes
    if cache is None:
        cache = TTLCache(maxsize=CACHE_MAX_PER_SCOPE, ttl=CACHE_TTL)
    _SCOPES[scope] = cache
    total = sum(len(entry) for entry in _SCOPES.values())
    while total > CACHE_MAX and len(_SCOPES) > 1:
        _old_scope, old = _SCOPES.popitem(last=False)
        total -= len(old)
    return cache


def cached(scope: str, key: str, sig: str, build) -> tuple[dict, bool]:
    """Return (payload, hit) for one key in ``scope``; entries expire after CACHE_TTL."""
    entry_key = (key, sig)  # a changed signature is a new key, so a stale payload is never read
    with _CACHE_LOCK:
        hit = _scope_cache(scope).get(entry_key, _MISSING)
        if hit is not _MISSING:
            return hit, True
    payload = build()
    with _CACHE_LOCK:
        _scope_cache(scope)[entry_key] = payload
    return payload, False


def cache_size(scope: str) -> int:
    """Live entries held for one scope (ops and tests)."""
    with _CACHE_LOCK:
        cache = _SCOPES.get(scope)
        if cache is None:
            return 0
        cache.expire()
        return len(cache)


def cache_total() -> int:
    """Live entries held across every scope; never above CACHE_MAX."""
    with _CACHE_LOCK:
        for cache in _SCOPES.values():
            cache.expire()
        return sum(len(cache) for cache in _SCOPES.values())


def clear_cache() -> None:
    with _CACHE_LOCK:
        _SCOPES.clear()


def model_in_project(db: Session, project_id: str, mid: str) -> TrainedModel:
    m = db.get(TrainedModel, mid)
    if not m or m.project_id != project_id:
        raise LookupError("model not found")
    return m
