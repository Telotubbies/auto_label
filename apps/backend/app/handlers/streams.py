"""Video frames and SAM tracking: the ``extract_frames`` and ``track_forward`` kinds.

Handlers resolve their runner dependencies through ``app.worker`` (``w.plan``, ``w.ADAPTERS``,
``w.QuotaExhausted``, ``w._set``, ``w._cancelled``) so the process that swaps one of them at runtime
keeps working.
"""
import hashlib
import io
import logging
from pathlib import Path

import cv2
from PIL import Image as PImage
from sqlalchemy import func, select

from ..config import DATA_DIR
from ..db import SessionLocal
from ..errors import safe_error
from ..models import Batch, Image, Project, Video, Workspace, new_id, set_annotations
from ..services import faceblur, imaging, metering, quality, track
from ..services.video import DEFAULT_SCENE_THRESHOLD, is_scene_change, plan_frames

log = logging.getLogger("labeldesk.worker")     # same logger the runner used before the split


def run_extract_frames(job):
    """Sample a video into a batch of JPEG frames (fps / every N seconds / scene cuts)."""
    from .. import worker as w
    P = job.params
    with SessionLocal() as db:
        v = db.get(Video, P["video_id"])
        if v is None or v.deleted_at:
            raise RuntimeError("video not found")
        p = db.get(Project, v.project_id)
        ws = db.get(Workspace, v.workspace_id)
        image_limit = int(w.plan(ws)["images"])
        have = int(db.scalar(select(func.count(Image.id)).join(Project)
                             .where(Project.workspace_id == ws.id, Image.deleted_at.is_(None))) or 0)
        if p.face_blur and not faceblur.available():
            v.status, v.error = "failed", "face blur is enabled but the face detector is unavailable"
            db.commit()
            raise RuntimeError("face blur is enabled but the face detector is unavailable")
        v.status, v.error = "extracting", ""
        db.commit()

        cap = cv2.VideoCapture(str(DATA_DIR / v.path))
        out_w = out_h = 0
        try:
            if not cap.isOpened():
                v.status, v.error = "failed", "video could not be opened"
                db.commit()
                raise RuntimeError("video could not be opened")

            # Trust the row when an earlier probe filled it; otherwise read it from the container.
            frame_count = v.frame_count or int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            fps = v.fps or float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            width = v.width or int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = v.height or int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            mode = P.get("mode", "fps")
            target_fps = float(P.get("target_fps") or 1.0)
            every_s = float(P.get("every_s") or 1.0)
            threshold = float(P.get("scene_threshold") or DEFAULT_SCENE_THRESHOLD)
            planned = set(plan_frames(frame_count, fps, mode, target_fps, every_s)) if (
                mode != "scene" and frame_count > 0 and fps > 0) else None
            step = max(1, round(fps * every_s) if mode == "every" else round(fps / target_fps)) if fps > 0 else 1
            storage_room = metering.remaining(db, ws, "storage_bytes")   # I8: frames are storage too

            batch = Batch(project_id=p.id, name=f"Video · {v.name}", source="video", created_by=P.get("created_by"))
            db.add(batch)
            db.flush()
            known = set(db.scalars(select(Image.sha256).where(Image.project_id == p.id, Image.deleted_at.is_(None))))
            stem = Path(v.name).stem or "video"
            kept = read = 0
            kept_bytes = 0
            last_kept_time = -1.0
            prev_hist = None
            while True:
                if w._cancelled(job.id):
                    break
                ok, frame = cap.read()
                if not ok or frame is None:
                    break
                index = read
                read += 1
                if mode == "scene":
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    hist = cv2.calcHist([gray], [0], None, [64], [0, 256])
                    cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
                    at = index / fps if fps > 0 else float(index)
                    keep = prev_hist is None or (at - last_kept_time >= 0.5
                                                 and is_scene_change(prev_hist, hist, threshold))
                    prev_hist = hist
                elif planned is not None:
                    keep = index in planned
                else:
                    keep = index % step == 0           # container did not report a frame count
                if not keep or kept >= 2000:
                    continue
                if have + kept + 1 > image_limit:
                    raise w.QuotaExhausted(f"image limit reached on the {w.plan(ws)['label']} plan — "
                                           f"{image_limit - have} frame slots left")

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                im = PImage.fromarray(rgb)
                if p.face_blur and not faceblur.available():
                    raise RuntimeError("face blur is enabled but the face detector is unavailable")
                if p.face_blur:                          # PDPA: blur before the bytes are stored
                    im, _ = faceblur.blur_faces(im)
                buf = io.BytesIO()
                im.save(buf, "JPEG", quality=92)
                data = buf.getvalue()
                if kept_bytes + len(data) > storage_room:   # I8: frames are billable storage too
                    raise w.QuotaExhausted(f"Storage quota reached on the {w.plan(ws)['label']} plan")
                digest = hashlib.sha256(data).hexdigest()
                if digest in known:                     # identical frame (long still, duplicate upload)
                    continue
                known.add(digest)
                im = imaging.open_image(data)
                out_w, out_h = out_w or im.width, out_h or im.height
                # frames bypass ingest(); score them here, where the pixels are already decoded
                sharpness, luminance = quality.analyze(im)
                img = Image(id=new_id(), project_id=p.id, batch_id=batch.id, video_id=v.id, frame_index=index,
                            name=f"{stem}_f{index:06d}.jpg", sha256=digest, width=im.width, height=im.height,
                            size=len(data), path="", thumb="", split="train", status="unassigned", tags=[],
                            assignee_id=P.get("created_by"), sharpness=sharpness, luminance=luminance)
                img.path, img.thumb = imaging.store(f"projects/{p.id}/images", img.id, im)
                db.add(img)
                set_annotations(db, img, [])
                metering.record(db, ws.id, "storage_bytes", len(data), project_id=p.id, image_id=img.id)
                kept_bytes += len(data)
                kept += 1
                if mode == "scene" and fps > 0:
                    last_kept_time = index / fps
                if kept % 10 == 0:                    # commit + report progress in one pause
                    db.commit()
                    w._set(job.id, progress=round(min(99.0, (index + 1) / frame_count * 100), 1)
                           if frame_count else 0.0)

            v.status = "ready"
            v.error = ""
            v.frame_count = frame_count or read
            v.fps = fps
            v.duration = v.frame_count / fps if fps > 0 else 0.0
            v.width, v.height = width or out_w, height or out_h
            v.batch_id = batch.id
            db.commit()
            return {"video_id": v.id, "frames": kept, "batch_id": batch.id}
        except Exception as exc:
            if v.status != "failed":
                v.status, v.error = "failed", safe_error(exc, "extract_frames")[:500]
                db.commit()
            raise
        finally:
            cap.release()


def run_track_forward(job):
    """SAM box-prompt tracking: copy one annotation onto the next N frames of its video."""
    from .. import jobs, worker as w
    P = job.params
    with SessionLocal() as db:
        src = db.get(Image, P["image_id"])
        if src is None or src.deleted_at:
            raise RuntimeError("image not found")
        ann = next((a for a in src.annotations or [] if a.get("id") == P["annotation_id"]), None)
        if ann is None:
            raise RuntimeError("annotation not found")
        v = db.get(Video, src.video_id) if src.video_id else None
        if v is None:
            raise RuntimeError("image is not part of a video")
        p = db.get(Project, src.project_id)
        limit = max(1, min(int(P.get("frames") or 30), 120))
        start = src.frame_index if src.frame_index is not None else -1
        targets = db.scalars(select(Image).where(
            Image.project_id == p.id, Image.video_id == v.id, Image.frame_index > start,
            Image.deleted_at.is_(None)).order_by(Image.frame_index.asc()).limit(120)).all()[:limit]
        pairs = []
        for target in targets:
            if w._cancelled(job.id):
                break
            try:
                pairs.append((target, imaging.load(target.path)))
            except Exception as e:                      # a missing file must not stop the whole track
                log.warning("track-forward skipped unreadable frame %s: %s", target.id, e)
        adapter = w.ADAPTERS.get("sam3")
        sam_box = adapter.segment_box if adapter is not None else None
        jobs.check(job)                                 # I22: no writes after the user cancelled
        shapes = track.track_forward([im for _, im in pairs], ann.get("shape") or {}, sam_box=sam_box,
                                     project_type=p.type)
        track_id = ann.get("trackId") or f"t{new_id()}"
        # The seed joins its own track as a keyframe, so a later "Set start" is a real interpolation start.
        seed_anns = [{**a, "trackId": track_id, "keyframe": True} if a.get("id") == ann.get("id") else a
                     for a in src.annotations or []]
        set_annotations(db, src, seed_anns)
        db.commit()
        written = 0
        for (target, _im), shape in zip(pairs, shapes):
            anns, keep = track.merge_track(target.annotations or [], {
                "id": "a" + new_id(), "classId": ann["classId"], "shape": shape, "source": "sam3",
                "trackId": track_id, "keyframe": False}, track_id)
            if keep:
                set_annotations(db, target, anns)
                db.commit()
                written += 1
            w._set(job.id, progress=round((written + 1) / max(1, len(pairs)) * 100, 1))
        return {"image_id": src.id, "tracked": written, "track_id": track_id}


HANDLERS = {"extract_frames": run_extract_frames, "track_forward": run_track_forward}
