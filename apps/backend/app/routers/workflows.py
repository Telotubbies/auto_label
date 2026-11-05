"""No-code workflow builder API: create, edit (versioned), list versions, restore, run."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import Ctx, project_ctx
from ..models import Image
from ..services import imaging
from ..services import workflow_runner as runner
from ..services import workflows as svc
from ..services.flags import require_flag

router = APIRouter(prefix="/api/ws/{ws}/projects/{project}/workflows", tags=["workflows"],
                   dependencies=[Depends(require_flag("task_31"))])
log = logging.getLogger(__name__)


def _workflow(c: Ctx, workflow_id: str):
    wf = svc.get(c.db, c.project, workflow_id)
    if wf is None:
        raise HTTPException(404, "workflow not found")
    return wf


def _bad(e: ValueError) -> HTTPException:
    return HTTPException(409 if "already exists" in str(e) else 400, str(e))


class WorkflowIn(BaseModel):
    name: str
    blocks: list[dict]


class WorkflowPatch(BaseModel):
    name: str | None = None
    blocks: list[dict] | None = None


class RestoreIn(BaseModel):
    version: int


class RunIn(BaseModel):
    image_id: str


@router.get("")
def list_workflows(c: Ctx = Depends(project_ctx)):
    return [svc.out(w) for w in svc.list_for_project(c.db, c.project)]


@router.post("")
def create_workflow(body: WorkflowIn, c: Ctx = Depends(project_ctx)):
    c.perm("project.models")
    try:
        wf = svc.create(c.db, c.project, body.name, body.blocks, c.uid)
    except ValueError as e:
        raise _bad(e) from e
    return svc.out(wf)


@router.get("/{workflow_id}")
def get_workflow(workflow_id: str, c: Ctx = Depends(project_ctx)):
    return svc.out(_workflow(c, workflow_id))


@router.put("/{workflow_id}")
def update_workflow(workflow_id: str, body: WorkflowPatch, c: Ctx = Depends(project_ctx)):
    c.perm("project.models")
    wf = _workflow(c, workflow_id)
    try:
        wf = svc.update(c.db, wf, body.name, body.blocks, c.uid)
    except ValueError as e:
        raise _bad(e) from e
    return svc.out(wf)


@router.get("/{workflow_id}/versions")
def list_versions(workflow_id: str, c: Ctx = Depends(project_ctx)):
    return [svc.version_out(v) for v in svc.versions(c.db, _workflow(c, workflow_id))]


@router.post("/{workflow_id}/restore")
def restore_workflow(workflow_id: str, body: RestoreIn, c: Ctx = Depends(project_ctx)):
    c.perm("project.models")
    wf = _workflow(c, workflow_id)
    try:
        wf = svc.restore(c.db, wf, body.version, c.uid)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return svc.out(wf)


@router.post("/{workflow_id}/run")
def run_workflow(workflow_id: str, body: RunIn, c: Ctx = Depends(project_ctx)):
    c.perm("project.infer")
    wf = _workflow(c, workflow_id)
    img = c.db.get(Image, body.image_id)
    if img is None or img.deleted_at or img.project_id != c.project.id:
        raise HTTPException(404, "image not found")
    try:
        image = imaging.load(img.path)
    except Exception:
        raise HTTPException(400, "not a valid image") from None
    try:
        result = runner.run(c.db, c.project, wf.blocks, image, image_row=img)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except RuntimeError:
        log.exception("workflow model unavailable")
        raise HTTPException(503, "model unavailable") from None
    except Exception:
        log.exception("workflow run failed")
        raise HTTPException(500, "inference failed") from None
    return {"workflow": wf.id, "version": wf.version, **result}
