from fastapi import APIRouter, Depends

from ..adapters import catalog
from ..deps import Ctx, current_user, ws_ctx
from ..gpu import gpu_label, scheduler
from ..models import User

router = APIRouter(prefix="/api/ws/{ws}", tags=["registry"])

gpu_router = APIRouter(prefix="/api", tags=["gpu"])


@router.get("/registry")
def registry(c: Ctx = Depends(ws_ctx)):
    return catalog(c.db, c.ws.id)


@gpu_router.get("/gpu")
def gpu_state(_u: User = Depends(current_user)):
    """Who holds the GPU right now; the header badge renders `label` verbatim."""
    st = scheduler.state()
    sleeping = scheduler.vlm_sleeping
    return {**st, "label": gpu_label(st["holder"], sleeping), "vlm_sleeping": sleeping}
