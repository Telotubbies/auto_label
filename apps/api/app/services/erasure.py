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
from ..models import Project, Stream, TrainedModel, UsageEvent, Version, Video
from . import versioning

log = logging.getLogger("labeldesk.erasure")


def _inside(path: Path) -> bool:
    try:
        path.resolve().relative_to(DATA_DIR)
        return True
    except (ValueError, OSError):
        return False


def _remove(path: Path) -> tuple[int, bool]:
    """Remove a file or directory under DATA_DIR.

    Returns ``(bytes_freed, ok)``; ``ok`` is false when the path is unsafe or still on disk after
    the attempt. A Windows sharing violation leaves the bytes behind, so the caller must not drop
    the DB row on a false result.
    """
    if not _inside(path):
        return 0, False
    if not path.exists():
        return 0, True
    size = 0
    try:
        if path.is_dir():
            size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
            shutil.rmtree(path)
        else:
            size = path.stat().st_size
            path.unlink()
    except OSError:
        log.warning("could not erase %s", path, exc_info=True)
    if path.exists():
        return 0, False
    return size, True


def _remove_all(paths: list[Path]) -> tuple[int, bool]:
    freed, ok = 0, True
    for path in paths:
        got, path_ok = _remove(path)
        freed += got
        ok = ok and path_ok
    return freed, ok


def stream_upload_paths(db: Session, project_id: str) -> list[Path]:
    """Uploaded stream clips billed to the project but attached to no ``Stream`` row.

    The upload writes ``videos/<name>`` before the operator creates the stream, so a cancelled
    dialog or a failed create leaves a file that only the storage meter knows about. The metering
    event is the ownership record; a clip still referenced by any stream is left alone.
    """
    referenced = set(db.scalars(select(Stream.source).where(Stream.source.like("file:videos/%"))))
    names: list[str] = []
    seen: set[str] = set()
    for event in db.scalars(select(UsageEvent).where(UsageEvent.project_id == project_id,
                                                    UsageEvent.metric == "storage_bytes")):
        name = (event.meta or {}).get("stream_upload")
        if (not isinstance(name, str) or not name or name in seen
                or name != Path(name).name or name in (".", "..") or "\\" in name):
            continue                             # only flat upload names are ever erased
        seen.add(name)
        if f"file:videos/{name}" not in referenced:
            names.append(name)
    return [DATA_DIR / "videos" / name for name in names]


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
    for s in db.scalars(select(Stream).where(Stream.project_id == project.id)):
        # C2: camera threads and their per-stream folder are project bytes too.
        paths.append(DATA_DIR / "streams" / s.id)
        if (s.source or "").startswith("file:videos/"):
            shared = db.scalar(select(Stream.id).where(Stream.source == s.source,
                                                       Stream.project_id != project.id).limit(1))
            if shared is None:                  # another project may reuse the same upload
                paths.append(DATA_DIR / s.source[len("file:"):])
    # I-1: clips uploaded but never attached to a stream row are still the project's bytes.
    paths += stream_upload_paths(db, project.id)
    return paths


def delete_project_data(db: Session, project: Project) -> tuple[int, bool]:
    """Erase every stored byte of a project; returns ``(bytes_freed, ok)``."""
    return _remove_all(project_paths(db, project))


def delete_image_files(path: str | None, thumb: str | None) -> tuple[int, bool]:
    """Erase one image and its thumbnail immediately.

    Returns ``(bytes_freed, gone)``; ``gone`` is false when a locked or undeletable file is still
    on disk, so the caller must not credit the storage meter for bytes that survived.
    """
    freed, gone = 0, True
    for rel in (path, thumb):
        if not rel:
            continue
        got, ok = _remove(DATA_DIR / rel)
        freed += got
        gone = gone and ok
    return freed, gone


def delete_model_files(model: TrainedModel) -> tuple[int, bool]:
    """Erase a model's weights, run directory, dataset copy and cached engine."""
    paths = [DATA_DIR / "models" / model.id, DATA_DIR / "train_data" / model.id,
             DATA_DIR / "runs" / model.id, DATA_DIR / "engines" / f"{model.id}.engine"]
    engine = (model.runtime_refs or {}).get("engine")
    if isinstance(engine, str) and engine:
        paths.append(DATA_DIR / engine)         # a pre-built engine may live outside engines/<id>
    if model.weights:
        paths.append(DATA_DIR / model.weights)
    return _remove_all(paths)


def delete_version_data(db: Session, version: Version) -> tuple[int, bool]:
    """Erase one version's snapshot and exports; the caller deletes the row afterwards."""
    return _remove_all([versioning.version_dir(version), DATA_DIR / "exports" / version.id])
