"""Workspace feature flags: read the effective set, admin toggle (audited)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import Ctx, audit, ws_ctx
from ..models import Stream
from ..services import flags as flag_service

router = APIRouter(prefix="/api/ws/{ws}", tags=["flags"])


def _stop_workspace_streams(db: Session, workspace_id: str, user_id: str | None) -> list[str]:
    """The streams kill switch must stop capture before it hides the API (I-2), within a budget (I-4)."""
    from ..services.stream_stop import stop_streams

    ids = list(db.scalars(select(Stream.id).where(Stream.workspace_id == workspace_id)))
    return stop_streams(db, ids, workspace_id=workspace_id, user_id=user_id, reason="flag.task_10b")


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
    enabled = flag_service.is_enabled(key, c.db, c.ws.id)     # the uncommitted row is visible here
    # I-4: signal capture *before* the flag commits, so the 404 window is bounded by one drain
    # (one read timeout / one predict), not by N × 4 s of inline joins. A forced-on env flag wins.
    if key == "task_10b" and not enabled:
        _stop_workspace_streams(c.db, c.ws.id, c.user.id)
    c.db.commit()
    return {"key": key, "enabled": enabled}
