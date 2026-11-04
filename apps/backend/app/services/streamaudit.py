"""Audit every view of stream footage (spec 7.1: "every view of stream footage").

The stream routes serve signed `/frame` and `/mjpeg` URLs, so the viewer may not carry an access
token in the browser request. The middleware records the workspace, the stream, the transport and,
when a bearer token is present, the user. Otherwise it accepts a viewer id bound into the signed URL
(Task 10b signs the route path with `security.sign_query(..., viewer=user_id)`); the signature must
cover the viewer id, so it cannot be swapped for someone else's. Rows are written after the response
so a 404/403 probe never pollutes the audit trail.
"""
import re

from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware

from ..db import SessionLocal
from ..models import Audit, User, Workspace

STREAM_VIEW = re.compile(
    r"^/api/ws/(?P<ws>[^/]+)/projects/(?P<project>[^/]+)/streams/(?P<stream>[^/]+)/(?P<kind>mjpeg|frame)$")


def view_of(path: str) -> dict | None:
    """Matched route parts for a footage request, else None."""
    m = STREAM_VIEW.match(path)
    return m.groupdict() if m else None


def _user_id(request) -> str | None:
    """Bearer token first, then a viewer id bound into a signed frame/MJPEG URL."""
    from ..security import check_signature, verify_access

    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        try:
            return (verify_access(auth.split(" ", 1)[1]) or {}).get("sub")
        except Exception:                  # an expired/foreign token still names a viewer we cannot trust
            return None
    q = request.query_params
    viewer, exp, sig = q.get("viewer"), q.get("exp"), q.get("sig")
    if not (viewer and exp and sig):
        return None
    try:
        expires = int(exp)
    except ValueError:
        return None
    rel = request.url.path.removeprefix("/api/").lstrip("/")
    return viewer if check_signature(rel, expires, sig, viewer) else None


def record(db, ws_slug: str, stream_id: str, kind: str, user_id: str | None, project: str = "") -> bool:
    """Write one `stream.view` row; False when the workspace slug is unknown."""
    ws = db.scalar(select(Workspace).where(Workspace.slug == ws_slug))
    if not ws:
        return False
    if user_id and not db.get(User, user_id):     # deleted account or forged id: do not attribute
        user_id = None
    db.add(Audit(workspace_id=ws.id, user_id=user_id, action="stream.view", target=stream_id,
                 meta={"via": kind, "project": project}))
    db.commit()
    return True


class StreamViewAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        hit = view_of(request.url.path) if response.status_code < 400 else None
        if hit:
            try:
                with SessionLocal() as db:
                    record(db, hit["ws"], hit["stream"], hit["kind"], _user_id(request), hit["project"])
            except Exception:              # auditing must never break the video feed
                import logging
                logging.getLogger("labeldesk.audit").exception("stream view audit failed")
        return response
