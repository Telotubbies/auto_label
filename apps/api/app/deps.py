"""Request dependencies: auth, tenancy (workspace → project → image), audit, credits."""
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import oidc, rbac
from .config import PLANS
from .db import get_db
from .models import Audit, CustomRole, Image, Member, Project, ProjectMember, User, Workspace
from .security import verify_access

bearer = HTTPBearer(auto_error=False)
# Kept for back-compat with existing `need()` call sites; new code should use permissions.
RANK = {"annotator": 1, "reviewer": 2, "admin": 3, "owner": 4, "billing": 2, "member": 1}
# need() is the legacy two-level threshold: pass on the workspace role OR the project role.
NEED = {
    "annotator": ({"annotator", "reviewer", "admin", "owner", "member"}, {"manager", "reviewer", "labeler"}),
    "reviewer": ({"reviewer", "admin", "owner"}, {"manager", "reviewer"}),
    "admin": ({"admin", "owner"}, {"manager"}),
    "billing": ({"billing", "owner"}, set()),
    "owner": ({"owner"}, set()),
}


def _oidc_user(db: Session, claims: dict) -> User:
    uid = f"oidc:{claims.get('sub')}"
    u = db.get(User, uid)
    if u:
        return u
    email = claims.get("email") or f"{claims.get('sub')}@oidc.local"
    u = User(id=uid, email=email, name=claims.get("name") or claims.get("preferred_username") or email)
    db.add(u); db.commit()
    return u


def current_user(request: Request, c: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
                 db: Session = Depends(get_db)) -> User:
    u = _authenticate(c, db)
    # Request-scoped marker: image_ctx is called directly (not as a dependency) by the image
    # routes, so it needs a way to tell a read from a write before granting annotate.
    u._http_method = request.method
    return u


def _authenticate(c: Optional[HTTPAuthorizationCredentials], db: Session) -> User:
    if not c:
        raise HTTPException(401, "login required")
    claims = oidc.verify_oidc(c.credentials)
    if claims:
        return _oidc_user(db, claims)
    claims = verify_access(c.credentials)
    u = db.get(User, claims["sub"]) if claims else None
    if not u:
        raise HTTPException(401, "bad token")
    return u


@dataclass
class Ctx:
    user: User
    ws: Workspace
    role: str                               # raw Member.role, kept for legacy call sites
    db: Session
    project: Optional[Project] = None
    ws_role: str = ""                       # owner | admin | billing | member (legacy rows map to member)
    project_role: Optional[str] = None      # manager | reviewer | labeler | viewer (None outside a project)
    ws_custom: tuple[str, ...] = ()         # workspace-level custom bundle
    project_custom: tuple[str, ...] = ()    # project-level custom bundle

    def __post_init__(self):
        """Fill the two-level roles for contexts built by hand (API keys, seed, internal jobs)."""
        if not self.ws_role:
            is_owner = bool(self.user) and self.ws.owner_id == self.user.id
            self.ws_role = rbac.workspace_role(self.role, is_owner)
        if self.project is not None and self.project_role is None:
            self.project_role = rbac.base_project_role(self.role, self.ws_role)

    @property
    def uid(self) -> Optional[str]:
        """None for API-key calls (no user session)."""
        return self.user.id if self.user else None

    def can(self, perm: str) -> bool:
        """True when the effective roles/custom bundles grant ``perm`` (project perms need a project)."""
        return rbac.has(perm, self.ws_role, self.project_role, self.ws_custom, self.project_custom)

    def perm(self, perm: str):
        if not self.can(perm):
            raise HTTPException(403, f"requires {perm}")
        return self

    def need(self, role: str):
        """Legacy threshold check: workspace role or, inside a project, project role."""
        ws_allowed, project_allowed = NEED[role]
        if self.ws_role in ws_allowed or (self.project is not None and self.project_role in project_allowed):
            return self
        raise HTTPException(403, f"requires {role} role")


def _custom_permissions(db: Session, role_id: Optional[str], level: str) -> tuple[str, ...]:
    """Permissions of a custom role, ignoring stale ids and level mismatches."""
    if not role_id:
        return ()
    row = db.get(CustomRole, role_id)
    if not row or row.level != level:
        return ()
    return tuple(row.permissions or ())


def _ctx_for_member(db: Session, u: User, ws: Workspace, m: Member) -> Ctx:
    is_owner = ws.owner_id == u.id
    return Ctx(user=u, ws=ws, role=m.role, db=db,
               ws_role=rbac.workspace_role(m.role, is_owner),
               ws_custom=_custom_permissions(db, m.custom_role_id, "workspace"))


def apply_project_role(c: Ctx, p: Project) -> None:
    """Attach the project and resolve the role: explicit ProjectMember row, else the inherited base.

    Workspace owners/admins stay managers in every project even if a stale ProjectMember row says
    otherwise — a mis-click must never lock the only admin out of project settings.
    """
    c.project = p
    row = c.db.get(ProjectMember, (p.id, c.user.id)) if c.user else None
    if c.ws_role in ("owner", "admin"):
        c.project_role = "manager"
        c.project_custom = _custom_permissions(c.db, row.custom_role_id, "project") if row else ()
    elif row:
        c.project_role = row.role
        c.project_custom = _custom_permissions(c.db, row.custom_role_id, "project")
    else:
        c.project_role = rbac.base_project_role(c.role, c.ws_role)
        c.project_custom = ()


def _workspace_ctx(db: Session, u: User, ws_slug: str) -> Ctx:
    ws = db.scalar(select(Workspace).where(Workspace.slug == ws_slug))
    if not ws:
        raise HTTPException(404, "workspace not found")
    m = db.get(Member, (ws.id, u.id))
    if not m:
        raise HTTPException(403, "not a member of this workspace")
    if ws.require_mfa and not u.mfa_enabled:
        raise HTTPException(403, "this workspace requires two-factor authentication — set it up in your account settings")
    return _ctx_for_member(db, u, ws, m)


def ws_ctx(ws: str, u: User = Depends(current_user), db: Session = Depends(get_db)) -> Ctx:
    return _workspace_ctx(db, u, ws)


def project_ctx(ws: str, project: str, u: User = Depends(current_user), db: Session = Depends(get_db)) -> Ctx:
    ctx = _workspace_ctx(db, u, ws)
    p = db.scalar(select(Project).where(Project.workspace_id == ctx.ws.id, Project.slug == project,
                                        Project.deleted_at.is_(None)))
    if not p:
        raise HTTPException(404, "project not found")
    apply_project_role(ctx, p)
    return ctx


def image_ctx(db: Session, u: User, image_id: str) -> tuple[Ctx, Image]:
    img = db.get(Image, image_id)
    if not img or img.deleted_at:
        raise HTTPException(404, "image not found")
    p = db.get(Project, img.project_id)
    ws = db.get(Workspace, p.workspace_id)
    m = db.get(Member, (ws.id, u.id))
    if not m:
        raise HTTPException(403, "no access to this image")
    if ws.require_mfa and not u.mfa_enabled:
        raise HTTPException(403, "this workspace requires two-factor authentication — set it up in your account settings")
    ctx = _ctx_for_member(db, u, ws, m)
    apply_project_role(ctx, p)
    # The image routes call this helper directly, so writes check annotate here. Reads stay open
    # to project viewers; labelers are additionally limited to their assigned images downstream.
    if getattr(u, "_http_method", "GET") not in ("GET", "HEAD", "OPTIONS") and not ctx.can("project.annotate"):
        raise HTTPException(403, "requires project.annotate")
    return ctx, img


def audit(db: Session, ws_id: str, user_id: Optional[str], action: str, target: str = "", **meta):
    db.add(Audit(workspace_id=ws_id, user_id=user_id, action=action, target=target, meta=meta))


def plan(ws: Workspace) -> dict:
    return PLANS.get(ws.plan, PLANS["free"])


def _roll_period(ws: Workspace):
    period = time.strftime("%Y-%m")
    if ws.credits_period != period:
        ws.credits_period, ws.credits_used = period, 0.0


def charge(db: Session, ws: Workspace, amount: float):
    """Meter credits; 402 once the monthly allowance is exhausted."""
    _roll_period(ws)
    if ws.credits_used + amount > plan(ws)["credits"]:
        raise HTTPException(402, f"monthly credit limit reached on the {plan(ws)['label']} plan")
    ws.credits_used = round(ws.credits_used + amount, 4)


def credits_left(ws: Workspace) -> float:
    _roll_period(ws)
    return max(0.0, plan(ws)["credits"] - ws.credits_used)
