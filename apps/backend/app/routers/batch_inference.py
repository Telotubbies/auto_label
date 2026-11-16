"""Batch inference: queue a model over a batch, video frames or a bucket prefix; fetch the result."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..adapters import resolve
from ..deps import Ctx, audit, project_ctx
from ..models import Connector, Job, LabelClass
from ..security import sign_path
from ..services import batch_inference, metering
from ..services.flags import require_flag
from .projects import job_out

router = APIRouter(prefix="/api/ws/{ws}/projects/{project}/batch-inference", tags=["batch-inference"])
FLAG = require_flag("task_36")


def job_with_url(j: Job) -> dict:
    out = job_out(j)
    file = (j.result or {}).get("file")
    out["url"] = sign_path(file) if j.status == "done" and file else None
    return out


class SourceIn(BaseModel):
    kind: Literal["batch", "video", "connector", "workflow"]   # workflow ships with Task 31
    batch_id: str | None = Field(None, max_length=32)
    video_id: str | None = Field(None, max_length=32)
    connector_id: str | None = Field(None, max_length=32)
    prefix: str = Field("", max_length=1024)
    limit: int = Field(batch_inference.MAX_IMAGES, ge=1, le=batch_inference.MAX_IMAGES)


class BatchInferenceIn(BaseModel):
    model_ref: str = Field(min_length=1, max_length=120)
    source: SourceIn
    output: Literal["csv", "coco", "dataset"] = "csv"
    confidence: float | None = Field(None, ge=0, le=1)
    classes: list[str] = Field(default_factory=list, max_length=100)
    name: str = Field("", max_length=120)


@router.post("")
def start(body: BatchInferenceIn, c: Ctx = Depends(project_ctx), _flag=Depends(FLAG)):
    """Queue the job; the worker resolves every input inside this project/workspace."""
    c.perm("project.infer")
    if body.source.kind == "workflow":
        raise HTTPException(501, "workflow inference requires Task 31 (workflow builder); run a model_ref instead")
    if body.source.kind != "connector" and body.source.limit != batch_inference.MAX_IMAGES:
        raise HTTPException(400, "limit only applies to connector sources")
    try:
        r = resolve(body.model_ref, c.db, workspace_id=c.ws.id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if body.output == "dataset" and r.adapter.family == "vlm":
        raise HTTPException(
            400, "VLM output cannot be written to the dataset without SAM 3.1 refinement — choose CSV or COCO"
        )
    if body.output == "coco" and r.variant.endswith("-cls"):
        raise HTTPException(
            400, "COCO export needs detection boxes; a classification model has none — choose CSV or dataset"
        )
    if body.source.kind == "connector":
        c.perm("workspace.connectors")
        conn = c.db.get(Connector, body.source.connector_id or "")
        if conn is None or conn.workspace_id != c.ws.id:
            raise HTTPException(404, "connector not found")
        if metering.remaining(c.db, c.ws, "ai_calls") < 1:
            raise HTTPException(402, "AI-call quota reached on this plan")
    else:
        try:
            count = len(batch_inference.source_images(c.db, c.project, body.source.model_dump()))
        except batch_inference.SourceNotFound as exc:
            raise HTTPException(404, str(exc)) from exc
        except batch_inference.SourceInvalid as exc:
            raise HTTPException(400, str(exc)) from exc
        metering.check(c.db, c.ws, "ai_calls", count)
    classes = list(dict.fromkeys(x.strip() for x in body.classes if x.strip()))
    if not classes:  # YOLO-World / VLM grounding needs the project's vocabulary
        classes = [
            row.name
            for row in c.db.scalars(
                select(LabelClass).where(LabelClass.project_id == c.project.id).order_by(LabelClass.created)
            )
        ]
    params = body.model_dump()
    params["classes"] = classes
    job = Job(workspace_id=c.ws.id, project_id=c.project.id, kind="batch_infer", params=params, created_by=c.uid)
    c.db.add(job)
    audit(
        c.db,
        c.ws.id,
        c.uid,
        "batch_infer.start",
        c.project.name,
        model_ref=body.model_ref,
        source=body.source.kind,
        output=body.output,
    )
    c.db.commit()
    return job_with_url(job)


@router.get("")
def list_jobs(c: Ctx = Depends(project_ctx), _flag=Depends(FLAG)):
    c.perm("project.read")
    rows = c.db.scalars(
        select(Job)
        .where(Job.project_id == c.project.id, Job.kind == "batch_infer")
        .order_by(Job.created.desc())
        .limit(50)
    ).all()
    return [job_with_url(j) for j in rows]


@router.get("/{jid}")
def get_job(jid: str, c: Ctx = Depends(project_ctx), _flag=Depends(FLAG)):
    c.perm("project.read")
    job = c.db.get(Job, jid)
    if job is None or job.project_id != c.project.id or job.kind != "batch_infer":
        raise HTTPException(404, "job not found")
    return job_with_url(job)
