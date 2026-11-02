"""Read models, caching and jobs for the Insights Studio dataset analytics.

Summary/distribution/geometry/labeling are cheap aggregates kept in a module cache keyed by a
dataset signature (the `_analytics` pattern). Pixel stats, pHash leakage and the embedding map are
`jobs` rows produced by the worker; the GET endpoints only read the latest job payload.
"""

import json
import threading

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Audit, Image, Job, LabelClass, LabelEvent, Member, Project, TrainedModel, User, Version, now
from ..security import sign_path
from . import insights_dataset, versioning
from . import insights_eval as agg
from .insights_common import cached, clear_cache, data_stamp, model_in_project
from .insights_common import signature as model_signature
from .insights_selection import resolve_selection, save_selection, selection_info  # noqa: F401 re-exported

IMGSZ = 640

# ---------- model / evaluation views (20b) ----------
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
    """Cheap fingerprint: any image/class/version change invalidates every cached aggregate.

    Classes are fingerprinted by (id, name, colour): a rename or recolour is a dataset change the
    analyst sees immediately, so the count/max-created pair alone is not enough.
    """
    count, updated, deleted = db.execute(
        select(func.count(Image.id), func.max(Image.updated), func.count(Image.deleted_at)).where(
            Image.project_id == project.id
        )
    ).one()
    class_rows = db.execute(
        select(LabelClass.id, LabelClass.name, LabelClass.color)
        .where(LabelClass.project_id == project.id)
        .order_by(LabelClass.id)
    ).all()
    # Labeling aggregates read LabelEvent, so a new save must invalidate them even though the image
    # row itself has not changed yet (a draft save does not touch the Image row).
    label_count, label_updated = db.execute(
        select(func.count(LabelEvent.id), func.max(LabelEvent.created)).where(
            LabelEvent.workspace_id == project.workspace_id, LabelEvent.project_id == project.id
        )
    ).one()
    base = (
        int(count or 0),
        float(updated or 0.0),
        int(deleted or 0),
        int(label_count or 0),
        float(label_updated or 0.0),
        json.dumps([(cid, name, color) for cid, name, color in class_rows], default=str),
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


def version_scope(db: Session, project: Project, version_id: str | None) -> tuple[Version | None, dict | None]:
    """(version, frozen split_of) for a version of this project; (None, None) when it is not ours.

    A version whose manifest is still being written keeps the version for the signature but has no
    frozen split map yet, so callers fall back to the images' current splits exactly like `_scoped`.
    """
    if not version_id:
        return None, None
    version = db.get(Version, version_id)
    if not version or version.project_id != project.id:
        return None, None
    manifest = _manifest(version)
    return version, (source_splits(manifest) if manifest else None)


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
        cutoff = now() - insights_dataset.WINDOW_DAYS * insights_dataset.DAY
        events = db.scalars(
            select(LabelEvent).where(
                LabelEvent.workspace_id == project.workspace_id,
                LabelEvent.project_id == project.id,
                LabelEvent.created >= cutoff,
            )
        ).all()
        return insights_dataset.labeling(rows, audits, users, events)

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


def _read_or_enqueue(
    db: Session,
    project: Project,
    kind: str,
    sig: tuple,
    auto: bool,
    version: Version | None = None,
):
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
        job = enqueue_scan(db, project, kind, version)
        jobs = [job, *jobs]
    return payload, job_out(jobs[0] if jobs else None), stale


def enqueue_scan(db: Session, project: Project, kind: str, version: Version | None = None) -> Job:
    """Queue one scan; an explicit click while one is running returns that job instead of piling up.

    `version` freezes the scope: a version-scoped scan never coalesces with a dataset-level one, and
    the version id rides along so the handler can use the manifest's splits.
    """
    if kind not in JOB_KINDS:
        raise ValueError(f"unknown insights scan kind: {kind}")
    version_id = version.id if version else ""
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
        if active and (active.params or {}).get("version", "") == version_id:
            return active
        job = Job(
            workspace_id=project.workspace_id,
            project_id=project.id,
            kind=kind,
            params={
                "imgsz": IMGSZ,
                "signature": list(signature(db, project, version)),
                "version": version_id,
            },
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
    payload, job, stale = _read_or_enqueue(
        db, project, "insights_leakage", signature(db, project, version), auto, version
    )
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


MAX_COMPARE_RUNS = 4
MAX_TRAINING_RUNS = (
    50  # catalogue: every run is selectable; the UI overlays at most six
)
MAX_SELECTED_RUNS = 8
MAX_DISAGREEMENT = 12
MAX_CONFUSION_URLS = 400  # a 20k-image split must not serialise 20k signed URLs

__all__ = [
    "clear_cache",
    "compare",
    "model_detections",
    "model_insights",
    "training_insights",
]


# ---------- one model --------------------------------------------------------
def model_insights(db: Session, project_id: str, mid: str) -> dict:
    m = model_in_project(db, project_id, mid)
    sig = f"{model_signature(m)}:{data_stamp(db, project_id)}"
    payload, hit = cached(f"eval:{project_id}:{mid}", sig, lambda: _build_model(db, m))
    split = payload.get("split") or "test"
    out = {k: v for k, v in payload.items() if k != "_files"}
    out["images"] = {
        f: sign_path(f"versions/{m.version_id}/{split}/{f}")
        for f in payload.get("_files") or []
    }
    out["cache"] = {"signature": sig, "hit": hit}
    return out


def _build_model(db: Session, m: TrainedModel) -> dict:
    head = _model_head(m, db)
    ev = (m.metrics or {}).get("eval")
    if not isinstance(ev, dict) or not ev.get("detections") and not ev.get("coco"):
        return {
            "model": head,
            "eval": None,
            "_files": [],
            "split": "test",
            "reason": "this model has no stored evaluation yet — it runs after training finishes",
        }
    detections = [
        d for d in ev.get("detections") or [] if isinstance(d, dict) and d.get("file")
    ]
    classes = agg.classes_for(ev, detections, m.classes)
    split = str(ev.get("split") or "test")
    files = _eval_files(ev, detections)
    has_detections = bool(detections)
    # Without per-image rows there is nothing to sweep or bin: return empty/null derived sections
    # instead of a zero curve that reads as a real (bad) measurement. The stored full-eval numbers
    # (coco, per_class, f1_best) still stand.
    out = {
        "split": split,
        "eval": {
            "split": split,
            "note": ev.get("note") or "",
            "iou": ev.get("iou") or "bbox",
            "coco": {k: float(v or 0.0) for k, v in (ev.get("coco") or {}).items()},
            "per_class": ev.get("per_class") or [],
            "pr_curve": ev.get("pr_curve") or [],
            "f1_best": ev.get("f1_best") or {"conf": 0.4, "f1": 0.0},
            "confusion": ev.get("confusion")
            or {"labels": [], "matrix": [], "images": []},
            "tide": ev.get("tide"),
            "latency_ms": float(ev.get("latency_ms") or 0.0),
            "split_images": int(ev.get("split_images") or len(detections)),
            "sample_images": len(detections),
            "has_detections": has_detections,
            "worst": ev.get("worst") or [],
            "detections": detections,
            "f1_curve": agg.f1_curve(detections) if has_detections else [],
            "per_class_pr": agg.per_class_pr(detections, classes)
            if has_detections
            else [],
            "calibration": agg.calibration(detections) if has_detections else None,
            "slices": agg.slices(db, m, detections, split, classes),
        },
        "model": head,
        "reason": None,
        "_files": files,
    }
    return out


def _model_head(m: TrainedModel, db: Session) -> dict:
    v = db.get(Version, m.version_id)
    return {
        "id": m.id,
        "name": m.name,
        "arch": m.arch,
        "task": m.task,
        "status": m.status,
        "version": v.number if v else None,
        "classes": list(m.classes or []),
        "created": m.created,
    }


def _eval_files(ev: dict, detections: list[dict]) -> list[str]:
    """Worst images + stored detections + a capped slice of the confusion-matrix galleries."""
    files: list[str] = []
    for row in ev.get("worst") or []:
        files += _files_in(row)
    files += [d["file"] for d in detections]
    count = 0
    for row in (ev.get("confusion") or {}).get("images") or []:
        for cell in row or []:
            for f in (cell or [])[:20]:
                if count >= MAX_CONFUSION_URLS:
                    break
                if isinstance(f, str):
                    files.append(f)
                    count += 1
    return list(dict.fromkeys(files))[: len(detections) + MAX_CONFUSION_URLS + 12]


def _files_in(obj) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        if isinstance(obj.get("file"), str):
            return [obj["file"]]
        return [f for value in obj.values() for f in _files_in(value)]
    if isinstance(obj, (list, tuple)):
        return [f for value in obj for f in _files_in(value)]
    return []


def model_detections(db: Session, project_id: str, mid: str, files: list[str]) -> dict:
    """Detections for a handful of images (the compare modal) without building the whole eval payload."""
    m = model_in_project(db, project_id, mid)
    ev = (m.metrics or {}).get("eval") or {}
    wanted = set(files)
    split = str(ev.get("split") or "test")
    dets = [
        d
        for d in ev.get("detections") or []
        if isinstance(d, dict) and d.get("file") in wanted
    ]
    return {
        "detections": dets,
        "images": {
            d["file"]: sign_path(f"versions/{m.version_id}/{split}/{d['file']}")
            for d in dets
        },
    }


# ---------- training curves --------------------------------------------------
def training_insights(
    db: Session, project_id: str, ids: list[str] | None = None
) -> dict:
    rows = db.execute(
        select(
            TrainedModel.id,
            TrainedModel.name,
            TrainedModel.arch,
            TrainedModel.task,
            TrainedModel.status,
            TrainedModel.version_id,
            TrainedModel.created,
            TrainedModel.history,
        )
        .where(TrainedModel.project_id == project_id)
        .order_by(TrainedModel.created.desc())
    ).all()
    if ids:
        found = {row.id: row for row in rows}
        missing = [i for i in ids if i not in found]
        if missing:
            raise LookupError("model not found")
        rows = [found[i] for i in dict.fromkeys(ids)][:MAX_SELECTED_RUNS]
    rows = [row for row in rows if row.history][:MAX_TRAINING_RUNS]
    versions = (
        {
            v.id: v.number
            for v in db.scalars(
                select(Version).where(Version.id.in_({row.version_id for row in rows}))
            ).all()
        }
        if rows
        else {}
    )
    runs = [
        {
            "id": row.id,
            "name": row.name,
            "arch": row.arch,
            "task": row.task,
            "status": row.status,
            "version": versions.get(row.version_id),
            "created": row.created,
            "epochs": len(row.history or []),
            "history": row.history or [],
        }
        for row in rows
    ]
    return {"runs": runs, "keys": _metric_keys([row.history or [] for row in rows])}


def _metric_keys(histories: list[list[dict]]) -> list[dict]:
    keys = {k for history in histories for row in history for k in row if k != "epoch"}
    quality = sorted(
        k
        for k in keys
        if any(t in k.lower() for t in ("map", "accuracy", "precision", "recall", "f1"))
    )
    loss = sorted(k for k in keys if "loss" in k.lower())
    other = sorted(keys - set(quality) - set(loss))
    out = []
    for group, names in (("quality", quality), ("loss", loss), ("other", other)):
        for key in names:
            out.append({"key": key, "label": _label(key), "group": group})
    return out


def _label(key: str) -> str:
    tail = key.split("/")[-1]
    return tail.replace("(B)", "").replace("(M)", "").strip() or key


# ---------- model compare ----------------------------------------------------
def compare(db: Session, project_id: str, ids: list[str]) -> dict:
    unique = list(dict.fromkeys(i for i in ids if i))
    if len(unique) < 2:
        raise ValueError("select at least two models to compare")
    if len(unique) > MAX_COMPARE_RUNS:
        raise ValueError(f"compare at most {MAX_COMPARE_RUNS} models at a time")
    models = [model_in_project(db, project_id, i) for i in unique]
    evals = [(m.metrics or {}).get("eval") for m in models]
    if any(not isinstance(ev, dict) or not ev.get("coco") for ev in evals):
        raise ValueError("every compared model needs a finished evaluation")
    if any(
        "not evaluated" in str((ev or {}).get("note") or "").lower()
        or "skipped" in str((ev or {}).get("note") or "").lower()
        for ev in evals
    ):
        raise ValueError("every compared model needs a finished evaluation")
    if any(m.task == "classify" for m in models):
        raise ValueError("classification models have no COCO curves to compare")
    if len({m.task for m in models}) > 1:
        raise ValueError("compared models must use the same task")
    if len({m.version_id for m in models}) > 1:
        raise ValueError("compared models must be trained on the same dataset version")
    splits = {str(ev.get("split")) for ev in evals}
    if len(splits) > 1:
        raise ValueError("compared models must be evaluated on the same split")

    sig = f"{'|'.join(model_signature(m) for m in models)}:{data_stamp(db, project_id)}"
    payload, hit = cached(
        f"compare:{project_id}:{','.join(unique)}",
        sig,
        lambda: _build_compare(db, models, evals),
    )
    split = payload["split"]
    out = dict(payload)
    out["disagreement"] = [
        {
            **{k: v for k, v in row.items() if k != "file"},
            "file": row["file"],
            "url": sign_path(f"versions/{models[0].version_id}/{split}/{row['file']}"),
        }
        for row in payload["disagreement"]
    ]
    out["cache"] = {"signature": sig, "hit": hit}
    return out


def _build_compare(db: Session, models: list[TrainedModel], evals: list[dict]) -> dict:
    v = db.get(Version, models[0].version_id)
    out_models = []
    for m, ev in zip(models, evals):
        out_models.append(
            {
                "id": m.id,
                "name": m.name,
                "arch": m.arch,
                "task": m.task,
                "coco": {
                    k: float(val or 0.0) for k, val in (ev.get("coco") or {}).items()
                },
                "per_class": ev.get("per_class") or [],
                "pr_curve": ev.get("pr_curve") or [],
                "latency_ms": float(ev.get("latency_ms") or 0.0),
                "tide": ev.get("tide"),
                "f1_best": ev.get("f1_best") or {"conf": 0.4, "f1": 0.0},
            }
        )
    threshold = round(
        max(float((ev.get("f1_best") or {}).get("conf") or 0.4) for ev in evals), 2
    )
    return {
        "version_id": models[0].version_id,
        "version": v.number if v else None,
        "split": str(evals[0].get("split") or "test"),
        "models": out_models,
        "pareto": _pareto(out_models),
        "threshold": threshold,
        "has_detections": all(bool(ev.get("detections")) for ev in evals),
        "disagreement": _disagreement(models, evals, threshold),
    }


def _pareto(models: list[dict]) -> list[str]:
    """Non-dominated models on (lower latency, higher AP50); zero latency is not a real win."""
    out = []
    for a in models:
        ap_a, lat_a = a["coco"].get("AP50", 0.0), a["latency_ms"]
        dominated = any(
            b["id"] != a["id"]
            and b["coco"].get("AP50", 0.0) >= ap_a
            and 0 < b["latency_ms"] <= lat_a
            and (b["coco"].get("AP50", 0.0) > ap_a or b["latency_ms"] < lat_a)
            for b in models
        )
        if not dominated:
            out.append(a["id"])
    return out


def _disagreement(
    models: list[TrainedModel], evals: list[dict], threshold: float
) -> list[dict]:
    """Images where the models' TP/FP/FN counts differ most, all scored at one shared threshold."""
    dets = [
        {(d.get("file")): d for d in (ev.get("detections") or []) if d.get("file")}
        for ev in evals
    ]
    if any(not d for d in dets):
        return []
    common = set(dets[0])
    for d in dets[1:]:
        common &= set(d)
    rows = []
    for file in common:
        counts = []
        for m, by_file in zip(models, dets):
            d = by_file[file]
            gt, pred = d.get("gt") or [], d.get("pred") or []
            pairs = agg.match(gt, pred, threshold)
            above = sum(1 for p in pred if p.get("conf", 0) >= threshold)
            counts.append(
                {
                    "id": m.id,
                    "tp": len(pairs),
                    "fp": above - len(pairs),
                    "fn": len(gt) - len(pairs),
                }
            )
        score = sum(
            max(c[field] for c in counts) - min(c[field] for c in counts)
            for field in ("tp", "fp", "fn")
        )
        if score:
            rows.append({"file": file, "score": score, "models": counts})
    rows.sort(key=lambda r: (-r["score"], r["file"]))
    return rows[:MAX_DISAGREEMENT]
