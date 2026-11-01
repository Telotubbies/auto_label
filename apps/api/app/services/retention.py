"""PDPA retention: per-project automatic deletion of frames, snapshots and stream events.

"Frames" are ``Image`` rows (plus their stored JPEG and thumbnail), "snapshots" are files under the
project's snapshots directory (and StreamEvent.snapshot_path), "events" are ``StreamEvent`` rows.
Stream models arrive with the Task 10b stream router, so they are looked up with ``getattr`` — this
module must import on a build that has no streams at all.
"""

import logging
from pathlib import Path

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..config import DATA_DIR
from ..db import SessionLocal
from ..deps import audit
from ..models import Comment, Image, ImageClass, Job, Project, now

log = logging.getLogger(__name__)
DAY = 86400.0
DUE_AFTER = 23 * 3600.0  # a completed cleanup suppresses the next one for 23 h


def _inside(path: Path) -> bool:
    """True when the resolved path stays inside DATA_DIR (symlinks pointing out are refused)."""
    try:
        path.resolve().relative_to(DATA_DIR)
    except (OSError, ValueError):
        return False
    return True


def _unlink(rel_or_path: str | Path) -> int | None:
    """Remove one file under DATA_DIR; bytes freed, or None when missing/unsafe/locked."""
    if not rel_or_path:
        return None
    path = Path(rel_or_path)
    if not path.is_absolute():
        path = DATA_DIR / path
    try:
        resolved = path.resolve(strict=True)
        if not resolved.is_file() or not _inside(resolved):
            return None
        size = resolved.stat().st_size
        resolved.unlink()
        return size
    except OSError:  # missing, locked or vanished mid-sweep: keep going
        log.warning("retention could not remove %s", path, exc_info=True)
        return None


def _older_than(path: Path, cutoff: float) -> bool:
    try:
        return path.is_file() and path.stat().st_mtime < cutoff and _inside(path)
    except OSError:
        return False


def _sweep(directory: Path, cutoff: float) -> tuple[int, int]:
    """Delete files older than the cutoff under one directory; returns (files, bytes)."""
    if not directory.is_dir():
        return 0, 0
    files = freed = 0
    for path in directory.rglob("*"):
        if _older_than(path, cutoff):
            size = _unlink(path)
            if size is not None:
                files += 1
                freed += size
    return files, freed


def event_rows(db: Session, project_id: str, cutoff: float) -> list:
    """Expired StreamEvent rows for one project, when the stream models exist (Task 10b)."""
    event = getattr(models, "StreamEvent", None)
    stream = getattr(models, "Stream", None)
    if event is None or not hasattr(event, "ts"):
        return []
    stmt = select(event).where(event.ts < cutoff)
    if hasattr(event, "project_id"):
        stmt = stmt.where(event.project_id == project_id)
    elif stream is not None and hasattr(event, "stream_id"):
        stmt = stmt.join(stream, event.stream_id == stream.id).where(stream.project_id == project_id)
    else:  # cannot attribute events to a project: leave them alone
        return []
    return list(db.scalars(stmt))


def count_events(db: Session, project_id: str, cutoff: float) -> int:
    """How many stream events would a retention run delete right now."""
    return len(event_rows(db, project_id, cutoff))


def _clean_project(db: Session, project: Project, cutoff: float) -> dict:
    """Delete one project's expired frames, events and snapshot files; caller commits."""
    stats = {"images": 0, "events": 0, "snapshots": 0, "bytes": 0}
    for image in db.scalars(select(Image).where(Image.project_id == project.id, Image.created < cutoff)):
        stats["bytes"] += (_unlink(image.path) or 0) + (_unlink(image.thumb) or 0)
        # SQLite does not enforce ON DELETE CASCADE: clear the derived rows explicitly.
        db.execute(sa_delete(ImageClass).where(ImageClass.image_id == image.id))
        db.execute(sa_delete(Comment).where(Comment.image_id == image.id))
        db.delete(image)
        stats["images"] += 1

    for event in event_rows(db, project.id, cutoff):
        stats["bytes"] += _unlink(getattr(event, "snapshot_path", "") or "") or 0
        db.delete(event)
        stats["events"] += 1

    files, freed = _sweep(DATA_DIR / "projects" / project.id / "snapshots", cutoff)
    stats["snapshots"] += files
    stats["bytes"] += freed
    files, freed = _sweep(DATA_DIR / "snapshots", cutoff)  # legacy global snapshot folder
    stats["snapshots"] += files
    stats["bytes"] += freed
    return stats


def run_retention(job) -> dict:
    """Delete everything past each project's retention window. Idempotent; one audit row per project.

    ``job.params["project_id"]`` runs that project only (RuntimeError when it no longer exists),
    otherwise every live project with a positive ``retention_days``.
    """
    params = getattr(job, "params", None) or {}
    result = {"projects": 0, "images_deleted": 0, "events_deleted": 0, "snapshots_deleted": 0, "bytes_freed": 0}
    with SessionLocal() as db:
        project_id = params.get("project_id")
        if project_id:
            project = db.get(Project, project_id)
            if not project:
                raise RuntimeError(f"unknown project {project_id}")
            projects = [project]
        else:
            projects = list(db.scalars(select(Project).where(Project.retention_days > 0, Project.deleted_at.is_(None))))
        for project in projects:
            days = project.retention_days or 0
            if days <= 0:  # "keep" — a manual run must never delete everything
                continue
            stats = _clean_project(db, project, now() - days * DAY)
            audit(
                db,
                project.workspace_id,
                None,
                "retention.run",
                project.name,
                images=stats["images"],
                events=stats["events"],
                snapshots=stats["snapshots"],
                bytes=stats["bytes"],
            )
            db.commit()
            result["projects"] += 1
            result["images_deleted"] += stats["images"]
            result["events_deleted"] += stats["events"]
            result["snapshots_deleted"] += stats["snapshots"]
            result["bytes_freed"] += stats["bytes"]
    return result


def _last_finished(db: Session) -> float | None:
    job = db.scalar(
        select(Job)
        .where(Job.kind == "retention", Job.status.in_(("done", "failed", "cancelled")))
        .order_by(Job.finished.desc().nulls_last(), Job.created.desc())
        .limit(1)
    )
    return (job.finished or job.created) if job else None


def enqueue_if_due(db: Session | None = None) -> str | None:
    """Queue one global retention run when a project is due and nothing is queued or recent."""
    own = db is None
    session = db or SessionLocal()
    try:
        due = session.scalar(
            select(Project)
            .where(Project.retention_days > 0, Project.deleted_at.is_(None))
            .order_by(Project.created)
            .limit(1)
        )
        if due is None:
            return None
        busy = session.scalar(
            select(Job.id).where(Job.kind == "retention", Job.status.in_(("queued", "running"))).limit(1)
        )
        if busy:
            return None
        last = _last_finished(session)
        if last is not None and now() - last < DUE_AFTER:
            return None
        job = Job(workspace_id=due.workspace_id, kind="retention", params={})
        session.add(job)
        session.commit()
        return job.id
    finally:
        if own:
            session.close()
