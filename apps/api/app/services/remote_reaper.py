"""Reap train/autolabel jobs whose remote GPU worker vanished (I9).

The pip worker claims a job, reports progress per epoch/image, and reports complete/fail. If its
session dies (Kaggle closes, the box reboots), the reports stop: nothing else transitions the row,
so the UI shows a forever-running stepper, `job.done` never fires, and Cancel stays `cancelling`.
This sweep notices the missing heartbeat and makes that transition. A local `app.worker` owns the
same kinds when it claims them, so only ``REMOTE_JOB_KINDS`` rows are touched — local recovery
keeps handling those.

Not a queue/scheduler: the DB job row is the queue and `worker.loop` is the scheduler, so this
is the state-machine half of it, not new infrastructure.
"""

from __future__ import annotations

import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import REMOTE_CANCEL_GRACE_S, REMOTE_JOB_KINDS, REMOTE_JOB_TIMEOUT_S
from ..models import Job, TrainedModel
from . import finalize

# A message we wrote, so it may reach the customer (never the worker's internals).
STALE_ERROR = "the remote worker stopped reporting — see the worker log"


def _last_seen(job: Job) -> float:
    """When the worker was last known alive: start, creation, or its latest progress report."""
    heartbeat = (job.result or {}).get("heartbeat")
    return max(float(job.started or 0.0), float(job.created or 0.0), float(heartbeat or 0.0))


def reap(db: Session, now_ts: float | None = None) -> list[str]:
    """Fail stale remote runs and finish abandoned remote cancels; returns the changed job ids.

    ``now_ts`` is injectable for tests; production leaves it None.
    """
    ts = time.time() if now_ts is None else now_ts
    changed: list[str] = []

    # A long, healthy run keeps reporting progress, so the clock is the last report, not `started`.
    # There are only a handful of running remote rows; filtering in Python keeps JSON portable.
    for job in db.scalars(
        select(Job).where(Job.kind.in_(REMOTE_JOB_KINDS), Job.status == "running")
    ).all():
        if ts - _last_seen(job) < REMOTE_JOB_TIMEOUT_S:
            continue
        job.status, job.error, job.finished = "failed", STALE_ERROR, ts
        if job.kind == "train":
            model_id = (job.params or {}).get("model_id")
            model = db.get(TrainedModel, model_id) if model_id else None
            if model is not None and model.status in ("queued", "training"):
                model.status = "failed"          # the model page must stop saying "training"
        finalize.job_done(db, job, "failed", STALE_ERROR)
        changed.append(job.id)

    for job in db.scalars(
        select(Job).where(Job.kind.in_(REMOTE_JOB_KINDS), Job.status == "cancelling")
    ).all():
        # The cancel route stamps `cancel_requested`; pre-upgrade rows fall back to the start time.
        requested = (job.result or {}).get("cancel_requested") or job.started or job.created or ts
        if ts - float(requested) < REMOTE_CANCEL_GRACE_S:
            continue
        job.status, job.finished = "cancelled", ts
        finalize.job_done(db, job, "cancelled")
        changed.append(job.id)

    if changed:
        db.commit()
    return changed
