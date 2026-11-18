"""Publishing a project: the licence choice and the explicit content check (T-033)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..deps import Ctx, project_ctx
from ..services import publishing
from ..services.flags import require_flag

router = APIRouter(prefix="/api/ws/{ws}/projects", tags=["publishing"],
                   dependencies=[Depends(require_flag("task_a1_publish"))])


class PublishIn(BaseModel):
    license: str = ""
    pii_ack: bool = False


@router.post("/{project}/publish")
def publish_project(body: PublishIn, c: Ctx = Depends(project_ctx)):
    return publishing.publish(c.db, c, c.project, body.license, body.pii_ack)


@router.post("/{project}/unpublish")
def unpublish_project(c: Ctx = Depends(project_ctx)):
    return publishing.unpublish(c.db, c, c.project)
