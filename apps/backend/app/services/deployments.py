"""Inference aliases per project (`production`, `staging`) with rollback history.

Only a ready model of the same project can be promoted. Every switch and rollback appends a
DeploymentEvent and commits once, so an alias never half-updates: on any failure the session is
rolled back and nothing changes.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import DRIFT_MIN_SAMPLES
from ..deps import audit
from ..models import DEPLOY_ALIASES, DeploymentAlias, DeploymentEvent, DriftRun, Project, TrainedModel, now

ALIASES = DEPLOY_ALIASES


def validate_alias(alias: str) -> str:
    """Return the alias when it is one of ours; raise ValueError otherwise."""
    if alias not in ALIASES:
        raise ValueError("unknown deployment alias")
    return alias


def _deployable(db: Session, project: Project, model_id: str) -> TrainedModel:
    """The model this project may deploy. Foreign/invisible models read as unknown, never as 403."""
    m = db.get(TrainedModel, model_id)
    if not m or m.workspace_id != project.workspace_id or m.project_id != project.id:
        raise ValueError("unknown model")
    if m.status != "ready":
        raise ValueError("model is not ready")
    return m


def _row(db: Session, project: Project, alias: str) -> DeploymentAlias | None:
    return db.scalar(
        select(DeploymentAlias).where(DeploymentAlias.project_id == project.id, DeploymentAlias.alias == alias)
    )


def switch(db: Session, project: Project, alias: str, model_id: str, user_id: str | None) -> DeploymentAlias:
    """Point `alias` at `model_id`; the old model becomes the rollback target."""
    validate_alias(alias)
    model = _deployable(db, project, model_id)
    row = _row(db, project, alias)
    old = row.model_id if row else None
    try:
        if row is None:
            row = DeploymentAlias(project_id=project.id, alias=alias)
            db.add(row)
        if old and old != model.id:
            row.previous_model_id = old
        row.model_id = model.id
        row.updated_by = user_id
        row.updated = now()
        db.add(
            DeploymentEvent(
                project_id=project.id,
                alias=alias,
                model_id=model.id,
                from_model_id=old,
                action="deploy",
                user_id=user_id,
            )
        )
        audit(
            db,
            project.workspace_id,
            user_id,
            "deployment.deploy",
            f"{alias} -> {model.name}",
            model_id=model.id,
            from_model_id=old,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return row


def rollback(db: Session, project: Project, alias: str, user_id: str | None) -> DeploymentAlias:
    """Swap the alias back to its previous model (the current one becomes the new rollback target)."""
    validate_alias(alias)
    row = _row(db, project, alias)
    previous = db.get(TrainedModel, row.previous_model_id) if row and row.previous_model_id else None
    if (
        row is None
        or not row.model_id
        or not previous
        or previous.status != "ready"
        or previous.project_id != project.id
        or previous.workspace_id != project.workspace_id
    ):
        raise ValueError("no previous model to roll back to")
    current = row.model_id
    try:
        row.model_id, row.previous_model_id = row.previous_model_id, row.model_id
        row.updated_by = user_id
        row.updated = now()
        db.add(
            DeploymentEvent(
                project_id=project.id,
                alias=alias,
                model_id=row.model_id,
                from_model_id=current,
                action="rollback",
                user_id=user_id,
            )
        )
        audit(
            db,
            project.workspace_id,
            user_id,
            "deployment.rollback",
            f"{alias} -> {previous.name}",
            model_id=row.model_id,
            from_model_id=current,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return row


def alias_model(db: Session, project: Project, alias: str) -> TrainedModel | None:
    """The ready model the alias currently serves; None when unset, unknown or no longer ready."""
    if alias not in ALIASES:
        return None
    row = _row(db, project, alias)
    m = db.get(TrainedModel, row.model_id) if row and row.model_id else None
    if not m or m.status != "ready" or m.project_id != project.id or m.workspace_id != project.workspace_id:
        return None
    return m


def _score(m: TrainedModel) -> float | None:
    """Best headline metric available on the model, for the deploy picker."""
    ev = (m.metrics or {}).get("eval") or {}
    for path in (("coco", "AP"), ("accuracy",), ("top1",)):
        value: Any = ev
        for key in path:
            value = value.get(key) if isinstance(value, dict) else None
        if isinstance(value, (int, float)):
            return float(value)
    return None


def model_out(m: TrainedModel) -> dict:
    """A ready model as the deployments page lists it."""
    return {"id": m.id, "name": m.name, "arch": m.arch, "score": _score(m), "metrics": m.metrics or {}}


def alias_out(db: Session, row: DeploymentAlias) -> dict:
    model = db.get(TrainedModel, row.model_id) if row.model_id else None
    previous = db.get(TrainedModel, row.previous_model_id) if row.previous_model_id else None
    return {
        "id": row.id,
        "alias": row.alias,
        "model_id": row.model_id,
        "model_name": model.name if model else None,
        "model_arch": model.arch if model else None,
        "model_status": model.status if model else None,
        "previous_model_id": row.previous_model_id,
        "previous_model_name": previous.name if previous else None,
        "updated": row.updated,
        "updated_by": row.updated_by,
    }


def _event_out(db: Session, event: DeploymentEvent) -> dict:
    model = db.get(TrainedModel, event.model_id) if event.model_id else None
    previous = db.get(TrainedModel, event.from_model_id) if event.from_model_id else None
    return {
        "id": event.id,
        "alias": event.alias,
        "action": event.action,
        "model_id": event.model_id,
        "model_name": model.name if model else None,
        "from_model_id": event.from_model_id,
        "from_model_name": previous.name if previous else None,
        "user_id": event.user_id,
        "created": event.created,
    }


def _aliases(db: Session, project: Project) -> list[dict]:
    rows = {
        r.alias: r for r in db.scalars(select(DeploymentAlias).where(DeploymentAlias.project_id == project.id)).all()
    }
    return [alias_out(db, rows[a]) for a in ALIASES if a in rows]


def _ready_models(db: Session, project: Project) -> list[TrainedModel]:
    return list(
        db.scalars(
            select(TrainedModel)
            .where(TrainedModel.project_id == project.id, TrainedModel.status == "ready")
            .order_by(TrainedModel.created.desc())
        ).all()
    )


def state(db: Session, project: Project, lean: bool = False) -> dict:
    """Everything the project deployments page renders: aliases, recent history and deployable models.

    ``lean`` strips the eval report from the ready models for readers without project.models (I1).
    """
    events = db.scalars(
        select(DeploymentEvent)
        .where(DeploymentEvent.project_id == project.id)
        .order_by(DeploymentEvent.created.desc())
        .limit(20)
    ).all()
    out = [model_out(m) for m in _ready_models(db, project)]
    if lean:
        out = [{**m, "metrics": {}} for m in out]
    return {
        "aliases": _aliases(db, project),
        "events": [_event_out(db, e) for e in events],
        "models": out,
    }


def _drift_out(run: DriftRun) -> dict:
    return {
        "run_id": run.id,
        "status": run.status,
        "alert": bool(run.alert),
        "statistic": run.statistic,
        "p_value": run.p_value,
        "n_reference": run.n_reference,
        "n_current": run.n_current,
        "feature_source": run.feature_source,
        "error": run.error,
        "min_samples": DRIFT_MIN_SAMPLES,
        "created": run.created,
    }


def workspace_state(db: Session, workspace_id: str) -> dict:
    """Alias overview for every live project, plus its latest drift run."""
    projects = db.scalars(
        select(Project)
        .where(Project.workspace_id == workspace_id, Project.deleted_at.is_(None))
        .order_by(Project.created)
    ).all()
    out = []
    for p in projects:
        drift = db.scalars(
            select(DriftRun).where(DriftRun.project_id == p.id).order_by(DriftRun.created.desc()).limit(1)
        ).first()
        out.append(
            {
                "id": p.id,
                "slug": p.slug,
                "name": p.name,
                "aliases": _aliases(db, p),
                "ready_models": [{"id": m.id, "name": m.name, "arch": m.arch} for m in _ready_models(db, p)],
                "drift": _drift_out(drift) if drift else None,
            }
        )
    return {"projects": out}
