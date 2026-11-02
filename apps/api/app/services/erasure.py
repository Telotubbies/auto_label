"""PDPA erasure: every file prefix owned by a project, in one place (I3).

DB rows are the caller's responsibility; this module only removes bytes after the caller has
resolved the ids. Every path is checked to stay inside DATA_DIR.
"""
import logging
import shutil
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import DATA_DIR
from ..models import Project, TrainedModel, Version, Video
from . import versioning

log = logging.getLogger("labeldesk.erasure")


def _inside(path: Path) -> bool:
    try:
        path.resolve().relative_to(DATA_DIR)
        return True
    except (ValueError, OSError):
        return False


def _remove(path: Path) -> int:
    """Remove a file or directory under DATA_DIR; returns bytes freed (best effort)."""
    if not _inside(path):
        return 0
    try:
        if path.is_dir():
            size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            size = path.stat().st_size
            path.unlink(missing_ok=True)
        else:
            return 0
    except OSError:
        log.warning("could not erase %s", path, exc_info=True)
        return 0
    return size


def project_paths(db: Session, project: Project) -> list[Path]:
    """Every file/directory prefix that belongs to ``project``."""
    paths = [DATA_DIR / "projects" / project.id,
             DATA_DIR / "snapshots" / project.id,
             DATA_DIR / "workspaces" / project.workspace_id / "drift" / project.id]
    for v in db.scalars(select(Video).where(Video.project_id == project.id)):
        if v.path:
            paths.append(DATA_DIR / v.path)
    for m in db.scalars(select(TrainedModel).where(TrainedModel.project_id == project.id)):
        paths += [DATA_DIR / "models" / m.id, DATA_DIR / "train_data" / m.id,
                  DATA_DIR / "runs" / m.id, DATA_DIR / "engines" / f"{m.id}.engine"]
        if m.weights:
            paths.append(DATA_DIR / m.weights)
    for v in db.scalars(select(Version).where(Version.project_id == project.id)):
        paths += [versioning.version_dir(v), DATA_DIR / "exports" / v.id]
    return paths


def delete_project_data(db: Session, project: Project) -> int:
    """Erase every stored byte of a project; returns the bytes freed."""
    return sum(_remove(path) for path in project_paths(db, project))


def delete_image_files(path: str | None, thumb: str | None) -> tuple[int, bool]:
    """Erase one image and its thumbnail immediately.

    Returns ``(bytes_freed, gone)``; ``gone`` is false when a locked or undeletable file is still
    on disk, so the caller must not credit the storage meter for bytes that survived.
    """
    freed = 0
    gone = True
    for rel in (path, thumb):
        if not rel:
            continue
        freed += _remove(DATA_DIR / rel)
        if (DATA_DIR / rel).exists():
            gone = False
    return freed, gone


def delete_model_files(model: TrainedModel) -> int:
    """Erase a model's weights, run directory, dataset copy and cached engine."""
    freed = (_remove(DATA_DIR / "models" / model.id) + _remove(DATA_DIR / "train_data" / model.id)
             + _remove(DATA_DIR / "runs" / model.id))
    if model.weights:
        freed += _remove(DATA_DIR / model.weights)
    freed += _remove(DATA_DIR / "engines" / f"{model.id}.engine")
    return freed


def delete_version_data(db: Session, version: Version) -> int:
    """Erase one version's snapshot and exports; the caller deletes the row afterwards."""
    return _remove(versioning.version_dir(version)) + _remove(DATA_DIR / "exports" / version.id)
