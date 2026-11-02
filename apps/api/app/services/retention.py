"""PDPA retention: per-project automatic deletion of frames, snapshots and stream events.

"Frames" are ``Image`` rows (plus their stored JPEG and thumbnail), "snapshots" are files under the
project's snapshots directory (and StreamEvent.snapshot_path), "events" are ``StreamEvent`` rows.
Snapshots are only ever swept from directories that are attributable to the project: the project
directory and the project-keyed subfolder of the shared snapshots root (Task 10b must write footage
under ``snapshots/<project id>/``). Flat files directly under the shared root carry no attribution
and are deliberately left alone — one tenant's retention policy must never delete another's footage.
Stream models arrive with the Task 10b stream router, so they are looked up with ``getattr`` — this
module must import on a build that has no streams at all.

Cached export archives are invalidated by comparing every version's manifest ``sources`` with the frames
that still exist, not with this run's deleted ids, so an archive that could not be removed (a locked file
on Windows) is retried on the next run and reported as a failure instead of a deletion.
"""

import json
import logging
import shutil
from pathlib import Path

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..config import DATA_DIR
from ..db import SessionLocal
from ..deps import audit
from ..models import Comment, Image, ImageClass, Job, Project, Version, now

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


def _delete_stored(rel_or_path: str | Path) -> tuple[bool, int]:
    """Remove one stored file; (True, bytes) when gone or never stored, (False, 0) when it remains."""
    if not rel_or_path:
        return True, 0
    path = Path(rel_or_path)
    if not path.is_absolute():
        path = DATA_DIR / path
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError:
        return True, 0                       # nothing left on disk: the row may go
    except OSError:
        log.warning("retention could not resolve %s", path, exc_info=True)
        return False, 0
    try:
        if not resolved.is_file() or not _inside(resolved):
            return False, 0                  # unsafe path: keep the row rather than lose attribution
        size = resolved.stat().st_size
        resolved.unlink()
        return True, size
    except OSError:                          # locked/read-only: keep the row so a later run retries
        log.warning("retention could not remove %s", path, exc_info=True)
        return False, 0


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


def _remove_export_cache(target: Path) -> bool:
    """Remove one cached export directory; True only when the path is verifiably gone."""
    try:
        shutil.rmtree(target)
    except OSError:                          # locked/read-only (Windows sharing violation)
        log.warning("retention could not remove export cache %s", target, exc_info=True)
    if target.exists():
        log.warning("retention left export cache %s in place; the next run retries", target)
        return False
    return True


def _stale_versions(db: Session, project_id: str) -> list[Version]:
    """Versions whose manifest sources a frame that no longer exists in the project.

    Derived from the manifests on every run (not from this run's deleted ids) so a failed cache
    removal is retried next time even though the Image rows are already gone.
    """
    existing = set(db.scalars(select(Image.id).where(Image.project_id == project_id)))
    stale = []
    for version in db.scalars(select(Version).where(Version.project_id == project_id)):
        try:
            manifest = json.loads((DATA_DIR / "versions" / version.id / "manifest.json").read_text())
        except (OSError, ValueError):         # never generated/kept: no cache can be attributed to it
            continue
        sources = {s.get("id") for s in manifest.get("sources") or [] if isinstance(s, dict)}
        if sources and not sources <= existing:
            stale.append(version)
    return stale


def _invalidate_exports(db: Session, project_id: str) -> tuple[int, int]:
    """Delete cached export archives of versions that include frames deleted by retention.

    Returns (removed, failed). A target counts as removed only when it is verifiably gone; a locked
    archive is left for the next run and reported as a failure with its path, so the job never
    claims a cache that is still being served. Version snapshots stay until the version is deleted.
    """
    removed = failed = 0
    for version in _stale_versions(db, project_id):
        for target in (DATA_DIR / "exports" / version.id, DATA_DIR / "versions" / version.id / "exports"):
            if not target.is_dir():
                continue
            if _remove_export_cache(target):
                removed += 1
            else:
                failed += 1
    return removed, failed


def _clean_project(db: Session, project: Project, cutoff: float) -> dict:
    """Delete one project's expired frames, events and snapshot files; caller commits."""
    stats = {"images": 0, "events": 0, "snapshots": 0, "exports": 0, "bytes": 0, "failed": 0}
    for image in db.scalars(select(Image).where(Image.project_id == project.id, Image.created < cutoff)):
        path_ok, path_bytes = _delete_stored(image.path)
        thumb_ok, thumb_bytes = _delete_stored(image.thumb)
        stats["bytes"] += path_bytes + thumb_bytes
        if not (path_ok and thumb_ok):
            stats["failed"] += 1             # row survives, so the next run retries the remaining file
            continue
        # SQLite does not enforce ON DELETE CASCADE: clear the derived rows explicitly.
        db.execute(sa_delete(ImageClass).where(ImageClass.image_id == image.id))
        db.execute(sa_delete(Comment).where(Comment.image_id == image.id))
        db.delete(image)
        stats["images"] += 1

    for event in event_rows(db, project.id, cutoff):
        ok, freed = _delete_stored(getattr(event, "snapshot_path", "") or "")
        stats["bytes"] += freed
        if not ok:
            stats["failed"] += 1
            continue
        db.delete(event)
        stats["events"] += 1

    # Only project-attributable snapshot folders: the flat shared root has no owner, so it stays.
    for directory in (DATA_DIR / "projects" / project.id / "snapshots", DATA_DIR / "snapshots" / project.id):
        files, freed = _sweep(directory, cutoff)
        stats["snapshots"] += files
        stats["bytes"] += freed
    stats["exports"], export_failed = _invalidate_exports(db, project.id)
    stats["failed"] += export_failed
    return stats


def run_retention(job) -> dict:
    """Delete everything past each project's retention window. Idempotent; one audit row per project.

    ``job.params["project_id"]`` runs that project only (RuntimeError when it no longer exists),
    otherwise every live project with a positive ``retention_days``.
    """
    params = getattr(job, "params", None) or {}
    result = {"projects": 0, "images_deleted": 0, "events_deleted": 0, "snapshots_deleted": 0,
              "exports_deleted": 0, "bytes_freed": 0, "failed": 0}
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
                exports=stats["exports"],
                bytes=stats["bytes"],
                failed=stats["failed"],
            )
            db.commit()
            result["projects"] += 1
            result["images_deleted"] += stats["images"]
            result["events_deleted"] += stats["events"]
            result["snapshots_deleted"] += stats["snapshots"]
            result["exports_deleted"] += stats["exports"]
            result["bytes_freed"] += stats["bytes"]
            result["failed"] += stats["failed"]
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
