"""Inference hub API: hosts, the engine and GPU catalogue, and per-host engine compatibility.

T-1001 owns the host routes and the deployment scope; every card that adds a route appends it here
under the same route-level ``task_inference`` flag and the same admin gate.
"""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException

from ..deps import Ctx, ws_ctx
from ..services import host_inventory, inference_access, inference_catalog, inference_compat, inference_estimate
from ..services.flags import require_flag

FLAG = "task_inference"
router = APIRouter(prefix="/api/ws/{ws}/inference", tags=["inference"],
                   dependencies=[Depends(require_flag(FLAG))])
log = logging.getLogger("labeldesk.inference")


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


@router.get("/catalog")
def catalog(c: Ctx = Depends(in_scope)):
    """Engine pins and GPU presets: the Engines tab and the calculator read this one list."""
    c.need("admin")
    started = time.perf_counter()
    body = inference_catalog.public_catalog()
    log.info("inference.catalog ws=%s role=%s outcome=ok engines=%d gpus=%d ms=%.1f",
             c.ws.slug, c.ws_role, len(body["engines"]), len(body["gpus"]),
             (time.perf_counter() - started) * 1000)
    return body


@router.get("/engines")
def engines(host: str, c: Ctx = Depends(in_scope)):
    """Every catalogue engine with this host's verdict; another host id is 404, never a default."""
    c.need("admin")
    started = time.perf_counter()
    host_row = next((row for row in host_inventory.hosts(c.db) if row["id"] == host), None)
    if host_row is None:
        raise HTTPException(404, "not found")
    inventory = host_row["inventory"]
    free_gb = ((inventory or {}).get("disk") or {}).get("models_free_gb")
    rows = []
    for engine in inference_catalog.public_catalog()["engines"]:
        compat = inference_compat.evaluate(inventory, engine, (engine["runtimes"] or [None])[0],
                                           free_gb=free_gb)
        if not host_row["online"]:                    # stale inventory still renders, installs stop
            compat = {"status": "blocked", "reasons": [inference_compat.OFFLINE],
                      "warnings": [], "installed": compat["installed"]}
        after = None if free_gb is None else round(free_gb - engine["disk_mb"] / 1024, 1)
        rows.append({**engine, "installed": compat["installed"],
                     "compatibility": {key: compat[key] for key in ("status", "reasons", "warnings")},
                     "disk_after_gb": after})
    log.info("inference.engines ws=%s role=%s host=%s outcome=ok engines=%d blocked=%d ms=%.1f",
             c.ws.slug, c.ws_role, host, len(rows),
             sum(row["compatibility"]["status"] == "blocked" for row in rows),
             (time.perf_counter() - started) * 1000)
    return {"host": host_row, "engines": rows}


@router.post("/estimate")
def estimate(body: inference_estimate.EstimateIn, c: Ctx = Depends(ws_ctx)):
    """Pure VRAM / throughput answer; any member may read it, nothing is stored (PLAN §12.5)."""
    started = time.perf_counter()
    try:
        result = inference_estimate.estimate(body)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    log.info("inference.estimate ws=%s role=%s outcome=ok fits=%s total_gb=%.1f ms=%.1f",
             c.ws.slug, c.ws_role, result["fits"], result["total_gb"],
             (time.perf_counter() - started) * 1000)
    return result
