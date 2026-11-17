"""Structured logs: one JSON object per line and one request id from the browser to the worker.

Shape and rules are MONITORING-PLAN §4.1: `X-Request-Id` is honoured when it is 8..64 chars of
[A-Za-z0-9_-] and minted otherwise, echoed on the response, kept in a contextvar and injected into
every record. `LD_LOG_JSON=0` restores the old text format for a local run.
"""
import datetime
import json
import logging
import os
import re
import time
import uuid
from contextvars import ContextVar

from starlette.responses import JSONResponse

request_id: ContextVar[str] = ContextVar("request_id", default="")

_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
# The fields a call site passes through `extra=`; everything else in §4.1 comes from the context.
_CALLER_FIELDS = ("request_id", "user_id", "workspace_id", "method", "route", "status",
                  "duration_ms", "job_id", "worker_id")
_TEXT = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
_installed = False
log = logging.getLogger("labeldesk.request")


class _CtxFilter(logging.Filter):
    """Fill the context fields a call site did not pass, so every line carries the same keys."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "request_id", ""):
            setattr(record, "request_id", request_id.get())
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line: the §4.1 key set, always complete, the traceback inside `msg`."""

    def format(self, record: logging.LogRecord) -> str:
        msg = record.getMessage()
        if record.exc_info:
            msg = f"{msg}\n{self.formatException(record.exc_info)}"     # json escapes it: still one line
        out = {"ts": datetime.datetime.fromtimestamp(record.created, datetime.timezone.utc)
               .isoformat(timespec="milliseconds").replace("+00:00", "Z"),
               "level": record.levelname, "logger": record.name, "msg": msg}
        for name in _CALLER_FIELDS:
            out[name] = getattr(record, name, "")
        return json.dumps(out, ensure_ascii=False, default=str)


class _ApiAccessOnly(logging.Filter):
    """The middleware writes the richer /api line; uvicorn keeps its own line for everything else."""

    def filter(self, record: logging.LogRecord) -> bool:
        return not (len(record.args or ()) > 2 and str(record.args[2]).startswith("/api/"))


def install() -> None:
    """Configure the root logger once; `LD_LOG_JSON=0` restores the text format."""
    global _installed
    if _installed:
        return
    _installed = True
    handler = logging.StreamHandler()
    handler.set_name("labeldesk")
    handler.setFormatter(_TEXT if os.environ.get("LD_LOG_JSON", "1") == "0" else JsonFormatter())
    handler.addFilter(_CtxFilter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").addFilter(_ApiAccessOnly())


def _valid(value: str) -> str:
    """An inbound id is honoured only when it is 8..64 chars of [A-Za-z0-9_-]."""
    return value if _ID.match(value) else ""


def _inbound(scope) -> str:
    for key, value in scope["headers"]:
        if key == b"x-request-id":
            return _valid(value.decode("latin-1"))
    return ""


def _route(scope) -> str:
    """The route template, never the raw path: a path carries ids we must not spread."""
    return getattr(scope.get("route"), "path", "")


def _write(scope, status: int, started: float, exc_info: bool = False) -> None:
    if not scope["path"].startswith("/api/"):
        return
    state = scope.get("state") or {}          # what the deps layer resolved for this request
    log.log(logging.ERROR if exc_info else logging.INFO, "http.request", exc_info=exc_info,
            extra={"method": scope["method"], "route": _route(scope), "status": status,
                   "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                   "user_id": state.get("user_id", ""), "workspace_id": state.get("workspace_id", "")})


class RequestLogMiddleware:
    """Honour or mint X-Request-Id, echo it, and write the one /api line per request.

    A raw ASGI middleware on purpose: it shares the request's context, so a record logged anywhere
    in the request carries the id, and a streamed response is never buffered.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        rid = _inbound(scope) or uuid.uuid4().hex[:16]
        token = request_id.set(rid)
        started, status = time.perf_counter(), 0

        async def echo(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message["headers"] = [*message["headers"], (b"x-request-id", rid.encode())]
            await send(message)

        try:
            await self.app(scope, receive, echo)
            _write(scope, status, started)
        except Exception:
            _write(scope, 500, started, exc_info=True)
            if status:                      # the response had already started: nothing left to send
                raise
            await JSONResponse({"detail": "Internal server error"}, 500,
                               headers={"X-Request-Id": rid})(scope, receive, send)
        finally:
            request_id.reset(token)
