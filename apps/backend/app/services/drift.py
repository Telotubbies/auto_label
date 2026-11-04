"""Production drift monitor: an RBF-kernel MMD two-sample test between the training
distribution (the model's version images when its manifest exists, else project images) and
recent production inputs (DriftSample rows).

Feature vectors come from the shared `services.embeddings` seam (CLIP when installed), otherwise
from a deterministic colour/layout descriptor so the monitor still works on a machine with no GPU
or vision encoder. The UI labels which one produced a run.
"""

import hashlib
import json
import logging
import time
from pathlib import Path

import numpy as np
from PIL import Image as PImage
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..adapters.base import Cancelled
from ..config import DATA_DIR, DRIFT_MAX_SAMPLES, DRIFT_MIN_SAMPLES, DRIFT_P
from ..db import SessionLocal
from ..deps import audit
from ..errors import safe_error
from ..models import (
    DriftRun,
    DriftSample,
    Image,
    Job,
    Project,
    TrainedModel,
    Workspace,
    now,
)
from . import embeddings, imaging

log = logging.getLogger(__name__)

WINDOW_S = 7 * 24 * 3600
MAX_REFERENCE = 300
MAX_CURRENT = 300
SEND_CAP = 20


# --- features -----------------------------------------------------------------------


def feature_source() -> str:
    """The descriptor the next run will use; shown in the drift strip before a run exists."""
    return "clip" if embeddings.available() else "colour/layout map"


SOURCE_UNKNOWN = "unknown"


def _colour_features(im: PImage.Image) -> list[float]:
    """Deterministic 54-dim descriptor: per-channel histograms, moments, grey grid, edges, shape."""
    small = im.convert("RGB").resize((32, 32), PImage.Resampling.BILINEAR)
    arr = np.asarray(small, dtype=np.float32) / 255.0
    out: list[float] = []
    for c in range(3):
        hist, _ = np.histogram(arr[..., c], bins=8, range=(0.0, 1.0))
        out.extend((hist / hist.sum()).tolist())
    for c in range(3):
        out.extend([float(arr[..., c].mean()), float(arr[..., c].std())])
    grey = (
        np.asarray(
            im.convert("L").resize((16, 16), PImage.Resampling.BILINEAR),
            dtype=np.float32,
        )
        / 255.0
    )
    out.extend(grey.reshape(4, 4, 4, 4).mean(axis=(1, 3)).ravel().tolist())
    dx, dy = np.abs(np.diff(grey, axis=1)), np.abs(np.diff(grey, axis=0))
    edges = np.concatenate([dx.ravel(), dy.ravel()])
    out.extend(
        [
            float(dx.mean()),
            float(dx.std()),
            float(dy.mean()),
            float(dy.std()),
            float((edges > 0.1).mean()),
        ]
    )
    out.extend([im.width / max(1, im.height), float(arr.mean())])
    return [round(v, 6) for v in out]


def features_with_source(im: PImage.Image, sha: str | None = None) -> tuple[list[float], str]:
    """(vector, source that produced it) — the label follows the encoder, not the module list."""
    if embeddings.available():
        try:
            return embeddings.embed_image(im, sha=sha), "clip"
        except Exception:  # noqa: BLE001 - a broken encoder must not stop the monitor
            log.debug(
                "CLIP embedding failed; falling back to colour/layout features",
                exc_info=True,
            )
    return _colour_features(im), "colour/layout map"


def features(im: PImage.Image, sha: str | None = None) -> list[float]:
    """Embedding when available, else the colour/layout descriptor. Never raises for a valid image."""
    return features_with_source(im, sha=sha)[0]


# --- MMD ----------------------------------------------------------------------------


def _as_2d(a) -> np.ndarray:
    arr = np.asarray(a, dtype=np.float64)
    if arr.ndim != 2:
        raise ValueError("samples must be 2-D arrays")
    return arr


def _sq_dists(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    d = (a * a).sum(axis=1)[:, None] + (b * b).sum(axis=1)[None, :] - 2.0 * (a @ b.T)
    return np.maximum(d, 0.0)


def _median_gamma(x: np.ndarray, y: np.ndarray) -> float:
    """Median heuristic over all pairwise squared distances of the pooled sample."""
    z = np.vstack([x, y])
    d = _sq_dists(z, z)
    vals = d[np.triu_indices(len(z), k=1)]
    med = float(np.median(vals)) if vals.size else 0.0
    return 1.0 / (2.0 * med) if med > 0 else 1.0


def _kernel(a: np.ndarray, b: np.ndarray, gamma: float) -> np.ndarray:
    return np.exp(-gamma * _sq_dists(a, b))


def _statistic(k: np.ndarray, n: int) -> float:
    """Biased MMD^2 from a pooled kernel matrix; the first n rows are group x."""
    kxx = k[:n, :n].mean()
    kyy = k[n:, n:].mean()
    kxy = k[:n, n:].mean()
    return float(max(0.0, kxx + kyy - 2.0 * kxy))


def mmd2(x, y, gamma: float | None = None) -> float:
    """RBF-kernel maximum mean discrepancy squared (biased V-statistic).

    Identical samples return exactly 0.0. `gamma` is the RBF bandwidth; None uses the
    median heuristic on the pooled sample, which is what the permutation test compares against.
    """
    xa, ya = _as_2d(x), _as_2d(y)
    if xa.shape[1] != ya.shape[1]:
        raise ValueError("the two samples must have the same number of features")
    if xa.shape == ya.shape and np.array_equal(xa, ya):
        return 0.0
    g = _median_gamma(xa, ya) if gamma is None else float(gamma)
    z = np.vstack([xa, ya])
    return _statistic(_kernel(z, z, g), len(xa))


def permutation_p(x, y, permutations: int = 200, seed: int = 0) -> float:
    """Permutation-test p-value for `mmd2`; deterministic for a given seed.

    The pooled kernel is built once so 200 permutations stay cheap even at 300+300 samples.
    """
    xa, ya = _as_2d(x), _as_2d(y)
    if xa.shape[1] != ya.shape[1]:
        raise ValueError("the two samples must have the same number of features")
    n, m = len(xa), len(ya)
    if n < 2 or m < 2 or permutations <= 0:
        return 1.0
    z = np.vstack([xa, ya])
    g = _median_gamma(xa, ya)
    k = _kernel(z, z, g)
    observed = _statistic(k, n)
    rng = np.random.default_rng(seed)
    mask = np.zeros(n + m, dtype=bool)
    mask[:n] = True
    hits = 0
    for _ in range(int(permutations)):
        rng.shuffle(mask)
        if _statistic_for_mask(k, mask) >= observed - 1e-12:
            hits += 1
    return (hits + 1) / (int(permutations) + 1)


def _statistic_for_mask(k: np.ndarray, mask: np.ndarray) -> float:
    ix, iy = np.flatnonzero(mask), np.flatnonzero(~mask)
    if not len(ix) or not len(iy):
        return 0.0
    return float(
        max(
            0.0,
            k[np.ix_(ix, ix)].mean() + k[np.ix_(iy, iy)].mean() - 2.0 * k[np.ix_(ix, iy)].mean(),
        )
    )


# --- sample retention ---------------------------------------------------------------


def _rel_path(workspace_id: str, project_id: str, sha: str) -> str:
    return f"workspaces/{workspace_id}/drift/{project_id}/{sha}.jpg"


def _unlink(rel: str) -> None:
    if not rel:
        return
    try:
        (DATA_DIR / rel).unlink(missing_ok=True)
    except OSError:
        log.debug("could not remove drift sample %s", rel, exc_info=True)


def record_sample(
    db: Session,
    workspace_id: str,
    project: Project,
    model_id: str | None,
    data: bytes,
    source: str = "api",
) -> DriftSample | None:
    """Persist one production input for the drift test; caller commits.

    Corrupt images and storage failures are logged and skipped: a full or read-only data volume
    must never turn a successful inference into an error. The same sha within seven days reuses the
    row (refreshing its timestamp), and retention is trimmed to DRIFT_MAX_SAMPLES per project.
    """
    try:
        im = imaging.open_image(data)
    except Exception:  # noqa: BLE001 - a bad input must never break inference
        log.warning(
            "drift sample rejected: unreadable image (%s bytes)",
            len(data),
            exc_info=True,
        )
        return None
    sha = hashlib.sha256(data).hexdigest()
    try:
        cutoff = now() - WINDOW_S
        row = db.scalar(
            select(DriftSample)
            .where(
                DriftSample.project_id == project.id,
                DriftSample.sha256 == sha,
                DriftSample.created >= cutoff,
            )
            .order_by(DriftSample.created.desc())
            .limit(1)
        )
        if row is not None:
            row.created = now()
            row.source = source
            row.model_id = model_id or row.model_id      # I23: the latest serving model owns it
            return row

        rel = _rel_path(workspace_id, project.id, sha)
        dest: Path = DATA_DIR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        im.save(dest, "JPEG", quality=90)
        row = DriftSample(
            workspace_id=workspace_id,
            project_id=project.id,
            model_id=model_id,
            source=source,
            sha256=sha,
            path=rel,
            features=features(im, sha=sha),
            width=im.width,
            height=im.height,
        )
        db.add(row)
        db.flush()
        _trim(db, project)
        return row
    except Exception:  # noqa: BLE001 - a full/read-only volume must only lose the sample
        log.warning("drift sample could not be stored; skipping it", exc_info=True)
        db.rollback()
        return None


def _trim(db: Session, project: Project) -> None:
    rows = db.scalars(
        select(DriftSample).where(DriftSample.project_id == project.id).order_by(DriftSample.created, DriftSample.id)
    ).all()
    excess = len(rows) - max(0, int(DRIFT_MAX_SAMPLES))
    for old in rows[: max(0, excess)]:
        _unlink(old.path)
        db.delete(old)


# --- analysis -----------------------------------------------------------------------


def production_model(db: Session, project: Project) -> TrainedModel | None:
    """The deployment `production` alias when that service exists, else the newest ready model."""
    try:
        from . import deployments
    except Exception:  # noqa: BLE001 - the alias service lands in another task
        deployments = None
    if deployments is not None:
        getter = getattr(deployments, "alias_model", None)
        if getter is not None:
            for args in ((db, project), (db, project, "production")):
                try:
                    m = getter(*args)
                except TypeError:
                    continue
                except Exception:  # noqa: BLE001 - fall back to the newest ready model
                    log.debug("deployment alias lookup failed", exc_info=True)
                    break
                if m is not None:
                    mid = getattr(m, "model_id", None) or (m if isinstance(m, str) else None)
                    m = db.get(TrainedModel, mid) if mid else m
                    if getattr(m, "status", None) == "ready":
                        return m
                break
    return db.scalar(
        select(TrainedModel)
        .where(TrainedModel.project_id == project.id, TrainedModel.status == "ready")
        .order_by(TrainedModel.created.desc())
        .limit(1)
    )


def _version_image_ids(model: TrainedModel | None) -> list[str]:
    """Source image ids recorded in the model version's manifest (empty when unavailable)."""
    if model is None or not model.version_id:
        return []
    manifest = DATA_DIR / "versions" / model.version_id / "manifest.json"
    try:
        items = json.loads(manifest.read_text()).get("items") or []
    except (OSError, ValueError):
        return []
    return list(dict.fromkeys(i["source"] for i in items if isinstance(i, dict) and i.get("source")))


def _stride_ids(ids: list[str], limit: int = MAX_REFERENCE) -> list[str]:
    """Deterministic stride so a 250k-image manifest never becomes one oversized `IN (...)`.

    Exactly `limit` ids that span the whole list (not just the first N), so the reference sample
    still covers the version; the same manifest always yields the same subset.
    """
    if limit <= 0:
        return []
    if len(ids) <= limit:
        return list(ids)
    step = len(ids) / limit
    return [ids[int(i * step)] for i in range(limit)]


def _reference_query(db: Session, project: Project, model: TrainedModel | None):
    ids = _stride_ids(_version_image_ids(model))
    q = select(Image).where(Image.deleted_at.is_(None))
    return q.where(Image.id.in_(ids)) if ids else q.where(Image.project_id == project.id)


def _reference_features(
    db: Session, project: Project, model: TrainedModel | None = None
) -> tuple[list[list[float]], str | None]:
    """(features, source) for the model version's images; source is what actually produced them."""
    rows = db.scalars(_reference_query(db, project, model).order_by(Image.created).limit(MAX_REFERENCE)).all()
    out: list[list[float]] = []
    source: str | None = None
    for img in rows:
        try:
            vector, used = features_with_source(imaging.load(img.path), sha=img.sha256)
        except Exception:  # noqa: BLE001 - a missing/corrupt file is skipped, not fatal
            log.debug("drift reference skipped %s", img.id, exc_info=True)
            continue
        if source is None:
            source = used
        if used != source:  # a mid-run backend switch would mix vector spaces: keep the run consistent
            log.debug("drift reference %s used %s, the run uses %s", img.id, used, source)
            continue
        out.append(vector)
    return out, source


def _reference_count(db: Session, project: Project, model: TrainedModel | None) -> int:
    """How many reference images the run would sample, without decoding any of them."""
    rows = _reference_query(db, project, model).limit(MAX_REFERENCE).subquery()
    return int(db.scalar(select(func.count()).select_from(rows)) or 0)


def _current_features(db: Session, project: Project, dim: int, model_id: str | None = None) -> list[list[float]]:
    cutoff = now() - WINDOW_S
    q = select(DriftSample).where(DriftSample.project_id == project.id, DriftSample.created >= cutoff)
    if model_id:
        q = q.where(DriftSample.model_id == model_id)      # I23: staging traffic must not alert production
    rows = db.scalars(q.order_by(DriftSample.created.desc()).limit(MAX_CURRENT)).all()
    return [list(r.features) for r in rows if r.features and len(r.features) == dim]


def analyse(db: Session, project: Project, should_stop=None) -> DriftRun:
    """Run the two-sample test and persist a DriftRun (insufficient/failed runs included)."""
    if should_stop and should_stop():
        raise Cancelled("drift job cancelled")
    model = production_model(db, project)
    run = DriftRun(
        workspace_id=project.workspace_id,
        project_id=project.id,
        model_id=model.id if model else None,
        version_id=model.version_id if model else None,
        status="running",
        threshold=DRIFT_P,
        feature_source=SOURCE_UNKNOWN,
    )
    db.add(run)
    db.commit()
    try:
        # Cheap gate first: without enough production inputs the test cannot run, so do not
        # spend up to MAX_REFERENCE image decodes (and an embedding pass) to find that out.
        current = sample_count(db, project, window_s=WINDOW_S, model_id=model.id if model else None)
        run.n_current = current
        if current < DRIFT_MIN_SAMPLES:
            run.n_reference = _reference_count(db, project, model)
            if should_stop and should_stop():
                raise Cancelled("drift job cancelled")
            run.status, run.p_value, run.finished = "insufficient", 1.0, now()
            db.commit()
            return run
        ref, source = _reference_features(db, project, model)
        run.feature_source = source or SOURCE_UNKNOWN  # label what was used, not what was importable
        dim = len(ref[0]) if ref else 0
        cur = _current_features(db, project, dim, model_id=model.id if model else None) if dim else []
        run.n_reference, run.n_current = len(ref), len(cur)
        if len(ref) < DRIFT_MIN_SAMPLES or len(cur) < DRIFT_MIN_SAMPLES:
            run.status, run.p_value, run.finished = "insufficient", 1.0, now()
            db.commit()
            return run
        x, y = np.asarray(ref, dtype=np.float64), np.asarray(cur, dtype=np.float64)
        run.statistic = mmd2(x, y)
        run.p_value = permutation_p(x, y)
        run.alert = run.p_value < run.threshold
        if should_stop and should_stop():
            raise Cancelled("drift job cancelled")
        run.status, run.finished = "done", now()
        if run.alert:
            audit(
                db,
                project.workspace_id,
                None,
                "drift.alert",
                project.name,
                run_id=run.id,
                p_value=run.p_value,
            )
        db.commit()
    except Cancelled:
        raise
    except Exception as e:  # noqa: BLE001 - surface the failure on the run row
        log.exception("drift analysis failed for project %s", project.id)
        db.rollback()
        run = db.get(DriftRun, run.id) or run
        run.status, run.error, run.finished = (
            "failed",
            safe_error(e, "drift"),
            now(),
        )
        db.commit()
    return run


def run_job(job: Job) -> dict:
    """Worker entrypoint: open a fresh session, analyse, and return a plain dict."""
    try:
        with SessionLocal() as db:
            project = db.get(Project, job.project_id) if job.project_id else None
            if project is None:
                raise ValueError("project not found")
            from .. import jobs
            run = analyse(db, project, should_stop=lambda: jobs.is_cancelled(job.id))
            return {
                "run_id": run.id,
                "status": run.status,
                "statistic": run.statistic,
                "p_value": run.p_value,
                "alert": bool(run.alert),
                "n_reference": run.n_reference,
                "n_current": run.n_current,
                "error": run.error,
            }
    except Exception as e:  # noqa: BLE001 - a worker job must never die silently
        log.exception("drift job %s failed", getattr(job, "id", "?"))
        return {
            "run_id": None,
            "status": "failed",
            "statistic": 0.0,
            "p_value": 1.0,
            "alert": False,
            "n_reference": 0,
            "n_current": 0,
            "error": safe_error(e, "drift"),
        }
    finally:
        embeddings.release()  # CLIP must not outlive the scan (training leases need the VRAM)


def schedule_daily(db: Session) -> int:
    """Queue one drift job per project whose latest attempt is more than a day old. Idempotent."""
    projects = db.scalars(select(Project).where(Project.deleted_at.is_(None))).all()
    enqueued = 0
    for project in projects:
        model = production_model(db, project)
        if model is None:
            continue
        busy = db.scalar(
            select(Job.id)
            .where(
                Job.project_id == project.id,
                Job.kind == "drift",
                Job.status.in_(("queued", "running")),
            )
            .limit(1)
        )
        if busy:
            continue
        # Any attempt counts — failed and insufficient runs too: a project with too little
        # traffic must not be retried every 15 minutes forever.
        last = db.scalar(
            select(DriftRun.created).where(DriftRun.project_id == project.id).order_by(DriftRun.created.desc()).limit(1)
        )
        if last is not None and now() - last < 24 * 3600:
            continue
        db.add(
            Job(
                workspace_id=project.workspace_id,
                project_id=project.id,
                kind="drift",
                params={"model_id": model.id},
            )
        )
        enqueued += 1
    db.commit()
    return enqueued


# --- read helpers -------------------------------------------------------------------


def _summary(run: DriftRun) -> dict:
    return {
        "id": run.id,
        "model_id": run.model_id,
        "version_id": run.version_id,
        "status": run.status,
        "statistic": run.statistic,
        "p_value": run.p_value,
        "threshold": run.threshold,
        "alert": bool(run.alert),
        "n_reference": run.n_reference,
        "n_current": run.n_current,
        "feature_source": run.feature_source,
        "samples_sent": run.samples_sent,
        "error": run.error,
        "created": run.created,
        "finished": run.finished,
    }


def latest(db: Session, project: Project) -> dict | None:
    run = db.scalar(
        select(DriftRun).where(DriftRun.project_id == project.id).order_by(DriftRun.created.desc()).limit(1)
    )
    return _summary(run) if run else None


def runs(db: Session, project: Project, limit: int = 10) -> list[dict]:
    rows = db.scalars(
        select(DriftRun).where(DriftRun.project_id == project.id).order_by(DriftRun.created.desc()).limit(max(1, limit))
    ).all()
    return [_summary(r) for r in rows]


def sample_count(db: Session, project: Project, window_s: float | None = None,
                 model_id: str | None = None) -> int:
    """Stored production samples; `window_s` limits it to the drift window used by `analyse`."""
    q = select(func.count(DriftSample.id)).where(DriftSample.project_id == project.id)
    if window_s:
        q = q.where(DriftSample.created >= now() - window_s)
    if model_id:
        q = q.where(DriftSample.model_id == model_id)
    return int(db.scalar(q) or 0)


# --- send to labeling ---------------------------------------------------------------


def send_to_labeling(db: Session, project: Project, run: DriftRun, user) -> int:
    """Copy up to 20 samples from the run window into a review batch; returns the ingested count."""
    start = run.created - WINDOW_S
    q = select(DriftSample).where(
        DriftSample.project_id == project.id,
        DriftSample.created <= run.created,
        DriftSample.created >= start,
    )
    if run.model_id:
        q = q.where(DriftSample.model_id == run.model_id)   # I23: only the monitored model's inputs
    rows = db.scalars(q.order_by(DriftSample.created.desc()).limit(SEND_CAP)).all()
    files: list[tuple[str, bytes]] = []
    for sample in rows:
        if not sample.path:
            continue
        try:
            files.append((f"drift-{sample.id}.jpg", (DATA_DIR / sample.path).read_bytes()))
        except OSError:
            log.debug("drift sample file missing: %s", sample.path)
    if not files:
        raise ValueError("no drift samples to send")

    from ..deps import Ctx
    from ..routers.images import ingest

    ws = db.get(Workspace, project.workspace_id)
    ctx = Ctx(user=user, ws=ws, role="admin", db=db, project=project)
    res = ingest(
        db,
        ctx,
        files,
        f"Drift samples {time.strftime('%b %d, %Y')}",
        "auto",
        ["drift"],
        source="active-learning",
        to_dataset=False,
        user_id=getattr(user, "id", None),
    )
    sent = int(res.get("uploaded") or 0)
    run.samples_sent = (run.samples_sent or 0) + sent
    audit(
        db,
        ws.id,
        getattr(user, "id", None),
        "drift.send_to_labeling",
        project.name,
        run_id=run.id,
        sent=sent,
    )
    db.commit()
    return sent
