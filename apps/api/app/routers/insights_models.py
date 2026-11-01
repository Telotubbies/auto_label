"""Read-only Insights Studio endpoints (Task 20b: training curves, evaluation analytics, model compare)."""

from fastapi import APIRouter, Depends, HTTPException, Query

from ..deps import Ctx, project_ctx
from ..services import insights

router = APIRouter(tags=["insights"])
P = "/api/ws/{ws}/projects/{project}/insights"


def _ids(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


@router.get(P + "/training")
def training(runs: str = Query(""), c: Ctx = Depends(project_ctx)):
    """Every run with history (newest first); `runs` fetches specific models for the overlay."""
    try:
        return insights.training_insights(c.db, c.project.id, _ids(runs) or None)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get(P + "/models/{mid}/detections")
def model_detections(mid: str, files: str = Query(""), c: Ctx = Depends(project_ctx)):
    """Stored detections for specific eval images (compare gallery) without rebuilding the full payload."""
    try:
        return insights.model_detections(c.db, c.project.id, mid, _ids(files)[:24])
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get(P + "/models/{mid}")
def model_eval(mid: str, c: Ctx = Depends(project_ctx)):
    """One model's evaluation plus derived calibration, per-class PR, F1 sweep and slice metrics."""
    try:
        return insights.model_insights(c.db, c.project.id, mid)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get(P + "/compare")
def compare(models: str = Query(""), c: Ctx = Depends(project_ctx)):
    """Two to four models on the same version/split: PR overlay, per-class AP, Pareto, disagreements."""
    try:
        return insights.compare(c.db, c.project.id, _ids(models))
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
