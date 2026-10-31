from fastapi import APIRouter, Depends

from ..adapters import catalog
from ..deps import Ctx, ws_ctx

router = APIRouter(prefix="/api/ws/{ws}", tags=["registry"])


@router.get("/registry")
def registry(c: Ctx = Depends(ws_ctx)):
    return catalog(c.db, c.ws.id)
