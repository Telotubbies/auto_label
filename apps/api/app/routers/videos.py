"""Video upload, frame-extraction job, timeline browsing and keyframe interpolation."""
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import DATA_DIR, MAX_UPLOAD_MB
from ..db import get_db
from ..deps import Ctx, current_user, image_ctx, project_ctx
from ..models import Image, Job, User, Video, new_id, set_annotations
from ..security import sign_path
from ..services import video as video_svc
from ..services.video import MAX_INTERPOLATION_SPAN
from .projects import job_out

router = APIRouter(tags=["videos"])
P = "/api/ws/{ws}/projects/{project}"
VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def video_out(v: Video) -> dict:
    return {"id": v.id, "name": v.name, "status": v.status, "error": v.error or "", "width": v.width,
            "height": v.height, "fps": v.fps, "duration": v.duration, "frameCount": v.frame_count,
            "batchId": v.batch_id, "params": v.params or {}, "created": v.created}


def _get_video(c: Ctx, vid: str) -> Video:
    v = c.db.scalar(select(Video).where(Video.id == vid, Video.project_id == c.project.id,
                                        Video.workspace_id == c.ws.id, Video.deleted_at.is_(None)))
    if v is None:
        raise HTTPException(404, "video not found")
    return v


@router.post(P + "/videos")
async def upload_video(file: UploadFile = File(...), batch_name: str = Form(""), mode: str = Form("fps"),
                       target_fps: float = Form(1.0), every_s: float = Form(1.0),
                       scene_threshold: float = Form(0.35), c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    if mode not in video_svc.EXTRACT_MODES:
        raise HTTPException(400, f"unknown extraction mode {mode!r} — use fps, every or scene")
    if target_fps <= 0:
        raise HTTPException(400, "target_fps must be greater than 0")
    if every_s <= 0:
        raise HTTPException(400, "every_s must be greater than 0")
    if not 0 < scene_threshold < 1:
        raise HTTPException(400, "scene_threshold must be between 0 and 1")
    name = (file.filename or "video").strip()
    ext = Path(name).suffix.lower()
    if ext not in VIDEO_EXT:
        raise HTTPException(400, "unsupported video format — use mp4, mov, avi, mkv or webm")
    budget = MAX_UPLOAD_MB * 1024 * 1024
    data = await file.read(budget + 1)
    if not data:
        raise HTTPException(400, "empty file")
    if len(data) > budget:
        raise HTTPException(413, f"video larger than {MAX_UPLOAD_MB} MB")

    v = Video(id=new_id(), project_id=c.project.id, workspace_id=c.ws.id, name=batch_name.strip() or name,
              path="", status="queued",
              params={"mode": mode, "target_fps": target_fps, "every_s": every_s,
                      "scene_threshold": scene_threshold, "batch_name": batch_name})
    dest = DATA_DIR / "videos" / f"{v.id}{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    v.path = dest.relative_to(DATA_DIR).as_posix()
    c.db.add(v)
    c.db.flush()
    j = Job(workspace_id=c.ws.id, project_id=c.project.id, kind="extract_frames", created_by=c.user.id,
            params={"video_id": v.id, "mode": mode, "target_fps": target_fps, "every_s": every_s,
                    "scene_threshold": scene_threshold, "created_by": c.user.id})
    c.db.add(j)
    c.db.commit()
    return {"video": video_out(v), "job": job_out(j)}


@router.get(P + "/videos")
def list_videos(c: Ctx = Depends(project_ctx)):
    rows = c.db.scalars(select(Video).where(Video.project_id == c.project.id, Video.workspace_id == c.ws.id,
                                            Video.deleted_at.is_(None)).order_by(Video.created.desc())).all()
    return [video_out(v) for v in rows]


@router.get(P + "/videos/{vid}")
def get_video(vid: str, c: Ctx = Depends(project_ctx)):
    return video_out(_get_video(c, vid))


@router.get(P + "/videos/{vid}/timeline")
def timeline(vid: str, from_index: int = Query(0, alias="from"), limit: int = Query(120, ge=1, le=500),
             c: Ctx = Depends(project_ctx)):
    v = _get_video(c, vid)
    q = select(Image).where(Image.project_id == c.project.id, Image.video_id == v.id, Image.deleted_at.is_(None))
    total = c.db.scalar(select(func.count()).select_from(q.subquery()))
    rows = c.db.scalars(q.order_by(Image.frame_index.asc(), Image.id).offset(max(0, from_index))
                        .limit(limit)).all()
    fps = v.fps or 0.0
    frames = [{"id": i.id, "name": i.name, "frameIndex": i.frame_index or 0,
               "time": round((i.frame_index or 0) / fps, 3) if fps else 0,
               "url": sign_path(i.path), "thumbnail": sign_path(i.thumb), "status": i.status,
               "annotations": i.annotations or []} for i in rows]
    return {"video": video_out(v), "total": total, "frames": frames}


class InterpolateIn(BaseModel):
    from_image_id: str
    to_image_id: str


@router.post(P + "/videos/{vid}/interpolate")
def interpolate(vid: str, body: InterpolateIn, c: Ctx = Depends(project_ctx)):
    v = _get_video(c, vid)
    ids = [body.from_image_id, body.to_image_id]
    picked = {i.id: i for i in c.db.scalars(select(Image).where(
        Image.id.in_(ids), Image.project_id == c.project.id, Image.video_id == v.id,
        Image.deleted_at.is_(None))).all()}
    if len(picked) != 2:
        raise HTTPException(404, "both images must belong to this video")
    a, b = (picked[i] for i in ids)
    if a.frame_index is None or b.frame_index is None:
        raise HTTPException(400, "images have no frame index")
    if a.frame_index > b.frame_index:
        a, b = b, a
    span = b.frame_index - a.frame_index
    if span < 1:
        raise HTTPException(400, "choose two different frames")
    if span > MAX_INTERPOLATION_SPAN:
        raise HTTPException(409, f"interpolation is limited to {MAX_INTERPOLATION_SPAN} frames")

    middle = c.db.scalars(select(Image).where(
        Image.project_id == c.project.id, Image.video_id == v.id, Image.deleted_at.is_(None),
        Image.frame_index > a.frame_index, Image.frame_index < b.frame_index)
        .order_by(Image.frame_index.asc())).all()
    tracks = ({x.get("trackId") for x in a.annotations or []}
              & {x.get("trackId") for x in b.annotations or []}) - {None}
    frames = [(a.frame_index, a.annotations or [])]
    frames += [(i.frame_index, i.annotations or []) for i in middle]
    frames.append((b.frame_index, b.annotations or []))
    writes = video_svc.interpolate_tracks(frames, a.frame_index, b.frame_index)

    by_index = {i.frame_index: i for i in middle}
    written = 0
    for index, new_anns in writes.items():
        img = by_index.get(index)
        if img is None:
            continue
        current = list(img.annotations or [])
        for new in new_anns:
            slot = next((k for k, x in enumerate(current)
                         if x.get("trackId") == new["trackId"] and not x.get("keyframe")), None)
            if slot is None:
                current.append(new)
            else:
                current[slot] = new
        set_annotations(c.db, img, current)
        written += len(new_anns)

    for endpoint in (a, b):                       # the two edited frames are the keyframes
        anns = [{**x, "keyframe": True} if x.get("trackId") in tracks else x for x in endpoint.annotations or []]
        set_annotations(c.db, endpoint, anns)
    c.db.commit()
    return {"frames": len(middle), "annotations": written}


class TrackIn(BaseModel):
    annotation_id: str
    frames: int = 30


@router.post("/api/images/{image_id}/track-forward")
def track_forward(image_id: str, body: TrackIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    c, img = image_ctx(db, u, image_id)
    if not img.video_id:
        raise HTTPException(400, "this image is not part of a video")
    if not any(a.get("id") == body.annotation_id for a in img.annotations or []):
        raise HTTPException(404, "annotation not found")
    c.need("annotator")
    if not 1 <= body.frames <= 120:
        raise HTTPException(400, "frames must be between 1 and 120")
    j = Job(workspace_id=c.ws.id, project_id=c.project.id, kind="track_forward", created_by=c.user.id,
            params={"image_id": image_id, "annotation_id": body.annotation_id, "frames": body.frames,
                    "created_by": c.user.id})
    db.add(j)
    db.commit()
    return job_out(j)
