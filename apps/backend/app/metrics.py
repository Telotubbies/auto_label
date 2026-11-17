"""Prometheus exposition for the API: request rate, error rate and latency (MONITORING-PLAN §4.2).

The contract is four HTTP series plus build info. The registry is private on purpose: the client's
default one also carries `python_gc_*`/`process_*`, which nothing here promises and no alert reads.

Labels are bounded by construction. `route` is always the matched route *template* (or
`<unmatched>`), never a raw path, so a scanner walking ids cannot manufacture series; nothing names
a workspace, a user, an email or a file. The surface is closed unless `LD_METRICS_TOKEN` is set:
404 when this deployment publishes nothing, 401 for a wrong token, and the body never says which.
"""
import hmac
import time

from fastapi import APIRouter, Header, HTTPException, Response
from prometheus_client import (CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram,
                               generate_latest)

from . import config
from .routers import health

REGISTRY = CollectorRegistry()          # process-local: the eight series below, nothing else

# 5 ms – 10 s: every load level a p50/p95/p99 is read at, from a cached list to a cold export.
BUCKETS = (.005, .01, .025, .05, .1, .15, .25, .5, 1, 2.5, 5, 10)
REQUESTS = Counter("labeldesk_http_requests_total", "HTTP requests by route template and status class",
                   ("method", "route", "status_class"), registry=REGISTRY)
DURATION = Histogram("labeldesk_http_request_duration_seconds", "HTTP request duration in seconds",
                     ("method", "route"), buckets=BUCKETS, registry=REGISTRY)
EXCEPTIONS = Counter("labeldesk_http_exceptions_total", "Unhandled exceptions by route template and type",
                     ("route", "type"), registry=REGISTRY)
INFLIGHT = Gauge("labeldesk_http_inflight", "API requests being served right now", registry=REGISTRY)
BUILD_INFO = Gauge("labeldesk_build_info", "The running API version", ("version",), registry=REGISTRY)
DB_UP = Gauge("labeldesk_db_up", "1 when the readiness database check passes", registry=REGISTRY)
BUILD_INFO.labels(version=config.APP_VERSION).set(1)

# --- T-1311 appends the queue, job, worker, disk and GPU gauges to this registry here. ------------


def _route(scope) -> str:
    """The matched template, or `<unmatched>`: a raw path would be one series per id."""
    return getattr(scope.get("route"), "path", "") or "<unmatched>"


class MetricsMiddleware:
    """One observation per `/api` request, in a `finally` so the exception path counts too.

    Raw ASGI on purpose: it reads the same scope the router fills in (that is where the template
    lives), and it never buffers a response. It sits inside `RequestLogMiddleware`, which turns an
    unhandled exception into the 500 the client sees — so the exception is counted here, and the
    5xx is counted when that response comes back through.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            await self.app(scope, receive, send)      # the SPA's own files are not API traffic
            return
        method, started, status = scope["method"], time.perf_counter(), 0

        async def capture(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        INFLIGHT.inc()
        try:
            await self.app(scope, receive, capture)
        except Exception as exc:
            EXCEPTIONS.labels(route=_route(scope), type=type(exc).__name__).inc()
            raise
        finally:
            INFLIGHT.dec()
            route = _route(scope)
            REQUESTS.labels(method=method, route=route,
                            status_class=f"{(status or 500) // 100}xx").inc()
            DURATION.labels(method=method, route=route).observe(time.perf_counter() - started)


router = APIRouter(tags=["monitoring"])


@router.get("/api/metrics", response_class=Response,
            responses={200: {"description": "Prometheus text exposition",
                             "content": {"text/plain": {"schema": {"type": "string"}}}}})
def metrics(authorization: str = Header(default="")):
    """The Prometheus text format, for a scraper holding the deployment's token."""
    token = config.METRICS_TOKEN
    if not token:
        # Not 403: an unset token means "no metrics in this deployment", and the body says nothing.
        raise HTTPException(404, "Not Found")
    given = authorization[len("Bearer "):].strip() if authorization.startswith("Bearer ") else ""
    # Bytes: a header can carry a non-ASCII byte, and comparing str would raise instead of answering.
    if not hmac.compare_digest(given.encode("utf-8"), token.encode("utf-8")):
        raise HTTPException(401, "Unauthorized")
    DB_UP.set(1 if health._db_ok() else 0)        # the same check `/api/readyz` answers with
    # Measured, but observed outside this call: the middleware records it after the body is sent.
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
