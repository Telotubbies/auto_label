"""Labeling QA & workforce: consensus jobs, honeypots, review queue, labeler dashboard."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import Ctx, audit, project_ctx
from ..models import ConsensusJob, Honeypot
from ..services import labeling_ops
from ..services.flags import require_flag

router = APIRouter(prefix="/api/ws/{ws}/projects/{project}/labeling", tags=["labeling"],
                   dependencies=[Depends(require_flag("task_23"))])


def _job(c: Ctx, job_id: str) -> ConsensusJob:
    job = c.db.get(ConsensusJob, job_id)
    if not job or job.project_id != c.project.id or job.workspace_id != c.ws.id:
        raise HTTPException(404, "consensus job not found")
    return job


@router.get("/dashboard")
def dashboard(days: int = 30, c: Ctx = Depends(project_ctx)):
    c.need("annotator")
    # Reviewers see the whole team; everyone else sees only their own numbers (I5).
    only_user = None if c.can("project.review") else c.user.id
    return labeling_ops.dashboard(c.db, c, days, only_user=only_user)


@router.get("/my-tasks")
def my_tasks(c: Ctx = Depends(project_ctx)):
    c.need("annotator")
    return {"tasks": labeling_ops.my_tasks(c.db, c)}


@router.get("/review-queue")
def review_queue(limit: int = 50, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    return {"items": labeling_ops.review_queue(c.db, c, limit)}


@router.get("/consensus")
def list_jobs(limit: int = 50, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    rows = c.db.scalars(select(ConsensusJob).where(ConsensusJob.project_id == c.project.id,
                                                   ConsensusJob.workspace_id == c.ws.id)
                        .order_by(ConsensusJob.created.desc(), ConsensusJob.id)
                        .limit(max(1, min(limit, 200)))).all()
    return {"jobs": [labeling_ops.job_out(c.db, job) for job in rows]}


class ConsensusIn(BaseModel):
    image_ids: list[str] = []
    count: int = Field(12, ge=1, le=100)
    k: int = Field(3, ge=2, le=10)
    iou_threshold: float = Field(0.5, ge=0.1, le=0.95)


@router.post("/consensus")
def create_job(body: ConsensusIn, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    job = labeling_ops.create_job(c.db, c, body.image_ids, body.count, body.k, body.iou_threshold)
    c.db.commit()
    return labeling_ops.job_out(c.db, job)


@router.get("/consensus/{job_id}")
def get_job(job_id: str, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    return labeling_ops.job_detail(c.db, _job(c, job_id))


@router.post("/consensus/{job_id}/merge")
def merge_job(job_id: str, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    out = labeling_ops.merge_job(c.db, c, _job(c, job_id))
    c.db.commit()
    return out


class SubmitIn(BaseModel):
    annotations: list[dict] | None = None


@router.post("/consensus/{job_id}/images/{image_id}/submit")
def submit_draft(job_id: str, image_id: str, body: SubmitIn | None = None, c: Ctx = Depends(project_ctx)):
    """Hand in one consensus draft; without a body the assignment's latest autosave is submitted."""
    c.need("annotator")
    out = labeling_ops.submit_consensus(c.db, c, _job(c, job_id), image_id,
                                        body.annotations if body else None)
    c.db.commit()
    return out


@router.get("/honeypots")
def honeypots(c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    return labeling_ops.honeypots_out(c.db, c)


class HoneypotIn(BaseModel):
    image_id: str
    annotations: list[dict] | None = None


@router.post("/honeypots")
def create_honeypot(body: HoneypotIn, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    if body.annotations is not None and len(body.annotations) > 5000:
        raise HTTPException(400, "at most 5000 ground-truth annotations")
    honeypot = labeling_ops.create_honeypot(c.db, c, body.image_id, body.annotations)
    c.db.commit()
    items = labeling_ops.honeypots_out(c.db, c)["items"]
    return next(item for item in items if item["id"] == honeypot.id)


@router.delete("/honeypots/{honeypot_id}")
def delete_honeypot(honeypot_id: str, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    honeypot = c.db.get(Honeypot, honeypot_id)
    if not honeypot or honeypot.project_id != c.project.id or honeypot.workspace_id != c.ws.id:
        raise HTTPException(404, "honeypot not found")
    audit(c.db, c.ws.id, c.user.id, "labeling.honeypot.delete", honeypot.image_id)
    c.db.delete(honeypot)
    c.db.commit()
    return {"ok": True}
