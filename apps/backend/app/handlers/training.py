"""Training and auto-labelling: the ``train`` and ``autolabel`` kinds.

Handlers resolve their runner dependencies through ``app.worker`` (``w.ADAPTERS``, ``w.scheduler``,
``w._Watchdog``, ``w._first_limit``, ``w._set``, ``w._cancelled``) so the process that swaps one of
them at runtime keeps working.
"""
import gc
import logging
import shutil
import time

from sqlalchemy import select, update

from ..adapters import Cancelled
from ..adapters.refine import sam_available
from ..config import CREDIT_COST, DATA_DIR
from ..db import SessionLocal
from ..deps import charge
from ..errors import safe_error
from ..models import Image, Job, LabelClass, Project, TrainedModel, Version, Workspace, now, set_annotations
from ..services import imaging, metering, ml, versioning, webhooks

log = logging.getLogger("labeldesk.worker")     # same logger the runner used before the split


def _is_oom(exc: BaseException) -> bool:
    """torch.cuda.OutOfMemoryError, matched by name so tests need no torch import."""
    if type(exc).__name__ == "OutOfMemoryError":
        return True
    try:
        import torch
    except ImportError:
        return False
    return isinstance(exc, torch.cuda.OutOfMemoryError)


def _meter_gpu(db, job: Job, seconds: float) -> None:
    """Meter wall-clock seconds a training lease held the card (spec 7.1)."""
    if seconds > 0:
        metering.record(db, job.workspace_id, "gpu_seconds", round(seconds, 2), project_id=job.project_id,
                        job_id=job.id)
        db.commit()


def run_train(job: Job):
    """Train, evaluate and register one model, recording progress stages for the UI."""
    from .. import worker as w
    t0 = time.monotonic()
    stages: dict[str, dict] = {}

    def mark(name: str, status: str = "done", note: str | None = None):
        entry = {"status": status, "t": round(time.monotonic() - t0, 2)}
        if note:
            entry["note"] = note
        stages[name] = entry
        w._set(job.id, result={"stages": stages})     # the UI polls job.result mid-run

    mark("queue")
    with SessionLocal() as db:
        tm = db.get(TrainedModel, job.params["model_id"])
        v = db.get(Version, tm.version_id)
        p = db.get(Project, tm.project_id)
        previous = (tm.status, tm.weights)      # what the row keeps when a run is cut short
        # The enqueue already reserved the estimate; this is the belt: if the allowance shrank
        # while the job waited, refuse rather than register a zero-epoch model.
        budget = metering.remaining(db, db.get(Workspace, job.workspace_id), "gpu_seconds")
        if budget < w.MIN_TRAIN_GPU_S:
            tm.status = "ready" if previous[0] == "ready" else "failed"     # never a promoted stub
            db.commit()
            raise w.QuotaExhausted(
                f"GPU time allowance exhausted: {budget:.0f} s left, a training run needs at least "
                f"{w.MIN_TRAIN_GPU_S:.0f} s"
            )
        tm.status = "training"; db.commit()
        history: list[dict] = []
        variant = tm.variant or tm.arch
        family = tm.family or "ultralytics"
        opts = {**job.params.get("options", {}), "model_id": tm.id}
        opts.update(batch=int(opts.get("batch", 8)), epochs=int(opts.get("epochs", 30)),
                    imgsz=int(opts.get("imgsz", 640)), max_minutes=opts.get("max_minutes"),
                    resume_from=opts.get("resume_from"))
        train_images = int((v.stats or {}).get("splits", {}).get("train") or 0)
        watchdog = w._Watchdog(w._first_limit(train_images, opts["epochs"], opts["imgsz"]))
        opts["stalled"] = lambda: watchdog.stalled     # read by the adapter's per-batch callbacks
        opts["heartbeat"] = watchdog.beat              # polling adapters call it only on real progress
        train_note = None
        lease_start: float | None = None
        budget_stop = False

        def on_epoch(ep, total, metrics):
            watchdog.tick()
            history[:] = [h for h in history if h["epoch"] != ep] + [{"epoch": ep, **metrics}]   # final val re-fires the last epoch
            with SessionLocal() as s:
                s.execute(update(TrainedModel).where(TrainedModel.id == tm.id).values(history=history))
                s.execute(update(Job).where(Job.id == job.id).values(progress=round(ep / total * 100, 1)))
                s.commit()

        def should_stop():
            nonlocal budget_stop
            if w._cancelled(job.id) or watchdog.stalled:
                return True
            if lease_start is not None and w._over_budget(lease_start, budget, time.monotonic()):
                budget_stop = True
                return True
            return False

        try:
            mark("acquire_gpu", "running")
            with w.scheduler.exclusive(f"training {variant}"):
                lease_start = time.monotonic()
                mark("acquire_gpu")
                mark("materialise", "running")
                versioning.cached_export(v, "coco")      # also proves the dataset is readable
                mark("materialise")
                mark("resolve_weights", "running")
                if family == "ultralytics":
                    start = w._start_weights(variant, tm.task, job.params.get("options", {}).get("resume_from"))
                    mark("resolve_weights", note=str(start))
                else:
                    mark("resolve_weights", note="adapter default")
                mark("build_config", "running")
                mark("build_config")
                mark("train", "running")
                watchdog.start()
                try:
                    attempts = 0
                    while True:
                        try:
                            res = w.ADAPTERS[family].train(variant, versioning.version_dir(v), ml.TASK[p.type],
                                                           opts, on_epoch, should_stop)
                            break
                        except Exception as e:
                            if watchdog.stalled:
                                raise RuntimeError(f"no training progress for {watchdog.limit:g} s") from e
                            if not (_is_oom(e) and attempts == 0 and not history and opts["batch"] >= 2):
                                raise
                            attempts += 1
                            opts["batch"] //= 2
                            train_note = f"retried with batch={opts['batch']}"
                            gc.collect()                       # drop the failed attempt's tensors first
                            try:
                                import torch
                                torch.cuda.empty_cache()
                            except Exception:                  # CPU-only installs have nothing to free
                                pass
                            watchdog.reset()
                finally:
                    watchdog.stop()
                if watchdog.stalled:
                    raise RuntimeError(f"no training progress for {watchdog.limit:g} s")
                if budget_stop and len(history) < opts["epochs"]:
                    # The adapter stopped cleanly and kept best.pt, but that checkpoint covers only
                    # part of the run: never register it as a ready (deployable) model.
                    mark("train", "failed", note="GPU allowance exhausted; model not registered")
                    raise w.QuotaExhausted(
                        f"GPU time allowance exhausted after {len(history)} of {opts['epochs']} epochs "
                        f"({budget:g} s was left when the run started); model not registered"
                    )
                mark("train", note=train_note)
                mark("evaluate", "running")
                tm.weights, tm.status = res.weights, "ready"     # resolve() only accepts ready models
                db.commit()
                base = ml.final_metrics(history, tm.task)
                try:
                    with w.scheduler.training_scope():            # the holder may load its own model for eval
                        ev = w.evaluate(f"trained:{tm.id}", versioning.version_dir(v), tm.task,
                                        db=db, workspace_id=tm.workspace_id)
                    tm.metrics = {**base, "eval": ev}
                    mark("evaluate")
                except Exception as e:                            # a broken eval must not discard good weights
                    log.exception("evaluation failed for model %s", tm.id)
                    tm.metrics = {**base, "eval_error": safe_error(e, "train")}
                    mark("evaluate", "failed", note="model kept ready without evaluation")
                tm.history = history
                mark("register", "running")
                webhooks.emit(db, tm.workspace_id, "model.ready", {
                    "model_id": tm.id, "project_id": tm.project_id, "name": tm.name,
                    "variant": tm.variant, "task": tm.task})
                db.commit()
                mark("register")
            mark("release")
        except Exception as e:
            if isinstance(e, w.QuotaExhausted):
                # Keep a previously good checkpoint deployable; a fresh (queued) model simply fails.
                tm.status = "ready" if previous[0] == "ready" else "failed"
                tm.weights = previous[1]
            else:
                tm.status = "cancelled" if isinstance(e, Cancelled) else "failed"
            db.commit()
            shutil.rmtree(DATA_DIR / "train_data" / tm.id, ignore_errors=True)   # adapter only cleans on success
            for name, entry in list(stages.items()):
                if entry["status"] == "running":
                    mark(name, "failed")
            mark("release")                 # the exclusive context has already released the GPU
            _meter_gpu(db, job, time.monotonic() - t0)   # failed runs still held the card
            raise
        _meter_gpu(db, job, time.monotonic() - t0)
        return {"model_id": tm.id, **tm.metrics, "stages": stages}


def run_autolabel(job: Job):
    from .. import worker as w
    P = job.params
    with SessionLocal() as db:
        p = db.get(Project, job.project_id)
        classes = db.scalars(select(LabelClass).where(LabelClass.project_id == p.id).order_by(LabelClass.created)).all()
        q = select(Image).where(Image.project_id == p.id, Image.deleted_at.is_(None))
        if P.get("image_ids"):
            q = q.where(Image.id.in_(P["image_ids"]))
        if P.get("batch_id"):
            q = q.where(Image.batch_id == P["batch_id"])
        if P.get("only_unannotated", True):
            q = q.where(Image.n_annotations == 0)
        rows = db.scalars(q).all()
        sam_ok = sam_available()
        ws = db.get(Workspace, job.workspace_id)
        labeled = total = processed = 0
        clamped = False
        for i, img in enumerate(rows):
            if w._cancelled(job.id):
                break
            if metering.remaining(db, ws, "ai_calls") <= 0:
                clamped = True            # an enqueued job stops at the allowance instead of overrunning it
                break
            processed += 1
            anns = w.label_image(imaging.load(img.path), project_type=p.type, params=P, classes=classes,
                                 db=db, workspace_id=job.workspace_id, sam_ok=sam_ok)
            if anns:
                set_annotations(db, img, (img.annotations or []) + anns)
                if img.status == "unassigned":
                    img.status = "review" if P.get("send_to_review", True) else "annotating"
                img.updated = now()
                labeled += 1
                total += len(anns)
                db.commit()          # keep earlier images even if a later VLM call dies
                # bill per committed image: a run that dies midway is still charged for what it labeled
                charge(db, ws, CREDIT_COST["autolabel_image"])
            # every processed image called the model, even when it produced no annotation
            metering.record(db, job.workspace_id, "ai_calls", 1, project_id=job.project_id, kind="autolabel")
            db.commit()
            w._set(job.id, progress=round((i + 1) / max(1, len(rows)) * 100, 1))
        return {"images": processed, "selected": len(rows), "labeled": labeled,
                "annotations": total, "quota_clamped": clamped}


HANDLERS = {"train": run_train, "autolabel": run_autolabel}
