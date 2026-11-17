"""Natural-language event search: start a ranked search, confirm a candidate, serve a signed frame."""

import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import Ctx, audit, project_ctx
from ..models import EventSearchFrame, Image, Job, Project, Stream, Video, Workspace
from ..security import check_signature, sign_query
from ..services import event_search, streamaudit
from ..services.flags import require_flag, require_workspace_flag
from .projects import job_out

P = "/api/ws/{ws}/projects/{project}/event-search"
router = APIRouter(prefix=P, tags=["event-search"])
FLAG = "task_38"
_GATE = [Depends(require_workspace_flag(FLAG))]


class SearchIn(BaseModel):
    query: str = ""
    from_ts: float | None = None
    to_ts: float | None = None
    stream_id: str | None = None
    limit: int = 20
    sample: int = event_search.DEFAULT_SAMPLE


class ConfirmIn(BaseModel):
    confirmed: bool = True


def _get_frame(c: Ctx, fid: str) -> EventSearchFrame:
    frame = c.db.get(EventSearchFrame, fid)
    if frame is None or frame.project_id != c.project.id or frame.workspace_id != c.ws.id:
        raise HTTPException(404, "search frame not found")
    return frame


def _source_name(db: Session, frame: EventSearchFrame) -> str:
    if frame.source == "footage" and frame.video_id:
        video = db.get(Video, frame.video_id)
        return video.name if video else ""
    if frame.source == "stream" and frame.stream_id:
        stream = db.get(Stream, frame.stream_id)
        return stream.name if stream else ""
    return ""


def _frame_out(c: Ctx, frame: EventSearchFrame, score: float | None = None) -> dict:
    rel = f"ws/{c.ws.slug}/projects/{c.project.slug}/event-search/frames/{frame.id}/image"
    out = {
        "id": frame.id,
        "source": frame.source,
        "source_id": frame.source_id,
        "stream_id": frame.stream_id,
        "video_id": frame.video_id,
        "ts": frame.ts,
        "label": frame.label or "",
        "confirmed": bool(frame.confirmed),
        "confirmed_by": frame.confirmed_by,
        "source_name": _source_name(c.db, frame),
        "image": f"/api/{rel}?{sign_query(rel, viewer=c.user.id)}",
    }
    if score is not None:
        out["score"] = score
    return out


@router.post("")
def start_search(body: SearchIn, c: Ctx = Depends(project_ctx),
                 _: None = Depends(require_flag(FLAG))):
    """Queue an index+rank job; a long window is sampled in the background."""
    # Stream footage is project.streams data and the stored result needs project.models
    # (visible_job strips it for anyone else), so the same roles that watch streams search them.
    c.perm("project.streams")
    query = body.query.strip()
    if not query or len(query) > 500:
        raise HTTPException(400, "query must be 1 to 500 characters")
    end = float(body.to_ts if body.to_ts is not None else time.time())
    start = float(body.from_ts if body.from_ts is not None else end - 7 * 24 * 3600)
    if start >= end:
        raise HTTPException(400, "from_ts must be before to_ts")
    if end - start > event_search.WINDOW_MAX_S:
        raise HTTPException(400, "search window is limited to 31 days")
    if not 1 <= body.limit <= event_search.MAX_RESULTS:
        raise HTTPException(400, f"limit must be 1 to {event_search.MAX_RESULTS}")
    if not 1 <= body.sample <= event_search.MAX_SAMPLE:
        raise HTTPException(400, f"sample must be 1 to {event_search.MAX_SAMPLE}")

    job = Job(
        workspace_id=c.ws.id,
        project_id=c.project.id,
        kind="event_search",
        created_by=c.user.id,
        params={
            "query": query,
            "from_ts": start,
            "to_ts": end,
            "stream_id": body.stream_id,
            "limit": body.limit,
            "sample": body.sample,
            "created_by": c.user.id,
        },
    )
    c.db.add(job)
    c.db.commit()
    return job_out(job)


@router.post("/frames/{fid}/confirm")
def confirm_frame(fid: str, body: ConfirmIn, c: Ctx = Depends(project_ctx),
                  _: None = Depends(require_flag(FLAG))):
    """A person accepts or rejects one ranked candidate; the decision is attributed and audited."""
    c.perm("project.review")
    frame = _get_frame(c, fid)
    event_search.confirm(frame, c.user.id, body.confirmed)
    audit(c.db, c.ws.id, c.user.id, "event_search.confirm", frame.id,
          confirmed=bool(body.confirmed), source=frame.source)
    c.db.commit()
    return _frame_out(c, frame)


@router.get("/frames/{fid}/image", dependencies=_GATE)
def frame_image(fid: str, exp: int, sig: str, viewer: str, ws: str, project: str,
                db: Session = Depends(get_db)):
    """Signed frame URL for `<img>` (no bearer header); stream frames are audited like live footage."""
    workspace = db.scalar(select(Workspace).where(Workspace.slug == ws))
    project_row = (
        db.scalar(
            select(Project).where(
                Project.workspace_id == workspace.id,
                Project.slug == project,
                Project.deleted_at.is_(None),
            )
        )
        if workspace
        else None
    )
    if not workspace or not project_row:
        raise HTTPException(404, "not found")
    rel = f"ws/{ws}/projects/{project}/event-search/frames/{fid}/image"
    if not check_signature(rel, exp, sig, viewer):
        raise HTTPException(403, "bad or expired signature")
    frame = db.get(EventSearchFrame, fid)
    if frame is None or frame.project_id != project_row.id:
        raise HTTPException(404, "search frame not found")
    if frame.source == "footage":
        # a frame outlives its dataset image only as a tombstone: never serve erased footage
        image = db.get(Image, frame.source_id)
        if image is None or image.deleted_at is not None:
            raise HTTPException(404, "frame image not found")
    path = event_search.data_path(frame.path)
    if path is None or not path.exists():
        raise HTTPException(404, "frame image not found")
    if frame.source == "stream" and frame.stream_id:
        streamaudit.record(db, ws, frame.stream_id, "event_search", viewer, project)
    return FileResponse(path, media_type="image/jpeg")
