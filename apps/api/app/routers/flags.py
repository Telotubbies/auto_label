"""Workspace feature flags: read the effective set, admin toggle (audited)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..db import SessionLocal
from ..deps import Ctx, audit, ws_ctx
from ..models import Stream
from ..services import flags as flag_service

router = APIRouter(prefix="/api/ws/{ws}", tags=["flags"])


def _stop_workspace_streams(workspace_id: str) -> None:
    """The streams kill switch must stop capture before it hides the API (I-2)."""
    from ..streams.manager import manager

    with SessionLocal() as db:
        ids = list(db.scalars(select(Stream.id).where(Stream.workspace_id == workspace_id)))
    for sid in ids:
        manager.stop(sid)


@router.get("/flags")
def get_flags(c: Ctx = Depends(ws_ctx)):
    enabled = flag_service.enabled_keys(c.db, c.ws.id)
    return {
        "enabled": enabled,
        "flags": [{"key": key, "description": desc, "enabled": key in enabled}
                  for key, desc in flag_service.FLAGS.items()],
    }


class FlagIn(BaseModel):
    enabled: bool


@router.put("/flags/{key}")
def put_flag(key: str, body: FlagIn, c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    try:
        flag_service.set_flag(c.db, c.ws.id, key, body.enabled)
    except ValueError:
        raise HTTPException(404, "unknown feature flag") from None
    audit(c.db, c.ws.id, c.user.id, "flag.update", key, enabled=body.enabled)
    c.db.commit()
    enabled = flag_service.is_enabled(key, c.db, c.ws.id)
    # Commit first: manager.stop() writes through its own session, and a forced-on env flag must win.
    if key == "task_10b" and not enabled:
        _stop_workspace_streams(c.ws.id)
    return {"key": key, "enabled": enabled}
