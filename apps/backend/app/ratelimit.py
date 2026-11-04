"""In-process sliding-window rate limiter (single API host). Disable with LD_RATE_LIMIT=0."""
import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

ENABLED = os.environ.get("LD_RATE_LIMIT", "1") != "0"
_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def client_ip(request: Request) -> str:
    # behind Caddy/nginx uvicorn runs with --proxy-headers, so request.client is the real peer
    return request.client.host if request.client else "?"


def limit(key: str, n: int, window: float):
    """Allow n hits per `window` seconds for `key`; raise 429 beyond that."""
    if not ENABLED:
        return
    now = time.monotonic()
    with _lock:
        q = _hits[key]
        while q and q[0] <= now - window:
            q.popleft()
        if len(q) >= n:
            retry = int(q[0] + window - now) + 1
            raise HTTPException(429, "too many attempts — try again shortly", headers={"Retry-After": str(retry)})
        q.append(now)
        if len(_hits) > 50_000:            # bound memory under key-spraying
            for k in list(_hits)[:10_000]:
                if not _hits[k] or _hits[k][-1] <= now - 3600:
                    _hits.pop(k, None)
