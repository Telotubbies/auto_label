"""Deployment aliases: read the workspace/project deployment state and move an alias."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import Ctx, project_ctx, ws_ctx
from ..services import deployments as svc

router = APIRouter(prefix="/api/ws/{ws}", tags=["deployments"])
P = "/projects/{project}/deployments"


@router.get("/deployments")
def workspace_deployments(c: Ctx = Depends(ws_ctx)):
    """Every live project with its aliases, deployable models and latest drift run."""
    return svc.workspace_state(c.db, c.ws.id)


@router.get(P)
def project_deployments(c: Ctx = Depends(project_ctx)):
    return svc.state(c.db, c.project)


class SwitchIn(BaseModel):
    model_id: str


@router.put(P + "/{alias}")
def switch_alias(alias: str, body: SwitchIn, c: Ctx = Depends(project_ctx)):
    c.need("admin")
    try:
        row = svc.switch(c.db, c.project, alias, body.model_id, c.uid)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return svc.alias_out(c.db, row)


@router.post(P + "/{alias}/rollback")
def rollback_alias(alias: str, c: Ctx = Depends(project_ctx)):
    c.need("admin")
    try:
        row = svc.rollback(c.db, c.project, alias, c.uid)
    except ValueError as e:
        # nothing to roll back to is a state conflict; an unknown alias is a bad request
        raise HTTPException(409 if str(e) == "no previous model to roll back to" else 400, str(e)) from e
    return svc.alias_out(c.db, row)
