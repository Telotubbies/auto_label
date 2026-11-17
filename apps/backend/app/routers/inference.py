"""Inference hub API: hosts, the engine and GPU catalogue, and per-host engine compatibility.

T-1001 owns the host routes and the deployment scope; every card that adds a route appends it here
under the same route-level ``task_inference`` flag and the same admin gate.
"""

import logging
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import Ctx, ws_ctx
from ..models import Job, now
from ..services import (host_inventory, inference_access, inference_catalog, inference_compat,
                        inference_estimate, inference_jobs, inference_models, inference_plan)
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


class ModelPlanIn(BaseModel):
    """One catalogue model and one of its variants, on one host."""
    host: str = Field(min_length=1, max_length=120)
    id: str = Field(min_length=1, max_length=64)
    variant: str = Field(min_length=1, max_length=32)


@router.get("/models")
def models(host: str, c: Ctx = Depends(in_scope)):
    """Catalogue rows joined with this host's installed state, fit verdict and block reasons."""
    c.need("admin")
    started = time.perf_counter()
    row = _host(c, host)
    body = inference_models.public_models(row)
    log.info("inference.models ws=%s role=%s host=%s outcome=ok rows=%d blocked=%d ms=%.1f",
             c.ws.slug, c.ws_role, row["id"], len(body["models"]),
             sum(1 for model in body["models"] if model["blocked"]),
             (time.perf_counter() - started) * 1000)
    return body


@router.post("/models/plan")
def plan_model(body: ModelPlanIn, c: Ctx = Depends(in_scope)):
    """The dry run for one variant; the download job is T-1011's route and writes the files."""
    c.need("admin")
    started = time.perf_counter()
    row = _host(c, body.host)
    try:
        plan = inference_models.plan(row, body.id, body.variant)
    except KeyError:
        raise HTTPException(404, "not found") from None
    except inference_models.InvalidRepo as exc:
        raise HTTPException(400, str(exc)) from None
    log.info("inference.model_plan ws=%s role=%s host=%s model=%s variant=%s outcome=ok "
             "blocked=%d bytes=%d ms=%.1f", c.ws.slug, c.ws_role, row["id"], body.id,
             body.variant, len(plan["blocked"]), plan["total_bytes"],
             (time.perf_counter() - started) * 1000)
    return plan


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


# --- engine jobs: the card, its log and its cancel (T-1009) -----------------------------------
ACTIVE_STATUSES = ("queued", "running", "cancelling")
JOBS_CAP = 20


def job_view(row: Job) -> dict:
    """A job the browser may read: the phase and log tail the worker wrote, never ``params``.

    ``params`` holds the install argv, so it never leaves the server; the host and the action are
    lifted out of it because the card has to name the machine and say whether it installs or removes.
    """
    result = row.result or {}
    params = row.params or {}
    return {"id": row.id, "kind": row.kind, "status": row.status, "progress": row.progress,
            "phase": result.get("phase") or "", "log": list(result.get("log") or []),
            "error": row.error, "host": params.get("host", ""),
            "action": params.get("action", "install"),
            "result": {"engines": result.get("engines") or []},
            "created": row.created, "finished": row.finished}


def _job(c: Ctx, jid: str) -> Job:
    """This workspace's job; an id it does not own is 404, never another tenant's row."""
    row = c.db.get(Job, jid)
    if row is None or row.workspace_id != c.ws.id:
        raise HTTPException(404, "not found")
    return row


@router.get("/jobs")
def active_jobs(status: Literal["active"] = "active", c: Ctx = Depends(in_scope)):
    """The workspace's engine jobs still on the wire, newest first, capped at 20."""
    c.need("admin")
    started = time.perf_counter()
    rows = c.db.scalars(select(Job).where(Job.workspace_id == c.ws.id,
                                          Job.kind.in_(inference_jobs.ENGINE_KINDS),
                                          Job.status.in_(ACTIVE_STATUSES))
                        .order_by(Job.created.desc()).limit(JOBS_CAP)).all()
    body = [job_view(row) for row in rows]
    log.info("inference.jobs ws=%s role=%s status=%s outcome=ok jobs=%d ms=%.1f",
             c.ws.slug, c.ws_role, status, len(body), (time.perf_counter() - started) * 1000)
    return body


@router.get("/jobs/{jid}")
def job_detail(jid: str, c: Ctx = Depends(in_scope)):
    """One job with its phase, log and the engines it finished, so a reload shows the same card."""
    c.need("admin")
    started = time.perf_counter()
    row = _job(c, jid)
    log.info("inference.job ws=%s role=%s job=%s status=%s outcome=ok ms=%.1f",
             c.ws.slug, c.ws_role, row.id, row.status, (time.perf_counter() - started) * 1000)
    return job_view(row)


@router.post("/jobs/{jid}/cancel")
def cancel_job(jid: str, c: Ctx = Depends(in_scope)):
    """Ask a running job to stop; a queued job no worker will claim is cancelled outright.

    Terminal rows and a job already cancelling are left alone, so the button is idempotent and the
    card can keep reading ``Cancelling…`` until the worker acknowledges.
    """
    c.need("admin")
    started = time.perf_counter()
    row = _job(c, jid)
    before = row.status
    if row.status == "queued":
        row.status, row.finished = "cancelled", now()
    elif row.status == "running":
        row.status = "cancelling"
    c.db.commit()
    log.info("inference.jobs.cancel ws=%s role=%s job=%s before=%s after=%s outcome=ok ms=%.1f",
             c.ws.slug, c.ws_role, row.id, before, row.status,
             (time.perf_counter() - started) * 1000)
    return job_view(row)

