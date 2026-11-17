"""Inference hub API: the engine and GPU catalogue.

T-1001 owns the host routes; every card that adds a route appends it here under the same
route-level ``task_inference`` flag and the same admin gate.
"""

import logging
import time

from fastapi import APIRouter, Depends

from ..deps import Ctx, ws_ctx
from ..services import inference_catalog
from ..services.flags import require_flag

FLAG = "task_inference"
router = APIRouter(prefix="/api/ws/{ws}/inference", tags=["inference"],
                   dependencies=[Depends(require_flag(FLAG))])
log = logging.getLogger("labeldesk.inference")


@router.get("/catalog")
def catalog(c: Ctx = Depends(ws_ctx)):
    """Engine pins and GPU presets: the Engines tab and the calculator read this one list."""
    c.need("admin")
    started = time.perf_counter()
    body = inference_catalog.public_catalog()
    log.info("inference.catalog ws=%s role=%s outcome=ok engines=%d gpus=%d ms=%.1f",
             c.ws.slug, c.ws_role, len(body["engines"]), len(body["gpus"]),
             (time.perf_counter() - started) * 1000)
    return body
