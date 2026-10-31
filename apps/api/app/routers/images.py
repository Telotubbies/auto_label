"""Upload, dataset browse/filter/bulk, annotation save, review, comments, kanban board, AI assists."""
import hashlib
import json
import random
import re
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import String, case, cast, exists, func, select
from sqlalchemy import delete as sa_delete
from sqlalchemy.orm import defer
from sqlalchemy.orm import Session

from ..config import MAX_UPLOAD_MB
from ..db import get_db
from ..deps import Ctx, audit, current_user, image_ctx, plan, project_ctx
from ..models import SPLITS, STATUSES, Batch, Comment, Image, ImageClass, Member, Project, TrainedModel, User, new_id, now, set_annotations
from ..ratelimit import limit
from ..security import sign_path
from ..services import imaging, importers, ml, segment
from .projects import ensure_class

router = APIRouter(tags=["images"])
P = "/api/ws/{ws}/projects/{project}"


def safe_name(path: str) -> str:
    """Display name only: last path segment, no separators/control chars (names reach export file names)."""
    name = re.split(r"[\/]", path)[-1]
    name = re.sub(r"[^\w.\- ()]+", "_", name).strip(". ") or "image.jpg"
    return name[:200]


def image_out(i: Image, full: bool = False, class_ids: list[str] | None = None) -> dict:
    out = {"id": i.id, "name": i.name, "width": i.width, "height": i.height, "split": i.split, "status": i.status,
           "assigneeId": i.assignee_id, "review": i.review, "tags": i.tags or [], "batchId": i.batch_id,
           "annotated": i.n_annotations > 0, "annotationCount": i.n_annotations, "created": i.created,
           "thumbnail": sign_path(i.thumb), "url": sign_path(i.path),
           "classIds": class_ids if class_ids is not None else sorted({a.get("classId") for a in i.annotations or []})}
    if full:
        out["annotations"] = i.annotations or []
    return out


def _assigned(c: Ctx, img: Image) -> tuple[Ctx, Image]:
    """Labelers may only touch images assigned to them; reviewers/admins see everything."""
    if c.role == "annotator" and img.assignee_id != c.user.id:
        raise HTTPException(403, "this image is not assigned to you")
    return c, img


def _visible(q, c: Ctx):
    """Annotators only ever see images assigned to them."""
    return q.where(Image.assignee_id == c.user.id) if c.role == "annotator" else q


# --- upload -------------------------------------------------------------------------------

class HashesIn(BaseModel):
    hashes: list[str]


@router.post(P + "/uploads/check")
def check(body: HashesIn, c: Ctx = Depends(project_ctx)):
    rows = c.db.scalars(select(Image.sha256).where(Image.project_id == c.project.id, Image.sha256.in_(body.hashes[:5000]),
                                                   Image.deleted_at.is_(None))).all()
    return {"duplicates": sorted(set(rows))}


def ingest(db: Session, c: Ctx, files: list[tuple[str, bytes]], batch_name: str, split: str, tags: list[str],
           source: str = "upload", to_dataset: bool = True, user_id: str | None = None) -> dict:
    p = c.project
    try:
        bundle = importers.collect(files)
    except importers.ImportError_ as e:
        raise HTTPException(400, str(e))
    if not bundle.images:
        raise HTTPException(400, "no images found (supported: jpg, png, bmp, webp, tif — loose or in a .zip)")
    have = db.scalar(select(func.count(Image.id)).join(Project).where(Project.workspace_id == c.ws.id, Image.deleted_at.is_(None)))
    if have + len(bundle.images) > plan(c.ws)["images"]:
        raise HTTPException(402, f"image limit reached on the {plan(c.ws)['label']} plan")
    batch = Batch(project_id=p.id, name=batch_name or time.strftime("Uploaded on %b %d, %Y %H:%M"), source=source,
                  created_by=user_id)
    db.add(batch); db.flush()
    known = set(db.scalars(select(Image.sha256).where(Image.project_id == p.id, Image.deleted_at.is_(None))))
    rng = random.Random()
    out, dups, annotated = [], 0, 0
    for path, data in sorted(bundle.images.items()):
        h = hashlib.sha256(data).hexdigest()
        if h in known:
            dups += 1; continue
        known.add(h)
        try:
            im = imaging.open_image(data)
        except Exception:
            continue
        img = Image(id=new_id(), project_id=p.id, batch_id=batch.id, name=safe_name(path), sha256=h, width=im.width,
                    height=im.height, size=len(data), path="", thumb="", tags=list(tags))
        img.path, img.thumb = imaging.store(f"projects/{p.id}/images", img.id, im)
        anns = []
        if p.type == "classification":
            cls = importers.folder_class(path)
            if cls and bundle.images and "/" in path:
                anns.append({"id": "a" + h[:10], "classId": ensure_class(db, p, cls).id, "shape": {"kind": "class"}})
        for k, (cls, shape) in enumerate(importers.annotations_for(bundle, path, im.width, im.height)):
            if p.type == "object-detection" and shape["kind"] == "polygon":
                pts = shape["points"]
                xs, ys = pts[0::2], pts[1::2]
                shape = {"kind": "bbox", "x": min(xs), "y": min(ys), "w": max(xs) - min(xs), "h": max(ys) - min(ys)}
            anns.append({"id": f"a{h[:8]}{k}", "classId": ensure_class(db, p, cls).id, "shape": shape})
        img.split = (importers.split_of(path) if split == "keep" else None) or (
            split if split in SPLITS else ("train" if (r := rng.random()) < 0.7 else "valid" if r < 0.9 else "test"))
        if anns:
            annotated += 1
            img.status = "done" if to_dataset else "review"
        db.add(img)
        set_annotations(db, img, anns)
        out.append(img)
    p.updated = now()
    audit(db, c.ws.id, user_id, "image.upload", p.name, images=len(out), duplicates=dups, source=source)
    db.commit()
    return {"batch": {"id": batch.id, "name": batch.name}, "uploaded": len(out), "duplicates": dups,
            "annotated": annotated, "images": [image_out(i) for i in out[:200]]}


@router.post(P + "/upload")
async def upload(files: list[UploadFile] = File(...), batch_name: str = Form(""), split: str = Form("auto"),
                 tags: str = Form(""), to_dataset: bool = Form(True), c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    if len(files) > 2000:
        raise HTTPException(413, "max 2000 files per request — the web uploader sends batches")
    budget = MAX_UPLOAD_MB * 1024 * 1024
    payload = []
    for f in files:
        data = await f.read(budget + 1)
        budget -= len(data)
        if budget < 0:
            raise HTTPException(413, f"upload larger than {MAX_UPLOAD_MB} MB")
        payload.append((f.filename or "file", data))
    return ingest(c.db, c, payload, batch_name, split, [t.strip() for t in tags.split(",") if t.strip()],
                  to_dataset=to_dataset, user_id=c.user.id)


# --- browse -----------------------------------------------------------------------------------

@router.get(P + "/images")
def list_images(q: str = "", split: str = "", status: str = "", class_id: str = "", tag: str = "", batch_id: str = "",
                annotated: str = "", assignee: str = "", sort: str = "newest", offset: int = 0, limit: int = 100,
                c: Ctx = Depends(project_ctx)):
    s = _visible(select(Image).where(Image.project_id == c.project.id, Image.deleted_at.is_(None)), c)
    if q:
        s = s.where(Image.name.ilike(f"%{q.replace('%', '').replace('_', '')}%"))
    if split:
        s = s.where(Image.split == split)
    if status:
        s = s.where(Image.status.in_(status.split(",")))
    if batch_id:
        s = s.where(Image.batch_id == batch_id)
    if assignee:
        s = s.where(Image.assignee_id == (None if assignee == "none" else assignee))
    if annotated == "yes":
        s = s.where(Image.n_annotations > 0)
    elif annotated == "no":
        s = s.where(Image.n_annotations == 0)
    if class_id:
        s = s.where(exists().where(ImageClass.image_id == Image.id, ImageClass.class_id == class_id))
    if tag:
        # tags is a JSON list; match the quoted element in its text form (portable sqlite/postgres)
        pat = json.dumps(tag).replace("\\", "\\\\").replace("%", "\%").replace("_", "\_")
        s = s.where(cast(Image.tags, String).like(f"%{pat}%", escape="\\"))
    total = c.db.scalar(select(func.count()).select_from(s.subquery()))
    order = {"newest": Image.created.desc(), "oldest": Image.created, "name": Image.name,
             "most": Image.n_annotations.desc(), "least": Image.n_annotations}.get(sort, Image.created.desc())
    rows = c.db.scalars(s.options(defer(Image.annotations)).order_by(order, Image.id)
                        .offset(max(0, offset)).limit(max(1, min(limit, 1000)))).all()
    by_img: dict[str, list[str]] = {}
    if rows:
        for iid, cid in c.db.execute(select(ImageClass.image_id, ImageClass.class_id)
                                     .where(ImageClass.image_id.in_([r.id for r in rows]))):
            by_img.setdefault(iid, []).append(cid)
    return {"total": total, "items": [image_out(r, class_ids=sorted(by_img.get(r.id, []))) for r in rows]}


class BulkIn(BaseModel):
    ids: list[str]
    action: str           # split | add_tag | remove_tag | delete | status | assign | clear_annotations
    value: str | None = None


@router.post(P + "/images/bulk")
def bulk(body: BulkIn, c: Ctx = Depends(project_ctx)):
    need = {"assign": "reviewer", "status": "reviewer", "delete": "reviewer", "clear_annotations": "reviewer"}
    c.need(need.get(body.action, "reviewer"))
    rows = c.db.scalars(select(Image).where(Image.project_id == c.project.id, Image.id.in_(body.ids))).all()
    v = body.value
    if body.action == "split" and v not in SPLITS:
        raise HTTPException(400, "bad split")
    if body.action == "status" and v not in STATUSES:
        raise HTTPException(400, "bad status")
    if body.action == "assign" and v and not c.db.get(Member, (c.ws.id, v)):
        raise HTTPException(400, "assignee is not a workspace member")
    for r in rows:
        if body.action == "split":
            r.split = v
        elif body.action == "add_tag" and v and v not in (r.tags or []):
            r.tags = [*(r.tags or []), v]
        elif body.action == "remove_tag":
            r.tags = [t for t in r.tags or [] if t != v]
        elif body.action == "delete":
            r.deleted_at = now()
            c.db.execute(sa_delete(ImageClass).where(ImageClass.image_id == r.id))   # deleted images drop out of counts
        elif body.action == "status":
            r.status = v
        elif body.action == "assign":
            r.assignee_id = v or None
            if v and r.status == "unassigned":
                r.status = "annotating"
        elif body.action == "clear_annotations":
            set_annotations(c.db, r, [])
        r.updated = now()
    audit(c.db, c.ws.id, c.user.id, f"image.bulk.{body.action}", c.project.name, count=len(rows), value=v)
    c.db.commit()
    return {"updated": len(rows)}


# --- annotate board (kanban) ----------------------------------------------------------------

@router.get(P + "/board")
def board(c: Ctx = Depends(project_ctx)):
    s = _visible(select(Image.batch_id, Image.assignee_id, Image.status, func.count(),
                        func.sum(case((Image.n_annotations > 0, 1), else_=0))).where(Image.project_id == c.project.id, Image.deleted_at.is_(None)), c)
    rows = c.db.execute(s.group_by(Image.batch_id, Image.assignee_id, Image.status)).all()
    batches = {b.id: b for b in c.db.scalars(select(Batch).where(Batch.project_id == c.project.id))}
    users = {u.id: u.name for u in c.db.scalars(select(User).join(Member, Member.user_id == User.id)
                                                .where(Member.workspace_id == c.ws.id))}
    cols = {s: [] for s in STATUSES}
    for bid, uid, status, n, done in rows:
        b = batches.get(bid)
        cols[status if status in cols else "unassigned"].append({
            "batchId": bid, "batchName": b.name if b else "Ungrouped", "created": b.created if b else 0,
            "assigneeId": uid, "assignee": users.get(uid), "images": n, "annotated": int(done or 0)})
    for v in cols.values():
        v.sort(key=lambda x: -x["created"])
    return {"columns": cols, "members": [{"id": k, "name": v} for k, v in users.items()]}


class BoardMove(BaseModel):
    batch_id: str | None = None
    from_status: str
    to_status: str
    assignee_id: str | None = None       # filter: card owner
    set_assignee: str | None = None      # when assigning
    only_annotated: bool = False


@router.post(P + "/board/move")
def board_move(body: BoardMove, c: Ctx = Depends(project_ctx)):
    """Move a kanban card (batch × assignee × status) to another column."""
    if body.to_status not in STATUSES:
        raise HTTPException(400, "bad status")
    # annotators may only submit their own work for review; everything else needs reviewer+
    if not (c.role == "annotator" and body.from_status == "annotating" and body.to_status == "review"):
        c.need("reviewer")
    s = _visible(select(Image).where(Image.project_id == c.project.id, Image.status == body.from_status,
                                     Image.deleted_at.is_(None), Image.batch_id == body.batch_id), c)
    if body.assignee_id is not None:
        s = s.where(Image.assignee_id == (body.assignee_id or None))
    if body.only_annotated:
        s = s.where(Image.n_annotations > 0)
    rows = c.db.scalars(s).all()
    if body.set_assignee and not c.db.get(Member, (c.ws.id, body.set_assignee)):
        raise HTTPException(400, "assignee is not a workspace member")
    for r in rows:
        r.status = body.to_status
        if body.set_assignee:
            r.assignee_id = body.set_assignee
        if body.to_status == "done":
            r.review = "approved"
        r.updated = now()
    audit(c.db, c.ws.id, c.user.id, "board.move", c.project.name, count=len(rows),
          to=body.to_status, frm=body.from_status)
    c.db.commit()
    return {"moved": len(rows)}


# --- single image -------------------------------------------------------------------------------

@router.get("/api/images/{image_id}")
def get_image(image_id: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    c, img = _assigned(*image_ctx(db, u, image_id))
    return image_out(img, full=True)


class AnnotationsIn(BaseModel):
    annotations: list[dict]


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and -0.5 <= v <= 1.5   # normalised, small overshoot ok


def _check_ann(a: dict) -> dict:
    if not isinstance(a, dict):
        raise HTTPException(400, "annotation must be an object")
    s = a.get("shape") or {}
    if not a.get("id") or not a.get("classId") or s.get("kind") not in ("bbox", "polygon", "class"):
        raise HTTPException(400, "each annotation needs id, classId and shape.kind in bbox|polygon|class")
    if not isinstance(a["id"], str) or not isinstance(a["classId"], str) or len(a["id"]) > 64 or len(a["classId"]) > 64:
        raise HTTPException(400, "bad id")
    if s["kind"] == "bbox":
        if not all(_num(s.get(k)) for k in "xywh"):
            raise HTTPException(400, "bbox needs normalised numeric x,y,w,h")
        shape = {"kind": "bbox", **{k: float(s[k]) for k in "xywh"}}
    elif s["kind"] == "polygon":
        pts = s.get("points")
        if not isinstance(pts, list) or not (6 <= len(pts) <= 20_000) or len(pts) % 2 or not all(_num(v) for v in pts):
            raise HTTPException(400, "polygon needs 3–10,000 normalised points")
        shape = {"kind": "polygon", "points": [float(v) for v in pts]}
    else:
        shape = {"kind": "class"}
    out = {"id": a["id"], "classId": a["classId"], "shape": shape}
    attrs = a.get("attributes")
    if isinstance(attrs, dict):
        out["attributes"] = {str(k)[:40]: bool(v) for k, v in list(attrs.items())[:32]}
    if _num(a.get("confidence")):
        out["confidence"] = float(a["confidence"])
    return out


@router.put("/api/images/{image_id}/annotations")
def save_annotations(image_id: str, body: AnnotationsIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if len(body.annotations) > 5000:
        raise HTTPException(413, "too many annotations on one image (max 5000)")
    c, img = _assigned(*image_ctx(db, u, image_id))
    set_annotations(db, img, [_check_ann(a) for a in body.annotations])
    if img.status == "unassigned" and img.n_annotations:
        img.status, img.assignee_id = "annotating", img.assignee_id or u.id
    img.updated = now()
    c.project.updated = now()
    db.commit()
    return {"saved": img.n_annotations, "status": img.status}


class ImagePatch(BaseModel):
    split: str | None = None
    tags: list[str] | None = None
    status: str | None = None


@router.patch("/api/images/{image_id}")
def patch_image(image_id: str, body: ImagePatch, u: User = Depends(current_user), db: Session = Depends(get_db)):
    c, img = _assigned(*image_ctx(db, u, image_id))
    if body.split:
        c.need("reviewer")
        if body.split not in SPLITS:
            raise HTTPException(400, "bad split")
        img.split = body.split
    if body.tags is not None:
        img.tags = list(dict.fromkeys(t.strip()[:64] for t in body.tags if t.strip()))[:50]
    if body.status:
        if body.status not in STATUSES:
            raise HTTPException(400, "bad status")
        if not (c.role == "annotator" and body.status == "review" and img.assignee_id == u.id):
            c.need("reviewer")
        img.status = body.status
    img.updated = now(); db.commit()
    return image_out(img, full=True)


@router.delete("/api/images/{image_id}")
def delete_image(image_id: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    c, img = _assigned(*image_ctx(db, u, image_id))
    c.need("reviewer")
    img.deleted_at = now()
    db.execute(sa_delete(ImageClass).where(ImageClass.image_id == img.id))
    db.commit()
    return {"ok": True}


class ReviewIn(BaseModel):
    approved: bool
    note: str | None = None


@router.post("/api/images/{image_id}/review")
def review(image_id: str, body: ReviewIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    c, img = _assigned(*image_ctx(db, u, image_id))
    c.need("reviewer")
    img.review = "approved" if body.approved else "rejected"
    img.status = "done" if body.approved else "annotating"
    if body.note:
        db.add(Comment(image_id=img.id, user_id=u.id, text=("✓ " if body.approved else "✗ Rejected: ") + body.note))
    audit(db, c.ws.id, u.id, "image.review", img.name, approved=body.approved)
    img.updated = now(); db.commit()
    return image_out(img, full=True)


class CommentIn(BaseModel):
    text: str


@router.get("/api/images/{image_id}/comments")
def comments(image_id: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    _assigned(*image_ctx(db, u, image_id))
    rows = db.scalars(select(Comment).where(Comment.image_id == image_id).order_by(Comment.created)).all()
    return [{"id": r.id, "author": r.user.name, "text": r.text, "at": r.created * 1000} for r in rows]


@router.post("/api/images/{image_id}/comments")
def add_comment(image_id: str, body: CommentIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    _assigned(*image_ctx(db, u, image_id))
    if not body.text.strip():
        raise HTTPException(400, "empty comment")
    r = Comment(image_id=image_id, user_id=u.id, text=body.text.strip()[:4000])
    limit(f"comment:{u.id}", 30, 60)
    db.add(r); db.commit()
    return {"id": r.id, "author": u.name, "text": r.text, "at": r.created * 1000}


# --- AI assists --------------------------------------------------------------------------------

class SmartIn(BaseModel):
    points: list[list[float]]
    negatives: list[list[float]] = []


@router.post("/api/images/{image_id}/smart-polygon")
def smart_polygon(image_id: str, body: SmartIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    c, img = _assigned(*image_ctx(db, u, image_id))
    if not body.points:
        raise HTTPException(400, "click at least one point")
    poly, source = segment.smart_polygon(imaging.load(img.path), body.points, body.negatives)
    if not poly:
        raise HTTPException(422, "could not find an object at those points — try clicking nearer its centre")
    return {"polygon": poly, "source": source}


class AssistIn(BaseModel):
    model_id: str
    confidence: float = 0.4


@router.post("/api/images/{image_id}/label-assist")
def label_assist(image_id: str, body: AssistIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    c, img = _assigned(*image_ctx(db, u, image_id))
    m = db.get(TrainedModel, body.model_id)
    if not m or m.workspace_id != c.ws.id or m.status != "ready":
        raise HTTPException(404, "model not ready")
    from .projects import classes_out
    by_name = {x["name"]: x["id"] for x in classes_out(db, c.project)}
    for name in m.classes:              # model classes missing from this project get created
        if name not in by_name:
            by_name[name] = ensure_class(db, c.project, name).id
    db.commit()
    pred = ml.predict(m.weights, imaging.load(img.path), body.confidence)
    return {"annotations": ml.to_annotations(pred, by_name)}
