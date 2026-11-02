"""Shared finalisation for a finished training run (local worker and remote GPU worker)."""
import logging

from ..errors import safe_error
from ..models import Job, TrainedModel, Version
from . import ml, versioning, webhooks
from .evaluate import evaluate

log = logging.getLogger("labeldesk.finalize")


def evaluate_and_announce(db, tm: TrainedModel) -> dict:
    """Attach the pycocotools eval (or a safe error) and emit ``model.ready``."""
    base = ml.final_metrics(tm.history, tm.task)
    v = db.get(Version, tm.version_id) if tm.version_id else None
    try:
        if v is None:
            raise ValueError("training version not found")
        ev = evaluate(f"trained:{tm.id}", versioning.version_dir(v), tm.task, db=db,
                      workspace_id=tm.workspace_id)
        tm.metrics = {**base, "eval": ev}
    except Exception as e:                      # a broken eval must not discard good weights
        log.exception("evaluation failed for model %s", tm.id)
        tm.metrics = {**base, "eval_error": safe_error(e, "train")}
    webhooks.emit(db, tm.workspace_id, "model.ready", {
        "model_id": tm.id, "project_id": tm.project_id, "name": tm.name,
        "variant": tm.variant, "task": tm.task})
    return tm.metrics


def job_done(db, job: Job, status: str, error: str = "") -> None:
    """Fan a terminal job status out to the workspace's webhooks."""
    webhooks.emit(db, job.workspace_id, "job.done", {
        "job_id": job.id, "kind": job.kind, "status": status, "project_id": job.project_id,
        "error": error})
