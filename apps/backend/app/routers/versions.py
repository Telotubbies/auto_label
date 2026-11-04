"""Dataset versions + exports."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from ..config import CREDIT_COST, DATA_DIR
from ..deps import Ctx, audit, charge, project_ctx
from ..models import Job, Version
from ..security import sign_path
from ..services import erasure, exporters
from .projects import job_out

router = APIRouter(prefix="/api/ws/{ws}/projects/{project}/versions", tags=["versions"])


def version_out(c: Ctx, v: Version) -> dict:
    jobs = c.db.scalars(select(Job).where(Job.project_id == v.project_id, Job.kind.in_(("version", "export")))
                        .order_by(Job.created.desc())).all()
    gen = next((j for j in jobs if j.kind == "version" and j.params.get("version_id") == v.id), None)
    # I14: a signed URL is a download grant, so only project.export roles get one; every reader keeps
    # the export metadata (job id/status/progress) the UI needs to show what exists.
    can_export = c.can("project.export")
    exports = {}
    for j in jobs:
        if j.kind == "export" and j.params.get("version_id") == v.id and j.params["format"] not in exports:
            item = job_out(j)
            if can_export:
                item["url"] = sign_path(j.result["file"]) if j.status == "done" else None
            exports[j.params["format"]] = item
    return {"id": v.id, "number": v.number, "name": v.name or f"v{v.number}", "settings": v.settings, "status": v.status,
            "stats": v.stats, "created": v.created, "job": job_out(gen) if gen else None, "exports": exports}


@router.get("")
def list_versions(c: Ctx = Depends(project_ctx)):
    rows = c.db.scalars(select(Version).where(Version.project_id == c.project.id).order_by(Version.number.desc())).all()
    return [version_out(c, v) for v in rows]


@router.get("/formats")
def formats(c: Ctx = Depends(project_ctx)):
    return [{"id": k, **v} for k, v in exporters.FORMATS.items() if c.project.type in v["tasks"]]


class VersionIn(BaseModel):
    name: str = ""
    settings: dict = {}


@router.post("")
def create_version(body: VersionIn, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    charge(c.db, c.ws, CREDIT_COST["version"])
    n = (c.db.scalar(select(func.max(Version.number)).where(Version.project_id == c.project.id)) or 0) + 1
    v = Version(project_id=c.project.id, number=n, name=body.name.strip(), settings=body.settings, created_by=c.user.id)
    c.db.add(v); c.db.flush()
    c.db.add(Job(workspace_id=c.ws.id, project_id=c.project.id, kind="version", params={"version_id": v.id},
                 created_by=c.user.id))
    audit(c.db, c.ws.id, c.user.id, "version.create", f"{c.project.name} v{n}")
    c.db.commit()
    return version_out(c, v)


def _get(c: Ctx, vid: str) -> Version:
    v = c.db.get(Version, vid)
    if not v or v.project_id != c.project.id:
        raise HTTPException(404, "version not found")
    return v


@router.get("/{vid}")
def get_version(vid: str, c: Ctx = Depends(project_ctx)):
    return version_out(c, _get(c, vid))


class RenameIn(BaseModel):
    name: str


@router.patch("/{vid}")
def rename_version(vid: str, body: RenameIn, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    v = _get(c, vid); v.name = body.name.strip(); c.db.commit()
    return version_out(c, v)


@router.delete("/{vid}")
def delete_version(vid: str, c: Ctx = Depends(project_ctx)):
    c.need("admin")
    v = _get(c, vid)
    _, ok = erasure.delete_version_data(c.db, v)     # bytes first: a failed delete never loses the row
    if not ok:
        raise HTTPException(409, "some files could not be deleted; retry")
    audit(c.db, c.ws.id, c.user.id, "version.delete", f"{c.project.name} v{v.number}")
    c.db.delete(v); c.db.commit()
    return {"ok": True}


class ExportIn(BaseModel):
    format: str


@router.post("/{vid}/export")
def export(vid: str, body: ExportIn, c: Ctx = Depends(project_ctx)):
    c.perm("project.export")
    v = _get(c, vid)
    if v.status != "ready":
        raise HTTPException(409, "version is still generating")
    if body.format not in exporters.FORMATS or c.project.type not in exporters.FORMATS[body.format]["tasks"]:
        raise HTTPException(400, "format not available for this project type")
    existing = c.db.scalar(select(Job).where(Job.kind == "export", Job.project_id == c.project.id,
                                             Job.status.in_(("queued", "running", "done"))).order_by(Job.created.desc())
                           .where(Job.params["version_id"].as_string() == vid, Job.params["format"].as_string() == body.format))
    if existing and (existing.status != "done" or (DATA_DIR / existing.result.get("file", "-")).exists()):
        return {**job_out(existing), "url": sign_path(existing.result["file"]) if existing.status == "done" else None}
    j = Job(workspace_id=c.ws.id, project_id=c.project.id, kind="export", params={"version_id": vid, "format": body.format},
            created_by=c.uid)
    c.db.add(j)
    audit(c.db, c.ws.id, c.uid, "version.export", f"{c.project.name} v{v.number}", format=body.format)
    c.db.commit()
    return {**job_out(j), "url": None}
