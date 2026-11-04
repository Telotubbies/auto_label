"""Text search over the CLIP features Task 20a already cached.

The search never runs image inference: a row participates when the embedding scan stored a
`clip` vector for its sha256, which keeps search fast and keeps it out of the GPU lease. The query
text is embedded by the one text tower in `services/embeddings`; the metadata filters (class, tag,
split, …) come from the request, never from a model, so results stay deterministic.
"""

from collections import Counter

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Image, LabelClass, Project
from ..security import sign_path
from . import insights, insights_embedding
from .embeddings import embed_text

MAX_RESULTS = 200
MAX_LIMIT = 500


def _project_classes(db: Session, project: Project) -> list[LabelClass]:
    return db.scalars(
        select(LabelClass).where(LabelClass.project_id == project.id).order_by(LabelClass.created)
    ).all()


def _project_tags(rows: list[Image]) -> list[str]:
    return sorted({tag for row in rows for tag in (row.tags or []) if isinstance(tag, str)})


def _apply_filters(rows: list[Image], *, class_ids: set[str], tags: list[str], split: str, status: str,
                   review: str, annotated: str) -> list[Image]:
    out = rows
    if split:
        out = [row for row in out if row.split == split]
    if status:
        out = [row for row in out if row.status == status]
    if review:
        out = [row for row in out if (row.review or "") == review]
    if annotated == "yes":
        out = [row for row in out if (row.n_annotations or 0) > 0]
    elif annotated == "no":
        out = [row for row in out if (row.n_annotations or 0) == 0]
    if class_ids:
        out = [
            row
            for row in out
            if any(isinstance(a, dict) and a.get("classId") in class_ids for a in (row.annotations or []))
        ]
    if tags:
        out = [row for row in out if all(tag in (row.tags or []) for tag in tags)]
    return out


def _facets(rows: list[Image], classes: list[LabelClass]) -> dict:
    counts: Counter[str] = Counter()
    tag_counts: Counter[str] = Counter()
    for row in rows:
        present = {a.get("classId") for a in (row.annotations or []) if isinstance(a, dict) and a.get("classId")}
        counts.update(present)
        tag_counts.update(tag for tag in (row.tags or []) if isinstance(tag, str))
    return {
        "classes": [
            {"id": cls.id, "name": cls.name, "count": counts[cls.id]} for cls in classes if counts.get(cls.id)
        ],
        "tags": sorted(tag_counts),
        "tag_counts": [{"name": tag, "count": count} for tag, count in sorted(tag_counts.items())],
    }


def _class_name(row: Image, names: dict[str, str]) -> str | None:
    counts: Counter[str] = Counter(
        names[a["classId"]] for a in (row.annotations or [])
        if isinstance(a, dict) and isinstance(a.get("classId"), str) and a["classId"] in names
    )
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if counts else None


def _item(row: Image, names: dict[str, str], score: float | None) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "score": score,
        "thumbnail": sign_path(row.thumb or row.path),
        "split": row.split,
        "status": row.status,
        "tags": [tag for tag in (row.tags or []) if isinstance(tag, str)],
        "class_name": _class_name(row, names),
    }


def _match_score(feature, vector: np.ndarray) -> float | None:
    if feature is None:
        return None
    feature = np.asarray(feature, dtype=np.float32)
    if feature.shape != vector.shape:  # a stale backend wrote a different dimension
        return None
    return round(float(np.dot(feature, vector)), 4)


def search(
    db: Session,
    project: Project,
    query: str = "",
    *,
    project_role: str = "manager",
    user_id: str | None = None,
    class_id: str = "",
    tag: str = "",
    split: str = "",
    status: str = "",
    review: str = "",
    annotated: str = "",
    limit: int = MAX_RESULTS,
) -> dict:
    """Rank this project's images by CLIP similarity, or browse them when the query is blank."""
    q = (query or "").strip()[:500]
    classes = _project_classes(db, project)
    rows = insights.live_images(db, project)
    if project_role == "labeler" and user_id:
        rows = [row for row in rows if row.assignee_id == user_id]

    wanted_classes = {class_id} if class_id else set()
    wanted_tags = [tag] if tag else []
    rows = _apply_filters(rows, class_ids=wanted_classes, tags=wanted_tags, split=split, status=status,
                          review=review, annotated=annotated)
    total = len(rows)
    features = {row.id: insights_embedding.load_feature("clip", row.sha256) for row in rows}
    indexed = sum(1 for feature in features.values() if feature is not None)

    mode, reason = "browse", None
    ranked: list[tuple[Image, float | None]] = [(row, None) for row in
                                                sorted(rows, key=lambda row: (-row.created, row.id))]
    if q:
        try:
            vector = embed_text(q)
        except Exception as exc:  # CLIP missing: browse the embedded rows with an explanation
            mode, reason = "filter", str(exc) or "CLIP embeddings are not available"
            ranked = [(row, None) for row in rows if features[row.id] is not None]
            ranked.sort(key=lambda pair: (-pair[0].created, pair[0].id))
        else:
            scored = [(row, score) for row in rows if (score := _match_score(features[row.id], vector)) is not None]
            scored.sort(key=lambda pair: (-pair[1], -pair[0].created, pair[0].id))
            mode, ranked = "semantic", scored

    names = {cls.id: cls.name for cls in classes}
    wanted = max(1, min(int(limit or MAX_RESULTS), MAX_LIMIT))
    return {
        "mode": mode,
        "reason": reason,
        "total": total,
        "indexed": indexed,
        "missing": total - indexed,
        "items": [_item(row, names, score) for row, score in ranked[:wanted]],
        "facets": _facets(rows, classes),
    }
