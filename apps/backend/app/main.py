"""LabelDesk API.  Dev: `uvicorn app.main:app --reload --port 8010` from apps/backend."""
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.gzip import DEFAULT_EXCLUDED_CONTENT_TYPES

from .bootstrap import init_db
from .config import CORS_ORIGINS, DATA_DIR, EMBEDDED_WORKER
from .gpu import GpuBusy
from .routers import include_routers
from .security import check_signature
from .services.streamaudit import StreamViewAuditMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    # streams live in-process: a restart forgets every worker, so their rows must say so
    from sqlalchemy import update

    from .db import session_scope
    from .gpu import wire_streams
    from .models import Stream
    from .streams.manager import manager
    with session_scope() as db:
        db.execute(update(Stream).values(status="stopped", last_error=""))
    wire_streams(manager)
    stop = None
    if EMBEDDED_WORKER:
        from .worker import assert_handlers_claimed, start_background
        # Fail before the daemon thread starts: a RuntimeError inside the thread leaves the API
        # serving with no executor and its jobs queued forever (C2/Important 3).
        assert_handlers_claimed()
        stop = start_background()
    yield
    manager.stop_all()
    if stop:
        stop.set()


app = FastAPI(title="LabelDesk API", version="1.0.0", lifespan=lifespan)


@app.exception_handler(GpuBusy)
async def gpu_busy(_request, exc: GpuBusy):
    """A training lease owns the card: inference is unavailable (spec 3.6)."""
    return JSONResponse(status_code=503, content={"detail": str(exc)})


# MJPEG is an endless stream: compressing it would delay the live view.
app.add_middleware(GZipMiddleware, minimum_size=1024,
                   exclude_content_types=(*DEFAULT_EXCLUDED_CONTENT_TYPES, "multipart/x-mixed-replace"))
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"],
                   allow_credentials=CORS_ORIGINS != ["*"])


@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    h = resp.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    h.setdefault("X-Frame-Options", "DENY")
    if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/files/"):
        h.setdefault("Cache-Control", "no-store")           # API JSON may carry tokens / private data
        h.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    return resp


include_routers(app)
# PDPA: every request for stream footage lands in the audit log (signed URLs carry no session cookie).
app.add_middleware(StreamViewAuditMiddleware)


@app.get("/api/health")
def health():
    return {"ok": True, "service": "labeldesk"}


@app.get("/api/files/{rel:path}")
def files(rel: str, exp: int, sig: str):
    if not check_signature(rel, exp, sig):
        raise HTTPException(403, "link expired")
    f = (DATA_DIR / rel).resolve()
    if DATA_DIR not in f.parents or not f.is_file():
        raise HTTPException(404, "file not found")
    # stored files never change (content is keyed by id), so cache until the link expires
    headers = {"Cache-Control": f"private, max-age={max(0, exp - int(time.time()))}, immutable"}
    return FileResponse(f, headers=headers, filename=f.name if f.suffix in (".zip", ".pt") else None)


# Single-container deploys: serve the built SPA when LD_WEB_DIST points at apps/frontend/dist
_dist = os.environ.get("LD_WEB_DIST")
if _dist and Path(_dist).is_dir():
    _dist_path = Path(_dist).resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = (_dist_path / path).resolve()
        if path and _dist_path in f.parents and f.is_file():
            return FileResponse(f)
        return FileResponse(_dist_path / "index.html")
