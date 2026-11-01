"""Labeling QA & workforce operations: consensus jobs, label events, honeypots, dashboard, review queue."""
import time
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..deps import Ctx, audit
from ..models import (ConsensusAssignment, ConsensusJob, Honeypot, HoneypotAttempt, Image, LabelEvent, Member, User,
                      now, set_annotations)
from ..security import sign_path
from .labeling import MAX_K, MIN_K, group_agreement, honeypot_score, merge_sets

MAX_JOB_IMAGES = 100
PROJECT_STATES = ("collecting", "ready", "merged")
ROLES = ("annotator", "reviewer", "admin")


def create_job(db: Session, c: Ctx, image_ids: list[str], count: int, k: int,
               iou_threshold: float) -> ConsensusJob:
    """Send up to `count` unlabeled, not-yet-open images to `k` distinct members, round-robin."""
    if not MIN_K <= k <= MAX_K:
        raise HTTPException(400, f"k must be between {MIN_K} and {MAX_K}")
    members = db.scalars(select(Member).join(User, User.id == Member.user_id)
                         .where(Member.workspace_id == c.ws.id)
                         .order_by(Member.created, User.id)).all()
    if len(members) < k:
        raise HTTPException(400, f"need at least k workspace members (have {len(members)})")
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
                                       image_id=img.id, user_id=members[(idx + step) % len(members)].user_id))
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
        if old.get("source") in (None, "human"):
            continue
        seen += 1
        if any(new.get("id") == old.get("id") and new.get("classId") == old.get("classId")
               and (new.get("shape") or {}) == (old.get("shape") or {}) for new in after or []):
            kept += 1
    honeypot = db.scalar(select(Honeypot).where(Honeypot.image_id == img.id, Honeypot.workspace_id == ws_id))
    event = None
    if honeypot is None:
        event = LabelEvent(workspace_id=ws_id, project_id=img.project_id, image_id=img.id, user_id=user_id,
                           annotations=len(after or []), ai_seen=seen, ai_kept=kept)
        db.add(event)
    if assignment is not None:
        assignment.annotations = list(after or [])
        job = db.get(ConsensusJob, assignment.job_id)
        if job is not None and assignment.submitted is not None:
            refresh_job(db, job)
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


def refresh_job(db: Session, job: ConsensusJob) -> ConsensusJob:
    """Recompute the job agreement and move it to ready once every assigned labeler has submitted."""
    rows = db.scalars(select(ConsensusAssignment).where(ConsensusAssignment.job_id == job.id)).all()
    per_image: dict[str, list[list[dict]]] = {}
    for row in rows:
        if row.submitted is not None:
            per_image.setdefault(row.image_id, []).append(row.annotations or [])
    scores = [group_agreement(sets, job.iou_threshold) for sets in per_image.values() if len(sets) >= 2]
    job.agreement = round(sum(scores) / len(scores), 4) if scores else None
    if job.status != "merged":
        job.status = "ready" if rows and all(row.submitted is not None for row in rows) else "collecting"
    job.updated = now()
    db.flush()
    return job


def submit_consensus(db: Session, c: Ctx, job: ConsensusJob, image_id: str,
                     annotations: list[dict] | None = None) -> dict:
    """Explicitly hand in one draft; the job only becomes ready once every assignment is submitted."""
    from ..routers.images import _check_ann      # local import: routers/images imports this module

    assignment = db.scalar(select(ConsensusAssignment).where(
        ConsensusAssignment.job_id == job.id, ConsensusAssignment.image_id == image_id,
        ConsensusAssignment.user_id == c.user.id))
    if assignment is None:
        raise HTTPException(404, "not your assignment")
    if job.status == "merged":
        raise HTTPException(409, "this consensus job is already merged")
    checked = [_check_ann(a) for a in (annotations if annotations is not None else assignment.annotations or [])]
    assignment.annotations = checked
    assignment.submitted = now()
    refresh_job(db, job)
    total, submitted = db.execute(select(func.count(ConsensusAssignment.id), func.count(ConsensusAssignment.submitted))
                                  .where(ConsensusAssignment.job_id == job.id)).one()
    return {"submitted": int(submitted or 0), "total": int(total or 0), "agreement": job.agreement,
            "jobStatus": job.status, "jobId": job.id}


def merge_job(db: Session, c: Ctx, job: ConsensusJob) -> dict:
    """Write the majority annotations back to each image and park it in the review queue."""
    if job.status == "merged":
        raise HTTPException(409, "this job is already merged")
    if job.status != "ready":
        raise HTTPException(409, "consensus job is not ready to merge")
    rows = db.scalars(select(ConsensusAssignment).where(ConsensusAssignment.job_id == job.id)).all()
    per_image: dict[str, list[list[dict]]] = {}
    for row in rows:
        if row.submitted is not None:
            per_image.setdefault(row.image_id, []).append(row.annotations or [])
    merged = skipped = 0
    for image_id in job.image_ids or []:
        sets = per_image.get(image_id, [])
        img = db.get(Image, image_id)
        if len(sets) < 2 or img is None or img.deleted_at is not None:
            skipped += 1
            continue
        set_annotations(db, img, merge_sets(sets, job.iou_threshold))
        img.status, img.review, img.updated = "review", None, now()
        merged += 1
    if merged == 0:
        raise HTTPException(409, "no image has two submitted drafts yet")
    job.status, job.updated = "merged", now()
    audit(db, c.ws.id, c.user.id, "labeling.consensus.merge", c.project.name, job=job.id, merged=merged)
    db.flush()
    return {"id": job.id, "merged": merged, "skipped": skipped, "status": job.status}


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
    images = []
    for image_id in job.image_ids or []:
        img = db.get(Image, image_id)
        mine = [r for r in rows if r.image_id == image_id]
        submitted = [r.annotations or [] for r in mine if r.submitted is not None]
        images.append({
            "image_id": image_id, "name": img.name if img else "",
            "thumbnail": sign_path(img.thumb) if img else "",
            "agreement": round(group_agreement(submitted, job.iou_threshold), 4) if len(submitted) >= 2 else None,
            "submissions": len(submitted),
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
    items = []
    for img in rows:
        picked = latest.get(img.id)
        sets = by_job.get((picked[1], img.id), []) if picked else []
        disagreement = (round(1 - group_agreement(sets, thresholds.get(picked[1], 0.5)), 4)
                        if picked and len(sets) >= 2 else 0.0)
        items.append({"image_id": img.id, "name": img.name, "thumbnail": sign_path(img.thumb),
                      "disagreement": disagreement, "submissions": len(sets), "status": img.status,
                      "updated": img.updated, "annotations": img.n_annotations})
    items.sort(key=lambda x: (-x["disagreement"], x["updated"]))
    return items[:size]


def dashboard(db: Session, c: Ctx, days: int = 30, only_user: str | None = None) -> dict:
    """Throughput, AI acceptance, rejection rate and honeypot accuracy for the project team."""
    days = max(1, min(int(days), 365))
    today = datetime.fromtimestamp(now()).date()
    start = today - timedelta(days=days - 1)
    cutoff = datetime.combine(start, datetime.min.time()).timestamp()
    events_q = select(LabelEvent.user_id, LabelEvent.image_id, LabelEvent.annotations, LabelEvent.ai_seen,
                      LabelEvent.ai_kept, LabelEvent.created).where(
        LabelEvent.workspace_id == c.ws.id, LabelEvent.project_id == c.project.id, LabelEvent.created >= cutoff)
    if only_user:
        events_q = events_q.where(LabelEvent.user_id == only_user)
    events = db.execute(events_q).all()

    seen = sum(e.ai_seen for e in events)
    kept = sum(e.ai_kept for e in events)
    # A save stores the draft's running total, so throughput is the latest draft per (labeler, image),
    # not the sum of every autosave event. AI counters still accumulate (each save re-checks the batch).
    best: dict[tuple[str, str], int] = {}
    for event in events:
        key = (event.user_id, event.image_id)
        best[key] = max(best.get(key, 0), event.annotations or 0)
    user_annotations: dict[str, int] = {}
    for (uid, _), n in best.items():
        user_annotations[uid] = user_annotations.get(uid, 0) + n
    pending_q = select(func.count(ConsensusAssignment.id)).join(
        ConsensusJob, ConsensusJob.id == ConsensusAssignment.job_id).where(
        ConsensusAssignment.workspace_id == c.ws.id, ConsensusJob.project_id == c.project.id,
        ConsensusJob.status == "collecting", ConsensusAssignment.submitted.is_(None))
    if only_user:
        pending_q = pending_q.where(ConsensusAssignment.user_id == only_user)
    hp_q = select(func.avg(HoneypotAttempt.score)).where(HoneypotAttempt.project_id == c.project.id)
    if only_user:
        hp_q = hp_q.where(HoneypotAttempt.user_id == only_user)
    honeypot_avg = db.scalar(hp_q)
    review_count = db.scalar(select(func.count(Image.id)).where(
        Image.project_id == c.project.id, Image.status == "review", Image.deleted_at.is_(None)))
    totals = {"images": len({e.image_id for e in events}), "annotations": sum(best.values()),
              "ai_acceptance": round(kept / seen, 4) if seen else None,
              "consensus_pending": int(db.scalar(pending_q) or 0),
              "honeypot_accuracy": round(float(honeypot_avg), 4) if honeypot_avg is not None else None,
              "review_queue": int(review_count or 0)}

    members_q = select(Member, User).join(User, User.id == Member.user_id).where(
        Member.workspace_id == c.ws.id, Member.role.in_(ROLES))
    if only_user:
        members_q = members_q.where(Member.user_id == only_user)
    members = db.execute(members_q.order_by(Member.created, Member.user_id)).all()
    user_ids = [user.id for _, user in members]

    by_user: dict[str, list] = {}
    for event in events:
        by_user.setdefault(event.user_id, []).append(event)
    reviews: dict[str, tuple[int, int]] = {}
    for uid, verdict, n in db.execute(select(Image.assignee_id, Image.review, func.count()).where(
            Image.project_id == c.project.id, Image.assignee_id.in_(user_ids), Image.updated >= cutoff,
            Image.review.in_(("approved", "rejected")), Image.deleted_at.is_(None))
            .group_by(Image.assignee_id, Image.review)):
        approved, rejected = reviews.get(uid, (0, 0))
        reviews[uid] = (approved + (n if verdict == "approved" else 0), rejected + (n if verdict == "rejected" else 0))
    honeypots = dict(db.execute(select(HoneypotAttempt.user_id, func.avg(HoneypotAttempt.score))
                                .where(HoneypotAttempt.project_id == c.project.id,
                                       HoneypotAttempt.user_id.in_(user_ids))
                                .group_by(HoneypotAttempt.user_id)).all())

    labelers = []
    for member, user in members:
        mine = by_user.get(user.id, [])
        seen_u, kept_u = sum(e.ai_seen for e in mine), sum(e.ai_kept for e in mine)
        approved, rejected = reviews.get(user.id, (0, 0))
        images = len({e.image_id for e in mine})
        labelers.append({"user_id": user.id, "name": user.name, "role": member.role, "images": images,
                         "annotations": user_annotations.get(user.id, 0), "per_day": round(images / days, 2),
                         "ai_acceptance": round(kept_u / seen_u, 4) if seen_u else None,
                         "honeypot_accuracy": (round(float(honeypots[user.id]), 4)
                                               if honeypots.get(user.id) is not None else None),
                         "rejection_rate": (round(rejected / (approved + rejected), 4)
                                            if approved + rejected else None)})

    daily = [{"date": (start + timedelta(days=i)).isoformat(), "images": 0, "annotations": 0} for i in range(days)]
    index = {row["date"]: row for row in daily}
    day_images: dict[str, set[str]] = {}
    day_best: dict[tuple[str, str, str], int] = {}
    for event in events:
        key = time.strftime("%Y-%m-%d", time.localtime(event.created))
        row = index.get(key)
        if row is None:
            continue
        day_images.setdefault(key, set()).add(event.image_id)
        bucket = (key, event.user_id, event.image_id)
        day_best[bucket] = max(day_best.get(bucket, 0), event.annotations or 0)
    for (key, _, _), n in day_best.items():
        index[key]["annotations"] += n
    for key, images in day_images.items():
        index[key]["images"] = len(images)
    return {"window_days": days, "totals": totals, "labelers": labelers, "daily": daily}


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


def create_honeypot(db: Session, c: Ctx, image_id: str, annotations: list[dict] | None = None) -> Honeypot:
    """Pin an image's labels as ground truth; a labeler is scored once per honeypot."""
    from ..routers.images import _check_ann      # local import: routers/images imports this module

    img = db.get(Image, image_id)
    if not img or img.deleted_at is not None or img.project_id != c.project.id:
        raise HTTPException(404, "image not found")
    checked = [_check_ann(a) for a in (annotations if annotations is not None else img.annotations or [])]
    if not checked:
        raise HTTPException(400, "honeypot needs at least one ground-truth annotation")
    if db.scalar(select(Honeypot.id).where(Honeypot.image_id == img.id)):
        raise HTTPException(409, "image is already a honeypot")
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
    for honeypot in rows:
        img = db.get(Image, honeypot.image_id)
        attempts, accuracy = stats.get(honeypot.id, (0, None))
        items.append({"id": honeypot.id, "image_id": honeypot.image_id, "name": img.name if img else "",
                      "thumbnail": sign_path(img.thumb) if img else "",
                      "annotations": len(honeypot.annotations or []), "attempts": attempts,
                      "accuracy": round(float(accuracy), 4) if accuracy is not None else None,
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
