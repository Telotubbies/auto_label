"""Platform super-admin console (LD_SUPERADMINS): workspaces, plans, queue health, workers, status."""
import os
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..adapters import ADAPTERS
from ..config import PLANS, WORKER_STALE_S
from ..db import get_db
from ..deps import audit, current_user, plan
from ..gpu import scheduler
from ..models import Image, Job, Member, Project, User, Workspace
from ..services import heartbeat
from ..superadmin import is_superadmin

router = APIRouter(prefix="/api/admin", tags=["admin"])
VERSION = "1.0.0"
JOB_STATUSES = ("queued", "running", "done", "failed", "cancelled")
QUEUE_DEGRADED_S = 600


def require_superadmin(u: User = Depends(current_user)) -> User:
    if not is_superadmin(u):
        raise HTTPException(403, "super-admin only")
    return u


# --- workspaces ----------------------------------------------------------------------

def _usage_counts(db: Session) -> tuple[dict, dict, dict]:
    """(projects, images, members) per workspace in three grouped queries; deleted rows are excluded."""
    live = select(Project.id, Project.workspace_id).where(Project.deleted_at.is_(None)).subquery()
    projects = dict(db.execute(select(live.c.workspace_id, func.count())
                               .group_by(live.c.workspace_id)).all())
    images = dict(db.execute(select(live.c.workspace_id, func.count(Image.id))
                             .join(Image, Image.project_id == live.c.id)
                             .where(Image.deleted_at.is_(None))
                             .group_by(live.c.workspace_id)).all())
    members = dict(db.execute(select(Member.workspace_id, func.count()).group_by(Member.workspace_id)).all())
    return projects, images, members


def _row(ws: Workspace, owner_email: str, counts: tuple[dict, dict, dict]) -> dict:
    projects, images, members = counts
    lim = plan(ws)
    return {"id": ws.id, "slug": ws.slug, "name": ws.name, "plan": ws.plan, "plan_label": lim["label"],
            "region": ws.data_region, "owner_email": owner_email, "created": ws.created,
            "members": members.get(ws.id, 0), "projects": projects.get(ws.id, 0), "images": images.get(ws.id, 0),
            "credits_used": round(ws.credits_used, 3), "credits_limit": lim["credits"]}


def _workspace_rows(db: Session, q: str = "", wid: str | None = None) -> list[dict]:
    stmt = select(Workspace, User.email).join(User, User.id == Workspace.owner_id).order_by(Workspace.created)
    if wid:
        stmt = stmt.where(Workspace.id == wid)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Workspace.name.ilike(like) | Workspace.slug.ilike(like) | User.email.ilike(like))
    counts = _usage_counts(db)
    return [_row(ws, email, counts) for ws, email in db.execute(stmt).all()]


@router.get("/overview")
def overview(db: Session = Depends(get_db), _u: User = Depends(require_superadmin)):
    jobs = dict(db.execute(select(Job.status, func.count()).group_by(Job.status)).all())
    live_projects = select(Project.id).where(Project.deleted_at.is_(None)).subquery()
    return {
        "version": VERSION,
        "workspaces": db.scalar(select(func.count(Workspace.id))),
        "users": db.scalar(select(func.count(User.id))),
        "projects": db.scalar(select(func.count()).select_from(live_projects)),
        "images": db.scalar(select(func.count(Image.id)).where(
            Image.project_id.in_(select(live_projects.c.id)), Image.deleted_at.is_(None))),
        "jobs": {s: jobs.get(s, 0) for s in JOB_STATUSES},
        "gpu": scheduler.state(),
        "workers_online": sum(1 for w in heartbeat.workers(db) if w["online"]),
        "vllm": {"configured": _vllm_configured(), "sleeping": scheduler.vlm_sleeping},
        "generated": time.time(),
    }


@router.get("/workspaces")
def workspaces(q: str = "", db: Session = Depends(get_db), _u: User = Depends(require_superadmin)):
    return _workspace_rows(db, q=q)


class PlanIn(BaseModel):
    plan: str


@router.patch("/workspaces/{wid}")
def set_plan(wid: str, body: PlanIn, db: Session = Depends(get_db), u: User = Depends(require_superadmin)):
    ws = db.get(Workspace, wid)
    if not ws:
        raise HTTPException(404, "workspace not found")
    if body.plan not in PLANS:
        raise HTTPException(400, "unknown plan")
    ws.plan = body.plan
    audit(db, ws.id, u.id, "admin.plan", ws.name, plan=body.plan, by=u.email)
    db.commit()
    return _workspace_rows(db, wid=ws.id)[0]


# --- queue, workers, status ----------------------------------------------------------

def _oldest_queued_s(db: Session) -> float | None:
    oldest = db.scalar(select(func.min(Job.created)).where(Job.status == "queued"))
    return round(time.time() - oldest, 1) if oldest else None


@router.get("/jobs")
def jobs(status: str | None = None, kind: str | None = None, limit: int = 50,
         db: Session = Depends(get_db), _u: User = Depends(require_superadmin)):
    stmt = (select(Job, Workspace.slug, Project.slug)
            .join(Workspace, Workspace.id == Job.workspace_id)
            .outerjoin(Project, Project.id == Job.project_id)
            .order_by(Job.created.desc()).limit(min(max(limit, 1), 200)))
    if status:
        stmt = stmt.where(Job.status == status)
    if kind:
        stmt = stmt.where(Job.kind == kind)
    now = time.time()
    rows = [{"id": j.id, "workspace": ws_slug, "project": project_slug, "kind": j.kind, "status": j.status,
             "progress": j.progress, "error": j.error, "created": j.created, "started": j.started,
             "finished": j.finished, "age_s": round(now - j.created, 1)}
            for j, ws_slug, project_slug in db.execute(stmt).all()]
    counts = dict(db.execute(select(Job.status, func.count()).group_by(Job.status)).all())
    return {"counts": {s: counts.get(s, 0) for s in JOB_STATUSES},
            "oldest_queued_s": _oldest_queued_s(db), "items": rows}


@router.get("/workers")
def workers(db: Session = Depends(get_db), _u: User = Depends(require_superadmin)):
    return {"stale_after": WORKER_STALE_S, "workers": heartbeat.workers(db)}


def _vllm_configured() -> bool:
    return bool(os.environ.get("LD_VLM_URL")) or "vlm" in ADAPTERS


def _component(name: str, status: str, detail: str) -> dict:
    return {"name": name, "status": status, "detail": detail}


def _database_component(db: Session) -> dict:
    try:
        db.execute(select(1))
        return _component("database", "operational", "ok")
    except Exception as e:                       # a failed SELECT 1 is the only thing this page can report
        return _component("database", "degraded", type(e).__name__)


def _worker_component(db: Session) -> dict:
    rows = heartbeat.workers(db)
    online = sum(1 for w in rows if w["online"])
    status = "operational" if online else "degraded"
    return _component("worker", status, f"{online} online / {len(rows)} total")


def _gpu_component() -> dict:
    holder = scheduler.state()["holder"]
    return _component("gpu", "degraded" if holder else "operational", holder or "idle")


def _vllm_component() -> dict:
    if not _vllm_configured():
        return _component("vllm", "unknown", "not configured")
    if scheduler.vlm_sleeping:
        return _component("vllm", "operational", "sleeping (GPU released)")
    return _component("vllm", "operational", "ready")


def _queue_component(db: Session) -> dict:
    oldest = _oldest_queued_s(db)
    if oldest is None:
        return _component("queue", "operational", "empty")
    status = "degraded" if oldest > QUEUE_DEGRADED_S else "operational"
    return _component("queue", status, f"oldest queued {oldest:.0f}s")


@router.get("/status")
def status_page(db: Session = Depends(get_db), _u: User = Depends(require_superadmin)):
    return {"checked": time.time(), "components": [
        _component("api", "operational", f"v{VERSION}"),
        _database_component(db),
        _worker_component(db),
        _gpu_component(),
        _vllm_component(),
        _queue_component(db),
    ]}
