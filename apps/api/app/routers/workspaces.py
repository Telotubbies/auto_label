"""Workspace-level: settings, members, invites, API keys, usage, audit, folders, trash."""
import shutil
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Text, cast, delete as sa_delete, func, or_, select
from sqlalchemy.orm import Session

from ..apikeys import scopes_of
from ..config import DATA_DIR, PLANS, PUBLIC_URL
from ..deps import Ctx, apply_project_role, audit, credits_left, plan, ws_ctx
from ..models import (API_SCOPES, ROLES, WORKSPACE_ROLES, ApiKey, Audit, Folder, Image, Invite, Job, Member, Project,
                      ProjectMember, TrainedModel, User, Workspace)
from ..security import new_api_key
from ..superadmin import is_superadmin
from .. import mailer

router = APIRouter(prefix="/api/ws/{ws}", tags=["workspace"])
# Roles an admin may hand out. Ownership is separate: it only moves through a transfer flow.
ASSIGNABLE = tuple(WORKSPACE_ROLES) + ROLES


def usage(db: Session, ws: Workspace) -> dict:
    pids = select(Project.id).where(Project.workspace_id == ws.id, Project.deleted_at.is_(None))
    lim = plan(ws)
    return {
        "plan": ws.plan, "plan_label": lim["label"], "limits": lim,
        "credits_used": round(ws.credits_used, 3), "credits_left": round(credits_left(ws), 3), "period": ws.credits_period,
        "projects": db.scalar(select(func.count()).select_from(pids.subquery())),
        "images": db.scalar(select(func.count(Image.id)).where(Image.project_id.in_(pids), Image.deleted_at.is_(None))),
        "seats": db.scalar(select(func.count()).where(Member.workspace_id == ws.id)),
        "models": db.scalar(select(func.count(TrainedModel.id)).where(TrainedModel.workspace_id == ws.id)),
    }


@router.get("")
def get_ws(c: Ctx = Depends(ws_ctx)):
    return {"id": c.ws.id, "slug": c.ws.slug, "name": c.ws.name, "role": c.role, "owner_id": c.ws.owner_id,
            "require_mfa": c.ws.require_mfa, "usage": usage(c.db, c.ws)}


class WsPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    plan: str | None = None
    require_mfa: bool | None = None


@router.patch("")
def patch_ws(body: WsPatch, c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    if body.name:
        c.ws.name = body.name.strip()
    if body.plan:
        # no billing provider wired: plan changes are a platform-operator action
        if not is_superadmin(c.user):
            raise HTTPException(403, "plan changes are handled by the platform operator (LD_SUPERADMINS)")
        if body.plan not in PLANS:
            raise HTTPException(400, "unknown plan")
        c.ws.plan = body.plan
    if body.require_mfa is not None:
        # Turning enforcement on locks out every member who has not enrolled — including this admin.
        if body.require_mfa and not c.user.mfa_enabled:
            raise HTTPException(400, "enable two-factor authentication on your own account first")
        c.ws.require_mfa = body.require_mfa
        audit(c.db, c.ws.id, c.user.id, "workspace.mfa", "required" if body.require_mfa else "optional")
    audit(c.db, c.ws.id, c.user.id, "workspace.update", c.ws.name)
    c.db.commit()
    return {"slug": c.ws.slug, "name": c.ws.name, "plan": c.ws.plan, "require_mfa": c.ws.require_mfa}


@router.get("/home")
def home(c: Ctx = Depends(ws_ctx)) -> dict:
    """Dashboard totals plus the caller's queue, resolved with their role in each project."""
    projects = c.db.scalars(select(Project).where(Project.workspace_id == c.ws.id, Project.deleted_at.is_(None))
                            .order_by(Project.updated.desc())).all()
    pids = [p.id for p in projects]
    images = annotations = models = deployments = 0
    rows = []
    if pids:
        live = (Image.project_id.in_(pids)) & Image.deleted_at.is_(None)
        images = c.db.scalar(select(func.count(Image.id)).where(live)) or 0
        annotations = c.db.scalar(select(func.sum(Image.n_annotations)).where(live)) or 0
        models = c.db.scalar(select(func.count(TrainedModel.id)).where(TrainedModel.project_id.in_(pids))) or 0
        deployments = c.db.scalar(select(func.count(TrainedModel.id)).where(
            TrainedModel.project_id.in_(pids), TrainedModel.status == "ready")) or 0
        rows = c.db.execute(select(Image.project_id, Image.status, Image.assignee_id, func.count())
                            .where(live).group_by(Image.project_id, Image.status, Image.assignee_id)).all()

    grouped: dict[str, list[tuple[str, str | None, int]]] = {}
    for pid, status, assignee, n in rows:
        grouped.setdefault(pid, []).append((status, assignee, int(n)))

    waiting: list[dict] = []
    totals = {"to_annotate": 0, "to_review": 0, "unassigned": 0}
    for p in projects:
        # Mutation is local to this request; every project can grant a different role.
        apply_project_role(c, p)
        can_review = c.can("project.review")
        queue = grouped.get(p.id, [])
        to_annotate = sum(n for status, assignee, n in queue if status == "annotating" and assignee == c.user.id)
        to_review = sum(n for status, _, n in queue if status == "review") if can_review else 0
        unassigned = sum(n for status, _, n in queue if status == "unassigned") if can_review else 0
        if not (to_annotate or to_review or unassigned):
            continue
        waiting.append({"project": p.slug, "project_name": p.name, "to_annotate": to_annotate,
                        "to_review": to_review, "unassigned": unassigned})
        for key, value in (("to_annotate", to_annotate), ("to_review", to_review), ("unassigned", unassigned)):
            totals[key] += value

    return {"stats": {"projects": len(projects), "images": images, "annotations": annotations,
                      "models": models, "deployments": deployments},
            "waiting": waiting, "totals": totals}


@router.get("/usage")
def get_usage(c: Ctx = Depends(ws_ctx)):
    out = usage(c.db, c.ws)
    since = time.time() - 30 * 86400
    rows = c.db.execute(select(Audit.action, Audit.created).where(Audit.workspace_id == c.ws.id, Audit.created >= since)).all()
    daily: dict[str, dict[str, int]] = {}
    for action, t in rows:
        d = time.strftime("%Y-%m-%d", time.localtime(t))
        key = action.split(".")[0]
        daily.setdefault(d, {}); daily[d][key] = daily[d].get(key, 0) + 1
    out["daily"] = [{"date": d, **v} for d, v in sorted(daily.items())]
    return out


# --- members & invites ---------------------------------------------------------------

@router.get("/members")
def members(c: Ctx = Depends(ws_ctx)):
    rows = c.db.scalars(select(Member).where(Member.workspace_id == c.ws.id).order_by(Member.created)).all()
    invites = c.db.scalars(select(Invite).where(Invite.workspace_id == c.ws.id, Invite.accepted.is_(False))).all() \
        if c.role == "admin" else []
    return {
        "members": [{"id": m.user_id, "name": m.user.name, "email": m.user.email, "role": m.role,
                     "custom_role_id": m.custom_role_id,
                     "owner": m.user_id == c.ws.owner_id, "joined": m.created} for m in rows],
        "invites": [{"token": i.token, "email": i.email, "role": i.role, "created": i.created,
                     "link": f"{PUBLIC_URL}/invite/{i.token}"} for i in invites],
    }


class InviteIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    role: str = "annotator"


@router.post("/invites")
def invite(body: InviteIn, c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    if body.role == "owner":
        raise HTTPException(400, "ownership transfers are not supported")
    if body.role not in ASSIGNABLE:
        raise HTTPException(400, f"role must be one of {ASSIGNABLE}")
    pending = c.db.scalar(select(func.count()).where(Invite.workspace_id == c.ws.id, Invite.accepted.is_(False)))
    if usage(c.db, c.ws)["seats"] + pending >= plan(c.ws)["seats"]:
        raise HTTPException(402, f"seat limit reached on the {plan(c.ws)['label']} plan")
    email = body.email.lower()
    u = c.db.scalar(select(User).where(User.email == email))
    if u and c.db.get(Member, (c.ws.id, u.id)):
        raise HTTPException(409, "already a member")
    inv = Invite(workspace_id=c.ws.id, email=email, role=body.role, invited_by=c.user.id)
    c.db.add(inv)
    audit(c.db, c.ws.id, c.user.id, "member.invite", email, role=body.role)
    c.db.commit()
    link = f"{PUBLIC_URL}/invite/{inv.token}"
    mailer.send(email, f"Join {c.ws.name} on LabelDesk",
                f"{c.user.name} invited you to {c.ws.name} as {body.role}.\n\nAccept the invite:\n{link}\n\n"
                f"The link is tied to this email address.", link=link, kind="invite")
    return {"token": inv.token, "email": email, "role": body.role, "link": link}


@router.delete("/invites/{token}")
def revoke_invite(token: str, c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    inv = c.db.get(Invite, token)
    if not inv or inv.workspace_id != c.ws.id:
        raise HTTPException(404, "invite not found")
    c.db.delete(inv); c.db.commit()
    return {"ok": True}


class RoleIn(BaseModel):
    role: str


@router.patch("/members/{uid}")
def set_role(uid: str, body: RoleIn, c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    if body.role == "owner":
        raise HTTPException(400, "ownership transfers are not supported")
    if body.role not in ASSIGNABLE:
        raise HTTPException(400, f"role must be one of {ASSIGNABLE}")
    if uid == c.ws.owner_id:
        raise HTTPException(400, "the workspace owner is always an admin")
    m = c.db.get(Member, (c.ws.id, uid))
    if not m:
        raise HTTPException(404, "member not found")
    m.role = body.role
    audit(c.db, c.ws.id, c.user.id, "member.role", m.user.email, role=body.role)
    c.db.commit()
    return {"id": uid, "role": m.role}


@router.delete("/members/{uid}")
def remove_member(uid: str, c: Ctx = Depends(ws_ctx)):
    if uid != c.user.id:
        c.need("admin")
    if uid == c.ws.owner_id:
        raise HTTPException(400, "the workspace owner cannot be removed")
    m = c.db.get(Member, (c.ws.id, uid))
    if not m:
        raise HTTPException(404, "member not found")
    email = m.user.email
    c.db.delete(m)
    pids = select(Project.id).where(Project.workspace_id == c.ws.id)
    for img in c.db.scalars(select(Image).where(Image.project_id.in_(pids), Image.assignee_id == uid)):
        img.assignee_id = None
    # No FK from project_members to members: revoke every project role explicitly, otherwise a later
    # re-invite silently inherits the old project manager/reviewer row (I5).
    revoked = c.db.execute(sa_delete(ProjectMember).where(ProjectMember.user_id == uid,
                                                          ProjectMember.project_id.in_(pids))).rowcount or 0
    audit(c.db, c.ws.id, c.user.id, "member.remove", email, projects=revoked)
    c.db.commit()
    return {"ok": True}


# --- API keys --------------------------------------------------------------------

@router.get("/keys")
def keys(c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    rows = c.db.scalars(select(ApiKey).where(ApiKey.workspace_id == c.ws.id).order_by(ApiKey.created.desc())).all()
    return [{"id": k.id, "name": k.name, "prefix": k.prefix, "scopes": list(scopes_of(k)),
             "publishable": bool(k.publishable), "created": k.created, "last_used": k.last_used} for k in rows]


class KeyIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: list[str] | None = None            # omitted = all scopes (legacy behaviour)
    publishable: bool = False                   # browser-safe: forces ["infer"]


@router.post("/keys")
def new_key(body: KeyIn, c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    if body.publishable:
        scopes = ["infer"]
    elif body.scopes is None:
        scopes = list(API_SCOPES)
    else:
        scopes = list(dict.fromkeys(body.scopes))
        if not scopes or any(s not in API_SCOPES for s in scopes):
            raise HTTPException(400, f"scopes must be a non-empty subset of {list(API_SCOPES)}")
    key, prefix, h = new_api_key(publishable=body.publishable)
    k = ApiKey(workspace_id=c.ws.id, name=body.name, prefix=prefix, hash=h, scopes=scopes,
               publishable=body.publishable, created_by=c.user.id)
    c.db.add(k)
    audit(c.db, c.ws.id, c.user.id, "apikey.create", body.name, scopes=scopes)
    c.db.commit()
    return {"id": k.id, "name": k.name, "prefix": prefix, "scopes": scopes,
            "publishable": body.publishable, "key": key}


@router.delete("/keys/{kid}")
def revoke_key(kid: str, c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    k = c.db.get(ApiKey, kid)
    if not k or k.workspace_id != c.ws.id:
        raise HTTPException(404, "key not found")
    audit(c.db, c.ws.id, c.user.id, "apikey.revoke", k.name)
    c.db.delete(k); c.db.commit()
    return {"ok": True}


# --- audit / activity ----------------------------------------------------------------

@router.get("/audit")
def audit_log(action: str = "", user: str = "", since: float | None = None, until: float | None = None,
              q: str = "", offset: int = 0, limit: int = 200, c: Ctx = Depends(ws_ctx)):
    """Workspace audit trail. Filters are additive; `action` also matches its dotted prefix."""
    c.perm("workspace.audit")
    s = select(Audit, User.name).outerjoin(User, User.id == Audit.user_id).where(Audit.workspace_id == c.ws.id)
    if action:
        s = s.where(or_(Audit.action == action, Audit.action.like(f"{action}.%")))
    if user:
        needle = f"%{user.lower()}%"
        cond = or_(func.lower(User.name).like(needle), func.lower(User.email).like(needle))
        if user.lower() in ("api", "system"):
            cond = or_(cond, Audit.user_id.is_(None))
        s = s.where(cond)
    if since is not None:
        s = s.where(Audit.created >= since)
    if until is not None:
        s = s.where(Audit.created <= until)
    if q:
        needle = f"%{q.lower()}%"
        s = s.where(or_(func.lower(Audit.target).like(needle),
                        func.lower(cast(Audit.meta, Text)).like(needle)))
    s = s.order_by(Audit.created.desc()).offset(max(offset, 0)).limit(min(max(limit, 1), 1000))
    rows = c.db.execute(s).all()
    return [{"id": a.id, "action": a.action, "target": a.target, "meta": a.meta, "created": a.created,
             "user": name or ("API" if a.user_id is None else a.user_id)} for a, name in rows]


@router.get("/jobs")
def ws_jobs(c: Ctx = Depends(ws_ctx)):
    rows = c.db.execute(select(Job, Project.slug, Project.name).outerjoin(Project, Project.id == Job.project_id)
                        .where(Job.workspace_id == c.ws.id).order_by(Job.created.desc()).limit(100)).all()
    from .projects import job_out
    return [{**job_out(j), "project": slug, "project_name": name} for j, slug, name in rows]


@router.get("/models")
def ws_models(c: Ctx = Depends(ws_ctx)):
    rows = c.db.execute(select(TrainedModel, Project.slug, Project.name).join(Project, Project.id == TrainedModel.project_id)
                        .where(TrainedModel.workspace_id == c.ws.id, Project.deleted_at.is_(None))
                        .order_by(TrainedModel.created.desc())).all()
    from .training import model_out
    return [{**model_out(m), "project": slug, "project_name": name} for m, slug, name in rows]


# --- folders --------------------------------------------------------------------------

class FolderIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


@router.get("/folders")
def folders(c: Ctx = Depends(ws_ctx)):
    rows = c.db.scalars(select(Folder).where(Folder.workspace_id == c.ws.id).order_by(Folder.name)).all()
    counts = dict(c.db.execute(select(Project.folder_id, func.count()).where(
        Project.workspace_id == c.ws.id, Project.deleted_at.is_(None)).group_by(Project.folder_id)).all())
    return [{"id": f.id, "name": f.name, "projectCount": counts.get(f.id, 0)} for f in rows]


@router.post("/folders")
def new_folder(body: FolderIn, c: Ctx = Depends(ws_ctx)):
    c.need("reviewer")
    f = Folder(workspace_id=c.ws.id, name=body.name.strip()); c.db.add(f); c.db.commit()
    return {"id": f.id, "name": f.name, "projectCount": 0}


@router.patch("/folders/{fid}")
def rename_folder(fid: str, body: FolderIn, c: Ctx = Depends(ws_ctx)):
    c.need("reviewer")
    f = c.db.get(Folder, fid)
    if not f or f.workspace_id != c.ws.id:
        raise HTTPException(404, "folder not found")
    f.name = body.name.strip(); c.db.commit()
    return {"id": f.id, "name": f.name}


@router.delete("/folders/{fid}")
def delete_folder(fid: str, c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    f = c.db.get(Folder, fid)
    if not f or f.workspace_id != c.ws.id:
        raise HTTPException(404, "folder not found")
    for p in c.db.scalars(select(Project).where(Project.folder_id == fid)):
        p.folder_id = None
    c.db.delete(f); c.db.commit()
    return {"ok": True}


# --- trash ------------------------------------------------------------------------------

@router.get("/trash")
def trash(c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    rows = c.db.scalars(select(Project).where(Project.workspace_id == c.ws.id, Project.deleted_at.is_not(None))).all()
    return [{"id": p.id, "slug": p.slug, "name": p.name, "type": p.type, "deleted_at": p.deleted_at} for p in rows]


@router.post("/trash/{pid}/restore")
def restore(pid: str, c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    p = c.db.get(Project, pid)
    if not p or p.workspace_id != c.ws.id:
        raise HTTPException(404, "project not found")
    p.deleted_at = None
    audit(c.db, c.ws.id, c.user.id, "project.restore", p.name)
    c.db.commit()
    return {"slug": p.slug}


@router.delete("/trash/{pid}")
def purge(pid: str, c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    p = c.db.get(Project, pid)
    if not p or p.workspace_id != c.ws.id or not p.deleted_at:
        raise HTTPException(404, "project not in trash")
    audit(c.db, c.ws.id, c.user.id, "project.purge", p.name)
    c.db.delete(p); c.db.commit()
    shutil.rmtree(DATA_DIR / "projects" / pid, ignore_errors=True)
    return {"ok": True}
