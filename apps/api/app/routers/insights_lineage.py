"""Read-only Insights Studio endpoints added by Task 20c: lineage, stream analytics, widget query."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..deps import Ctx, project_ctx
from ..services import insights_lineage, insights_query, insights_stream

router = APIRouter(prefix="/api/ws/{ws}/projects/{project}/insights", tags=["insights"])


class QueryIn(BaseModel):
    source: str
    measure: str
    dimension: str = "none"
    dimension2: str | None = None
    filters: dict = Field(default_factory=dict)


@router.get("/lineage")
def lineage(c: Ctx = Depends(project_ctx)):
    """Batches → versions → training runs → models → streams, with each node's outputs."""
    return insights_lineage.build(c.db, c.project)


@router.get("/streams")
def stream_analytics(
    days: int = Query(30, ge=1, le=365), c: Ctx = Depends(project_ctx)
):
    """Event volume per rule/zone/class, dwell distribution, hourly heatmap and top cameras."""
    return insights_stream.analytics(c.db, c.project, days)


@router.post("/query")
def widget_query(body: QueryIn, c: Ctx = Depends(project_ctx)):
    """One dashboard widget's aggregate; the dashboard stores the spec, never the numbers."""
    try:
        return insights_query.run(c.db, c.project, body.model_dump())
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
