"""LabelDesk API.  Dev: `uvicorn app.main:app --reload --port 8010` from apps/api."""
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse

from .bootstrap import init_db
from .config import CORS_ORIGINS, DATA_DIR, EMBEDDED_WORKER
from .routers import auth, images, playground, projects, registry, remote, training, versions, workspaces
from .security import check_signature

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    stop = None
    if EMBEDDED_WORKER:
        from .worker import start_background
        stop = start_background()
    yield
    if stop:
        stop.set()


app = FastAPI(title="LabelDesk API", version="1.0.0", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1024)
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


for r in (auth, workspaces, projects, images, versions, training, remote, registry, playground):
    app.include_router(r.router)


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


# Single-container deploys: serve the built SPA when LD_WEB_DIST points at apps/web/dist
_dist = os.environ.get("LD_WEB_DIST")
if _dist and Path(_dist).is_dir():
    _dist_path = Path(_dist).resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = (_dist_path / path).resolve()
        if path and _dist_path in f.parents and f.is_file():
            return FileResponse(f)
        return FileResponse(_dist_path / "index.html")
