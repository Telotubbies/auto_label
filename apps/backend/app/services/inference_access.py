"""The three locks on one inference action: admin role, deployment scope, and a minute's budget.

One deployment serves one hub: ``LD_INFERENCE_WORKSPACE`` (a workspace id or slug) pins it, and
every hub route 404s for another workspace. Unset means the deployment serves every workspace,
which is the single-tenant case.

On top of the scope, every route asks :func:`require_admin` (the hub is owner/admin work, and a
project manager never inherits it), every write enqueues through :func:`require_under_limit`, and a
host id the deployment does not list is a 404 from :func:`host_or_404` rather than a default. The
helpers live here so no route can grow a second copy.
"""
import logging
import os

from fastapi import HTTPException
from sqlalchemy import select

from ..models import Job, Workspace, now

MAX_ENQUEUES_PER_MIN = 4                # per user per workspace, every install action together
MINUTE = 60
log = logging.getLogger("labeldesk.inference")


def scope() -> str:
    """The configured workspace id or slug; empty when the deployment is not pinned."""
    return os.environ.get("LD_INFERENCE_WORKSPACE", "").strip()


def workspace_allowed(db, ws_id: str) -> bool:
    """False when the hub belongs to another workspace, so its routes must 404."""
    pinned = scope()
    if not pinned or pinned == ws_id:
        return True
    return db.scalar(select(Workspace.id).where(Workspace.slug == pinned)) == ws_id


def require_admin(c) -> None:
    """403 unless the caller may change a host; a project role is never a substitute."""
    if c.ws_role not in ("owner", "admin"):
        raise HTTPException(403, "requires workspace admin")


def host_or_404(db, c, host: str) -> dict:
    """This deployment's host row; an id it does not list is 404, never a default or a guess."""
    from . import host_inventory                   # local: routers/inference owns the import order

    row = next((h for h in host_inventory.hosts(db) if h["id"] == host), None)
    if row is None:
        log.info("inference.host_miss ws=%s user=%s outcome=404", c.ws.slug, c.user.id)
        raise HTTPException(404, "not found")
    return row


def recent_actions(db, ws_id: str, user_id: str, action: str = "", window_s: int = MINUTE) -> int:
    """Install-class jobs ``user_id`` queued in ``ws_id`` inside the window.

    ``action`` narrows the count to one action name; empty counts every one of them, which is what
    the budget uses: alternating installs and downloads must not buy a second minute.
    """
    from .inference_jobs import ENGINE_KINDS       # jobs imports this module, so this stays one-way

    rows = db.scalars(select(Job.params).where(Job.workspace_id == ws_id, Job.created_by == user_id,
                                               Job.kind.in_(ENGINE_KINDS),
                                               Job.created >= now() - window_s)).all()
    return sum(1 for params in rows if not action or (params or {}).get("action") == action)


def require_under_limit(db, c) -> None:
    """429 with the retry hint once this user has queued a minute's worth of install actions."""
    if recent_actions(db, c.ws.id, c.user.id) >= MAX_ENQUEUES_PER_MIN:
        log.info("inference.rate_limited ws=%s user=%s outcome=429 limit=%d",
                 c.ws.slug, c.user.id, MAX_ENQUEUES_PER_MIN)
        raise HTTPException(429, "too many inference actions; wait a minute",
                            headers={"Retry-After": str(MINUTE)})
