"""Ops API: drift monitoring and active-learning control (thin router, logic in services)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from ..config import DRIFT_MIN_SAMPLES, DRIFT_P
from ..deps import Ctx, project_ctx, ws_ctx
from ..models import Batch, DriftRun, Image, Job, Project
from ..services import active_learning, drift

P = "/api/ws/{ws}/projects/{project}"
router = APIRouter(prefix=P, tags=["ops"])
ws_router = APIRouter(prefix="/api/ws/{ws}", tags=["ops"])


# --- drift --------------------------------------------------------------------------


@router.get("/drift")
def get_drift(c: Ctx = Depends(project_ctx)):
    return {
        "latest": drift.latest(c.db, c.project),
        "runs": drift.runs(c.db, c.project),
        "samples": drift.sample_count(c.db, c.project),
        "config": {"p_value": DRIFT_P, "min_samples": DRIFT_MIN_SAMPLES},
        "source": drift.feature_source(),
    }


@router.post("/drift/scan")
def scan_drift(c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    model = drift.production_model(c.db, c.project)
    if model is None:
        raise HTTPException(409, "no ready model — train a model first")
    job = Job(
        workspace_id=c.ws.id,
        project_id=c.project.id,
        kind="drift",
        params={"model_id": model.id},
        created_by=c.uid,
    )
    c.db.add(job)
    c.db.commit()
    return {"job_id": job.id}


@router.post("/drift/{run_id}/send-to-labeling")
def send_drift_samples(run_id: str, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    run = c.db.get(DriftRun, run_id)
    if run is None or run.project_id != c.project.id:
        raise HTTPException(404, "drift run not found")
    try:
        sent = drift.send_to_labeling(c.db, c.project, run, c.user)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    return {"sent": sent}


@ws_router.get("/drift")
def workspace_drift(c: Ctx = Depends(ws_ctx)):
    projects = c.db.scalars(
        select(Project).where(Project.workspace_id == c.ws.id, Project.deleted_at.is_(None)).order_by(Project.name)
    ).all()
    return [
        {
            "project_id": p.id,
            "slug": p.slug,
            "name": p.name,
            "latest": drift.latest(c.db, p),
        }
        for p in projects
    ]


# --- active learning ----------------------------------------------------------------


class ActiveRunIn(BaseModel):
    k: int | None = Field(default=None, ge=1, le=200)


@router.get("/active-learning")
def get_active_learning(c: Ctx = Depends(project_ctx)):
    out = active_learning.summary(c.db, c.project)
    rows = c.db.execute(
        select(Batch.id, Batch.name, Batch.created, func.count(Image.id))
        .outerjoin(Image, (Image.batch_id == Batch.id) & Image.deleted_at.is_(None))
        .where(Batch.project_id == c.project.id, Batch.source == "active-learning")
        .group_by(Batch.id)
        .order_by(Batch.created.desc())
        .limit(10)
    ).all()
    out["batches"] = [{"id": r[0], "name": r[1], "created": r[2], "images": r[3]} for r in rows]
    return out


@router.post("/active-learning/run")
def run_active_learning(body: ActiveRunIn | None = None, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    if active_learning.remaining(c.db, c.project) <= 0:
        raise HTTPException(409, "active-learning daily cap reached")
    job = Job(
        workspace_id=c.ws.id,
        project_id=c.project.id,
        kind="active_learning",
        params={"k": body.k if body else None},
        created_by=c.uid,
    )
    c.db.add(job)
    c.db.commit()
    return {"job_id": job.id}
