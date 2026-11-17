"""Inference hub: the GPU hosts this deployment installs engines on (T-1001; later cards append)."""
from fastapi import APIRouter, Depends, HTTPException

from ..deps import Ctx, ws_ctx
from ..services import host_inventory, inference_access
from ..services.flags import require_flag

router = APIRouter(prefix="/api/ws/{ws}/inference", tags=["inference"],
                   dependencies=[Depends(require_flag("task_inference"))])


def in_scope(c: Ctx = Depends(ws_ctx)) -> Ctx:
    """The hub belongs to one workspace in this deployment; another one must 404, not 403."""
    if not inference_access.workspace_allowed(c.db, c.ws.id):
        raise HTTPException(404, "not found")
    return c


@router.get("/hosts")
def hosts(c: Ctx = Depends(in_scope)):
    """Every host with the hardware it reports; owner/admin only."""
    c.need("admin")
    return {"hosts": host_inventory.hosts(c.db)}
