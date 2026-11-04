"""Natural-language search over stored stream events and recorded footage frames.

The indexer samples the requested window from the footage frames already in the project and from
the stream events the CCTV rules stored. Each sampled frame keeps a CLIP image vector. A search
embeds the query text in the same CLIP space, blends visual similarity with word overlap against
the stored caption/label words and returns a probabilistic ranking. Every result is a candidate: a
person confirms it before it is trusted. No model is asked to rewrite the query or caption a frame.
"""

import logging
import math
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import DATA_DIR
from ..models import EventSearchFrame, Image, Project, Stream, StreamEvent, Video, Workspace, new_id, now
from ..security import sign_query
from . import embeddings, imaging

log = logging.getLogger(__name__)

DEFAULT_SAMPLE = 300
MAX_SAMPLE = 1000
MAX_RESULTS = 100
WINDOW_MAX_S = 31 * 24 * 3600
SOFTMAX_T = 0.15  # relative scores: a rank, not a calibrated probability claim
LEXICAL_SHARE = 0.25  # stored words still count next to visual similarity
_WORD = re.compile(r"[a-z0-9]{2,}")
_STOP = {
    "the", "and", "for", "with", "from", "that", "this", "into", "over", "under", "near", "at", "in",
    "on", "of", "to", "by", "as", "is", "be", "it", "or", "we", "you", "an", "are", "was", "were",
    "has", "have", "had", "not", "but", "its", "his", "her", "their",
}


# --- ranking (pure, no DB) ---------------------------------------------------


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall((text or "").lower()) if w not in _STOP}


def lexical_score(query: str, text: str) -> float:
    """Share of the query's meaningful words that appear in the frame's caption/label."""
    wanted = _words(query)
    if not wanted:
        return 0.0
    return len(wanted & _words(text)) / len(wanted)


def _cosine(a, b) -> float | None:
    if not a or not b or len(a) != len(b):
        return None
    dot = sum(float(x) * float(y) for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(float(x) * float(x) for x in a))
    nb = math.sqrt(sum(float(y) * float(y) for y in b))
    if not na or not nb:
        return None
    return max(0.0, dot / (na * nb))


def _softmax(values: list[float]) -> list[float]:
    if not values:
        return []
    top = max(values)
    exps = [math.exp((v - top) / SOFTMAX_T) for v in values]
    total = sum(exps) or 1.0
    return [e / total for e in exps]


def rank_candidates(query: str, rows: list, query_vector: list[float] | None,
                    limit: int = 20) -> tuple[list[dict], str]:
    """Rank indexed frames against a query.

    Returns ``(results, ranking)`` where ranking is ``"clip+lexical"`` when at least one frame
    carried a usable vector, else ``"lexical"``. Scores are a softmax over the whole sampled window:
    they compare candidates with each other, they are not a calibrated probability of the event.
    """
    has_clip = bool(query_vector) and any(getattr(row, "embedding", None) for row in rows)
    matches: list[tuple[float, object]] = []
    for row in rows:
        text = row.label or ""
        lexical = lexical_score(query, text)
        visual = _cosine(query_vector, getattr(row, "embedding", None)) if has_clip else None
        match = (1 - LEXICAL_SHARE) * visual + LEXICAL_SHARE * lexical if visual is not None else lexical
        matches.append((match, row))

    weights = _softmax([match for match, _ in matches])
    kept = [
        (match, weight, row)
        for (match, row), weight in zip(matches, weights, strict=True)
        if match > 0
    ]
    kept.sort(key=lambda item: (-item[0], -float(getattr(item[2], "ts", 0))))
    out = [
        {
            "id": row.id,
            "source": row.source,
            "source_id": row.source_id,
            "stream_id": row.stream_id,
            "video_id": row.video_id,
            "ts": row.ts,
            "score": round(weight, 4),
            "match": round(match, 4),
            "label": row.label or "",
            "confirmed": bool(row.confirmed),
            "confirmed_by": row.confirmed_by,
        }
        for match, weight, row in kept[: max(1, min(limit, MAX_RESULTS))]
    ]
    return out, ("clip+lexical" if has_clip else "lexical")


def sample_candidates(candidates: list[dict], limit: int) -> list[dict]:
    """Deterministic spread over a newest-first window: cap the work without losing the window."""
    limit = max(1, min(int(limit), MAX_SAMPLE))
    if len(candidates) <= limit:
        return list(candidates)
    step = max(1, math.ceil(len(candidates) / limit))
    return candidates[::step][:limit]


# --- indexing ----------------------------------------------------------------


def collect_candidates(db: Session, project: Project, start: float, end: float,
                       stream_id: str | None = None) -> list[dict]:
    """Frames inside the window, from recorded footage and from stored stream events."""
    out: list[dict] = []
    videos = {v.id: v.name for v in db.scalars(select(Video).where(Video.project_id == project.id)).all()}
    images = db.scalars(
        select(Image)
        .where(
            Image.project_id == project.id,
            Image.deleted_at.is_(None),
            Image.video_id.is_not(None),
            Image.created >= start,
            Image.created <= end,
        )
        .order_by(Image.created.desc())
    ).all()
    for img in images:
        if not img.path:
            continue
        out.append({
            "source": "footage",
            "source_id": img.id,
            "stream_id": None,
            "video_id": img.video_id,
            "ts": float(img.created),
            "path": img.path,
            "sha": img.sha256,
            "label": " ".join([img.name, *(img.tags or [])]),
            "source_name": videos.get(img.video_id, ""),
        })

    q = (
        select(StreamEvent, Stream)
        .join(Stream, StreamEvent.stream_id == Stream.id)
        .where(
            Stream.workspace_id == project.workspace_id,
            Stream.project_id == project.id,
            StreamEvent.ts >= start,
            StreamEvent.ts <= end,
        )
    )
    if stream_id:
        q = q.where(StreamEvent.stream_id == stream_id)
    for event, stream in db.execute(q.order_by(StreamEvent.ts.desc())).all():
        path = event.clean_path or event.snapshot_path
        if not path:
            continue
        out.append({
            "source": "stream",
            "source_id": event.id,
            "stream_id": event.stream_id,
            "video_id": None,
            "ts": float(event.ts),
            "path": path,
            "sha": None,
            "label": " ".join(part for part in (event.summary, event.rule_label, event.classes) if part),
            "source_name": stream.name,
        })

    out.sort(key=lambda c: c["ts"], reverse=True)
    return out


def _image_vector(im, sha: str | None) -> list[float] | None:
    try:
        return embeddings.embed_image(im, sha)
    except Exception:  # noqa: BLE001 - CLIP is optional; lexical ranking still works
        log.info("event search: CLIP image embedding unavailable", exc_info=True)
        return None


def _text_vector(text: str) -> list[float] | None:
    if not embeddings.available():
        return None
    try:
        return [float(v) for v in embeddings.embed_text(text)]
    except Exception:  # noqa: BLE001 - fall back to caption/label matching
        log.info("event search: CLIP text embedding unavailable", exc_info=True)
        return None


def index_candidates(db: Session, project: Project, candidates: list[dict],
                     should_stop=None) -> tuple[list[EventSearchFrame], dict]:
    """Upsert the window into the index, then backfill image vectors that are missing."""
    stats = {"indexed": 0, "embeddings": 0}
    if not candidates:
        return [], stats

    ids = [c["source_id"] for c in candidates]
    existing = {
        (row.source, row.source_id): row
        for row in db.scalars(
            select(EventSearchFrame).where(
                EventSearchFrame.project_id == project.id,
                EventSearchFrame.source_id.in_(ids),
            )
        ).all()
    }
    rows: list[EventSearchFrame] = []
    for cand in candidates:
        row = existing.get((cand["source"], cand["source_id"]))
        if row is None:
            row = EventSearchFrame(
                id=new_id(),
                workspace_id=project.workspace_id,
                project_id=project.id,
                source=cand["source"],
                source_id=cand["source_id"],
                stream_id=cand.get("stream_id"),
                video_id=cand.get("video_id"),
                ts=cand["ts"],
                path=cand["path"],
                label=cand.get("label", ""),
                embedding=[],
            )
            db.add(row)
            existing[(row.source, row.source_id)] = row
            stats["indexed"] += 1
        else:
            row.ts, row.path = cand["ts"], cand["path"]
            if cand.get("label"):
                row.label = cand["label"]
        rows.append(row)
    db.commit()

    sha_by_id = {c["source_id"]: c.get("sha") for c in candidates}
    clip = embeddings.available()
    for row in rows:
        if should_stop is not None and should_stop():
            break
        if clip and not row.embedding:
            vector = _image_vector(imaging.load(row.path), sha_by_id.get(row.source_id))
            if vector is not None:
                row.embedding = vector
                stats["embeddings"] += 1
                db.commit()
    return rows, stats


# --- job entry point ---------------------------------------------------------


def _image_url(ws_slug: str, project_slug: str, frame_id: str, viewer: str | None) -> str:
    rel = f"ws/{ws_slug}/projects/{project_slug}/event-search/frames/{frame_id}/image"
    return f"/api/{rel}?{sign_query(rel, viewer=viewer)}"


def run_search(db: Session, project: Project, params: dict, should_stop=None) -> dict:
    """Worker entry point: index the requested window, then rank it against the query."""
    start = float(params["from_ts"])
    end = float(params["to_ts"])
    query = str(params["query"]).strip()
    limit = max(1, min(int(params.get("limit") or 20), MAX_RESULTS))
    sample = max(1, min(int(params.get("sample") or DEFAULT_SAMPLE), MAX_SAMPLE))
    workspace = db.get(Workspace, project.workspace_id)

    candidates = sample_candidates(
        collect_candidates(db, project, start, end, params.get("stream_id")), sample
    )
    rows, stats = index_candidates(db, project, candidates, should_stop=should_stop)
    results, ranking = rank_candidates(query, rows, _text_vector(query), limit)

    names = {c["source_id"]: c.get("source_name", "") for c in candidates}
    viewer = params.get("created_by")
    for result in results:
        result["source_name"] = names.get(result["source_id"], "")
        result["image"] = _image_url(workspace.slug if workspace else "", project.slug, result["id"], viewer)
    return {
        "query": query,
        "ranking": ranking,
        "from_ts": start,
        "to_ts": end,
        "candidates": len(candidates),
        "sampled": sample,
        "indexed": stats["indexed"],
        "embeddings": stats["embeddings"],
        "results": results,
    }


def confirm(frame: EventSearchFrame, user_id: str, confirmed: bool) -> None:
    """Record the person who confirmed (or rejected) one ranked candidate."""
    frame.confirmed = bool(confirmed)
    frame.confirmed_by = user_id if confirmed else None
    frame.confirmed_at = now() if confirmed else None


def data_path(rel: str):
    """Resolve a frame path, refusing anything outside DATA_DIR."""
    path = (DATA_DIR / rel).resolve()
    return path if DATA_DIR in path.parents else None
