"""Signup / login / refresh / profile / invites, plus account v2: email links, TOTP MFA, sessions, history."""
import logging
import re
import secrets
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import mailer, oidc, totp
from ..config import PUBLIC_URL, SIGNUP_ENABLED
from ..db import get_db
from ..deps import audit, current_user, plan
from ..models import EmailToken, Invite, LoginEvent, Member, RefreshToken, User, Workspace
from ..ratelimit import client_ip, limit
from ..security import (hash_password, issue_access, issue_mfa_pending, new_refresh, recovery_hash, recovery_match,
                        token_hash, verify_mfa, verify_password)

_DUMMY_HASH = hash_password('timing-equaliser')
from ..services import secretbox, segment

log = logging.getLogger("labeldesk")

router = APIRouter(prefix="/api", tags=["auth"])

RESET_TTL = 30 * 60
VERIFY_TTL = 24 * 3600


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


def _agent(request: Request | None) -> tuple[str, str]:
    if not request:
        return "", ""
    return client_ip(request), (request.headers.get("user-agent") or "")[:255]


def tokens(db: Session, u: User, request: Request | None = None, created: float | None = None) -> dict:
    rt, exp = new_refresh()
    ip, ua = _agent(request)
    now = time.time()
    row = RefreshToken(token=token_hash(rt), user_id=u.id, expires=exp, created=created or now, last_seen=now,
                       ip=ip, user_agent=ua)
    db.add(row); db.commit()                                  # only the hash is stored
    return {"token": issue_access(u.id), "refresh_token": rt, "user": user_out(u), "session": row.token}


def _record(db: Session, u: User | None, request: Request, method: str, ok: bool):
    """Login history. Unknown emails are not recorded — there is no account to show them on."""
    if not u:
        return
    ip, ua = _agent(request)
    db.add(LoginEvent(user_id=u.id, email=u.email, method=method, ok=ok, ip=ip, user_agent=ua))
    db.commit()


def _email_token(db: Session, u: User, kind: str, ttl: float) -> str:
    """Mint one link token; any other token of the same kind stops working immediately."""
    now = time.time()
    db.execute(delete(EmailToken).where(EmailToken.user_id == u.id, EmailToken.kind == kind))
    raw = secrets.token_urlsafe(32)
    db.add(EmailToken(token=token_hash(raw), user_id=u.id, kind=kind, expires=now + ttl))
    db.commit()
    return raw


def _send_link(u: User, kind: str, raw: str):
    path = "reset" if kind == "reset" else "verify"
    link = f"{PUBLIC_URL}/{path}/{raw}"
    if kind == "reset":
        subject = "Reset your LabelDesk password"
        text = (f"Hi {u.name},\n\nUse the link below to choose a new password. It works once and expires in "
                f"30 minutes.\n\n{link}\n\nIf you didn't ask for this, you can ignore this email.")
    else:
        subject = "Verify your LabelDesk email"
        text = (f"Hi {u.name},\n\nConfirm this email address so we can reach you about your account.\n\n"
                f"{link}\n\nThe link expires in 24 hours.")
    mailer.send(u.email, subject, text, link=link, kind=kind)


def _totp_secret(u: User) -> str | None:
    """Decrypt the stored seed through secretbox (which also accepts a not-yet-migrated plaintext seed)."""
    if not u.totp_secret:
        return None
    try:
        return secretbox.decrypt(u.totp_secret)
    except ValueError:
        log.warning("TOTP secret for user %s cannot be decrypted (LD_SECRET changed?)", u.id)
        return None


def _second_factor_ok(db: Session, u: User, code: str) -> bool:
    """TOTP code or an unused recovery code (consumed on success). A code can only be used once."""
    step = totp.matching_step(_totp_secret(u), code)
    if step is not None:
        if step <= (u.totp_last_step or 0):           # replay of a code already spent this step
            return False
        u.totp_last_step = step
        db.add(u); db.commit()
        return True
    matched = recovery_match(code, u.recovery_codes or [])
    if matched:
        u.recovery_codes = [h for h in u.recovery_codes if h != matched]
        db.add(u); db.commit()
        return True
    return False


def _revoke_other_sessions(db: Session, u: User, request: Request):
    """Sign out every other device; the caller's session id travels in X-Session."""
    keep = request.headers.get("x-session", "").strip()
    stmt = delete(RefreshToken).where(RefreshToken.user_id == u.id)
    if keep:
        stmt = stmt.where(RefreshToken.token != keep)
    db.execute(stmt)


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
    _send_link(u, "verify", _email_token(db, u, "verify", VERIFY_TTL))
    return tokens(db, u, request)


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
        _record(db, u, request, "password", False)
        raise HTTPException(401, "invalid email or password")
    if u.mfa_enabled:
        # Password step passed; the session is only created after the second factor.
        return {"mfa_required": True, "mfa_token": issue_mfa_pending(u.id)}
    _record(db, u, request, "password", True)
    return tokens(db, u, request)


class MfaVerifyIn(BaseModel):
    mfa_token: str
    code: str = Field(min_length=1, max_length=32)


@router.post("/auth/mfa/verify")
def mfa_verify(body: MfaVerifyIn, request: Request, db: Session = Depends(get_db)):
    limit(f"mfa:{client_ip(request)}", 20, 300)
    claims = verify_mfa(body.mfa_token)
    u = db.get(User, claims["sub"]) if claims else None
    if not u or not u.mfa_enabled:
        raise HTTPException(401, "verification expired — sign in again")
    limit(f"mfa:{u.id}", 10, 300)
    if not _second_factor_ok(db, u, body.code):
        _record(db, u, request, "mfa", False)
        raise HTTPException(401, "that code didn't work — check your authenticator and try again")
    _record(db, u, request, "mfa", True)
    return tokens(db, u, request)


class RefreshIn(BaseModel):
    refresh_token: str


@router.post("/auth/refresh")
def refresh(body: RefreshIn, request: Request, db: Session = Depends(get_db)):
    limit(f"refresh:{client_ip(request)}", 60, 60)
    row = db.get(RefreshToken, token_hash(body.refresh_token))
    if not row or row.expires < time.time():
        raise HTTPException(401, "session expired")
    u = db.get(User, row.user_id)
    if not u:
        db.execute(delete(RefreshToken).where(RefreshToken.token == row.token)); db.commit()
        raise HTTPException(401, "session expired")
    db.execute(delete(RefreshToken).where((RefreshToken.token == row.token) | (RefreshToken.expires < time.time())))
    return tokens(db, u, request, created=row.created)


@router.post("/auth/logout")
def logout(body: RefreshIn, db: Session = Depends(get_db)):
    db.execute(delete(RefreshToken).where(RefreshToken.token == token_hash(body.refresh_token))); db.commit()
    return {"ok": True}


# --- password reset & email verification ---------------------------------------------

class ForgotIn(BaseModel):
    email: str = Field(max_length=255)


@router.post("/auth/password/forgot")
def forgot_password(body: ForgotIn, request: Request, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    ip = client_ip(request)
    limit(f"forgot:{ip}", 5, 900)
    limit(f"forgot:{ip}:{email}", 3, 900)
    u = db.scalar(select(User).where(User.email == email))
    if u:
        _send_link(u, "reset", _email_token(db, u, "reset", RESET_TTL))
    # Same answer whether or not the account exists.
    return {"ok": True, "message": "If an account exists for that email, a reset link is on its way."}


class ResetIn(BaseModel):
    token: str = Field(max_length=200)
    password: str = Field(min_length=8, max_length=200)


@router.post("/auth/password/reset")
def reset_password(body: ResetIn, request: Request, db: Session = Depends(get_db)):
    limit(f"reset:{client_ip(request)}", 10, 900)
    row = db.get(EmailToken, token_hash(body.token))
    if not row or row.kind != "reset" or row.used or row.expires < time.time():
        raise HTTPException(400, "invalid or expired reset link")
    u = db.get(User, row.user_id)
    if not u:
        raise HTTPException(400, "invalid or expired reset link")
    u.pw_hash = hash_password(body.password)
    u.email_verified = u.email_verified or time.time()     # the link arrived in their inbox
    row.used = True
    # A stolen password should not survive its reset: sign every device out.
    db.execute(delete(RefreshToken).where(RefreshToken.user_id == u.id))
    db.add(u); db.commit()
    return {"ok": True}


class VerifyEmailIn(BaseModel):
    token: str = Field(max_length=200)


@router.post("/auth/email/verify")
def verify_email(body: VerifyEmailIn, request: Request, db: Session = Depends(get_db)):
    limit(f"verify-email:{client_ip(request)}", 20, 900)
    row = db.get(EmailToken, token_hash(body.token))
    if not row or row.kind != "verify" or row.used or row.expires < time.time():
        raise HTTPException(400, "invalid or expired verification link")
    u = db.get(User, row.user_id)
    if not u:
        raise HTTPException(400, "invalid or expired verification link")
    u.email_verified = time.time()
    row.used = True
    db.add(u); db.commit()
    return {"ok": True, "email": u.email, "email_verified": u.email_verified}


@router.post("/auth/email/resend")
def resend_verification(u: User = Depends(current_user), db: Session = Depends(get_db)):
    limit(f"verify-resend:{u.id}", 3, 3600)
    if u.email_verified:
        return {"ok": True, "already_verified": True}
    _send_link(u, "verify", _email_token(db, u, "verify", VERIFY_TTL))
    return {"ok": True}


# --- TOTP enrolment -------------------------------------------------------------------

class MfaSetupIn(BaseModel):
    password: str


@router.post("/auth/mfa/setup")
def mfa_setup(body: MfaSetupIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    limit(f"pwcheck:{u.id}", 5, 900)
    if not verify_password(body.password, u.pw_hash):
        raise HTTPException(400, "password is incorrect")
    if u.mfa_enabled:
        raise HTTPException(400, "two-factor authentication is already enabled")
    secret = totp.new_secret()
    u.totp_secret = secretbox.encrypt(secret)
    db.add(u); db.commit()
    uri = totp.provisioning_uri(secret, u.email)
    return {"secret": secret, "otpauth": uri, "qr": totp.qr_data_uri(uri)}


class MfaCodeIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)


@router.post("/auth/mfa/enable")
def mfa_enable(body: MfaCodeIn, request: Request, u: User = Depends(current_user), db: Session = Depends(get_db)):
    limit(f"mfa-enable:{u.id}", 10, 3600)
    if u.mfa_enabled:
        raise HTTPException(400, "two-factor authentication is already enabled")
    if not u.totp_secret:
        raise HTTPException(400, "start the setup first")
    step = totp.matching_step(_totp_secret(u), body.code)
    if step is None:
        raise HTTPException(400, "that code didn't work — check your authenticator and try again")
    codes = totp.new_recovery_codes()
    u.recovery_codes = [recovery_hash(c) for c in codes]
    u.totp_last_step = step                        # the enrolment code cannot be replayed at sign-in
    u.mfa_enabled = True
    db.add(u)
    _revoke_other_sessions(db, u, request)          # a stolen session must not survive enrolment
    db.commit()
    return {"recovery_codes": codes}


class MfaDisableIn(BaseModel):
    password: str


@router.post("/auth/mfa/disable")
def mfa_disable(body: MfaDisableIn, request: Request, u: User = Depends(current_user), db: Session = Depends(get_db)):
    limit(f"pwcheck:{u.id}", 5, 900)
    if not verify_password(body.password, u.pw_hash):
        raise HTTPException(400, "password is incorrect")
    enforced = db.scalar(select(Workspace.id).join(Member, Member.workspace_id == Workspace.id)
                         .where(Member.user_id == u.id, Workspace.require_mfa.is_(True)).limit(1))
    if enforced:
        raise HTTPException(400, "a workspace you belong to requires two-factor authentication")
    u.mfa_enabled = False
    u.totp_secret = None
    u.recovery_codes = []
    u.totp_last_step = 0
    db.add(u)
    _revoke_other_sessions(db, u, request)          # removing a factor signs other devices out
    db.commit()
    return {"ok": True}


# --- profile, sessions, history -------------------------------------------------------

@router.get("/me")
def me(u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(Workspace, Member.role).join(Member, Member.workspace_id == Workspace.id)
                      .where(Member.user_id == u.id).order_by(Workspace.created)).all()
    return {**user_out(u), "email_verified": u.email_verified, "mfa_enabled": u.mfa_enabled,
            "workspaces": [{"id": w.id, "slug": w.slug, "name": w.name, "role": r, "plan": w.plan,
                            "plan_label": plan(w)["label"], "owner": w.owner_id == u.id,
                            "mfa_required": bool(w.require_mfa)} for w, r in rows]}


class MePatch(BaseModel):
    name: str | None = None
    password: str | None = Field(default=None, min_length=8)
    current_password: str | None = None


@router.patch("/me")
def patch_me(body: MePatch, request: Request, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.name:
        u.name = body.name.strip()
    if body.password:
        limit(f"pwcheck:{u.id}", 5, 900)
        if u.pw_hash and not verify_password(body.current_password or "", u.pw_hash):
            raise HTTPException(400, "current password is incorrect")
        u.pw_hash = hash_password(body.password)
        _revoke_other_sessions(db, u, request)      # a new password should end old sessions
    db.add(u); db.commit()
    return user_out(u)


@router.get("/me/sessions")
def sessions(u: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(RefreshToken).where(RefreshToken.user_id == u.id, RefreshToken.expires < time.time()))
    db.commit()
    rows = db.scalars(select(RefreshToken).where(RefreshToken.user_id == u.id)
                      .order_by(RefreshToken.last_seen.desc(), RefreshToken.created.desc())).all()
    return [{"id": r.token, "created": r.created, "last_seen": r.last_seen, "ip": r.ip,
             "user_agent": r.user_agent} for r in rows]


@router.delete("/me/sessions/{sid}")
def revoke_session(sid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.get(RefreshToken, sid)
    if not row or row.user_id != u.id:
        raise HTTPException(404, "session not found")
    db.delete(row); db.commit()
    return {"ok": True}


@router.get("/me/logins")
def login_history(limit: int = 50, u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(LoginEvent).where(LoginEvent.user_id == u.id)
                      .order_by(LoginEvent.created.desc()).limit(min(max(limit, 1), 200))).all()
    return [{"method": r.method, "ok": r.ok, "ip": r.ip, "user_agent": r.user_agent, "created": r.created}
            for r in rows]


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
