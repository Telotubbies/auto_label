"""Request dependencies: auth, tenancy (workspace → project → image), audit, credits."""
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import oidc
from .config import PLANS
from .db import get_db
from .models import Audit, Image, Member, Project, User, Workspace
from .security import verify_access

bearer = HTTPBearer(auto_error=False)
RANK = {"annotator": 1, "reviewer": 2, "admin": 3}


def _oidc_user(db: Session, claims: dict) -> User:
    uid = f"oidc:{claims.get('sub')}"
    u = db.get(User, uid)
    if u:
        return u
    email = claims.get("email") or f"{claims.get('sub')}@oidc.local"
    u = User(id=uid, email=email, name=claims.get("name") or claims.get("preferred_username") or email)
    db.add(u); db.commit()
    return u


def current_user(c: Optional[HTTPAuthorizationCredentials] = Depends(bearer), db: Session = Depends(get_db)) -> User:
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
    role: str
    db: Session
    project: Optional[Project] = None

    def need(self, role: str):
        if RANK[self.role] < RANK[role]:
            raise HTTPException(403, f"requires {role} role")
        return self


def _workspace_ctx(db: Session, u: User, ws_slug: str) -> Ctx:
    ws = db.scalar(select(Workspace).where(Workspace.slug == ws_slug))
    if not ws:
        raise HTTPException(404, "workspace not found")
    m = db.get(Member, (ws.id, u.id))
    if not m:
        raise HTTPException(403, "not a member of this workspace")
    return Ctx(user=u, ws=ws, role=m.role, db=db)


def ws_ctx(ws: str, u: User = Depends(current_user), db: Session = Depends(get_db)) -> Ctx:
    return _workspace_ctx(db, u, ws)


def project_ctx(ws: str, project: str, u: User = Depends(current_user), db: Session = Depends(get_db)) -> Ctx:
    ctx = _workspace_ctx(db, u, ws)
    p = db.scalar(select(Project).where(Project.workspace_id == ctx.ws.id, Project.slug == project,
                                        Project.deleted_at.is_(None)))
    if not p:
        raise HTTPException(404, "project not found")
    ctx.project = p
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
    return Ctx(user=u, ws=ws, role=m.role, db=db, project=p), img


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
