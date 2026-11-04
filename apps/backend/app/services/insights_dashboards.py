"""Saved dashboards: validation, CRUD and workspace share links.

A dashboard stores widget specs only; the data always comes from the read-only aggregation
endpoint, so a saved dashboard can never go stale in a way the source cannot explain.
"""

from __future__ import annotations

import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Dashboard, Project, now
from . import insights_query

CHART_TYPES = ("bar", "line", "scatter", "heatmap", "pie", "donut", "table", "kpi")
WIDTHS = (3, 4, 6, 12)
MAX_WIDGETS = 24
WIDGET_KEYS = {
    "id",
    "title",
    "source",
    "measure",
    "dimension",
    "dimension2",
    "chart",
    "filters",
    "w",
}


def _name(value) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("dashboard name is required")
    if len(value.strip()) > 120:
        raise ValueError("dashboard name is limited to 120 characters")
    return value.strip()


def _widgets(value) -> list[dict]:
    if not isinstance(value, list):
        raise ValueError("widgets must be a list")
    if len(value) > MAX_WIDGETS:
        raise ValueError(f"a dashboard holds at most {MAX_WIDGETS} widgets")
    out: list[dict] = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise ValueError(f"widget {index + 1} must be an object")
        extra = set(raw) - WIDGET_KEYS
        if extra:
            raise ValueError(f"widget {index + 1} has unknown fields: {sorted(extra)}")
        wid = raw.get("id")
        if not isinstance(wid, str) or not wid.strip() or len(wid) > 16:
            raise ValueError(f"widget {index + 1} needs an id (1-16 characters)")
        if wid in seen:
            raise ValueError(f"duplicate widget id {wid!r}")
        seen.add(wid)
        title = raw.get("title")
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 120:
            raise ValueError(f"widget {index + 1} needs a title (1-120 characters)")
        chart = raw.get("chart")
        if chart not in CHART_TYPES:
            raise ValueError(f"chart must be one of {list(CHART_TYPES)}")
        spec = insights_query.validate(raw)
        if chart == "heatmap" and not spec["dimension2"]:
            raise ValueError(f"widget {index + 1}: a heatmap needs a second dimension")
        width = raw.get("w", 6)
        if width not in WIDTHS:
            raise ValueError(f"widget width must be one of {list(WIDTHS)}")
        out.append(
            {
                "id": wid,
                "title": title.strip(),
                "chart": chart,
                "w": width,
                **{
                    k: spec[k]
                    for k in ("source", "measure", "dimension", "dimension2", "filters")
                },
            }
        )
    return out


def out(dash: Dashboard) -> dict:
    return {
        "id": dash.id,
        "name": dash.name,
        "widgets": dash.widgets or [],
        "share_token": dash.share_token or "",
        "created_by": dash.created_by,
        "created": dash.created,
        "updated": dash.updated,
    }


def _get(db: Session, project: Project, dashboard_id: str) -> Dashboard:
    dash = db.get(Dashboard, dashboard_id)
    if not dash or dash.project_id != project.id:
        raise LookupError("dashboard not found")
    return dash


def list_dashboards(db: Session, project: Project) -> list[dict]:
    rows = db.scalars(
        select(Dashboard)
        .where(Dashboard.project_id == project.id)
        .order_by(Dashboard.updated.desc())
    ).all()
    return [out(d) for d in rows]


def get(db: Session, project: Project, dashboard_id: str) -> dict:
    return out(_get(db, project, dashboard_id))


def create(db: Session, project: Project, user_id: str | None, name, widgets) -> dict:
    dash = Dashboard(
        workspace_id=project.workspace_id,
        project_id=project.id,
        name=_name(name),
        widgets=_widgets(widgets),
        created_by=user_id,
    )
    db.add(dash)
    db.commit()
    db.refresh(dash)
    return out(dash)


def update(
    db: Session, project: Project, dashboard_id: str, name=None, widgets=None
) -> dict:
    dash = _get(db, project, dashboard_id)
    if name is not None:
        dash.name = _name(name)
    if widgets is not None:
        dash.widgets = _widgets(widgets)
    dash.updated = now()
    db.commit()
    db.refresh(dash)
    return out(dash)


def delete(db: Session, project: Project, dashboard_id: str) -> None:
    dash = _get(db, project, dashboard_id)
    db.delete(dash)
    db.commit()


def share(db: Session, project: Project, dashboard_id: str, base_path: str) -> dict:
    """One stable token per dashboard; re-sharing returns the same link."""
    dash = _get(db, project, dashboard_id)
    if not dash.share_token:
        dash.share_token = secrets.token_urlsafe(18)
        dash.updated = now()
        db.commit()
    return {"token": dash.share_token, "path": f"{base_path}{dash.share_token}"}


QUERY_KEYS = ("source", "measure", "dimension", "dimension2")


def widget_query(dash: dict, spec) -> dict:
    """Validate a widget request against the dashboard a share token names.

    The token is the capability: it may read the aggregates of the widgets this dashboard holds,
    never an arbitrary query. ``tz_offset`` is viewer-local and is not persisted with the widget,
    so it is ignored when matching.
    """
    if not isinstance(spec, dict):
        raise ValueError("widget must be an object")
    query = insights_query.validate(spec)
    wanted = {k: query[k] for k in QUERY_KEYS}
    wanted_filters = {k: v for k, v in query["filters"].items() if k != "tz_offset"}
    for widget in dash.get("widgets") or []:
        if not isinstance(widget, dict):
            continue
        if any(widget.get(k) != wanted[k] for k in QUERY_KEYS):
            continue
        if {k: v for k, v in (widget.get("filters") or {}).items() if k != "tz_offset"} == wanted_filters:
            return query
    raise ValueError("widget is not part of this dashboard")


def shared(db: Session, project: Project, token: str) -> dict:
    if not token or len(token) > 64:
        raise LookupError("dashboard not found")
    dash = db.scalar(
        select(Dashboard).where(
            Dashboard.share_token == token, Dashboard.project_id == project.id
        )
    )
    if not dash:
        raise LookupError("dashboard not found")
    return out(dash)
