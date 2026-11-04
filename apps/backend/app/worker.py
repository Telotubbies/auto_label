"""Background job runner. The DB `jobs` table is the queue — no Redis needed.

Run standalone (`python -m app.worker`) on the GPU host, or embedded in the api
process (LD_EMBEDDED_WORKER=1, the dev default).

The job bodies live in `app.handlers`, one module per feature; this module keeps the queue, the
training watchdog and the one registry that maps a job kind to its handler.
"""
import cv2                      # noqa: F401  seam: handlers resolve cv2 through this module
import gc                       # noqa: F401  seam
import logging
import statistics
import threading
import time
import traceback

from sqlalchemy import select, update

from .adapters import ADAPTERS, Cancelled          # noqa: F401  ADAPTERS is a runtime seam
from .adapters.refine import label_image           # noqa: F401  seam
from .adapters.ultralytics_ad import _start_weights  # noqa: F401  seam
from .config import LOCAL_JOB_KINDS
from .db import SessionLocal
from .deps import plan                             # noqa: F401  seam
from .errors import safe_error, safe_text
from .gpu import scheduler                         # noqa: F401  seam
from .handlers import MODULES as HANDLER_MODULES
from .handlers.insights import (run_health, run_insights_embedding, run_insights_images,
                                run_insights_leakage)
from .handlers.ops import run_retention
from .handlers.streams import run_extract_frames, run_track_forward
from .handlers.training import run_autolabel, run_train
from .handlers.versioning import run_export, run_export_engine, run_version
from .models import Job, now
from .services import (drift, imaging, insights_embedding, insights_jobs, metering,  # noqa: F401
                       remote_reaper, versioning, webhooks)
from .services.evaluate import evaluate            # noqa: F401  seam

# The names marked "seam" above are bound here on purpose: the handlers in app.handlers resolve
# their dependencies through this module (``w.ADAPTERS``, ``w.scheduler``, ``w.plan`` …), so a
# process that swaps one of them — the suite, an adapter install — keeps taking effect.

log = logging.getLogger("labeldesk.worker")
POLL = 1.5
WATCHDOG_MIN_S = 120.0                      # later epochs: never call a run stalled sooner than this
FIRST_EPOCH_MIN_S = 600.0                   # the first epoch also pays for export + model load
WATCHDOG_POLL_S = 0.01                      # floor for the adaptive poll (tests shrink the limit)
MAX_EPOCH_SAMPLES = 50                      # median over the recent epochs only
MIN_TRAIN_GPU_S = 60.0                      # the /train estimate floor: less cannot fund a minimal run


class QuotaExhausted(RuntimeError):
    """A job stopped at the workspace allowance; it must fail instead of reporting a truncated result."""


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
        self.last = self.last_epoch = time.monotonic()   # last = any progress; last_epoch = the last epoch
        self.epoch_secs: list[float] = []
        self._seen_epoch = False
        self.limit = self.first_limit
        self.stalled = False

    def start(self) -> "_Watchdog":
        # The first-epoch grace runs from the first epoch, not from construction: dataset export
        # and weight resolution happen in between and must not eat the training budget.
        with self._lock:
            self.last = self.last_epoch = time.monotonic()
        self._thread.start()
        return self

    def tick(self) -> None:
        """Record an on_epoch callback; the gap since the previous one feeds the limit."""
        now = time.monotonic()
        with self._lock:
            self.epoch_secs.append(now - self.last_epoch)  # the first gap includes load/export: a generous seed
            del self.epoch_secs[:-MAX_EPOCH_SAMPLES]       # old epochs must not pin the limit forever
            self._seen_epoch = True
            self.last = self.last_epoch = now
            self.stalled = False                           # an epoch is progress: clear a pre-epoch false alarm

    def beat(self) -> None:
        """Refresh liveness only (a polling adapter saw real progress); never an epoch sample."""
        with self._lock:
            self.last = time.monotonic()

    def reset(self) -> None:
        with self._lock:
            self.last = self.last_epoch = time.monotonic()
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
                           .values(status="running", started=now(), executor="local")).rowcount
            db.commit()
            if n:
                return jid
    return None


def _set(jid: str, **kw):
    with SessionLocal() as db:
        db.execute(update(Job).where(Job.id == jid).values(**kw)); db.commit()
    try:                                          # long jobs keep the admin console green
        from .services import heartbeat
        done = kw.get("status") in ("done", "failed", "cancelled")
        heartbeat.beat(LOCAL_JOB_KINDS, current_job=None if done else jid)
    except Exception:                             # a heartbeat failure must never fail a job
        log.exception("worker heartbeat failed")


def _cancelled(jid: str) -> bool:
    with SessionLocal() as db:
        return db.scalar(select(Job.status).where(Job.id == jid)) == "cancelling"


def _over_budget(started: float, budget: float, now_m: float) -> bool:
    """True when a lease has run longer than the GPU allowance the job started with."""
    return now_m - started > budget


HANDLERS = {kind: handler for module in HANDLER_MODULES for kind, handler in module.HANDLERS.items()}


def missing_handlers() -> set[str]:
    """CPU handlers that no local process claims (a job that would queue forever)."""
    from .config import REMOTE_JOB_KINDS
    return set(HANDLERS) - set(REMOTE_JOB_KINDS) - set(LOCAL_JOB_KINDS)


def assert_handlers_claimed() -> None:
    missing = missing_handlers()
    if missing:
        raise RuntimeError(f"no local executor claims job kinds {sorted(missing)}; add them to LD_LOCAL_JOBS")


def _notify(job: Job, status: str, error: str = ""):
    """Fan the terminal job status out to webhooks; failures to notify never fail the job."""
    try:
        with SessionLocal() as db:
            webhooks.emit(db, job.workspace_id, "job.done", {
                "job_id": job.id, "kind": job.kind, "status": status, "project_id": job.project_id,
                "error": error})
            db.commit()
    except Exception:
        log.exception("could not enqueue job.done webhook for %s", job.id)


def run_one(jid: str):
    with SessionLocal() as db:
        job = db.get(Job, jid)
        db.expunge(job)
    if _cancelled(jid):                       # I22: never start work the user already cancelled
        _set(jid, status="cancelled", finished=now())
        return
    try:
        result = HANDLERS[job.kind](job)
        failed = isinstance(result, dict) and result.get("status") == "failed"
        final = "cancelled" if _cancelled(jid) else "failed" if failed else "done"
        err = safe_text(result.get("error"), job.kind) if failed else ""
        _set(jid, status=final, progress=100.0 if final == "done" else job.progress, error=err,
             result=result, finished=now())
        _notify(job, final, err)
    except Cancelled:
        _set(jid, status="cancelled", finished=now())     # stopped on purpose before anything was produced
    except Exception as e:
        log.error("job %s (%s) failed\n%s", jid, job.kind, traceback.format_exc())
        err = safe_error(e, job.kind)
        _set(jid, status="failed", error=err, finished=now())
        _notify(job, "failed", err)


def recover():
    """Jobs left by a crashed *local* process go back to the queue; remote claims are untouched.

    A remote GPU job is owned by the reaper: requeueing it here would run the same train twice
    when the API (which also handles train in dev) restarts beside a pip worker (I9).
    """
    with SessionLocal() as db:
        jobs = db.scalars(select(Job).where(
            Job.status.in_(("running", "cancelling")), Job.kind.in_(LOCAL_JOB_KINDS)
        )).all()
        for job in jobs:
            if remote_reaper.remote_owned(job):
                continue
            if job.status == "cancelling":
                job.status, job.finished = "cancelled", now()
            else:
                job.status = "queued"
        db.commit()


OPS_SCHEDULE_S = 900           # check for due daily drift runs every 15 minutes
_last_ops_schedule = time.monotonic()
REAP_S = 60                    # a dead remote worker is noticed within a minute of its timeout


def _reap_remote() -> None:
    """Fail remote jobs whose worker vanished; cheap query, safe to call from its own thread."""
    try:
        with SessionLocal() as db:
            changed = remote_reaper.reap(db)
        if changed:
            log.warning("failed %d remote job(s) whose worker stopped reporting: %s", len(changed), changed)
    except Exception:                  # a reaper bug must never stop the job loop
        log.exception("could not reap remote jobs")


def _reaper_loop(stop: threading.Event) -> None:
    """Sweep on its own cadence: a multi-hour local job must not delay reaping (I9)."""
    while not stop.is_set():
        _reap_remote()
        stop.wait(REAP_S)


def _schedule_ops() -> None:
    """Queue the daily drift job for projects that have a ready model and no run in 24 h."""
    global _last_ops_schedule
    if time.monotonic() - _last_ops_schedule < OPS_SCHEDULE_S:
        return
    _last_ops_schedule = time.monotonic()
    try:
        with SessionLocal() as db:
            drift.schedule_daily(db)
    except Exception:                  # a scheduler failure must never stop the job loop
        log.exception("could not schedule drift jobs")


def loop(stop: threading.Event | None = None):
    from .config import RETENTION_CHECK_S
    from .services import heartbeat, retention
    assert_handlers_claimed()          # fail fast instead of leaving a kind queued forever
    recover()
    heartbeat.beat(LOCAL_JOB_KINDS)
    next_cleanup = 0.0
    while not (stop and stop.is_set()):
        if time.monotonic() >= next_cleanup:
            try:
                retention.enqueue_if_due()
            except Exception:                    # a broken retention pass must not stop every job
                log.exception("could not enqueue the retention job")
            next_cleanup = time.monotonic() + RETENTION_CHECK_S
        _schedule_ops()           # self-throttled; long jobs must not starve the daily drift check
        jid = _claim()
        if jid:
            heartbeat.beat(LOCAL_JOB_KINDS, current_job=jid)
            try:
                run_one(jid)
            finally:
                heartbeat.beat(LOCAL_JOB_KINDS)
        else:
            heartbeat.beat(LOCAL_JOB_KINDS)
            time.sleep(POLL)


def start_background() -> threading.Event:
    stop = threading.Event()
    threading.Thread(target=loop, args=(stop,), daemon=True, name="labeldesk-worker").start()
    threading.Thread(target=_reaper_loop, args=(stop,), daemon=True, name="labeldesk-reaper").start()
    threading.Thread(target=webhooks.flush_loop, args=(stop,), daemon=True, name="labeldesk-webhooks").start()
    return stop


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from .bootstrap import init_db
    init_db()
    # Production runs the worker as its own process (LD_EMBEDDED_WORKER=0), so retries need a flusher here too.
    threading.Thread(target=webhooks.flush_loop, args=(threading.Event(),), daemon=True,
                     name="labeldesk-webhooks").start()
    threading.Thread(target=_reaper_loop, args=(threading.Event(),), daemon=True,
                     name="labeldesk-reaper").start()
    log.info("worker started")
    loop()
