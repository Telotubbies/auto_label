"""Workspace feature flags: read the effective set, admin toggle (audited)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import Ctx, audit, ws_ctx
from ..services import flags as flag_service

router = APIRouter(prefix="/api/ws/{ws}", tags=["flags"])


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
    return {"key": key, "enabled": flag_service.is_enabled(key, c.db, c.ws.id)}
