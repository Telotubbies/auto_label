"""Feature flags.

One registry lists every flag the API knows about; each task adds one ``task_<id>`` line.
A flag is off unless the workspace has an override row with ``enabled=True`` or the process
env ``LD_FLAGS_ON`` names it. Unknown keys are always off. The registry is deliberately a
plain dict with no external service.
"""
import os
from collections.abc import Callable

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import Ctx, ws_ctx
from ..models import Workspace, WorkspaceFlag, now

# One line per shipped surface, keyed `task_<id>`, described in one sentence. Default is off;
# each surface's API router and UI route/nav entry references the same key.
FLAGS: dict[str, str] = {
    "task_10b": "CCTV streams: live cameras, zones and event rules",
    "task_20c": "Analysis studio: lineage, dashboards and stream analytics",
    "task_22": "Video authoring: frame timeline and track forward",
    "task_23": "Review & quality: consensus, honeypots and the review queue",
}


def _forced_on() -> set[str]:
    """Keys forced on by ``LD_FLAGS_ON=key1,key2`` (whitespace tolerated)."""
    return {key.strip() for key in os.environ.get("LD_FLAGS_ON", "").split(",") if key.strip()}


def is_enabled(key: str, db: Session, workspace_id: str) -> bool:
    """True when ``key`` is known and env-forced or explicitly enabled for this workspace."""
    if key not in FLAGS:
        return False
    if key in _forced_on():
        return True
    row = db.get(WorkspaceFlag, (workspace_id, key))
    return bool(row and row.enabled)


def enabled_keys(db: Session, workspace_id: str) -> list[str]:
    """Registry keys that evaluate on for the workspace, in registry order."""
    forced = _forced_on()
    stored = set(db.scalars(select(WorkspaceFlag.key).where(
        WorkspaceFlag.workspace_id == workspace_id, WorkspaceFlag.enabled.is_(True))))
    return [key for key in FLAGS if key in forced or key in stored]


def set_flag(db: Session, workspace_id: str, key: str, enabled: bool) -> None:
    """Store the workspace override; unknown keys raise ``ValueError``."""
    if key not in FLAGS:
        raise ValueError(f"unknown feature flag: {key}")
    row = db.get(WorkspaceFlag, (workspace_id, key))
    if row:
        row.enabled = enabled
        row.updated = now()
    else:
        db.add(WorkspaceFlag(workspace_id=workspace_id, key=key, enabled=enabled))


def require_flag(key: str) -> Callable[..., None]:
    """FastAPI dependency: 404 for the whole workspace when ``key`` is off."""
    def dependency(c: Ctx = Depends(ws_ctx)) -> None:
        if not is_enabled(key, c.db, c.ws.id):
            raise HTTPException(404, "not found")
    return dependency


def require_workspace_flag(key: str) -> Callable[..., None]:
    """Like :func:`require_flag`, for routers that also serve signature-only URLs.

    The workspace comes from the path instead of a session, so a signed ``frame``/``mjpeg``
    URL is gated by the same flag without demanding a bearer token.
    """
    def dependency(ws: str, db: Session = Depends(get_db)) -> None:
        workspace_id = db.scalar(select(Workspace.id).where(Workspace.slug == ws))
        if workspace_id is None or not is_enabled(key, db, workspace_id):
            raise HTTPException(404, "not found")
    return dependency
