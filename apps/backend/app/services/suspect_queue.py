"""Cached suspect-label queue and reviewer feedback statistics.

Scoring runs in the `health` job (``health_scan``) and is cached on the job row. The queue request
only reads that row plus the feedback table; it never runs inference. Feedback is an upsert per
(project, annotation), so changing a verdict or a rescan reclassifying the issue does not duplicate
statistics, and it survives later scans.
"""

from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Job, Project, SuspectFeedback, now
from . import health_scan

VERDICTS = ("confirmed", "dismissed")
QUEUE_LIMIT = 50


def _cached_run(db: Session, project: Project) -> tuple[list[dict], Job | None]:
    """Suspect items from the newest completed scan for the current model."""
    model = health_scan.latest_model(db, project)
    model_id = model.id if model else None
    jobs = db.scalars(
        select(Job).where(Job.project_id == project.id, Job.kind == "health").order_by(Job.created.desc()).limit(5)
    ).all()
    for job in jobs:
        result = job.result or {}
        if job.status == "done" and result.get("model_id") == model_id:
            return result.get("suspect_labels") or [], job
    return [], None


def stats(db: Session, project: Project) -> dict:
    """Confirmed/dismissed counts and queue precision, overall and per issue kind."""
    rows = db.execute(
        select(SuspectFeedback.kind, SuspectFeedback.verdict, func.count(SuspectFeedback.id))
        .where(SuspectFeedback.project_id == project.id, SuspectFeedback.workspace_id == project.workspace_id)
        .group_by(SuspectFeedback.kind, SuspectFeedback.verdict)
        .order_by(SuspectFeedback.kind)
    ).all()
    counts: Counter = Counter()
    by_kind: dict[str, dict] = {}
    for kind, verdict, n in rows:
        counts[verdict] += n
        by_kind.setdefault(kind, {"confirmed": 0, "dismissed": 0})
        if verdict in VERDICTS:
            by_kind[kind][verdict] = n
    reviewed = counts["confirmed"] + counts["dismissed"]
    return {
        "reviewed": reviewed,
        "confirmed": counts["confirmed"],
        "dismissed": counts["dismissed"],
        "precision": round(counts["confirmed"] / reviewed, 3) if reviewed else None,
        "by_kind": by_kind,
    }


def _verdicts(db: Session, project: Project) -> dict[str, str]:
    rows = db.execute(
        select(SuspectFeedback.annotation_id, SuspectFeedback.verdict).where(
            SuspectFeedback.project_id == project.id, SuspectFeedback.workspace_id == project.workspace_id
        )
    ).all()
    return {annotation_id: verdict for annotation_id, verdict in rows}


def queue(db: Session, project: Project, limit: int = QUEUE_LIMIT) -> dict:
    """Score-sorted review queue with each item's saved verdict, plus dataset staleness."""
    items, job = _cached_run(db, project)
    verdicts = _verdicts(db, project)
    out = [{**item, "feedback": verdicts.get(item.get("annotation_id"))} for item in items]
    out.sort(key=lambda x: (-float(x.get("score") or 0), str(x.get("annotation_id"))))
    model = health_scan.latest_model(db, project)
    stale = bool(job and (job.result or {}).get("signature") != health_scan.signature(db, project))
    return {
        "items": out[: max(0, limit)],
        "total": len(out),
        "open": sum(1 for item in out if not item["feedback"]),
        "stats": stats(db, project),
        "job_id": job.id if job else None,
        "stale": stale,
        "model": {"id": model.id, "name": model.name} if model else None,
    }


def record_feedback(
    db: Session, project: Project, annotation_id: str, verdict: str, user_id: str | None
) -> dict | None:
    """Upsert one reviewer verdict; ``None`` when the id is not in the project's current queue."""
    if verdict not in VERDICTS:
        raise ValueError("verdict must be confirmed or dismissed")
    items, _ = _cached_run(db, project)
    item = next((x for x in items if x.get("annotation_id") == annotation_id), None)
    if item is None:
        return None
    row = db.scalar(
        select(SuspectFeedback).where(
            SuspectFeedback.project_id == project.id, SuspectFeedback.annotation_id == annotation_id
        )
    )
    if row is None:
        row = SuspectFeedback(
            workspace_id=project.workspace_id, project_id=project.id, annotation_id=annotation_id
        )
        db.add(row)
    row.kind = item.get("kind")  # a rescan may reclassify the issue; stats follow the latest kind
    row.verdict = verdict
    row.user_id = user_id
    row.updated = now()
    db.commit()
    return stats(db, project)
