"""Dashboard builder API: saved widget specs plus a read-only workspace share link."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import Ctx, audit, project_ctx
from ..services import insights_dashboards

router = APIRouter(
    prefix="/api/ws/{ws}/projects/{project}/dashboards", tags=["insights"]
)


class DashboardIn(BaseModel):
    name: str
    widgets: list[dict] = Field(default_factory=list)


class DashboardPatch(BaseModel):
    name: str | None = None
    widgets: list[dict] | None = None


def _bad(exc: ValueError) -> HTTPException:
    return HTTPException(400, str(exc))


@router.get("")
def list_dashboards(c: Ctx = Depends(project_ctx)):
    return insights_dashboards.list_dashboards(c.db, c.project)


@router.post("")
def create_dashboard(body: DashboardIn, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    try:
        dash = insights_dashboards.create(
            c.db, c.project, c.uid, body.name, body.widgets
        )
    except ValueError as exc:
        raise _bad(exc) from exc
    audit(
        c.db, c.ws.id, c.uid, "dashboard.create", c.project.name, dashboard=dash["id"]
    )
    c.db.commit()
    return dash


@router.get("/shared/{token}")
def shared_dashboard(token: str, c: Ctx = Depends(project_ctx)):
    """Read-only view for a shared link; every project member may open it, nobody may edit it."""
    try:
        return insights_dashboards.shared(c.db, c.project, token)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/{dashboard_id}")
def get_dashboard(dashboard_id: str, c: Ctx = Depends(project_ctx)):
    try:
        return insights_dashboards.get(c.db, c.project, dashboard_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.patch("/{dashboard_id}")
def update_dashboard(
    dashboard_id: str, body: DashboardPatch, c: Ctx = Depends(project_ctx)
):
    c.need("reviewer")
    try:
        dash = insights_dashboards.update(
            c.db, c.project, dashboard_id, body.name, body.widgets
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise _bad(exc) from exc
    audit(
        c.db, c.ws.id, c.uid, "dashboard.update", c.project.name, dashboard=dash["id"]
    )
    c.db.commit()
    return dash


@router.delete("/{dashboard_id}")
def delete_dashboard(dashboard_id: str, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    try:
        insights_dashboards.delete(c.db, c.project, dashboard_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    audit(
        c.db, c.ws.id, c.uid, "dashboard.delete", c.project.name, dashboard=dashboard_id
    )
    c.db.commit()
    return {"ok": True}


@router.post("/{dashboard_id}/share")
def share_dashboard(dashboard_id: str, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    base = f"/api/ws/{c.ws.slug}/projects/{c.project.slug}/dashboards/shared/"
    try:
        link = insights_dashboards.share(c.db, c.project, dashboard_id, base)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    audit(
        c.db, c.ws.id, c.uid, "dashboard.share", c.project.name, dashboard=dashboard_id
    )
    c.db.commit()
    return link
