"""One definition of labeler throughput, review outcome and AI acceptance.

Task 23's QA dashboard and Task 20a's Insights page describe the same people; they must not drift
into two definitions. Everything they share lives here.

AI acceptance is **provenance-based and per image**, never a per-autosave counter:

- denominator (`seen`): distinct `(image, AI annotation id)` pairs the labeler was shown, recorded
  as `LabelEvent.ai_ids` on each save;
- numerator (`kept`): those ids that are still present in the image's final annotations *and* the
  image is accepted (`status == "done"` or `review == "approved"`).

Task 20a's `insights_dataset.labeling()` should call `ai_acceptance()` (or `statistics()`) when it
lands so both pages report the same number.
"""
import time
from datetime import datetime, timedelta

from sqlalchemy import func, select

from ..models import (
    ConsensusAssignment,
    ConsensusJob,
    HoneypotAttempt,
    Image,
    LabelEvent,
    Member,
    User,
    now,
)

ROLES = ("annotator", "reviewer", "admin")


def _accepted(img: Image) -> bool:
    return img.status == "done" or img.review == "approved"


def _final_ids(images: dict[str, Image]) -> dict[str, set[str]]:
    """Annotation ids left on each accepted image; acceptance intersects these with the ids seen."""
    return {image_id: {a.get("id") for a in img.annotations or [] if isinstance(a, dict)}
            for image_id, img in images.items() if _accepted(img)}


def ai_acceptance(events, images: dict[str, Image]) -> dict[str, tuple[int, int]]:
    """`{user_id: (kept, seen)}` — the one AI-acceptance definition both dashboards must use."""
    seen: dict[str, set[tuple[str, str]]] = {}
    for event in events:
        ids = seen.setdefault(event.user_id, set())
        for aid in event.ai_ids or []:
            ids.add((event.image_id, aid))
    final = _final_ids(images)
    return {user_id: (sum(1 for image_id, aid in ids if aid in final.get(image_id, set())), len(ids))
            for user_id, ids in seen.items()}


def project_ai_acceptance(events, images: dict[str, Image]) -> tuple[int, int]:
    """Project-wide `(kept, seen)` with ids deduplicated across labelers."""
    ids = {(event.image_id, aid) for event in events for aid in (event.ai_ids or [])}
    final = _final_ids(images)
    return sum(1 for image_id, aid in ids if aid in final.get(image_id, set())), len(ids)


def _rate(kept: int, seen: int) -> float | None:
    return round(kept / seen, 4) if seen else None


def statistics(db, *, workspace_id: str, project_id: str, days: int = 30,
               only_user: str | None = None) -> dict:
    """Dashboard payload: per-labeler throughput, AI acceptance, rejection rate and daily counts."""
    days = max(1, min(int(days), 365))
    today = datetime.fromtimestamp(now()).date()
    start = today - timedelta(days=days - 1)
    cutoff = datetime.combine(start, datetime.min.time()).timestamp()
    events_q = select(LabelEvent.user_id, LabelEvent.image_id, LabelEvent.annotations, LabelEvent.ai_ids,
                      LabelEvent.created).where(
        LabelEvent.workspace_id == workspace_id, LabelEvent.project_id == project_id,
        LabelEvent.created >= cutoff)
    if only_user:
        events_q = events_q.where(LabelEvent.user_id == only_user)
    events = db.execute(events_q).all()

    image_ids = {event.image_id for event in events}
    images = ({img.id: img for img in db.scalars(select(Image).where(
        Image.id.in_(image_ids), Image.deleted_at.is_(None)))} if image_ids else {})
    acceptance = ai_acceptance(events, images)
    accepted_total, seen_total = project_ai_acceptance(events, images)

    # A save stores the draft's running total, so throughput is the largest draft per
    # (labeler, image), not the sum of every autosave event.
    best: dict[tuple[str, str], int] = {}
    for event in events:
        key = (event.user_id, event.image_id)
        best[key] = max(best.get(key, 0), event.annotations or 0)
    user_annotations: dict[str, int] = {}
    for (uid, _), n in best.items():
        user_annotations[uid] = user_annotations.get(uid, 0) + n

    pending_q = select(func.count(ConsensusAssignment.id)).join(
        ConsensusJob, ConsensusJob.id == ConsensusAssignment.job_id).where(
        ConsensusAssignment.workspace_id == workspace_id, ConsensusJob.project_id == project_id,
        ConsensusJob.status == "collecting", ConsensusAssignment.submitted.is_(None))
    if only_user:
        pending_q = pending_q.where(ConsensusAssignment.user_id == only_user)
    hp_q = select(func.avg(HoneypotAttempt.score)).where(HoneypotAttempt.project_id == project_id)
    if only_user:
        hp_q = hp_q.where(HoneypotAttempt.user_id == only_user)
    honeypot_avg = db.scalar(hp_q)
    review_count = db.scalar(select(func.count(Image.id)).where(
        Image.project_id == project_id, Image.status == "review", Image.deleted_at.is_(None)))
    totals = {"images": len(image_ids), "annotations": sum(best.values()),
              "ai_acceptance": _rate(accepted_total, seen_total),
              "consensus_pending": int(db.scalar(pending_q) or 0),
              "honeypot_accuracy": round(float(honeypot_avg), 4) if honeypot_avg is not None else None,
              "review_queue": int(review_count or 0)}

    members_q = select(Member, User).join(User, User.id == Member.user_id).where(
        Member.workspace_id == workspace_id, Member.role.in_(ROLES))
    if only_user:
        members_q = members_q.where(Member.user_id == only_user)
    members = db.execute(members_q.order_by(Member.created, Member.user_id)).all()
    user_ids = [user.id for _, user in members]

    by_user: dict[str, list] = {}
    for event in events:
        by_user.setdefault(event.user_id, []).append(event)
    reviews: dict[str, tuple[int, int]] = {}
    for uid, verdict, n in db.execute(select(Image.assignee_id, Image.review, func.count()).where(
            Image.project_id == project_id, Image.assignee_id.in_(user_ids), Image.updated >= cutoff,
            Image.review.in_(("approved", "rejected")), Image.deleted_at.is_(None))
            .group_by(Image.assignee_id, Image.review)):
        approved, rejected = reviews.get(uid, (0, 0))
        reviews[uid] = (approved + (n if verdict == "approved" else 0), rejected + (n if verdict == "rejected" else 0))
    honeypots = dict(db.execute(select(HoneypotAttempt.user_id, func.avg(HoneypotAttempt.score))
                                .where(HoneypotAttempt.project_id == project_id,
                                       HoneypotAttempt.user_id.in_(user_ids))
                                .group_by(HoneypotAttempt.user_id)).all())

    labelers = []
    for member, user in members:
        mine = by_user.get(user.id, [])
        kept, seen = acceptance.get(user.id, (0, 0))
        approved, rejected = reviews.get(user.id, (0, 0))
        images_count = len({e.image_id for e in mine})
        labelers.append({"user_id": user.id, "name": user.name, "role": member.role, "images": images_count,
                         "annotations": user_annotations.get(user.id, 0),
                         "per_day": round(images_count / days, 2),
                         "ai_acceptance": _rate(kept, seen),
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
    for key, images_seen in day_images.items():
        index[key]["images"] = len(images_seen)
    return {"window_days": days, "totals": totals, "labelers": labelers, "daily": daily}
