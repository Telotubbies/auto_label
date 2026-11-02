"""Projects, classes, tags, batches, analytics, jobs."""
import re
import time
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..deps import Ctx, audit, plan, project_ctx, ws_ctx
from ..models import (PROJECT_TYPES, Batch, Image, ImageClass, Job, LabelClass, Project, TrainedModel, Version, now,
                      set_annotations)
from ..security import sign_path
from ..services import health

router = APIRouter(prefix="/api/ws/{ws}/projects", tags=["projects"])
PALETTE = ["#8b5cf6", "#22c55e", "#3b82f6", "#f97316", "#ec4899", "#eab308", "#14b8a6", "#ef4444",
           "#6366f1", "#84cc16", "#06b6d4", "#a855f7", "#f43f5e", "#10b981", "#0ea5e9", "#d946ef"]
# project slugs share the /:ws/<name> namespace with these workspace pages
RESERVED = {"models", "deployments", "activity", "settings", "qa"}


def job_out(j: Job) -> dict:
    return {"id": j.id, "kind": j.kind, "status": j.status, "progress": j.progress, "params": j.params,
            "result": j.result, "error": j.error, "created": j.created, "started": j.started, "finished": j.finished}


def _counts(db: Session, pids: list[str]) -> tuple[dict, dict, dict]:
    """(images, models, cover thumb) per project in three grouped queries."""
    live = (Image.project_id.in_(pids)) & Image.deleted_at.is_(None)
    imgs = dict(db.execute(select(Image.project_id, func.count()).where(live).group_by(Image.project_id)).all())
    models = dict(db.execute(select(TrainedModel.project_id, func.count()).where(TrainedModel.project_id.in_(pids))
                             .group_by(TrainedModel.project_id)).all())
    # cover = most-annotated image (first one wins on ties)
    best = select(Image.project_id, func.max(Image.n_annotations).label("m")).where(live).group_by(Image.project_id).subquery()
    covers = {}
    for pid, thumb in db.execute(select(Image.project_id, Image.thumb).join(
            best, (best.c.project_id == Image.project_id) & (best.c.m == Image.n_annotations)).where(live)):
        covers.setdefault(pid, thumb)
    return imgs, models, covers


def project_out(db: Session, p: Project, detail: bool = False, counts: tuple | None = None) -> dict:
    imgs, models, covers = counts or _counts(db, [p.id])
    cover = covers.get(p.id)
    out = {"id": p.id, "slug": p.slug, "name": p.name, "type": p.type, "visibility": p.visibility, "license": p.license,
           "annotationGroup": p.annotation_group, "multilabel": p.multilabel, "folderId": p.folder_id,
           "images": imgs.get(p.id, 0), "models": models.get(p.id, 0), "created": p.created, "updated": p.updated,
           "thumbnail": sign_path(cover) if cover else None, "settings": p.settings or {}}
    if detail:
        out["classes"] = classes_out(db, p)
        out["statusCounts"] = dict(db.execute(select(Image.status, func.count()).where(
            Image.project_id == p.id, Image.deleted_at.is_(None)).group_by(Image.status)).all())
    return out


def classes_out(db: Session, p: Project) -> list[dict]:
    rows = db.scalars(select(LabelClass).where(LabelClass.project_id == p.id).order_by(LabelClass.created)).all()
    # image_classes rows are removed when an image is soft-deleted, so no join is needed
    counts = dict(db.execute(select(ImageClass.class_id, func.sum(ImageClass.n))
                             .where(ImageClass.project_id == p.id).group_by(ImageClass.class_id)).all())
    return [{"id": c.id, "name": c.name, "color": c.color, "count": int(counts.get(c.id) or 0),
             "skeleton": c.skeleton} for c in rows]


# project slugs must not shadow workspace pages (mirrors apps/web/src/components/shell.tsx)
RESERVED = {"models", "deployments", "activity", "settings", "audit", "admin", "legal", "qa"}


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80] or "project"
    return f"{s}-project" if s in RESERVED else s


# --- projects ------------------------------------------------------------------------

@router.get("")
def list_projects(c: Ctx = Depends(ws_ctx)):
    rows = c.db.scalars(select(Project).where(Project.workspace_id == c.ws.id, Project.deleted_at.is_(None))
                        .order_by(Project.updated.desc())).all()
    counts = _counts(c.db, [p.id for p in rows])
    return [project_out(c.db, p, counts=counts) for p in rows]


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: str = "object-detection"
    visibility: str = "private"
    license: str = "CC BY 4.0"
    annotation_group: str = "objects"
    multilabel: bool = False
    folder_id: str | None = None
    classes: list[str] = []


@router.post("")
def create_project(body: ProjectIn, c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    if body.type not in PROJECT_TYPES:
        raise HTTPException(400, f"type must be one of {PROJECT_TYPES}")
    n = c.db.scalar(select(func.count(Project.id)).where(Project.workspace_id == c.ws.id, Project.deleted_at.is_(None)))
    if n >= plan(c.ws)["projects"]:
        raise HTTPException(402, f"project limit reached on the {plan(c.ws)['label']} plan")
    base = slugify(body.name); slug = base; i = 1
    while c.db.scalar(select(Project.id).where(Project.workspace_id == c.ws.id, Project.slug == slug)):
        i += 1; slug = f"{base}-{i}"
    p = Project(workspace_id=c.ws.id, slug=slug, name=body.name.strip(), type=body.type, visibility=body.visibility,
                license=body.license, annotation_group=body.annotation_group or "objects", multilabel=body.multilabel,
                folder_id=body.folder_id, settings={})
    c.db.add(p); c.db.flush()
    for k, name in enumerate(dict.fromkeys(n.strip() for n in body.classes if n.strip())):
        c.db.add(LabelClass(project_id=p.id, name=name, color=PALETTE[k % len(PALETTE)]))
    audit(c.db, c.ws.id, c.user.id, "project.create", p.name, type=p.type)
    c.db.commit()
    return project_out(c.db, p)


@router.get("/{project}")
def get_project(c: Ctx = Depends(project_ctx)):
    return {**project_out(c.db, c.project, detail=True), "role": c.role}


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    visibility: str | None = None
    license: str | None = None
    annotation_group: str | None = None
    folder_id: str | None = None
    settings: dict | None = None


@router.patch("/{project}")
def patch_project(body: ProjectPatch, c: Ctx = Depends(project_ctx)):
    c.need("admin")
    p = c.project
    for k in ("name", "visibility", "license", "annotation_group"):
        v = getattr(body, k)
        if v is not None:
            setattr(p, k, v.strip() if isinstance(v, str) else v)
    if "folder_id" in body.model_fields_set:
        p.folder_id = body.folder_id or None
    if body.settings is not None:
        p.settings = {**(p.settings or {}), **body.settings}
    p.updated = now()
    audit(c.db, c.ws.id, c.user.id, "project.update", p.name)
    c.db.commit()
    return project_out(c.db, p, detail=True)


@router.delete("/{project}")
def delete_project(c: Ctx = Depends(project_ctx)):
    c.need("admin")
    c.project.deleted_at = time.time()
    audit(c.db, c.ws.id, c.user.id, "project.delete", c.project.name)
    c.db.commit()
    return {"ok": True}


# --- classes ---------------------------------------------------------------------------

@router.get("/{project}/classes")
def get_classes(c: Ctx = Depends(project_ctx)):
    return classes_out(c.db, c.project)


class ClassIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    color: str | None = None
    skeleton: dict | None = None


def _clean_skeleton(raw: dict | None) -> dict | None:
    """Validate a class keypoint schema; unknown keys are dropped. Raises ValueError for bad input."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("skeleton must be an object")
    names = raw.get("names")
    if not isinstance(names, list) or not 1 <= len(names) <= 100:
        raise ValueError("skeleton names must be a list of 1–100 names")
    clean_names, seen = [], set()
    for name in names:
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 60:
            raise ValueError("skeleton names must be non-empty strings of at most 60 characters")
        name = name.strip()
        if name in seen:
            raise ValueError("skeleton names must be unique")
        seen.add(name)
        clean_names.append(name)
    edges = raw.get("edges", [])
    if not isinstance(edges, list) or len(edges) > 200:
        raise ValueError("skeleton edges must be a list of at most 200 pairs")
    clean_edges = []
    for pair in edges:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("skeleton edges must be index pairs")
        a, b = pair
        if (not isinstance(a, int) or isinstance(a, bool) or not isinstance(b, int) or isinstance(b, bool)
                or not 0 <= a < len(clean_names) or not 0 <= b < len(clean_names) or a == b):
            raise ValueError("skeleton edges must reference two distinct valid indices")
        clean_edges.append([a, b])
    out = {"names": clean_names, "edges": clean_edges}
    if "flip_idx" in raw:
        flip = raw["flip_idx"]
        if (not isinstance(flip, list) or len(flip) != len(clean_names)
                or not all(isinstance(i, int) and not isinstance(i, bool) and 0 <= i < len(clean_names) for i in flip)):
            raise ValueError("skeleton flip_idx must list one valid index per name")
        out["flip_idx"] = flip
    return out


def _skeleton_or_400(raw: dict | None) -> dict | None:
    try:
        return _clean_skeleton(raw)
    except ValueError as e:
        raise HTTPException(400, str(e))


def ensure_class(db: Session, p: Project, name: str) -> LabelClass:
    lc = db.scalar(select(LabelClass).where(LabelClass.project_id == p.id, LabelClass.name == name))
    if not lc:
        n = db.scalar(select(func.count(LabelClass.id)).where(LabelClass.project_id == p.id))
        lc = LabelClass(project_id=p.id, name=name, color=PALETTE[n % len(PALETTE)])
        db.add(lc); db.flush()
    return lc


@router.post("/{project}/classes")
def add_class(body: ClassIn, c: Ctx = Depends(project_ctx)):
    c.perm("project.classes")   # Roboflow lets labelers add classes while annotating
    name = body.name.strip()
    if c.db.scalar(select(LabelClass.id).where(LabelClass.project_id == c.project.id, LabelClass.name == name)):
        raise HTTPException(409, "class already exists")
    lc = ensure_class(c.db, c.project, name)
    lc.skeleton = _skeleton_or_400(body.skeleton)
    if body.color:
        lc.color = body.color
    c.db.commit()
    return {"id": lc.id, "name": lc.name, "color": lc.color, "count": 0, "skeleton": lc.skeleton}


@router.patch("/{project}/classes/{cid}")
def edit_class(cid: str, body: ClassIn, c: Ctx = Depends(project_ctx)):
    c.perm("project.classes")
    lc = c.db.get(LabelClass, cid)
    if not lc or lc.project_id != c.project.id:
        raise HTTPException(404, "class not found")
    name = body.name.strip()
    other = c.db.scalar(select(LabelClass).where(LabelClass.project_id == c.project.id, LabelClass.name == name,
                                                 LabelClass.id != cid))
    if other:
        raise HTTPException(409, "another class has this name — use merge instead")
    audit(c.db, c.ws.id, c.user.id, "class.rename", f"{lc.name} → {name}")
    lc.name = name
    if body.color:
        lc.color = body.color
    if "skeleton" in body.model_fields_set:
        lc.skeleton = _skeleton_or_400(body.skeleton)
    c.db.commit()
    return {"id": lc.id, "name": lc.name, "color": lc.color, "skeleton": lc.skeleton}


class MergeIn(BaseModel):
    source_ids: list[str]
    target_id: str


@router.post("/{project}/classes/merge")
def merge_classes(body: MergeIn, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    src = set(body.source_ids) - {body.target_id}
    n = 0
    hit = select(ImageClass.image_id).where(ImageClass.class_id.in_(src))
    for img in c.db.scalars(select(Image).where(Image.project_id == c.project.id, Image.id.in_(hit))):
        if any(a.get("classId") in src for a in img.annotations or []):
            set_annotations(c.db, img, [{**a, "classId": body.target_id} if a.get("classId") in src else a for a in img.annotations])
            n += 1
    for lc in c.db.scalars(select(LabelClass).where(LabelClass.id.in_(src), LabelClass.project_id == c.project.id)):
        c.db.delete(lc)
    audit(c.db, c.ws.id, c.user.id, "class.merge", body.target_id, sources=list(src))
    c.db.commit()
    return {"images_updated": n}


@router.delete("/{project}/classes/{cid}")
def delete_class(cid: str, c: Ctx = Depends(project_ctx)):
    c.perm("project.classes")
    lc = c.db.get(LabelClass, cid)
    if not lc or lc.project_id != c.project.id:
        raise HTTPException(404, "class not found")
    hit = select(ImageClass.image_id).where(ImageClass.class_id == cid)
    for img in c.db.scalars(select(Image).where(Image.project_id == c.project.id, Image.id.in_(hit))):
        if any(a.get("classId") == cid for a in img.annotations or []):
            set_annotations(c.db, img, [a for a in img.annotations if a.get("classId") != cid])
    audit(c.db, c.ws.id, c.user.id, "class.delete", lc.name)
    c.db.delete(lc); c.db.commit()
    return {"ok": True}


# --- tags ----------------------------------------------------------------------------------

@router.get("/{project}/tags")
def get_tags(c: Ctx = Depends(project_ctx)):
    counts = Counter()
    for tags in c.db.scalars(select(Image.tags).where(Image.project_id == c.project.id, Image.deleted_at.is_(None))):
        counts.update(tags or [])
    return [{"name": t, "count": n} for t, n in counts.most_common()]


class TagRename(BaseModel):
    name: str
    new_name: str | None = None     # None = delete tag everywhere


@router.post("/{project}/tags/rename")
def rename_tag(body: TagRename, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    n = 0
    for img in c.db.scalars(select(Image).where(Image.project_id == c.project.id)):
        if body.name in (img.tags or []):
            tags = [t for t in img.tags if t != body.name]
            if body.new_name and body.new_name not in tags:
                tags.append(body.new_name)
            # Insights slices group by live tags; bumping `updated` invalidates their cache stamp.
            img.tags = tags
            img.updated = now()
            n += 1
    c.db.commit()
    return {"images_updated": n}


# --- batches --------------------------------------------------------------------------------

@router.get("/{project}/batches")
def batches(c: Ctx = Depends(project_ctx)):
    rows = c.db.execute(select(Batch, func.count(Image.id)).outerjoin(Image, (Image.batch_id == Batch.id) & Image.deleted_at.is_(None))
                        .where(Batch.project_id == c.project.id).group_by(Batch.id).order_by(Batch.created.desc())).all()
    return [{"id": b.id, "name": b.name, "source": b.source, "created": b.created, "images": n} for b, n in rows]


# --- analytics (Roboflow "Health Check") ------------------------------------------------------

@router.get("/{project}/analytics")
def analytics(c: Ctx = Depends(project_ctx)):
    # the full scan is cached until any image (or the latest health job) changes
    sig = (*health.signature(c.db, c.project), health.job_state(c.db, c.project))
    hit = _analytics_cache.get(c.project.id)
    out = hit[1] if hit and hit[0] == sig else None
    if out is None:
        out = _analytics(c)
        _analytics_cache[c.project.id] = (sig, out)
        while len(_analytics_cache) > 256:
            _analytics_cache.pop(next(iter(_analytics_cache)))
    # class names/colors/counts are cheap and may change without touching images (rename, recolor)
    classes = classes_out(c.db, c.project)
    counts = [x["count"] for x in classes if x["count"]]
    job, stale = health.job_summary(c.db, c.project)
    return {**out, "classes": sorted(classes, key=lambda x: -x["count"]),
            "imbalance_ratio": round(max(counts) / min(counts), 1) if len(counts) > 1 else 1,
            "health_job": job, "health_stale": stale}


class HealthIn(BaseModel):
    imgsz: int = Field(640, ge=64, le=2048)


@router.post("/{project}/health")
def queue_health(body: HealthIn | None = None, c: Ctx = Depends(project_ctx)):
    """Queue the missing-box scan; inference never runs inside the analytics request."""
    c.need("reviewer")
    j = health.enqueue(c.db, c.project, (body or HealthIn()).imgsz)
    audit(c.db, c.ws.id, c.user.id, "health.scan", c.project.name)
    c.db.commit()
    return job_out(j)


_analytics_cache: dict[str, tuple] = {}


def _analytics(c: Ctx) -> dict:
    rows = c.db.execute(select(Image.width, Image.height, Image.annotations, Image.split, Image.status)
                        .where(Image.project_id == c.project.id, Image.deleted_at.is_(None))).all()
    per_img, sizes, splits, statuses = Counter(), Counter(), Counter(), Counter()
    heat = [[0] * 10 for _ in range(10)]
    ratios = Counter()
    widths, heights, n_ann, null = [], [], 0, 0
    for w, h, anns, split, status in rows:
        anns = anns or []
        widths.append(w); heights.append(h); splits[split] += 1; statuses[status] += 1
        per_img[min(len(anns), 20)] += 1
        n_ann += len(anns)
        null += not anns
        mp = w * h / 1e6
        sizes["< 0.3 MP" if mp < 0.3 else "0.3–1 MP" if mp < 1 else "1–4 MP" if mp < 4 else "> 4 MP"] += 1
        r = w / h if h else 1
        ratios["tall" if r < 0.8 else "square" if r < 1.25 else "wide" if r < 2 else "very wide"] += 1
        for a in anns:
            s = a.get("shape") if isinstance(a, dict) else None
            if not isinstance(s, dict):
                continue
            if s.get("kind") == "bbox":
                cx, cy = s["x"] + s["w"] / 2, s["y"] + s["h"] / 2
            elif s.get("kind") == "polygon" and s.get("points"):
                cx, cy = sum(s["points"][0::2]) / (len(s["points"]) / 2), sum(s["points"][1::2]) / (len(s["points"]) / 2)
            else:
                continue
            heat[min(9, max(0, int(cy * 10)))][min(9, max(0, int(cx * 10)))] += 1
    n = len(rows)
    # annotators can read analytics but must not queue GPU work just by opening the page
    checks = health.checks(c.db, c.project, auto_scan=c.role != "annotator")
    return {
        "images": n, "annotations": n_ann, "null_images": null,
        "avg_annotations": round(n_ann / n, 2) if n else 0,
        "avg_width": round(sum(widths) / n) if n else 0, "avg_height": round(sum(heights) / n) if n else 0,
        "median_size": f"{sorted(widths)[n // 2]}×{sorted(heights)[n // 2]}" if n else "—",
        "annotations_per_image": [{"n": k if k < 20 else "20+", "images": v} for k, v in sorted(per_img.items())],
        "sizes": [{"bucket": k, "images": v} for k, v in sizes.items()],
        "aspect": [{"bucket": k, "images": v} for k, v in ratios.items()],
        "splits": dict(splits), "statuses": dict(statuses), "heatmap": heat,
        "checks": checks, "recommendations": health.recommendations(checks),
    }


# --- jobs --------------------------------------------------------------------------------------

@router.get("/{project}/jobs")
def project_jobs(kind: str | None = None, c: Ctx = Depends(project_ctx)):
    q = select(Job).where(Job.project_id == c.project.id)
    if kind:
        q = q.where(Job.kind == kind)
    return [job_out(j) for j in c.db.scalars(q.order_by(Job.created.desc()).limit(100))]


@router.get("/{project}/jobs/{jid}")
def get_job(jid: str, c: Ctx = Depends(project_ctx)):
    j = c.db.get(Job, jid)
    if not j or j.project_id != c.project.id:
        raise HTTPException(404, "job not found")
    return job_out(j)


@router.post("/{project}/jobs/{jid}/cancel")
def cancel_job(jid: str, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    j = c.db.get(Job, jid)
    if not j or j.project_id != c.project.id:
        raise HTTPException(404, "job not found")
    if j.status == "queued":
        j.status = "cancelled"; j.finished = now()
    elif j.status == "running":
        j.status = "cancelling"
    c.db.commit()
    return job_out(j)


def latest_versions(db: Session, p: Project) -> list[Version]:
    return db.scalars(select(Version).where(Version.project_id == p.id).order_by(Version.number.desc())).all()
