"""Background job runner. The DB `jobs` table is the queue — no Redis needed.

Run standalone (`python -m app.worker`) on the GPU host, or embedded in the api
process (LD_EMBEDDED_WORKER=1, the dev default).
"""
import gc
import logging
import shutil
import statistics
import threading
import time
import traceback

from sqlalchemy import select, update

from .adapters import ADAPTERS
from .adapters.refine import label_image, sam_available
from .adapters.ultralytics_ad import _start_weights
from .config import CREDIT_COST, DATA_DIR, LOCAL_JOB_KINDS
from .db import SessionLocal
from .deps import charge
from .gpu import scheduler
from .models import Image, Job, LabelClass, Project, TrainedModel, Version, Workspace, now, set_annotations
from .services import exporters, ml, versioning, imaging
from .services.evaluate import evaluate

log = logging.getLogger("labeldesk.worker")
POLL = 1.5
WATCHDOG_MIN_S = 120.0                      # later epochs: never call a run stalled sooner than this
FIRST_EPOCH_MIN_S = 600.0                   # the first epoch also pays for export + model load
WATCHDOG_POLL_S = 0.01                      # floor for the adaptive poll (tests shrink the limit)


def _stall_limit(epoch_secs: list[float]) -> float:
    """Later epochs: stalled after 3x the median epoch, but never sooner than WATCHDOG_MIN_S."""
    return max(WATCHDOG_MIN_S, 3 * statistics.median(epoch_secs)) if epoch_secs else WATCHDOG_MIN_S


def _first_limit(train_images: int, epochs: int, imgsz: int) -> float:
    """First-epoch grace: max(600 s, 2x the estimate the Train page shows).

    The Train page estimates `train_images * epochs * (imgsz/640)^2 / 600` minutes; the first epoch
    also pays for the dataset export and the model load, so it gets the larger of the two budgets."""
    estimate_s = train_images * max(1, epochs) * (imgsz / 640) ** 2 / 600 * 60
    return max(FIRST_EPOCH_MIN_S, 2 * estimate_s)


class _Watchdog:
    """Daemon thread that flips `stalled` when on_epoch callbacks stop arriving."""

    def __init__(self, first_limit: float = FIRST_EPOCH_MIN_S):
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="labeldesk-train-watchdog")
        self.first_limit = float(first_limit)
        self.last = time.monotonic()
        self.epoch_secs: list[float] = []
        self._seen_epoch = False
        self.limit = self.first_limit
        self.stalled = False

    def start(self) -> "_Watchdog":
        self._thread.start()
        return self

    def tick(self) -> None:
        """Record an on_epoch callback; the gap since the previous one feeds the limit."""
        now = time.monotonic()
        with self._lock:
            self.epoch_secs.append(now - self.last)      # the first gap includes load/export: a generous seed
            self._seen_epoch = True
            self.last = now

    def reset(self) -> None:
        with self._lock:
            self.last = time.monotonic()
            self.epoch_secs.clear()
            self._seen_epoch = False
            self.limit = self.first_limit
            self.stalled = False

    def _run(self) -> None:
        while True:
            with self._lock:
                self.limit = _stall_limit(self.epoch_secs) if self._seen_epoch else self.first_limit
                limit = self.limit
                if time.monotonic() - self.last > limit:
                    self.stalled = True
            # poll a few times per limit (max 1 s) so a long run does not spin
            if self._stop.wait(min(1.0, max(WATCHDOG_POLL_S, limit / 4))):
                return

    def stop(self) -> None:
        self._stop.set()


def _claim():
    with SessionLocal() as db:
        for jid in db.scalars(select(Job.id).where(Job.status == "queued", Job.kind.in_(LOCAL_JOB_KINDS)).order_by(Job.created).limit(5)):
            # compare-and-set so two workers never run the same job
            n = db.execute(update(Job).where(Job.id == jid, Job.status == "queued")
                           .values(status="running", started=now())).rowcount
            db.commit()
            if n:
                return jid
    return None


def _set(jid: str, **kw):
    with SessionLocal() as db:
        db.execute(update(Job).where(Job.id == jid).values(**kw)); db.commit()


def _cancelled(jid: str) -> bool:
    with SessionLocal() as db:
        return db.scalar(select(Job.status).where(Job.id == jid)) == "cancelling"


# --- handlers ---------------------------------------------------------------------

def run_version(job: Job):
    with SessionLocal() as db:
        v = db.get(Version, job.params["version_id"])
        v.status = "generating"; db.commit()
        try:
            stats = versioning.generate(db, v, lambda f: _set(job.id, progress=round(f * 100, 1)))
            v.status, v.stats = "ready", stats
        except Exception:
            v.status = "failed"; db.commit(); raise
        db.commit()
        return {"version_id": v.id, **stats}


def run_export(job: Job):
    with SessionLocal() as db:
        v = db.get(Version, job.params["version_id"])
        fmt = job.params["format"]
        out = DATA_DIR / "exports" / v.id / fmt
        z = exporters.export(fmt, versioning.version_dir(v), out)
        import shutil
        shutil.rmtree(out, ignore_errors=True)
        return {"version_id": v.id, "format": fmt, "file": z.relative_to(DATA_DIR).as_posix(), "bytes": z.stat().st_size}


def _is_oom(exc: BaseException) -> bool:
    """torch.cuda.OutOfMemoryError, matched by name so tests need no torch import."""
    if type(exc).__name__ == "OutOfMemoryError":
        return True
    try:
        import torch
    except ImportError:
        return False
    return isinstance(exc, torch.cuda.OutOfMemoryError)


def run_train(job: Job):
    """Train, evaluate and register one model, recording progress stages for the UI."""
    t0 = time.monotonic()
    stages: dict[str, dict] = {}

    def mark(name: str, status: str = "done", note: str | None = None):
        entry = {"status": status, "t": round(time.monotonic() - t0, 2)}
        if note:
            entry["note"] = note
        stages[name] = entry
        _set(job.id, result={"stages": stages})     # the UI polls job.result mid-run

    mark("queue")
    with SessionLocal() as db:
        tm = db.get(TrainedModel, job.params["model_id"])
        v = db.get(Version, tm.version_id)
        p = db.get(Project, tm.project_id)
        tm.status = "training"; db.commit()
        history: list[dict] = []
        variant = tm.variant or tm.arch
        family = tm.family or "ultralytics"
        opts = {**job.params.get("options", {}), "model_id": tm.id}
        opts.update(batch=int(opts.get("batch", 8)), epochs=int(opts.get("epochs", 30)),
                    imgsz=int(opts.get("imgsz", 640)), max_minutes=opts.get("max_minutes"),
                    resume_from=opts.get("resume_from"))
        train_images = int((v.stats or {}).get("splits", {}).get("train") or 0)
        watchdog = _Watchdog(_first_limit(train_images, opts["epochs"], opts["imgsz"]))
        opts["stalled"] = lambda: watchdog.stalled     # read by the adapter's per-batch callbacks
        train_note = None

        def on_epoch(ep, total, metrics):
            watchdog.tick()
            history[:] = [h for h in history if h["epoch"] != ep] + [{"epoch": ep, **metrics}]   # final val re-fires the last epoch
            with SessionLocal() as s:
                s.execute(update(TrainedModel).where(TrainedModel.id == tm.id).values(history=history))
                s.execute(update(Job).where(Job.id == job.id).values(progress=round(ep / total * 100, 1)))
                s.commit()

        def should_stop():
            return _cancelled(job.id) or watchdog.stalled

        try:
            mark("acquire_gpu", "running")
            with scheduler.exclusive(f"training {variant}"):
                mark("acquire_gpu")
                mark("materialise", "running")
                versioning.cached_export(v, "coco")      # also proves the dataset is readable
                mark("materialise")
                mark("resolve_weights", "running")
                if family == "ultralytics":
                    start = _start_weights(variant, tm.task, job.params.get("options", {}).get("resume_from"))
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
                            res = ADAPTERS[family].train(variant, versioning.version_dir(v), ml.TASK[p.type],
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
                mark("train", note=train_note)
                mark("evaluate", "running")
                tm.weights, tm.status = res.weights, "ready"     # resolve() only accepts ready models
                db.commit()
                base = ml.final_metrics(history, tm.task)
                try:
                    with scheduler.training_scope():              # the holder may load its own model for eval
                        ev = evaluate(f"trained:{tm.id}", versioning.version_dir(v), tm.task,
                                      db=db, workspace_id=tm.workspace_id)
                    tm.metrics = {**base, "eval": ev}
                    mark("evaluate")
                except Exception as e:                            # a broken eval must not discard good weights
                    log.exception("evaluation failed for model %s", tm.id)
                    tm.metrics = {**base, "eval_error": f"{type(e).__name__}: {e}"}
                    mark("evaluate", "failed", note="model kept ready without evaluation")
                tm.history = history
                mark("register", "running")
                db.commit()
                mark("register")
            mark("release")
        except Exception:
            tm.status = "failed"; db.commit()
            shutil.rmtree(DATA_DIR / "train_data" / tm.id, ignore_errors=True)   # adapter only cleans on success
            for name, entry in list(stages.items()):
                if entry["status"] == "running":
                    mark(name, "failed")
            mark("release")                 # the exclusive context has already released the GPU
            raise
        return {"model_id": tm.id, **tm.metrics, "stages": stages}


def run_autolabel(job: Job):
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
        labeled = total = 0
        for i, img in enumerate(rows):
            if _cancelled(job.id):
                break
            anns = label_image(imaging.load(img.path), project_type=p.type, params=P, classes=classes,
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
                charge(db, db.get(Workspace, job.workspace_id), CREDIT_COST["autolabel_image"])
                db.commit()
            _set(job.id, progress=round((i + 1) / max(1, len(rows)) * 100, 1))
        return {"images": len(rows), "labeled": labeled, "annotations": total}


HANDLERS = {"version": run_version, "export": run_export, "train": run_train, "autolabel": run_autolabel}


def run_one(jid: str):
    with SessionLocal() as db:
        job = db.get(Job, jid)
        db.expunge(job)
    try:
        result = HANDLERS[job.kind](job)
        final = "cancelled" if _cancelled(jid) else "done"
        _set(jid, status=final, progress=100.0 if final == "done" else job.progress, result=result, finished=now())
    except Exception as e:
        log.error("job %s (%s) failed\n%s", jid, job.kind, traceback.format_exc())
        _set(jid, status="failed", error=f"{type(e).__name__}: {e}", finished=now())


def recover():
    """Jobs left 'running' by a crashed process go back to the queue."""
    with SessionLocal() as db:
        db.execute(update(Job).where(Job.status.in_(("running", "cancelling")), Job.kind.in_(LOCAL_JOB_KINDS))
                   .values(status="queued"))
        db.commit()


def loop(stop: threading.Event | None = None):
    recover()
    while not (stop and stop.is_set()):
        jid = _claim()
        if jid:
            run_one(jid)
        else:
            time.sleep(POLL)


def start_background() -> threading.Event:
    stop = threading.Event()
    threading.Thread(target=loop, args=(stop,), daemon=True, name="labeldesk-worker").start()
    return stop


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from .bootstrap import init_db
    init_db()
    log.info("worker started")
    loop()
