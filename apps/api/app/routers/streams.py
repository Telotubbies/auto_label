"""Streams API: CRUD, signed live views, rule events, review and dataset ingest."""
import secrets
import shutil
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete as sa_delete, func, select

from ..adapters import resolve
from ..config import DATA_DIR, MAX_UPLOAD_MB, PLANS
from ..db import SessionLocal
from ..deps import Ctx, audit, project_ctx
from ..models import Project, Stream, StreamEvent, UsageEvent, Workspace
from ..security import check_signature, sign_path, sign_query
from ..services import metering
from ..streams import creds
from ..streams.event_fields import class_key
from ..services.flags import require_workspace_flag
from ..streams.manager import check_source, display_source, manager
from .images import ingest, safe_name

P = "/api/ws/{ws}/projects/{project}/streams"
router = APIRouter(prefix=P, tags=["streams"])
# Gated per route, not on the router: stop/delete stay reachable while task_10b is off, so the
# kill switch never goes dark on a camera that is still capturing (I-2).
_GATE = [Depends(require_workspace_flag("task_10b"))]

VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}
TOKEN_TTL = 12 * 3600
_MODEL_MSG = "stream model must be ultralytics:*, trained:* or tensorrt:*"
_RULE_KINDS = {"count", "zone", "line", "dwell", "vlm"}
_OPS = {">=", ">", "<=", "<", "=="}


# --- signed frame / MJPEG urls (an <img src> cannot send a bearer header) ------

def _view_rel(ws: str, project: str, sid: str, kind: str) -> str:
    """The API-relative route path the audit middleware checks the signature against (Task 26)."""
    return f"ws/{ws}/projects/{project}/streams/{sid}/{kind}"


def _view_query(c: Ctx, sid: str, kind: str) -> str:
    """Sign a footage URL for the current user, so every watched frame is attributable."""
    return sign_query(_view_rel(c.ws.slug, c.project.slug, sid, kind), TOKEN_TTL, viewer=c.user.id)


def _check_view(ws: str, project: str, sid: str, kind: str, exp: int, sig: str, viewer: str) -> None:
    if not (sig and viewer) or not check_signature(_view_rel(ws, project, sid, kind), exp, sig, viewer):
        raise HTTPException(403, "bad or expired signature")


# --- serialisation ------------------------------------------------------------

def event_out(ev: StreamEvent) -> dict:
    return {"id": ev.id, "ts": ev.ts, "rule": ev.rule or {}, "summary": ev.summary or "",
            "snapshot": sign_path(ev.snapshot_path) if ev.snapshot_path else None,
            "reviewed": bool(ev.reviewed), "predictions": ev.predictions or []}


def stream_out(c: Ctx, s: Stream) -> dict:
    live = manager.status(s.id)
    events = c.db.scalar(select(func.count(StreamEvent.id)).where(StreamEvent.stream_id == s.id)) or 0
    base = f"/api/ws/{c.ws.slug}/projects/{c.project.slug}/streams/{s.id}"
    return {"id": s.id, "name": s.name, "source": creds.mask_source(s.source), "modelRef": s.model_ref,
            "sampleFps": s.sample_fps, "zones": s.zones or [], "rules": s.rules or [],
            "status": live["status"] if live else s.status,
            "lastError": live["last_error"] if live else (s.last_error or ""),
            "fps": live["fps"] if live else 0.0,
            "frames": live["frames"] if live else 0,
            "detections": live["detections"] if live else 0,
            "events": events,
            "mjpeg": f"{base}/mjpeg?{_view_query(c, s.id, 'mjpeg')}",
            "frame": f"{base}/frame?{_view_query(c, s.id, 'frame')}",
            "created": s.created}


def _get(c: Ctx, sid: str) -> Stream:
    s = c.db.get(Stream, sid)
    if s is None or s.workspace_id != c.ws.id or s.project_id != c.project.id:
        raise HTTPException(404, "stream not found")
    return s


def _unlink_stored(rel_paths: list[str]) -> int:
    """Delete the event files of a removed stream and return the bytes actually freed.

    Anything outside DATA_DIR is left alone. A file still held open on Windows is left for the
    retention job instead of failing the delete, and is not credited because it still exists.
    """
    freed = 0
    for rel in dict.fromkeys(rel_paths):
        path = (DATA_DIR / rel).resolve()
        if DATA_DIR not in path.parents:
            continue
        try:
            size = path.stat().st_size
            path.unlink()
        except OSError:
            continue
        freed += size
    return freed


# --- validation ---------------------------------------------------------------

def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_fps(v) -> float:
    if not _num(v) or not 0.5 <= v <= 30:
        raise HTTPException(400, "sample_fps must be between 0.5 and 30")
    return float(v)


def check_zones(zones: list) -> list[dict]:
    if not isinstance(zones, list):
        raise HTTPException(400, "zones must be a list")
    out, ids = [], set()
    for z in zones:
        if not isinstance(z, dict) or not isinstance(z.get("id"), str) or not z["id"].strip():
            raise HTTPException(400, "each zone needs an id")
        zid = z["id"].strip()
        if len(zid) > 64:
            raise HTTPException(400, "zone ids are limited to 64 characters")
        if zid in ids:
            raise HTTPException(400, f"duplicate zone id {zid!r}")
        pts = z.get("points")
        if (not isinstance(pts, list) or len(pts) < 6 or len(pts) > 4000 or len(pts) % 2
                or not all(_num(v) and 0 <= v <= 1 for v in pts)):
            raise HTTPException(400, "zone points must be normalised x,y pairs (3-2000 points)")
        ids.add(zid)
        zone = {"id": zid, "points": [float(v) for v in pts]}
        if isinstance(z.get("label"), str):
            zone["label"] = z["label"][:120]
        out.append(zone)
    return out


def check_rules(rules: list, zone_ids: set[str]) -> list[dict]:
    if not isinstance(rules, list):
        raise HTTPException(400, "rules must be a list")
    out = []
    for r in rules:
        if not isinstance(r, dict) or r.get("kind") not in _RULE_KINDS:
            raise HTTPException(400, f"rule kind must be one of {sorted(_RULE_KINDS)}")
        kind = r["kind"]
        if kind == "vlm":
            q, every = r.get("question"), r.get("every_s", 30)
            if not isinstance(q, str) or not q.strip():
                raise HTTPException(400, "vlm rules need a question")
            if not _num(every) or every <= 0:
                raise HTTPException(400, "every_s must be a positive number")
            out.append({"kind": "vlm", "question": q.strip()[:500], "every_s": float(every)})
            continue
        cls = r.get("class")
        if not isinstance(cls, str) or not cls.strip():
            raise HTTPException(400, "rules need a class")
        cls = cls.strip()[:120]
        if kind == "count":
            op, k, for_s = r.get("op", ">="), r.get("k"), r.get("for_s", 0)
            if op not in _OPS or not isinstance(k, int) or isinstance(k, bool) or k < 0:
                raise HTTPException(400, "count rules need op, k")
            if not _num(for_s) or for_s < 0:
                raise HTTPException(400, "for_s must be a non-negative number")
            out.append({"kind": "count", "class": cls, "op": op, "k": k, "for_s": float(for_s)})
        elif kind == "zone":
            zid = r.get("zone_id")
            if not isinstance(zid, str) or zid not in zone_ids:
                raise HTTPException(400, f"zone rule references an unknown zone_id {zid!r}")
            out.append({"kind": "zone", "class": cls, "zone_id": zid})
        elif kind == "line":
            line, direction = r.get("line"), r.get("direction", "both")
            if (not isinstance(line, list) or len(line) != 4
                    or not all(_num(v) and 0 <= v <= 1 for v in line)):
                raise HTTPException(400, "line rules need normalised [x1, y1, x2, y2]")
            if direction not in ("in", "out", "both"):
                raise HTTPException(400, "line direction must be in, out or both")
            out.append({"kind": "line", "class": cls, "line": [float(v) for v in line], "direction": direction})
        else:                                        # dwell
            zid, seconds = r.get("zone_id"), r.get("seconds")
            if not isinstance(zid, str) or zid not in zone_ids:
                raise HTTPException(400, f"dwell rule references an unknown zone_id {zid!r}")
            if not _num(seconds) or seconds <= 0:
                raise HTTPException(400, "dwell seconds must be positive")
            out.append({"kind": "dwell", "class": cls, "zone_id": zid, "seconds": float(seconds)})
    return out


def check_model(c: Ctx, ref: str) -> str:
    if not isinstance(ref, str) or ":" not in ref:
        raise HTTPException(400, _MODEL_MSG)
    ref = ref.strip()[:255]
    try:
        resolved = resolve(ref, c.db, workspace_id=c.ws.id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if resolved.adapter.family not in ("ultralytics", "tensorrt"):
        raise HTTPException(400, _MODEL_MSG)
    return ref


# --- CRUD ---------------------------------------------------------------------

class StreamIn(BaseModel):
    name: str
    source: str
    model_ref: str
    sample_fps: float = 5
    zones: list = Field(default_factory=list)
    rules: list = Field(default_factory=list)


@router.post("", dependencies=_GATE)
def create(body: StreamIn, c: Ctx = Depends(project_ctx)):
    c.need("admin")
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "name and source are required")
    try:
        source = creds.seal_source(check_source(body.source))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    zones = check_zones(body.zones)
    rules = check_rules(body.rules, {z["id"] for z in zones})
    s = Stream(workspace_id=c.ws.id, project_id=c.project.id, name=name[:255], source=source,
               model_ref=check_model(c, body.model_ref), sample_fps=check_fps(body.sample_fps),
               zones=zones, rules=rules, status="stopped")
    c.db.add(s)
    audit(c.db, c.ws.id, c.user.id, "stream.create", s.name, source=creds.mask_source(s.source), model=s.model_ref)
    c.db.commit()
    return stream_out(c, s)


@router.get("", dependencies=_GATE)
def list_streams(c: Ctx = Depends(project_ctx)):
    c.perm("project.streams")
    rows = c.db.scalars(select(Stream).where(Stream.workspace_id == c.ws.id, Stream.project_id == c.project.id)
                        .order_by(Stream.created.desc(), Stream.id)).all()
    return [stream_out(c, s) for s in rows]


class StreamPatch(BaseModel):
    name: str | None = None
    source: str | None = None
    model_ref: str | None = None
    sample_fps: float | None = None
    zones: list | None = None
    rules: list | None = None


@router.get("/{sid}", dependencies=_GATE)
def get_stream(sid: str, c: Ctx = Depends(project_ctx)):
    c.perm("project.streams")
    return stream_out(c, _get(c, sid))


@router.patch("/{sid}", dependencies=_GATE)
def update_stream(sid: str, body: StreamPatch, c: Ctx = Depends(project_ctx)):
    c.need("admin")
    s = _get(c, sid)
    live = manager.status(sid) is not None
    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(400, "name must not be empty")
        s.name = body.name.strip()[:255]
    if body.source is not None:
        try:
            s.source = creds.seal_source(check_source(body.source))
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
    if body.model_ref is not None:
        s.model_ref = check_model(c, body.model_ref)
    if body.sample_fps is not None:
        s.sample_fps = check_fps(body.sample_fps)
    zones = check_zones(body.zones) if body.zones is not None else list(s.zones or [])
    rules = check_rules(body.rules, {z["id"] for z in zones}) if body.rules is not None else None
    if body.zones is not None:
        if body.rules is None:
            # An atomic edit supplies both fields: new rules were already validated against the new zones.
            check_rules(s.rules or [], {z["id"] for z in zones})   # no dangling zone_id after an edit
        s.zones = zones
    if rules is not None:
        s.rules = rules
    if live:
        manager.stop(sid)
    audit(c.db, c.ws.id, c.user.id, "stream.update", s.name, source=creds.mask_source(s.source), model=s.model_ref)
    c.db.commit()
    if live:
        manager.start(sid)
    c.db.refresh(s)                                  # manager.stop() persisted "stopped" from another session
    return stream_out(c, s)


@router.delete("/{sid}")
def delete_stream(sid: str, c: Ctx = Depends(project_ctx)):
    c.need("admin")
    s = _get(c, sid)
    try:
        source = creds.open_source(s.source)
    except ValueError:
        source = ""
    manager.stop(sid)
    event_ids = set(c.db.scalars(select(StreamEvent.id)
                                 .where(StreamEvent.stream_id == sid)).all())
    stored = [p for row in c.db.execute(select(StreamEvent.snapshot_path, StreamEvent.clean_path)
                                        .where(StreamEvent.stream_id == sid)).all() for p in row if p]
    c.db.execute(sa_delete(StreamEvent).where(StreamEvent.stream_id == sid))
    c.db.delete(s)
    audit(c.db, c.ws.id, c.user.id, "stream.delete", s.name)
    c.db.commit()
    freed = _unlink_stored(stored)
    shutil.rmtree(DATA_DIR / "streams" / sid, ignore_errors=True)   # pre-fix footage, keyed by stream
    if freed and event_ids:
        # I-1: the event JPEGs were billed with `stream_event=<eid>`; refund exactly what this
        # delete actually removed, bounded by what the workspace was charged for those events.
        metered = sum(float(row.quantity or 0.0) for row in c.db.scalars(
            select(UsageEvent).where(UsageEvent.project_id == c.project.id,
                                     UsageEvent.metric == "storage_bytes"))
            if (row.meta or {}).get("stream_event") in event_ids)
        refund = max(0.0, min(float(freed), metered))
        if refund:
            metering.adjust(c.db, c.ws, "storage_bytes", -refund, project_id=c.project.id,
                            stream="delete")
            c.db.commit()
    if source.startswith("file:videos/"):
        left = c.db.scalar(select(func.count(Stream.id)).where(Stream.source == source)) or 0
        if not left:                                  # demo uploads must not accumulate
            path = DATA_DIR / source[len("file:"):]
            freed = path.stat().st_size if path.is_file() else 0
            path.unlink(missing_ok=True)
            if freed:                                 # give the bytes back to the storage meter
                metering.adjust(c.db, c.ws, "storage_bytes", -freed, project_id=c.project.id)
                c.db.commit()
    return {"ok": True}


@router.post("/{sid}/start", dependencies=_GATE)
def start_stream(sid: str, c: Ctx = Depends(project_ctx)):
    c.need("admin")
    s = _get(c, sid)
    limits = PLANS.get(c.ws.plan, PLANS["free"])
    cap = int(limits.get("streams", 0))
    if cap and manager.active_count(c.ws.id, exclude=s.id) >= cap:
        raise HTTPException(402, f"Stream limit reached on the {limits['label']} plan")
    metering.check(c.db, c.ws, "stream_hours", 1 / 3600)
    try:
        manager.start(s.id)
    except KeyError:
        raise HTTPException(404, "stream not found")
    audit(c.db, c.ws.id, c.user.id, "stream.start", s.name)
    c.db.commit()
    return stream_out(c, s)


@router.post("/{sid}/stop")
def stop_stream(sid: str, c: Ctx = Depends(project_ctx)):
    c.need("admin")
    s = _get(c, sid)
    manager.stop(s.id)
    c.db.refresh(s)
    audit(c.db, c.ws.id, c.user.id, "stream.stop", s.name)
    c.db.commit()
    return stream_out(c, s)


@router.post("/upload-video", dependencies=_GATE)
async def upload_video(file: UploadFile = File(...), c: Ctx = Depends(project_ctx)):
    c.need("admin")
    original = file.filename or "clip"
    suffix = Path(original).suffix.lower()
    if suffix not in VIDEO_EXTS:
        raise HTTPException(400, f"unsupported video type {suffix or '(none)'}")
    budget = MAX_UPLOAD_MB * 1024 * 1024
    room = metering.remaining(c.db, c.ws, "storage_bytes")
    label = PLANS.get(c.ws.plan, PLANS["free"])["label"]
    folder = DATA_DIR / "videos"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{secrets.token_hex(4)}_{safe_name(original)}"
    dest = folder / name
    size = 0
    try:
        with dest.open("wb") as fh:                  # never hold a 1 GB upload in memory
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > budget:
                    raise HTTPException(413, f"upload larger than {MAX_UPLOAD_MB} MB")
                if size > room:                      # stream_uploads are billable storage (I8)
                    raise HTTPException(402, f"Storage quota reached on the {label} plan")
                fh.write(chunk)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    if size == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, "empty video")
    metering.record(c.db, c.ws.id, "storage_bytes", size, project_id=c.project.id, stream_upload=name)
    c.db.commit()
    return {"source": f"file:videos/{name}"}


# --- live views (signed, no bearer auth) ---------------------------------------

def _live_stream(ws: str, project: str, sid: str) -> None:
    """The token is the credential, but the URL must still name the stream's real workspace/project.

    Uses its own short session: the MJPEG response is endless, and FastAPI closes `Depends(get_db)`
    sessions only after the body finishes, which would pin a pooled connection per viewer.
    """
    with SessionLocal() as db:
        s = db.scalar(select(Stream).join(Project, Project.id == Stream.project_id)
                      .join(Workspace, Workspace.id == Stream.workspace_id)
                      .where(Stream.id == sid, Workspace.slug == ws, Project.slug == project,
                             Project.deleted_at.is_(None)))
        if s is None:
            raise HTTPException(404, "stream not found")


@router.get("/{sid}/frame", dependencies=_GATE)
def frame(ws: str, project: str, sid: str, exp: int = 0, sig: str = "", viewer: str = ""):
    _check_view(ws, project, sid, "frame", exp, sig, viewer)
    _live_stream(ws, project, sid)
    data = manager.latest_jpeg(sid)
    if data is None:
        raise HTTPException(503, "no frame yet")
    return Response(data, media_type="image/jpeg")


@router.get("/{sid}/mjpeg", dependencies=_GATE)
def mjpeg(ws: str, project: str, sid: str, exp: int = 0, sig: str = "", viewer: str = ""):
    _check_view(ws, project, sid, "mjpeg", exp, sig, viewer)
    _live_stream(ws, project, sid)

    def frames():
        last, last_frame = None, time.time()
        while True:
            data = manager.latest_jpeg(sid)
            if data is not None and data is not last:
                last, last_frame = data, time.time()
                yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                       + str(len(data)).encode() + b"\r\n\r\n" + data + b"\r\n")
            if time.time() - last_frame > 60:          # a dead source closes the view
                return
            time.sleep(0.1)                            # ~10 fps

    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")


# --- events -------------------------------------------------------------------

def _like(term: str) -> str:
    """Escape LIKE wildcards so a rule label or class name is matched literally."""
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


@router.get("/{sid}/events", dependencies=_GATE)
def list_events(sid: str, rule: str = "", klass: str = Query("", alias="class"), reviewed: str = "",
                kind: str = "", offset: int = 0, limit: int = 100, c: Ctx = Depends(project_ctx)):
    c.perm("project.streams")
    _get(c, sid)
    limit = max(1, min(limit, 500))
    if reviewed.lower() not in ("", "yes", "no", "true", "false", "1", "0"):
        raise HTTPException(400, "reviewed must be yes, no or omitted")
    # Filter and page in SQL: a long-running stream accumulates thousands of rows, each with up to
    # 50 predictions, and the timeline polls every 3 s. `rule_index/kind/label/classes` are the
    # denormalised columns the manager writes next to the JSON snapshot.
    where = [StreamEvent.stream_id == sid]
    if kind:
        where.append(StreamEvent.rule_kind == kind)
    if rule:
        try:                                         # "#2" selects rule 2; text matches the label
            index = int(rule.lstrip("#"))
        except ValueError:
            index = None
        if index is not None:
            where.append(StreamEvent.rule_index == index)
        else:
            where.append(StreamEvent.rule_label.ilike(_like(rule), escape="\\"))
    if klass:
        where.append(StreamEvent.classes.like(_like(class_key({klass})), escape="\\"))
    if reviewed:
        where.append(StreamEvent.reviewed == (reviewed.lower() in ("1", "true", "yes")))
    total = c.db.scalar(select(func.count()).select_from(StreamEvent).where(*where)) or 0
    rows = c.db.scalars(select(StreamEvent).where(*where)
                        .order_by(StreamEvent.ts.desc(), StreamEvent.id)
                        .offset(max(0, offset)).limit(limit)).all()
    return {"total": total, "items": [event_out(ev) for ev in rows]}


class ReviewIn(BaseModel):
    reviewed: bool


@router.patch("/{sid}/events/{eid}", dependencies=_GATE)
def patch_event(sid: str, eid: str, body: ReviewIn, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    _get(c, sid)
    ev = c.db.get(StreamEvent, eid)
    if ev is None or ev.stream_id != sid:
        raise HTTPException(404, "event not found")
    ev.reviewed = body.reviewed
    c.db.commit()
    return event_out(ev)


@router.post("/{sid}/events/{eid}/to-dataset", dependencies=_GATE)
def event_to_dataset(sid: str, eid: str, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    s = _get(c, sid)
    ev = c.db.get(StreamEvent, eid)
    if ev is None or ev.stream_id != sid:
        raise HTTPException(404, "event not found")
    # Reviewers see the annotated snapshot; the dataset must receive the untouched frame.
    rel = ev.clean_path or ev.snapshot_path        # fallback only for events captured before the fix
    if not rel:
        raise HTTPException(404, "snapshot not found")
    path = (DATA_DIR / rel).resolve()
    if DATA_DIR not in path.parents or not path.is_file():
        raise HTTPException(404, "clean frame not found" if ev.clean_path else "snapshot not found")
    res = ingest(c.db, c, [(f"{ev.id}.jpg", path.read_bytes())], f"{s.name} · stream event", "auto",
                 ["stream"], source="stream", to_dataset=True, user_id=c.user.id)
    audit(c.db, c.ws.id, c.user.id, "stream.event.to_dataset", s.name, event=ev.id, uploaded=res["uploaded"])
    c.db.commit()
    return {"uploaded": res["uploaded"], "duplicates": res["duplicates"]}
