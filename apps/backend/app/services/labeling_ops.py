"""Labeling QA & workforce operations: consensus jobs, label events, honeypots, dashboard, review queue."""
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import rbac
from ..deps import Ctx, audit
from ..models import (
    ConsensusAssignment,
    ConsensusJob,
    Honeypot,
    HoneypotAttempt,
    Image,
    LabelEvent,
    User,
    now,
    set_annotations,
)
from ..security import sign_path
from . import labeler_stats
from .labeling import (
    MAX_DRAFT_ANNOTATIONS,
    MAX_IMAGE_ANNOTATIONS,
    MAX_K,
    MIN_K,
    group_agreement,
    honeypot_score,
    merge_sets,
)

MAX_JOB_IMAGES = 100
PROJECT_STATES = ("collecting", "ready", "merged")


def _is_ai(ann: dict) -> bool:
    return ann.get("source") not in (None, "human")


def _image_metrics(sets: list[list[dict]], iou_threshold: float) -> dict:
    """Agreement and tie flag for one image's submitted drafts, computed by the bounded per-image pass.

    The stored result is what every later read uses; only the image whose draft changed is recomputed.
    Rows over `MAX_IMAGE_ANNOTATIONS` can only be legacy data, so they are left unscored instead of
    blocking the single API process on a quadratic scan.
    """
    if len(sets) < 2:
        return {"agreement": None, "no_consensus": False}
    if sum(len(anns) for anns in sets) > MAX_IMAGE_ANNOTATIONS:
        return {"agreement": None, "no_consensus": False, "oversized": True}
    return {"agreement": round(group_agreement(sets, iou_threshold), 4),
            "no_consensus": not merge_sets(sets, iou_threshold)}


def check_image_cap(db: Session, job_id: str, image_id: str, user_id: str, count: int) -> None:
    """Reject a draft that would push one image's submitted annotations past the supported bound."""
    rows = db.scalars(select(ConsensusAssignment).where(ConsensusAssignment.job_id == job_id,
                                                        ConsensusAssignment.image_id == image_id)).all()
    others = sum(len(row.annotations or []) for row in rows if row.user_id != user_id and row.submitted is not None)
    if others + count > MAX_IMAGE_ANNOTATIONS:
        raise HTTPException(413, f"at most {MAX_IMAGE_ANNOTATIONS} annotations across the submitted drafts "
                                 "of one image")



def create_job(db: Session, c: Ctx, image_ids: list[str], count: int, k: int,
               iou_threshold: float) -> ConsensusJob:
    """Send up to `count` unlabeled, not-yet-open images to `k` distinct members, round-robin."""
    if not MIN_K <= k <= MAX_K:
        raise HTTPException(400, f"k must be between {MIN_K} and {MAX_K}")
    members = _annotator_ids(db, c)
    if len(members) < k:
        raise HTTPException(400, f"need at least k members who can annotate this project (have {len(members)})")
    open_images = select(ConsensusAssignment.image_id).join(
        ConsensusJob, ConsensusJob.id == ConsensusAssignment.job_id).where(
        ConsensusAssignment.project_id == c.project.id, ConsensusJob.status.in_(("collecting", "ready")))
    if image_ids:
        wanted = list(dict.fromkeys(image_ids))
        if len(wanted) > MAX_JOB_IMAGES:
            raise HTTPException(400, f"at most {MAX_JOB_IMAGES} images per job")
        found = {img.id: img for img in db.scalars(
            select(Image).where(Image.project_id == c.project.id, Image.deleted_at.is_(None),
                                Image.id.in_(wanted)))}
        if any(i not in found for i in wanted):
            raise HTTPException(400, "image is not part of this project")
        images = [found[i] for i in wanted]          # all of them: `count` only bounds the auto-pick
        if any(img.n_annotations for img in images):
            raise HTTPException(400, "consensus needs unlabeled images")
        if db.scalar(open_images.where(ConsensusAssignment.image_id.in_(wanted)).limit(1)):
            raise HTTPException(400, "image is already in an open consensus job")
    else:
        limit = max(1, min(count, MAX_JOB_IMAGES))
        images = list(db.scalars(select(Image).where(Image.project_id == c.project.id, Image.deleted_at.is_(None),
                                                    Image.n_annotations == 0,
                                                    ~Image.id.in_(open_images))
                                 .order_by(Image.created, Image.id).limit(limit)).all())
    if not images:
        raise HTTPException(400, "project has no images to label")
    job = ConsensusJob(workspace_id=c.ws.id, project_id=c.project.id, k=k, iou_threshold=iou_threshold,
                       image_ids=[img.id for img in images], created_by=c.user.id)
    db.add(job)
    db.flush()
    for idx, img in enumerate(images):
        for step in range(k):
            db.add(ConsensusAssignment(job_id=job.id, workspace_id=c.ws.id, project_id=c.project.id,
                                       image_id=img.id, user_id=members[(idx + step) % len(members)]))
    audit(db, c.ws.id, c.user.id, "labeling.consensus.create", c.project.name, images=len(images), k=k)
    db.flush()
    return job


def latest_assignment(db: Session, image_id: str, user_id: str) -> ConsensusAssignment | None:
    """The caller's assignment in the newest unmerged job for this image (draft stays visible until the merge)."""
    return db.scalar(select(ConsensusAssignment).join(ConsensusJob, ConsensusJob.id == ConsensusAssignment.job_id)
                     .where(ConsensusAssignment.image_id == image_id, ConsensusAssignment.user_id == user_id,
                            ConsensusJob.status.in_(("collecting", "ready")))
                     .order_by(ConsensusJob.created.desc(), ConsensusJob.id.desc()).limit(1))


def honeypot_for_image(db: Session, image_id: str) -> Honeypot | None:
    """The honeypot row pinned to this image, if any (image ids are globally unique)."""
    return db.scalar(select(Honeypot).where(Honeypot.image_id == image_id))


def merged_assignment_for(db: Session, image_id: str, user_id: str) -> ConsensusAssignment | None:
    """The caller's assignment in a job that already merged this image (their draft is now the result)."""
    return db.scalar(select(ConsensusAssignment).join(ConsensusJob, ConsensusJob.id == ConsensusAssignment.job_id)
                     .where(ConsensusAssignment.image_id == image_id, ConsensusAssignment.user_id == user_id,
                            ConsensusJob.status == "merged")
                     .order_by(ConsensusJob.created.desc(), ConsensusJob.id.desc()).limit(1))


def record_save(db: Session, ws_id: str, img: Image, user_id: str, before: list[dict], after: list[dict],
                assignment: ConsensusAssignment | None = None) -> LabelEvent | None:
    """One save = one LabelEvent + AI-acceptance counters; consensus drafts and honeypots update here too.

    Autosave stores the draft but never marks it submitted; only `submit_consensus` does that.
    Re-editing an already-submitted draft refreshes the job so agreement tracks the new version.
    Honeypot attempts are deliberately not logged as label events (their work stays hidden from throughput).
    """
    seen = kept = 0
    for old in before or []:
        if not _is_ai(old):
            continue
        seen += 1
        if any(new.get("id") == old.get("id") and new.get("classId") == old.get("classId")
               and (new.get("shape") or {}) == (old.get("shape") or {}) for new in after or []):
            kept += 1
    # The counters above describe one save; acceptance needs the ids themselves so repeated
    # autosaves of the same AI box cannot multiply the denominator.
    ai_ids = sorted({a.get("id") for a in [*(before or []), *(after or [])]
                     if _is_ai(a) and isinstance(a.get("id"), str)})
    honeypot = db.scalar(select(Honeypot).where(Honeypot.image_id == img.id, Honeypot.workspace_id == ws_id))
    event = None
    if honeypot is None:
        event = LabelEvent(workspace_id=ws_id, project_id=img.project_id, image_id=img.id, user_id=user_id,
                           annotations=len(after or []), ai_seen=seen, ai_kept=kept, ai_ids=ai_ids)
        db.add(event)
    if assignment is not None:
        assignment.annotations = list(after or [])
        job = db.get(ConsensusJob, assignment.job_id)
        if job is not None and assignment.submitted is not None:
            refresh_job(db, job, image_id=img.id)
    if honeypot is not None:
        score = honeypot_score(honeypot.annotations or [], after or [])
        attempt = db.scalar(select(HoneypotAttempt).where(HoneypotAttempt.honeypot_id == honeypot.id,
                                                         HoneypotAttempt.user_id == user_id))
        if attempt is None:
            db.add(HoneypotAttempt(honeypot_id=honeypot.id, project_id=honeypot.project_id, user_id=user_id,
                                   score=score))
        else:
            attempt.score, attempt.created = score, now()
    db.flush()
    return event


def refresh_job(db: Session, job: ConsensusJob, image_id: str | None = None) -> ConsensusJob:
    """Recompute one image's agreement (or all of them) and move the job to ready once everyone submitted.

    Only the image whose draft just changed is recomputed; the job mean comes from the cached
    per-image metrics, so a submit/autosave costs one bounded pass instead of one per image.
    """
    rows = db.scalars(select(ConsensusAssignment).where(ConsensusAssignment.job_id == job.id)).all()
    per_image: dict[str, list[list[dict]]] = {}
    for row in rows:
        if row.submitted is not None:
            per_image.setdefault(row.image_id, []).append(row.annotations or [])
    metrics = dict(job.image_metrics or {})
    targets = [image_id] if image_id is not None else list(per_image)
    for target in targets:
        metrics[target] = _image_metrics(per_image.get(target, []), job.iou_threshold)
    job.image_metrics = metrics
    scores = [m["agreement"] for m in metrics.values() if m.get("agreement") is not None]
    job.agreement = round(sum(scores) / len(scores), 4) if scores else None
    if job.status != "merged":
        job.status = "ready" if rows and all(row.submitted is not None for row in rows) else "collecting"
    job.updated = now()
    db.flush()
    return job


def submit_consensus(db: Session, c: Ctx, job: ConsensusJob, image_id: str,
                     annotations: list[dict] | None = None) -> dict:
    """Explicitly hand in one draft; the job only becomes ready once every assignment is submitted."""
    # local import: routers/images imports this module
    from ..routers.images import _check_ann, _check_class_ids

    assignment = db.scalar(select(ConsensusAssignment).where(
        ConsensusAssignment.job_id == job.id, ConsensusAssignment.image_id == image_id,
        ConsensusAssignment.user_id == c.user.id))
    if assignment is None:
        raise HTTPException(404, "not your assignment")
    if job.status == "merged":
        raise HTTPException(409, "this consensus job is already merged")
    raw = annotations if annotations is not None else assignment.annotations or []
    if len(raw) > MAX_DRAFT_ANNOTATIONS:          # the merge runs synchronously in the API process
        raise HTTPException(413, f"at most {MAX_DRAFT_ANNOTATIONS} annotations per consensus draft")
    check_image_cap(db, job.id, image_id, c.user.id, len(raw))
    checked = [_check_ann(a) for a in raw]
    _check_class_ids(c, checked)
    assignment.annotations = checked
    assignment.submitted = now()
    refresh_job(db, job, image_id=image_id)
    total, submitted = db.execute(select(func.count(ConsensusAssignment.id), func.count(ConsensusAssignment.submitted))
                                  .where(ConsensusAssignment.job_id == job.id)).one()
    return {"submitted": int(submitted or 0), "total": int(total or 0), "agreement": job.agreement,
            "jobStatus": job.status, "jobId": job.id}


def merge_job(db: Session, c: Ctx, job: ConsensusJob) -> dict:
    """Write the majority annotations back to each image and park it in the review queue.

    A tie is not a majority. An image whose drafts do not cluster into a strict majority is left
    untouched and reported in `no_consensus`: clearing it would destroy the only copy of the work,
    and the drafts stay readable through `job_detail`. If no image reaches a majority, the merge
    fails closed and the job stays open.
    """
    if job.status == "merged":
        raise HTTPException(409, "this job is already merged")
    if job.status != "ready":
        raise HTTPException(409, "consensus job is not ready to merge")
    rows = db.scalars(select(ConsensusAssignment).where(ConsensusAssignment.job_id == job.id)).all()
    per_image: dict[str, list[list[dict]]] = {}
    for row in rows:
        if row.submitted is not None:
            per_image.setdefault(row.image_id, []).append(row.annotations or [])
    oversized = [image_id for image_id, sets in per_image.items()
                 if sum(len(anns) for anns in sets) > MAX_IMAGE_ANNOTATIONS]
    if oversized:                     # legacy data beyond the write cap: fail closed before writing anything
        raise HTTPException(409, f"{len(oversized)} image(s) exceed the supported {MAX_IMAGE_ANNOTATIONS}"
                                 "-annotation consensus limit")
    merged = skipped = eligible = 0
    no_consensus: list[str] = []
    pending: list[tuple[Image, list[dict]]] = []
    for image_id in job.image_ids or []:
        sets = per_image.get(image_id, [])
        img = db.get(Image, image_id)
        if len(sets) < 2 or img is None or img.deleted_at is not None:
            skipped += 1
            continue
        eligible += 1
        consensus = merge_sets(sets, job.iou_threshold)
        if not consensus:
            no_consensus.append(image_id)
            continue
        pending.append((img, consensus))
    if pending:
        # Re-validate every class id before the first write: a stale/foreign draft must not create
        # an ImageClass row under this project, and a rejected merge must leave every image untouched.
        from ..routers.images import _check_class_ids
        for _, consensus in pending:
            _check_class_ids(c, consensus)
    for img, consensus in pending:
        set_annotations(db, img, consensus)
        img.status, img.review, img.updated = "review", None, now()
        merged += 1
    if merged == 0:
        if eligible:
            raise HTTPException(409, "no image reached a strict majority — review the drafts in the job detail")
        raise HTTPException(409, "no image has two submitted drafts yet")
    job.status, job.updated = "merged", now()
    audit(db, c.ws.id, c.user.id, "labeling.consensus.merge", c.project.name, job=job.id, merged=merged,
          no_consensus=len(no_consensus))
    db.flush()
    return {"id": job.id, "merged": merged, "skipped": skipped + len(no_consensus), "status": job.status,
            "no_consensus": no_consensus}


def job_out(db: Session, job: ConsensusJob) -> dict:
    assignments, submitted = db.execute(
        select(func.count(ConsensusAssignment.id), func.count(ConsensusAssignment.submitted))
        .where(ConsensusAssignment.job_id == job.id)).one()
    return {"id": job.id, "status": job.status, "k": job.k, "iou_threshold": job.iou_threshold,
            "images": len(job.image_ids or []), "image_ids": list(job.image_ids or []),
            "assignments": int(assignments or 0), "submitted": int(submitted or 0),
            "agreement": job.agreement, "created_by": job.created_by, "created": job.created}


def job_detail(db: Session, job: ConsensusJob) -> dict:
    out = job_out(db, job)
    rows = list(db.scalars(select(ConsensusAssignment).where(ConsensusAssignment.job_id == job.id)
                           .order_by(ConsensusAssignment.created, ConsensusAssignment.id)).all())
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_({r.user_id for r in rows})))} if rows else {}
    metrics = dict(job.image_metrics or {})
    images = []
    for image_id in job.image_ids or []:
        img = db.get(Image, image_id)
        mine = [r for r in rows if r.image_id == image_id]
        submitted_rows = [r for r in mine if r.submitted is not None]
        submitted = [r.annotations or [] for r in submitted_rows]
        cached = metrics.get(image_id)
        if cached is None and len(submitted) >= 2:
            cached = _image_metrics(submitted, job.iou_threshold)       # legacy job: score once, in memory
        cached = cached or {}
        images.append({
            "image_id": image_id, "name": img.name if img else "",
            "thumbnail": sign_path(img.thumb) if img else "",
            "agreement": cached.get("agreement"),
            "submissions": len(submitted),
            # a tie must stay visible (and adjudicable) instead of looking like a clean merge
            "no_consensus": bool(cached.get("no_consensus")),
            "drafts": [{"user_id": r.user_id, "name": users[r.user_id].name if r.user_id in users else "",
                        "submitted": r.submitted, "annotations": list(r.annotations or [])}
                       for r in submitted_rows],
            "assignees": [{"user_id": r.user_id, "name": users[r.user_id].name if r.user_id in users else "",
                           "submitted": r.submitted, "count": len(r.annotations or [])} for r in mine]})
    out["images"] = images
    return out


def review_queue(db: Session, c: Ctx, limit: int = 50) -> list[dict]:
    """Review-status images, most disputed consensus first, then longest-waiting.

    Scoring disagreement needs each image's draft JSON, so the scan is still bounded — but at
    5000 review images instead of 2000, which covers any realistic project backlog. The page
    itself stays capped by `limit`.
    """
    size = max(1, min(int(limit), 200))
    rows = list(db.scalars(select(Image).where(Image.project_id == c.project.id, Image.status == "review",
                                               Image.deleted_at.is_(None))
                           .order_by(Image.updated).limit(5000)).all())
    if not rows:
        return []
    subs = db.execute(select(ConsensusAssignment.image_id, ConsensusAssignment.annotations,
                             ConsensusJob.created, ConsensusJob.id, ConsensusJob.iou_threshold)
                      .join(ConsensusJob, ConsensusJob.id == ConsensusAssignment.job_id)
                      .where(ConsensusAssignment.project_id == c.project.id,
                             ConsensusAssignment.image_id.in_([r.id for r in rows]),
                             ConsensusAssignment.submitted.is_not(None),
                             ConsensusJob.status.in_(PROJECT_STATES))).all()
    latest: dict[str, tuple[float, str]] = {}
    by_job: dict[tuple[str, str], list[list[dict]]] = {}
    thresholds: dict[str, float] = {}
    for image_id, anns, created, job_id, threshold in subs:
        by_job.setdefault((job_id, image_id), []).append(anns or [])
        thresholds[job_id] = threshold
        if image_id not in latest or (created, job_id) > latest[image_id]:
            latest[image_id] = (created, job_id)
    # The per-image scores were cached when each draft was saved; a review-page read never re-runs
    # the pairwise pass. Legacy jobs without a cache are scored once, in memory.
    jobs = {job_id: db.get(ConsensusJob, job_id) for _, job_id in latest.values()}
    items = []
    for img in rows:
        picked = latest.get(img.id)
        sets = by_job.get((picked[1], img.id), []) if picked else []
        job = jobs.get(picked[1]) if picked else None
        cached = (job.image_metrics or {}).get(img.id) if job is not None else None
        if cached is None and picked and len(sets) >= 2:
            cached = _image_metrics(sets, thresholds.get(picked[1], 0.5))
        agreement = (cached or {}).get("agreement")
        disagreement = round(1 - agreement, 4) if agreement is not None else 0.0
        items.append({"image_id": img.id, "name": img.name, "thumbnail": sign_path(img.thumb),
                      "disagreement": disagreement, "submissions": len(sets), "status": img.status,
                      "updated": img.updated, "annotations": img.n_annotations})
    items.sort(key=lambda x: (-x["disagreement"], x["updated"]))
    return items[:size]


def dashboard(db: Session, c: Ctx, days: int = 30, only_user: str | None = None) -> dict:
    """Throughput, AI acceptance, rejection rate and honeypot accuracy for the project team.

    The definitions (and the AI-acceptance rule shared with Task 20a) live in `labeler_stats`.
    """
    return labeler_stats.statistics(db, workspace_id=c.ws.id, project_id=c.project.id, days=days,
                                    only_user=only_user)


def my_tasks(db: Session, c: Ctx) -> list[dict]:
    """The caller's open consensus drafts, newest first."""
    rows = db.execute(select(ConsensusAssignment, Image)
                      .join(ConsensusJob, ConsensusJob.id == ConsensusAssignment.job_id)
                      .join(Image, Image.id == ConsensusAssignment.image_id)
                      .where(ConsensusAssignment.workspace_id == c.ws.id,
                             ConsensusAssignment.project_id == c.project.id,
                             ConsensusAssignment.user_id == c.user.id,
                             ConsensusAssignment.submitted.is_(None), ConsensusJob.status == "collecting",
                             Image.deleted_at.is_(None))
                      .order_by(ConsensusAssignment.created.desc(), ConsensusAssignment.id).limit(200)).all()
    return [{"job_id": row.job_id, "image_id": row.image_id, "name": img.name, "thumbnail": sign_path(img.thumb),
             "created": row.created} for row, img in rows]


def _annotator_ids(db: Session, c: Ctx) -> list[str]:
    """Members whose effective project role grants `project.annotate` (I5: billing/viewers excluded)."""
    return rbac.project_permission_holders(db, c.ws.id, c.project.id, "project.annotate")


def _labeler_ids(db: Session, c: Ctx) -> list[str]:
    """Annotators the honeypot answer key may be shown to: `project.annotate` without `project.review`."""
    reviewers = set(rbac.project_permission_holders(db, c.ws.id, c.project.id, "project.review"))
    return [uid for uid in _annotator_ids(db, c) if uid not in reviewers]


def create_honeypot(db: Session, c: Ctx, image_id: str, annotations: list[dict] | None = None) -> Honeypot:
    """Pin an image's labels as ground truth; a labeler is scored once per honeypot."""
    # local import: routers/images imports this module
    from ..routers.images import _check_ann, _check_class_ids

    img = db.get(Image, image_id)
    if not img or img.deleted_at is not None or img.project_id != c.project.id:
        raise HTTPException(404, "image not found")
    checked = [_check_ann(a) for a in (annotations if annotations is not None else img.annotations or [])]
    _check_class_ids(c, checked)
    if not checked:
        raise HTTPException(400, "honeypot needs at least one ground-truth annotation")
    if db.scalar(select(Honeypot.id).where(Honeypot.image_id == img.id)):
        raise HTTPException(409, "image is already a honeypot")
    # A honeypot nobody can open never records an attempt: deliver it to a labeler round-robin so the
    # accuracy feature gets data. The key never goes to a member who can review it.
    labelers = _labeler_ids(db, c)
    if labelers and img.assignee_id not in set(labelers):
        offset = int(db.scalar(select(func.count(Honeypot.id)).where(
            Honeypot.project_id == c.project.id)) or 0)
        img.assignee_id = labelers[offset % len(labelers)]
        if img.status == "unassigned":
            img.status = "annotating"
        img.updated = now()
        db.flush()
    honeypot = Honeypot(workspace_id=c.ws.id, project_id=c.project.id, image_id=img.id, annotations=checked,
                        created_by=c.user.id)
    db.add(honeypot)
    audit(db, c.ws.id, c.user.id, "labeling.honeypot.create", img.name, image_id=img.id)
    db.flush()
    return honeypot


def honeypots_out(db: Session, c: Ctx) -> dict:
    rows = list(db.scalars(select(Honeypot).where(Honeypot.workspace_id == c.ws.id,
                                                  Honeypot.project_id == c.project.id)
                           .order_by(Honeypot.created.desc(), Honeypot.id)).all())
    stats = {hid: (int(n), avg) for hid, n, avg in db.execute(
        select(HoneypotAttempt.honeypot_id, func.count(HoneypotAttempt.id), func.avg(HoneypotAttempt.score))
        .where(HoneypotAttempt.project_id == c.project.id).group_by(HoneypotAttempt.honeypot_id))}
    items = []
    labelers = set(_labeler_ids(db, c))
    for honeypot in rows:
        img = db.get(Image, honeypot.image_id)
        attempts, accuracy = stats.get(honeypot.id, (0, None))
        items.append({"id": honeypot.id, "image_id": honeypot.image_id, "name": img.name if img else "",
                      "thumbnail": sign_path(img.thumb) if img else "",
                      "annotations": len(honeypot.annotations or []), "attempts": attempts,
                      "accuracy": round(float(accuracy), 4) if accuracy is not None else None,
                      "needs_assignee": bool(img is None or img.assignee_id not in labelers),
                      "created": honeypot.created})
    label_rows = db.execute(select(HoneypotAttempt.user_id, func.count(HoneypotAttempt.id),
                                   func.avg(HoneypotAttempt.score))
                            .join(Honeypot, Honeypot.id == HoneypotAttempt.honeypot_id)
                            .where(Honeypot.project_id == c.project.id, Honeypot.workspace_id == c.ws.id)
                            .group_by(HoneypotAttempt.user_id)).all()
    user_ids = [row[0] for row in label_rows]
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids)))} if user_ids else {}
    labelers = [{"user_id": uid, "name": users[uid].name if uid in users else "", "attempts": int(n),
                 "accuracy": round(float(avg), 4) if avg is not None else None}
                for uid, n, avg in label_rows]
    labelers.sort(key=lambda row: (row["name"], row["user_id"]))
    return {"items": items, "labelers": labelers}
