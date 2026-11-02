"""Read-only Insights Studio endpoints (Task 20b: training curves, evaluation analytics, model compare)."""

from fastapi import APIRouter, Depends, HTTPException, Query

from ..deps import Ctx, project_ctx
from ..services import insights

router = APIRouter(tags=["insights"])
P = "/api/ws/{ws}/projects/{project}/insights"


def _ids(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _models_only(c: Ctx = Depends(project_ctx)) -> Ctx:
    """Every payload here signs held-out eval images or carries the eval report (I15/I1).

    ``project.models`` is the manager/reviewer grant that ``training.get_model`` already uses;
    a labeler or viewer must not receive the signed ``versions/<vid>/test/...`` URLs.
    """
    return c.perm("project.models")


@router.get(P + "/training")
def training(runs: str = Query(""), c: Ctx = Depends(_models_only)):
    """Every run with history (newest first); `runs` fetches specific models for the overlay."""
    try:
        return insights.training_insights(c.db, c.project.id, _ids(runs) or None)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get(P + "/models/{mid}/detections")
def model_detections(mid: str, files: str = Query(""), c: Ctx = Depends(_models_only)):
    """Stored detections for specific eval images (compare gallery) without rebuilding the full payload."""
    try:
        return insights.model_detections(c.db, c.project.id, mid, _ids(files)[:24])
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get(P + "/models/{mid}")
def model_eval(mid: str, c: Ctx = Depends(_models_only)):
    """One model's evaluation plus derived calibration, per-class PR, F1 sweep and slice metrics."""
    try:
        return insights.model_insights(c.db, c.project.id, mid)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get(P + "/compare")
def compare(models: str = Query(""), c: Ctx = Depends(_models_only)):
    """Two to four models on the same version/split: PR overlay, per-class AP, Pareto, disagreements."""
    try:
        return insights.compare(c.db, c.project.id, _ids(models))
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
