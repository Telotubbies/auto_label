"""Version generation and artifact export: the ``version``, ``export`` and ``export_engine`` kinds.

Handlers resolve their runner dependencies through ``app.worker`` (``w.ADAPTERS``, ``w.scheduler``,
``w._set``, ``w._cancelled``) so the process that swaps one of them at runtime keeps working.
"""
import shutil
from pathlib import Path

from ..adapters import Cancelled
from ..config import DATA_DIR
from ..db import SessionLocal
from ..models import Job, TrainedModel, Version
from ..services import exporters, versioning


def run_version(job: Job):
    from .. import jobs, worker as w
    jobs.check(job)
    with SessionLocal() as db:
        v = db.get(Version, job.params["version_id"])
        v.status = "generating"; db.commit()
        try:
            stats = versioning.generate(db, v, lambda f: w._set(job.id, progress=round(f * 100, 1)),
                                        should_stop=lambda: w._cancelled(job.id))
            v.status, v.stats = "ready", stats
        except Cancelled:
            v.status = "cancelled"; db.commit(); raise      # I22: no ready version after a cancel
        except Exception:
            v.status = "failed"; db.commit(); raise
        db.commit()
        return {"version_id": v.id, **stats}


def run_export(job: Job):
    from .. import jobs, worker as w
    jobs.check(job)
    with SessionLocal() as db:
        v = db.get(Version, job.params["version_id"])
        fmt = job.params["format"]
        out = DATA_DIR / "exports" / v.id / fmt
        try:
            z = exporters.export(fmt, versioning.version_dir(v), out,
                                 should_stop=lambda: w._cancelled(job.id))
        except Cancelled:
            shutil.rmtree(out, ignore_errors=True)
            raise
        shutil.rmtree(out, ignore_errors=True)
        return {"version_id": v.id, "format": fmt, "file": z.relative_to(DATA_DIR).as_posix(), "bytes": z.stat().st_size}


def run_export_engine(job: Job):
    """Build a TensorRT engine for a ready model, cache it under engines/, and register the runtime."""
    from .. import jobs, worker as w
    jobs.check(job)
    with SessionLocal() as db:
        tm = db.get(TrainedModel, job.params["model_id"])
        if tm is None or tm.status != "ready" or not tm.weights:
            raise RuntimeError("model is not ready")
        mid, family, variant, weights = tm.id, tm.family or "ultralytics", tm.variant or tm.arch, tm.weights
    src = DATA_DIR / weights
    if not src.exists():
        raise RuntimeError("model weights are missing")
    dest = DATA_DIR / "engines" / f"{mid}.engine"
    adapter = w.ADAPTERS.get(family)
    build = getattr(adapter, "export", None)
    if build is None:
        raise RuntimeError(f"{family} models cannot be exported to TensorRT")
    w._set(job.id, progress=10.0)
    with w.scheduler.exclusive(f"engine export {variant}"):        # the build owns the whole card
        out = build(str(src), "engine", half=True, dest=dest)
    if w._cancelled(job.id):                                       # I22: never register a cancelled build
        Path(dest).unlink(missing_ok=True)
        raise Cancelled("engine build cancelled")
    rel = out.relative_to(DATA_DIR).as_posix()
    with SessionLocal() as db:                                    # fresh row: the build ran for minutes
        tm = db.get(TrainedModel, mid)
        if tm is None:
            raise RuntimeError("model was deleted during the export")
        tm.runtime_refs = {**(tm.runtime_refs or {}), "pt": weights, "engine": rel}
        db.commit()
    return {"model_id": mid, "format": "engine", "engine": rel, "bytes": out.stat().st_size}


HANDLERS = {"version": run_version, "export": run_export, "export_engine": run_export_engine}
