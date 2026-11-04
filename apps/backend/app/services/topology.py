"""Which executor actually runs GPU-training kinds in this deployment (I7).

``LD_TRAIN_WORKER`` is only an operator override. By default the answer comes from the
heartbeat rows: a local ``app.worker`` advertises ``train``/``autolabel`` in ``Worker.kinds``
when it claims them. The pip GPU worker never writes a heartbeat, so its presence cannot make
the API accept families/options that its v1 CLI rejects. This is the same truth the admin
console shows, not a second topology description.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..models import Worker, now


def local_worker_claims_training(db: Session) -> bool:
    """True when an online local worker advertises a GPU-training kind."""
    wanted = set(config.REMOTE_JOB_KINDS)
    cutoff = now() - config.WORKER_STALE_S
    rows = db.scalars(select(Worker).where(Worker.last_seen >= cutoff)).all()
    return any(wanted & set(w.kinds or []) for w in rows)


def remote_training(db: Session) -> bool:
    """True when train/autolabel run on the pip GPU worker (v1: YOLO + size only).

    Precedence: explicit ``LD_TRAIN_WORKER``, this process's own executor, then the workers
    that are currently online. No worker advertising training means the pip-worker contract.
    """
    if config.TRAIN_WORKER:
        return config.TRAIN_WORKER == "remote"
    if any(config.runs_locally(kind) for kind in config.REMOTE_JOB_KINDS):
        return False
    return not local_worker_claims_training(db)
