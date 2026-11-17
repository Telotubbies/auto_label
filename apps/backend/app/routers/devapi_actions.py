"""Key-authenticated actions for agents: start auto-label, build a version, read deployments.

Three thin routes; the validation and the work stay in routers/training.py, routers/versions.py
and services/deployments.py, so a key and the browser share one code path.
"""
from fastapi import APIRouter, Depends

from ..apikeys import KeyCtx, key_ctx
from ..services import deployments
from . import training, versions
from .devapi import _ctx, _scopes

router = APIRouter(prefix="/api/v1", tags=["developer"])


@router.post("/projects/{project}/autolabel", operation_id="run_auto_label", **_scopes("write"))
def run_auto_label(project: str, body: training.AutoLabelIn, k: KeyCtx = Depends(key_ctx)):
    k.need("write")
    return training.autolabel(body, _ctx(k, k.project(project)))


@router.post("/projects/{project}/versions", operation_id="create_version", **_scopes("write"))
def create_version(project: str, body: versions.VersionIn, k: KeyCtx = Depends(key_ctx)):
    k.need("write")
    return versions.create_version(body, _ctx(k, k.project(project)))


@router.get("/deployments", operation_id="list_deployments", **_scopes("read"))
def list_deployments(k: KeyCtx = Depends(key_ctx)):
    k.need("read")
    return deployments.workspace_state(k.db, k.ws.id)
