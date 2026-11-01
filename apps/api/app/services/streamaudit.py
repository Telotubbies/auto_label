"""Audit every view of stream footage (spec 7.1: "every view of stream footage").

The stream routes serve signed `/frame` and `/mjpeg` URLs, so the viewer may not carry an access
token in the browser request. The middleware records the workspace, the stream, the transport and,
when a bearer token is present, the user. Rows are written after the response so a 404/403 probe
never pollutes the audit trail.
"""
import re

from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware

from ..db import SessionLocal
from ..models import Audit, Workspace

STREAM_VIEW = re.compile(
    r"^/api/ws/(?P<ws>[^/]+)/projects/(?P<project>[^/]+)/streams/(?P<stream>[^/]+)/(?P<kind>mjpeg|frame)$")


def view_of(path: str) -> dict | None:
    """Matched route parts for a footage request, else None."""
    m = STREAM_VIEW.match(path)
    return m.groupdict() if m else None


def _user_id(request) -> str | None:
    from ..security import verify_access

    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None
    try:
        return (verify_access(auth.split(" ", 1)[1]) or {}).get("sub")
    except Exception:                      # an expired/foreign token still names a viewer we cannot trust
        return None


def record(db, ws_slug: str, stream_id: str, kind: str, user_id: str | None, project: str = "") -> bool:
    """Write one `stream.view` row; False when the workspace slug is unknown."""
    ws = db.scalar(select(Workspace).where(Workspace.slug == ws_slug))
    if not ws:
        return False
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
