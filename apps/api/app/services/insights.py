"""Read models, caching and jobs for the Insights Studio dataset analytics.

Summary/distribution/geometry/labeling are cheap aggregates kept in a module cache keyed by a
dataset signature (the `_analytics` pattern). Pixel stats, pHash leakage and the embedding map are
`jobs` rows produced by the worker; the GET endpoints only read the latest job payload.
"""

import json
import threading

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Audit, Image, Job, LabelClass, Member, Project, User, Version, now
from ..security import sign_path
from . import insights_dataset, versioning
from .insights_selection import resolve_selection, save_selection, selection_info  # noqa: F401 re-exported

IMGSZ = 640
CACHE_MAX = 256
MANIFEST_CACHE_MAX = 32
JOB_KINDS = ("insights_images", "insights_leakage", "insights_embedding")
_CACHE: dict[tuple, tuple] = {}
_MANIFEST_CACHE: dict[str, tuple[tuple[int, int], dict | None]] = {}
_ENQ_LOCK = threading.Lock()  # one uvicorn process: serialise the enqueue read-then-insert


# --- dataset reads ------------------------------------------------------------------------


def live_images(db: Session, project: Project) -> list[Image]:
    return db.scalars(
        select(Image)
        .where(Image.project_id == project.id, Image.deleted_at.is_(None))
        .order_by(Image.created, Image.id)
    ).all()


def classes(db: Session, project: Project) -> list[LabelClass]:
    return db.scalars(
        select(LabelClass).where(LabelClass.project_id == project.id).order_by(LabelClass.created, LabelClass.id)
    ).all()


def signature(db: Session, project: Project, version: Version | None = None) -> tuple:
    """Cheap fingerprint: any image/class/version change invalidates every cached aggregate."""
    count, updated, deleted = db.execute(
        select(func.count(Image.id), func.max(Image.updated), func.count(Image.deleted_at)).where(
            Image.project_id == project.id
        )
    ).one()
    class_count, class_created = db.execute(
        select(func.count(LabelClass.id), func.max(LabelClass.created)).where(LabelClass.project_id == project.id)
    ).one()
    base = (
        int(count or 0),
        float(updated or 0.0),
        int(deleted or 0),
        int(class_count or 0),
        float(class_created or 0.0),
    )
    scope = ""
    if version is not None:
        scope = json.dumps(
            {"id": version.id, "status": version.status, "stats": version.stats or {}},
            sort_keys=True,
            default=str,
        )
    return (*base, scope)


def _cached(db: Session, project: Project, version: Version | None, kind: str, compute) -> dict:
    key = (project.id, version.id if version else "", kind)
    sig = signature(db, project, version)
    hit = _CACHE.get(key)
    if hit and hit[0] == sig:
        return hit[1]
    payload = compute()
    _CACHE[key] = (sig, payload)
    while len(_CACHE) > CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    return payload


# --- versions ------------------------------------------------------------------------------


def _manifest(version: Version) -> dict | None:
    """Parse manifest.json at most once per (mtime_ns, size); a version dir is immutable once written."""
    path = versioning.version_dir(version) / "manifest.json"
    try:
        stat = path.stat()
    except OSError:
        _MANIFEST_CACHE.pop(version.id, None)
        return None
    stamp = (int(stat.st_mtime_ns), int(stat.st_size))
    hit = _MANIFEST_CACHE.get(version.id)
    if hit and hit[0] == stamp:
        return hit[1]
    try:
        parsed = json.loads(path.read_text())
    except (OSError, ValueError):
        parsed = None
    _MANIFEST_CACHE[version.id] = (stamp, parsed)
    while len(_MANIFEST_CACHE) > MANIFEST_CACHE_MAX:
        _MANIFEST_CACHE.pop(next(iter(_MANIFEST_CACHE)))
    return parsed


def source_splits(manifest: dict) -> dict:
    """source image id -> split; the first item per source wins (augmented copies share it)."""
    out: dict = {}
    for item in manifest.get("items") or []:
        source, split = item.get("source"), item.get("split")
        if source and split and source not in out:
            out[source] = split
    return out


def version_meta(version: Version) -> dict:
    stats = version.stats or {}
    manifest = _manifest(version) or {}
    return {
        "id": version.id,
        "number": version.number,
        "name": version.name or f"v{version.number}",
        "status": version.status,
        "version_hash": stats.get("version_hash") or manifest.get("version_hash"),
        "splits": stats.get("splits") or {},
        "classes": stats.get("classes") or {},
        "leakage_moved": stats.get("leakage_moved"),
        "created": version.created,
    }


def _scoped(db: Session, project: Project, version: Version | None) -> tuple[list[Image], dict | None]:
    rows = live_images(db, project)
    if version is None:
        return rows, None
    manifest = _manifest(version)
    if not manifest:  # version still generating or its directory is gone: keep the live dataset
        return rows, None
    split_of = source_splits(manifest)
    return [row for row in rows if row.id in split_of], split_of


# --- aggregates ----------------------------------------------------------------------------


def summary(db: Session, project: Project, version: Version | None = None) -> dict:
    def compute() -> dict:
        rows, split_of = _scoped(db, project, version)
        return insights_dataset.summary(rows, classes(db, project), split_of)

    payload = _cached(db, project, version, "summary", compute)
    return {
        **payload,
        "project": {"id": project.id, "name": project.name, "type": project.type},
        "version": version_meta(version) if version else None,
    }


def distribution(db: Session, project: Project, version: Version | None = None) -> dict:
    def compute() -> dict:
        rows, split_of = _scoped(db, project, version)
        return insights_dataset.distribution(rows, classes(db, project), split_of)

    return _cached(db, project, version, "distribution", compute)


def geometry(db: Session, project: Project, version: Version | None = None) -> dict:
    def compute() -> dict:
        rows, split_of = _scoped(db, project, version)
        return insights_dataset.geometry(rows, classes(db, project), IMGSZ, split_of)

    return _cached(db, project, version, "geometry", compute)


def _review_audits(db: Session, project: Project) -> list[Audit]:
    names = set(db.scalars(select(Image.name).where(Image.project_id == project.id)))
    if not names:
        return []
    rows = db.scalars(
        select(Audit).where(Audit.workspace_id == project.workspace_id, Audit.action == "image.review")
    ).all()
    # New audit rows carry the project id; legacy rows only have the image file name.
    return [
        row
        for row in rows
        if (row.meta or {}).get("project_id") == project.id
        or ((row.meta or {}).get("project_id") is None and row.target in names)
    ]


def labeling(db: Session, project: Project) -> dict:
    def compute() -> dict:
        rows = live_images(db, project)
        audits = _review_audits(db, project)
        users = {
            u.id: u.name
            for u in db.scalars(
                select(User).join(Member, Member.user_id == User.id).where(Member.workspace_id == project.workspace_id)
            )
        }
        return insights_dataset.labeling(rows, audits, users, now())

    return _cached(db, project, None, "labeling", compute)


# --- jobs ----------------------------------------------------------------------------------


def job_out(job: Job | None) -> dict | None:
    if job is None:
        return None
    return {
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "progress": job.progress,
        "params": job.params,
        "error": job.error,
        "created": job.created,
        "started": job.started,
        "finished": job.finished,
    }


def _jobs(db: Session, project: Project, kind: str, limit: int = 10) -> list[Job]:
    return db.scalars(
        select(Job).where(Job.project_id == project.id, Job.kind == kind).order_by(Job.created.desc()).limit(limit)
    ).all()


def _same_sig(stored, current) -> bool:
    return list(stored or []) == list(current)


def _read_or_enqueue(db: Session, project: Project, kind: str, sig: tuple, auto: bool):
    jobs = _jobs(db, project, kind)
    done_match = next(
        (j for j in jobs if j.status == "done" and _same_sig((j.result or {}).get("signature"), sig)),
        None,
    )
    done_any = next((j for j in jobs if j.status == "done"), None)
    source = done_match or done_any
    payload = (source.result or {}) if source else {}
    stale = bool(done_any and not _same_sig((done_any.result or {}).get("signature"), sig))
    # mirror health.checks: a failed/running scan for the same dataset blocks automatic retries
    blocked = any(
        j.status in ("queued", "running", "failed") and _same_sig((j.params or {}).get("signature"), sig) for j in jobs
    )
    if auto and done_match is None and not blocked:
        job = enqueue_scan(db, project, kind)
        jobs = [job, *jobs]
    return payload, job_out(jobs[0] if jobs else None), stale


def enqueue_scan(db: Session, project: Project, kind: str) -> Job:
    """Queue one scan; an explicit click while one is running returns that job instead of piling up."""
    if kind not in JOB_KINDS:
        raise ValueError(f"unknown insights scan kind: {kind}")
    with _ENQ_LOCK:
        active = db.scalar(
            select(Job)
            .where(
                Job.project_id == project.id,
                Job.kind == kind,
                Job.status.in_(("queued", "running")),
            )
            .order_by(Job.created.desc())
            .limit(1)
        )
        if active:
            return active
        job = Job(
            workspace_id=project.workspace_id,
            project_id=project.id,
            kind=kind,
            params={"imgsz": IMGSZ, "signature": list(signature(db, project))},
        )
        db.add(job)
        db.commit()
        return job


def _signed(ref: dict | None) -> dict | None:
    if not ref:
        return None
    thumb = ref.get("thumb")
    return {**ref, "thumb": sign_path(thumb) if thumb else None}


def image_stats(db: Session, project: Project, *, auto: bool = True) -> dict:
    payload, job, stale = _read_or_enqueue(db, project, "insights_images", signature(db, project), auto)
    return {
        "imgsz": IMGSZ,
        "resolution": payload.get("resolution") or [],
        "brightness": payload.get("brightness") or [],
        "blur": payload.get("blur") or [],
        "scanned": int(payload.get("scanned") or 0),
        "job": job,
        "stale": stale,
    }


def _leakage_moved(db: Session, project: Project, version: Version | None) -> int | None:
    latest = version or db.scalar(
        select(Version).where(Version.project_id == project.id).order_by(Version.number.desc()).limit(1)
    )
    if latest is None:
        return None
    moved = (latest.stats or {}).get("leakage_moved")
    return int(moved) if moved is not None else None


def leakage(db: Session, project: Project, version: Version | None = None, *, auto: bool = True) -> dict:
    payload, job, stale = _read_or_enqueue(db, project, "insights_leakage", signature(db, project), auto)
    return {
        "pairs": [
            {
                "a": _signed(p.get("a")),
                "b": _signed(p.get("b")),
                "distance": int(p.get("distance") or 0),
            }
            for p in payload.get("pairs") or []
        ],
        "split_pairs": payload.get("split_pairs") or [],
        "total_pairs": int(payload.get("total_pairs") or 0),
        "leakage_moved": _leakage_moved(db, project, version),
        "job": job,
        "stale": stale,
    }


def embedding(db: Session, project: Project, *, auto: bool = True) -> dict:
    payload, job, stale = _read_or_enqueue(db, project, "insights_embedding", signature(db, project), auto)
    points = [_signed(p) for p in payload.get("points") or []]
    return {
        "points": points,
        "projection": payload.get("projection") or "pca",
        "features": payload.get("features") or "cv",
        "total": int(payload.get("total") or 0),
        "used": int(payload.get("used") if payload.get("used") is not None else len(points)),
        "sampled": bool(payload.get("sampled")),
        "job": job,
        "stale": stale,
    }


# --- version diff --------------------------------------------------------------------------


def version_diff(db: Session, project: Project, base: Version, target: Version) -> dict:
    base_manifest, target_manifest = _manifest(base), _manifest(target)
    if base_manifest is None or target_manifest is None:
        raise ValueError("version has no manifest yet")
    base_splits = source_splits(base_manifest)
    target_splits = source_splits(target_manifest)
    images = {i.id: i for i in db.scalars(select(Image).where(Image.project_id == project.id))}

    def entry(image_id: str, split: str) -> dict:
        image = images.get(image_id)
        return {
            "image_id": image_id,
            "name": image.name if image else image_id,
            "split": split,
            "thumb": sign_path(image.thumb) if image and image.thumb else None,
        }

    added = [entry(i, target_splits[i]) for i in sorted(set(target_splits) - set(base_splits))]
    removed = [entry(i, base_splits[i]) for i in sorted(set(base_splits) - set(target_splits))]
    moved = [
        {
            "image_id": image_id,
            "name": images[image_id].name if image_id in images else image_id,
            "from": base_splits[image_id],
            "to": target_splits[image_id],
        }
        for image_id in sorted(set(base_splits) & set(target_splits))
        if base_splits[image_id] != target_splits[image_id]
    ]
    base_classes = (base.stats or {}).get("classes") or {}
    target_classes = (target.stats or {}).get("classes") or {}
    deltas = []
    for name in sorted(set(base_classes) | set(target_classes)):
        before, after = int(base_classes.get(name, 0)), int(target_classes.get(name, 0))
        deltas.append({"class": name, "base": before, "target": after, "delta": after - before})
    return {
        "base": version_meta(base),
        "target": version_meta(target),
        "added": added,
        "removed": removed,
        "class_delta": deltas,
        "split_moves": moved,
        "summary": {"added": len(added), "removed": len(removed), "moved": len(moved)},
    }
