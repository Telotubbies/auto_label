"""Public developer API (`/api/v1`) — what the Python SDK/CLI call.

Every route declares its API-key scope in `x-scopes`, which `tools/gen_sdk.py` copies into the
generated client. Hosted predict lives in routers/training.py (same path, since v1 shipped it).
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select

from ..apikeys import KeyCtx, key_ctx
from ..deps import Ctx
from ..models import Image, Job, LabelClass, Project, TrainedModel, Version
from ..security import sign_path
from . import training as training_router
from . import versions as versions_router
from .images import image_out, ingest
from .projects import job_out

router = APIRouter(prefix="/api/v1", tags=["developer"])


def _ctx(k: KeyCtx, project: Project | None = None) -> Ctx:
    """Developer calls run as the workspace admin: the key's scopes already gate the action."""
    return Ctx(user=None, ws=k.ws, role="admin", db=k.db, project=project)


def _scopes(*names: str) -> dict:
    return {"openapi_extra": {"x-scopes": list(names)}}


@router.get("/whoami", operation_id="whoami", **_scopes("read"))
def whoami(k: KeyCtx = Depends(key_ctx)):
    k.need("read")
    return {"workspace": k.ws.slug, "name": k.ws.name, "plan": k.ws.plan,
            "scopes": list(k.scopes), "publishable": bool(k.key.publishable)}


@router.get("/projects", operation_id="list_projects", **_scopes("read"))
def list_projects(k: KeyCtx = Depends(key_ctx)):
    k.need("read")
    rows = k.db.scalars(select(Project).where(Project.workspace_id == k.ws.id, Project.deleted_at.is_(None))
                        .order_by(Project.updated.desc())).all()
    pids = [p.id for p in rows]
    counts = dict(k.db.execute(select(Image.project_id, func.count())
                               .where(Image.project_id.in_(pids), Image.deleted_at.is_(None))
                               .group_by(Image.project_id)).all()) if pids else {}
    classes: dict[str, list[str]] = {}
    for pid, name in k.db.execute(select(LabelClass.project_id, LabelClass.name)
                                  .where(LabelClass.project_id.in_(pids)).order_by(LabelClass.created)):
        classes.setdefault(pid, []).append(name)
    return [{"id": p.id, "slug": p.slug, "name": p.name, "type": p.type, "images": counts.get(p.id, 0),
             "classes": classes.get(p.id, [])} for p in rows]


@router.get("/projects/{project}/images", operation_id="list_images", **_scopes("read"))
def list_images(project: str, offset: int = 0, limit: int = 100, k: KeyCtx = Depends(key_ctx)):
    k.need("read")
    p = k.project(project)
    s = select(Image).where(Image.project_id == p.id, Image.deleted_at.is_(None))
    total = k.db.scalar(select(func.count()).select_from(s.subquery()))
    rows = k.db.scalars(s.order_by(Image.created, Image.id).offset(max(0, offset)).limit(min(max(limit, 1), 1000))).all()
    return {"total": total, "items": [image_out(i) for i in rows]}


@router.post("/projects/{project}/upload", operation_id="upload_images", **_scopes("upload"))
async def upload_images(project: str, files: list[UploadFile] = File(...), batch_name: str = Form("API Upload"),
                        split: str = Form("auto"), tags: str = Form(""), k: KeyCtx = Depends(key_ctx)):
    k.need("upload")
    p = k.project(project)
    payload = [(f.filename or "file", await f.read()) for f in files]
    return ingest(k.db, _ctx(k, p), payload, batch_name, split, [t.strip() for t in tags.split(",") if t.strip()],
                  source="api", to_dataset=True)


@router.get("/projects/{project}/versions", operation_id="list_versions", **_scopes("read"))
def list_versions(project: str, k: KeyCtx = Depends(key_ctx)):
    k.need("read")
    p = k.project(project)
    c = _ctx(k, p)
    rows = k.db.scalars(select(Version).where(Version.project_id == p.id).order_by(Version.number.desc())).all()
    return [versions_router.version_out(c, v) for v in rows]


class ExportIn(BaseModel):
    format: str


@router.post("/projects/{project}/versions/{vid}/export", operation_id="export_version", **_scopes("read"))
def export_version(project: str, vid: str, body: ExportIn, k: KeyCtx = Depends(key_ctx)):
    k.need("read")
    p = k.project(project)
    return versions_router.export(vid, versions_router.ExportIn(format=body.format), _ctx(k, p))


class TrainIn(BaseModel):
    version_id: str
    name: str = ""
    variant: str = "yolo26n"
    epochs: int = 30
    imgsz: int = 640
    batch: int = 8


@router.post("/projects/{project}/train", operation_id="start_training", **_scopes("train"))
def start_training(project: str, body: TrainIn, k: KeyCtx = Depends(key_ctx)):
    k.need("train")
    p = k.project(project)
    return training_router.train(training_router.TrainIn(**body.model_dump()), _ctx(k, p))


@router.get("/jobs/{job_id}", operation_id="get_job", **_scopes("read"))
def get_job(job_id: str, k: KeyCtx = Depends(key_ctx)):
    k.need("read")
    j = k.db.get(Job, job_id)
    if not j or j.workspace_id != k.ws.id:
        raise HTTPException(404, "job not found")
    out = job_out(j)
    file = (j.result or {}).get("file")
    out["url"] = sign_path(file) if j.status == "done" and file else None
    return out


@router.get("/models", operation_id="list_models", **_scopes("read"))
def list_models(k: KeyCtx = Depends(key_ctx)):
    k.need("read")
    rows = k.db.scalars(select(TrainedModel).where(TrainedModel.workspace_id == k.ws.id)
                        .order_by(TrainedModel.created.desc())).all()
    return [{**training_router.model_out(m), "metrics": training_router._lean_metrics(m.metrics)} for m in rows]


@router.get("/models/{model_id}", operation_id="get_model", **_scopes("read"))
def get_model(model_id: str, k: KeyCtx = Depends(key_ctx)):
    k.need("read")
    m = k.db.get(TrainedModel, model_id)
    if not m or m.workspace_id != k.ws.id:
        raise HTTPException(404, "model not found")
    return {**training_router.model_out(m), "metrics": training_router._lean_metrics(m.metrics)}
