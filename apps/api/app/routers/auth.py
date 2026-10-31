"""Signup / login / refresh / profile / invite acceptance."""
import re
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import oidc
from ..config import SIGNUP_ENABLED
from ..db import get_db
from ..deps import audit, current_user, plan
from ..models import Invite, Member, RefreshToken, User, Workspace
from ..ratelimit import client_ip, limit
from ..security import hash_password, issue_access, new_refresh, token_hash, verify_password

_DUMMY_HASH = hash_password('timing-equaliser')
from ..services import segment

router = APIRouter(prefix="/api", tags=["auth"])


def slugify(s: str, fallback: str = "workspace") -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60] or fallback


def unique_ws_slug(db: Session, name: str) -> str:
    base = slugify(name); slug = base; n = 1
    while db.scalar(select(Workspace.id).where(Workspace.slug == slug)):
        n += 1; slug = f"{base}-{n}"
    return slug


def create_workspace(db: Session, owner: User, name: str) -> Workspace:
    ws = Workspace(slug=unique_ws_slug(db, name), name=name, owner_id=owner.id, credits_period=time.strftime("%Y-%m"))
    db.add(ws); db.flush()
    db.add(Member(workspace_id=ws.id, user_id=owner.id, role="admin"))
    audit(db, ws.id, owner.id, "workspace.create", name)
    return ws


def user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name}


def tokens(db: Session, u: User) -> dict:
    rt, exp = new_refresh()
    db.add(RefreshToken(token=token_hash(rt), user_id=u.id, expires=exp)); db.commit()   # only the hash is stored
    return {"token": issue_access(u.id), "refresh_token": rt, "user": user_out(u)}


@router.get("/config")
def public_config():
    return {"signup_enabled": SIGNUP_ENABLED, "oidc": {"issuer": oidc.ISSUER or None, "client_id": oidc.CLIENT_ID or None},
            "sam": segment.sam_status()}


class SignupIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(pattern=EMAIL, max_length=255)
    password: str = Field(min_length=8, max_length=200)
    workspace: str | None = None
    invite: str | None = None


@router.post("/auth/signup")
def signup(body: SignupIn, request: Request, db: Session = Depends(get_db)):
    limit(f"signup:{client_ip(request)}", 5, 3600)
    inv = db.get(Invite, body.invite) if body.invite else None
    if not SIGNUP_ENABLED and not inv:
        raise HTTPException(403, "sign-up is invite-only on this server")
    email = body.email.lower()
    if inv and inv.email.lower() != email:
        raise HTTPException(403, "this invite was sent to a different email address")
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "an account with this email already exists")
    u = User(email=email, name=body.name.strip(), pw_hash=hash_password(body.password))
    db.add(u); db.flush()
    if inv and not inv.accepted:
        _accept(db, inv, u)
    else:
        create_workspace(db, u, body.workspace or f"{body.name.split()[0]}'s Workspace")
    db.commit()
    return tokens(db, u)


class LoginIn(BaseModel):
    email: str
    password: str


@router.post("/auth/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    ip = client_ip(request)
    limit(f"login:{ip}", 30, 300)
    limit(f"login:{ip}:{email}", 8, 300)
    u = db.scalar(select(User).where(User.email == email))
    # always run one PBKDF2 so response time doesn't reveal whether the email exists
    ok = verify_password(body.password, u.pw_hash if u and u.pw_hash else _DUMMY_HASH)
    if not u or not ok:
        raise HTTPException(401, "invalid email or password")
    return tokens(db, u)


class RefreshIn(BaseModel):
    refresh_token: str


@router.post("/auth/refresh")
def refresh(body: RefreshIn, request: Request, db: Session = Depends(get_db)):
    limit(f"refresh:{client_ip(request)}", 60, 60)
    row = db.get(RefreshToken, token_hash(body.refresh_token))
    if not row or row.expires < time.time():
        raise HTTPException(401, "session expired")
    u = db.get(User, row.user_id)
    db.execute(delete(RefreshToken).where((RefreshToken.token == row.token) | (RefreshToken.expires < time.time())))
    return tokens(db, u)


@router.post("/auth/logout")
def logout(body: RefreshIn, db: Session = Depends(get_db)):
    db.execute(delete(RefreshToken).where(RefreshToken.token == token_hash(body.refresh_token))); db.commit()
    return {"ok": True}


@router.get("/me")
def me(u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(Workspace, Member.role).join(Member, Member.workspace_id == Workspace.id)
                      .where(Member.user_id == u.id).order_by(Workspace.created)).all()
    return {**user_out(u), "workspaces": [{"id": w.id, "slug": w.slug, "name": w.name, "role": r, "plan": w.plan,
                                           "plan_label": plan(w)["label"], "owner": w.owner_id == u.id} for w, r in rows]}


class MePatch(BaseModel):
    name: str | None = None
    password: str | None = Field(default=None, min_length=8)
    current_password: str | None = None


@router.patch("/me")
def patch_me(body: MePatch, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.name:
        u.name = body.name.strip()
    if body.password:
        if u.pw_hash and not verify_password(body.current_password or "", u.pw_hash):
            raise HTTPException(400, "current password is incorrect")
        u.pw_hash = hash_password(body.password)
    db.add(u); db.commit()
    return user_out(u)


# --- invites -----------------------------------------------------------------------

def _accept(db: Session, inv: Invite, u: User):
    if not db.get(Member, (inv.workspace_id, u.id)):
        db.add(Member(workspace_id=inv.workspace_id, user_id=u.id, role=inv.role))
    inv.accepted = True
    audit(db, inv.workspace_id, u.id, "member.join", u.email, role=inv.role)


@router.get("/invites/{token}")
def invite_info(token: str, db: Session = Depends(get_db)):
    inv = db.get(Invite, token)
    if not inv or inv.accepted:
        raise HTTPException(404, "invite not found or already used")
    ws = db.get(Workspace, inv.workspace_id)
    return {"email": inv.email, "role": inv.role, "workspace": {"name": ws.name, "slug": ws.slug},
            "has_account": bool(db.scalar(select(User.id).where(User.email == inv.email.lower())))}


@router.post("/invites/{token}/accept")
def invite_accept(token: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    inv = db.get(Invite, token)
    if not inv or inv.accepted:
        raise HTTPException(404, "invite not found or already used")
    if inv.email.lower() != u.email.lower():
        raise HTTPException(403, f"this invite was sent to {inv.email} — sign in with that account")
    _accept(db, inv, u); db.commit()
    ws = db.get(Workspace, inv.workspace_id)
    return {"workspace": ws.slug}


class WorkspaceIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


@router.post("/workspaces")
def new_workspace(body: WorkspaceIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    ws = create_workspace(db, u, body.name.strip()); db.commit()
    return {"slug": ws.slug, "name": ws.name}
