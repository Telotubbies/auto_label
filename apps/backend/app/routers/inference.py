"""Inference hub API: hosts, the engine and GPU catalogue, and per-host engine compatibility.

T-1001 owns the host routes and the deployment scope; every card that adds a route appends it here
under the same route-level ``task_inference`` flag and the same admin gate.
"""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import Ctx, ws_ctx
from ..services import (host_inventory, inference_access, inference_catalog, inference_compat,
                        inference_jobs, inference_plan)
from ..services.flags import require_flag
from .projects import job_out

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


class EngineChoice(BaseModel):
    """One engine the admin picked: a catalogue id, the catalogue version and a runtime it offers."""
    id: str = Field(min_length=1, max_length=32)
    version: str = Field(min_length=1, max_length=32)
    runtime: str = Field(min_length=1, max_length=16)


class EnginePlanIn(BaseModel):
    host: str = Field(min_length=1, max_length=120)
    engines: list[EngineChoice] = Field(min_length=1, max_length=8)


class InstallIn(EnginePlanIn):
    plan_id: str = Field(min_length=1, max_length=64)
    confirm: bool = False


class UninstallIn(BaseModel):
    host: str = Field(min_length=1, max_length=120)
    id: str = Field(min_length=1, max_length=32)
    confirm: bool = False


def _host(c: Ctx, host: str) -> dict:
    """This deployment's host row; an id it does not list is 404, never a default."""
    row = next((host_row for host_row in host_inventory.hosts(c.db) if host_row["id"] == host), None)
    if row is None:
        raise HTTPException(404, "not found")
    return row


def _build(c: Ctx, host: str, choices: list[EngineChoice]) -> tuple[dict, dict]:
    row = _host(c, host)
    try:
        plan = inference_plan.build(row, [choice.model_dump() for choice in choices],
                                    row["inventory"])
    except inference_plan.InvalidSelection as exc:
        raise HTTPException(422, str(exc)) from exc
    return row, plan


@router.post("/engines/plan")
def plan_engines(body: EnginePlanIn, c: Ctx = Depends(in_scope)):
    """A dry run: exact argv, bytes and disk after. It writes nothing, on the host or here."""
    c.need("admin")
    started = time.perf_counter()
    _, plan = _build(c, body.host, body.engines)
    log.info("inference.plan ws=%s role=%s host=%s outcome=ok engines=%d blocked=%d noop=%s ms=%.1f",
             c.ws.slug, c.ws_role, body.host, len(plan["steps"]), len(plan["blocked"]),
             plan["noop"], (time.perf_counter() - started) * 1000)
    return plan


@router.post("/engines/install")
def install_engines(body: InstallIn, c: Ctx = Depends(in_scope)):
    """Queue one confirmed install for one host; a stale plan or a busy host is refused first."""
    c.need("admin")
    started = time.perf_counter()
    row, plan = _build(c, body.host, body.engines)
    if not body.confirm:
        raise HTTPException(400, {"error": "Confirm that this installs software on the host.",
                                  "plan": plan})
    if plan["plan_id"] != body.plan_id:
        raise HTTPException(409, {"error": "The plan is stale: the host changed. Review the install "
                                           "plan again.", "plan": plan})
    running = inference_jobs.running_for_host(c.db, row["id"])
    if running is not None:
        raise HTTPException(409, {"error": "An engine job is already running on this host.",
                                  "job_id": running.id})
    engines = [{key: step[key] for key in ("id", "version", "runtime", "argv")}
               for step in plan["steps"] if step["status"] == "install"]
    if not engines:
        raise HTTPException(409, {"error": "Nothing to install.", "plan": plan})
    job = inference_jobs.enqueue_engine(c.db, c, row["id"], "install", engines, plan["plan_id"])
    log.info("inference.install ws=%s role=%s host=%s outcome=queued job=%s engines=%d bytes=%d ms=%.1f",
             c.ws.slug, c.ws_role, row["id"], job.id, len(engines), plan["total_disk_mb"],
             (time.perf_counter() - started) * 1000)
    return {"job": job_out(job)}


@router.post("/engines/uninstall")
def uninstall_engine(body: UninstallIn, c: Ctx = Depends(in_scope)):
    """Queue the removal of an installed engine: its container, or the venv on that host."""
    c.need("admin")
    started = time.perf_counter()
    row = _host(c, body.host)
    installed = next((engine for engine in (row["inventory"] or {}).get("engines") or []
                      if engine.get("id") == body.id), None)
    if installed is None:
        raise HTTPException(404, "not found")
    try:
        engine = inference_catalog.engine(body.id)
    except KeyError:
        raise HTTPException(404, "not found") from None
    if not body.confirm:
        raise HTTPException(400, "Confirm that this removes the engine from the host.")
    running = inference_jobs.running_for_host(c.db, row["id"])
    if running is not None:
        raise HTTPException(409, {"error": "An engine job is already running on this host.",
                                  "job_id": running.id})
    runtime = installed.get("runtime")
    if runtime not in engine["runtimes"]:
        runtime = (engine["runtimes"] or ["uv"])[0]
    version = inference_plan.installed_version(engine, installed)
    argv = inference_plan.uninstall_commands(engine, runtime, version)
    payload = [{"id": engine["id"], "version": version, "runtime": runtime, "argv": argv}]
    job = inference_jobs.enqueue_engine(c.db, c, row["id"], "uninstall", payload, "")
    log.info("inference.uninstall ws=%s role=%s host=%s outcome=queued job=%s engine=%s ms=%.1f",
             c.ws.slug, c.ws_role, row["id"], job.id, engine["id"],
             (time.perf_counter() - started) * 1000)
    return {"job": job_out(job)}
