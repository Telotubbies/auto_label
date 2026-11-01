"""Insights Studio dataset analytics: read-only aggregates plus on-demand scan jobs."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..deps import Ctx, audit, project_ctx
from ..models import Version
from ..services import insights

router = APIRouter(prefix="/api/ws/{ws}/projects/{project}/insights", tags=["insights"])


class SelectionIn(BaseModel):
    image_ids: list[str]


def _version(c: Ctx, version_id: str) -> Version | None:
    if not version_id:
        return None
    version = c.db.get(Version, version_id)
    if not version or version.project_id != c.project.id:
        raise HTTPException(404, "version not found")
    return version


def _required_version(c: Ctx, version_id: str) -> Version:
    version = _version(c, version_id)
    if version is None:
        raise HTTPException(400, "version is required")
    return version


def _auto(c: Ctx) -> bool:
    """Annotators can read analytics but must not queue scans just by opening the page."""
    return c.role != "annotator"


def _scan(c: Ctx, kind: str) -> dict:
    c.need("reviewer")
    job = insights.enqueue_scan(c.db, c.project, kind)
    audit(c.db, c.ws.id, c.user.id, "insights.scan", c.project.name, kind=kind)
    c.db.commit()
    return insights.job_out(job)


@router.get("/summary")
def summary(version: str = "", c: Ctx = Depends(project_ctx)):
    return insights.summary(c.db, c.project, _version(c, version))


@router.get("/distribution")
def distribution(version: str = "", c: Ctx = Depends(project_ctx)):
    return insights.distribution(c.db, c.project, _version(c, version))


@router.get("/geometry")
def geometry(version: str = "", c: Ctx = Depends(project_ctx)):
    return insights.geometry(c.db, c.project, _version(c, version))


@router.get("/image-stats")
def image_stats(c: Ctx = Depends(project_ctx)):
    return insights.image_stats(c.db, c.project, auto=_auto(c))


@router.post("/image-stats/scan")
def scan_image_stats(c: Ctx = Depends(project_ctx)):
    return _scan(c, "insights_images")


@router.get("/leakage")
def leakage(version: str = "", c: Ctx = Depends(project_ctx)):
    return insights.leakage(c.db, c.project, _version(c, version), auto=_auto(c))


@router.post("/leakage/scan")
def scan_leakage(c: Ctx = Depends(project_ctx)):
    return _scan(c, "insights_leakage")


@router.get("/embedding")
def embedding(c: Ctx = Depends(project_ctx)):
    return insights.embedding(c.db, c.project, auto=_auto(c))


@router.post("/embedding/scan")
def scan_embedding(c: Ctx = Depends(project_ctx)):
    return _scan(c, "insights_embedding")


@router.get("/version-diff")
def version_diff(base: str = Query(...), target: str = Query(...), c: Ctx = Depends(project_ctx)):
    base_version = _required_version(c, base)
    target_version = _required_version(c, target)
    try:
        return insights.version_diff(c.db, c.project, base_version, target_version)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/labeling")
def labeling(c: Ctx = Depends(project_ctx)):
    return insights.labeling(c.db, c.project)


@router.post("/selections")
def create_selection(body: SelectionIn, c: Ctx = Depends(project_ctx)):
    """Save the lasso's image ids for a follow-up browse request; any project member may create one."""
    return insights.save_selection(c.db, c.project, body.image_ids)


@router.get("/selections/{token}")
def get_selection(token: str, c: Ctx = Depends(project_ctx)):
    info = insights.selection_info(c.db, c.project, token)
    if info is None:
        raise HTTPException(404, "selection not found")
    return info
