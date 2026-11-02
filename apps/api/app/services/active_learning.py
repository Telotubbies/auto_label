"""Automatic active-learning sampling: uncertainty + diversity selection under a daily cap.

Candidates are unlabelled images scored by the project's trained model through the normal
adapter path; picked images land in an "Active Learning" review batch. `auto_offer` is the
inference-time hook that keeps only uncertain (or randomly sampled) production inputs.
"""

import logging
import random
import secrets
import threading
import time
from typing import Any

import numpy as np
from sqlalchemy import func
from sqlalchemy import select as sa_select
from sqlalchemy.orm import Session

from ..adapters import resolve
from ..config import AL_BAND, AL_DAILY_CAP
from ..db import SessionLocal
from ..deps import Ctx, audit
from ..models import Batch, Image, Job, Project, TrainedModel, Workspace, now
from . import embeddings, imaging
from .drift import features, production_model

log = logging.getLogger(__name__)

CANDIDATE_LIMIT = 200
RUN_DEFAULT_K = 20
QUALIFY_AT = 0.5
# The cap check and the picks must be one decision: request threads offer samples while the
# worker picks a batch. The project row is touched first, which also takes the DB write lock.
_PICK_LOCK = threading.Lock()


def uncertainty(preds: list[dict] | None, band: tuple[float, float] = AL_BAND) -> float:
    """0..1 uncertainty from the top confidence: 1.0 inside `band`, decaying outside it.

    No predictions (or no usable confidence) means maximum uncertainty.
    """
    confs = [
        float(p["confidence"])
        for p in preds or []
        if isinstance(p, dict)
        and isinstance(p.get("confidence"), (int, float))
        and not isinstance(p.get("confidence"), bool)
    ]
    if not confs:
        return 1.0
    c = max(confs)
    lo, hi = band
    if lo <= c <= hi:
        return 1.0
    if c < lo:
        return max(0.0, 1.0 - (lo - c) / lo) if lo > 0 else 1.0
    return max(0.0, 1.0 - (c - hi) / (1.0 - hi)) if hi < 1 else 0.0


def _cosine(a, b) -> float:
    av, bv = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    if av.shape != bv.shape or not av.size:
        return 0.0
    na, nb = float(np.linalg.norm(av)), float(np.linalg.norm(bv))
    return float(av @ bv / (na * nb)) if na and nb else 0.0


def select(candidates: list[dict], k: int) -> list[str]:
    """Greedy uncertainty+diversity pick: uncertainty minus 0.5 * similarity to the picked set.

    Ties break by id so the same input always yields the same batch (first id wins).
    """
    if k <= 0 or not candidates:
        return []
    pool = sorted(candidates, key=lambda c: str(c["id"]))
    picked: list[dict] = []
    while pool and len(picked) < k:
        best = None
        best_score = float("-inf")
        for cand in pool:  # pool is id-sorted, so the first best wins ties
            score = float(cand.get("uncertainty") or 0.0)
            if picked:
                score -= 0.5 * max(_cosine(cand.get("features") or [], p.get("features") or []) for p in picked)
            if score > best_score:
                best, best_score = cand, score
        if best is None:
            break
        picked.append(best)
        pool.remove(best)
    return [str(c["id"]) for c in picked]


# --- daily cap ----------------------------------------------------------------------


def _settings(project: Project) -> dict:
    return (project.settings or {}).get("active_learning") or {}


def cap(project: Project) -> int:
    value = _settings(project).get("daily_cap")
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return AL_DAILY_CAP


def _midnight() -> float:
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))


def daily_used(db: Session, project: Project) -> int:
    """Picks made today.

    Measured by when the pick happened — the active-learning batch that was created today — not
    by `Image.created`: a backlog image uploaded weeks ago still consumes today's cap once moved.
    """
    rows = (
        sa_select(func.count(Image.id))
        .join(Batch, Batch.id == Image.batch_id)
        .where(
            Image.project_id == project.id,
            Image.deleted_at.is_(None),
            Batch.project_id == project.id,
            Batch.source == "active-learning",
            Batch.created >= _midnight(),
        )
    )
    return int(db.scalar(rows) or 0)


def remaining(db: Session, project: Project) -> int:
    return max(0, cap(project) - daily_used(db, project))


def summary(db: Session, project: Project) -> dict:
    used = daily_used(db, project)
    limit = cap(project)
    return {
        "used_today": used,
        "cap": limit,
        "remaining": max(0, limit - used),
        "enabled": bool(_settings(project).get("enabled", False)),
    }


# --- job ----------------------------------------------------------------------------


def _resolve_model(db: Session, project: Project, params: dict) -> TrainedModel | None:
    mid = (params or {}).get("model_id")
    if mid:
        m = db.get(TrainedModel, mid)
        if m is not None and m.project_id == project.id and m.status == "ready":
            return m
    return production_model(db, project)


def _score_image(resolved, image: Image, classes: list[str]) -> tuple[float, list[float]]:
    """One candidate's (uncertainty, features). Tests monkeypatch this seam."""
    im = imaging.load(image.path)
    pred = resolved.predict(im, conf=0.4, classes=classes)
    return uncertainty(pred.get("predictions") or []), features(im, sha=image.sha256)


def run_job(job: Job) -> dict:
    """Worker entrypoint: score unlabelled images, select a diverse batch, tag it for review."""
    try:
        return _run(job)
    finally:
        embeddings.release()  # CLIP must not outlive the scan (training leases need the VRAM)


def _run(job: Job) -> dict:
    params: dict[str, Any] = dict(job.params or {})
    with SessionLocal() as db:
        project = db.get(Project, job.project_id)
        if project is None:
            raise ValueError("project not found")
        model = _resolve_model(db, project, params)
        if model is None:
            raise ValueError("no ready model for active learning")
        requested = int(params["k"]) if params.get("k") is not None else RUN_DEFAULT_K
        if remaining(db, project) <= 0:  # fast path; the pick re-checks under the lock
            return {"selected": 0, "candidates": 0, "remaining": 0}

        rows = db.scalars(
            sa_select(Image)
            .where(
                Image.project_id == project.id,
                Image.deleted_at.is_(None),
                Image.n_annotations == 0,
            )
            .order_by(Image.created.desc())
            .limit(CANDIDATE_LIMIT)
        ).all()
        resolved = resolve(f"trained:{model.id}", db, workspace_id=job.workspace_id)
        candidates: list[dict] = []
        from .. import jobs
        for img in rows:
            jobs.check(job)
            try:
                score, feats = _score_image(resolved, img, model.classes or [])
            except Exception:  # noqa: BLE001 - one unreadable image must not stop the run
                log.debug("active-learning score skipped %s", img.id, exc_info=True)
                continue
            candidates.append({"id": img.id, "uncertainty": float(score), "features": feats})
        ids = select(candidates, requested)
        if not ids:
            return {"selected": 0, "candidates": len(candidates), "remaining": remaining(db, project)}

        with _PICK_LOCK:
            project.updated = now()
            db.flush()  # per-project mutex: concurrent offers serialise here
            jobs.check(job)
            left = remaining(db, project)
            ids = ids[:left]
            if not ids:
                db.rollback()
                return {"selected": 0, "candidates": len(candidates), "remaining": left}

            batch = Batch(
                project_id=project.id,
                name=f"Active learning {time.strftime('%b %d, %Y')}",
                source="active-learning",
                created_by=getattr(job, "created_by", None),
            )
            db.add(batch)
            db.flush()
            by_id = {img.id: img for img in rows}
            selected = 0
            for img_id in ids:
                img = by_id.get(img_id)
                if img is None:
                    continue
                img.batch_id = batch.id
                img.status = "review"
                tags = list(img.tags or [])
                if "active-learning" not in tags:
                    tags.append("active-learning")
                img.tags = tags
                img.updated = now()
                selected += 1
            audit(
                db,
                project.workspace_id,
                getattr(job, "created_by", None),
                "active_learning.run",
                project.name,
                batch_id=batch.id,
                selected=selected,
            )
            db.commit()  # the batch and its picks land as one decision
        return {
            "selected": selected,
            "candidates": len(candidates),
            "remaining": remaining(db, project),
        }


# --- inference-time offer ------------------------------------------------------------


def auto_offer(db: Session, ws: Workspace, project: Project, data: bytes, pred: dict) -> bool:
    """Ingest a production input into the active-learning pool when it is worth labelling."""
    cfg = _settings(project)
    if not cfg.get("enabled"):
        return False
    if remaining(db, project) <= 0:
        return False
    preds = pred.get("predictions") or []
    confs = [
        p.get("confidence") for p in preds if isinstance(p, dict) and isinstance(p.get("confidence"), (int, float))
    ]
    below = float(cfg.get("below", 0.5))
    qualifies = uncertainty(preds, band=(0.0, below)) >= QUALIFY_AT if confs else bool(cfg.get("include_empty", True))
    sampled = random.random() * 100 < float(cfg.get("sample_pct", 0) or 0)
    if not (qualifies or sampled):
        return False

    from ..routers.images import ingest

    ctx = Ctx(user=None, ws=ws, role="admin", db=db, project=project)
    name = f"al_{int(time.time() * 1000)}_{secrets.token_hex(3)}.jpg"
    try:
        with _PICK_LOCK:
            project.updated = now()
            db.flush()  # same per-project mutex as run_job, before the re-count
            if remaining(db, project) <= 0:
                return False
            res = ingest(
                db,
                ctx,
                [(name, data)],
                "Active Learning",
                "train",
                ["active-learning"],
                source="active-learning",
                to_dataset=False,
            )
    except Exception:  # noqa: BLE001 - an offer is best-effort and must never fail the inference
        log.info("active-learning offer skipped", exc_info=True)
        db.rollback()
        return False
    return int(res.get("uploaded") or 0) > 0
