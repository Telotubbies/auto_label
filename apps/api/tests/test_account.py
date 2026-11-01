"""Account v2: reset/verification tokens, TOTP MFA, workspace enforcement, sessions, history."""
import os
import secrets
import tempfile
import time

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-account-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"
os.environ["LD_MAIL_DEV"] = "1"
os.environ["LD_ENV"] = "dev"
os.environ.pop("LD_SMTP_HOST", None)          # a developer's exported SMTP config must not change these tests

import pytest
from fastapi.testclient import TestClient

from app import mailer, ratelimit, totp
from app.main import app
from app.security import token_hash

PW = "longpassword1"


@pytest.fixture(autouse=True)
def clean_rate_limit():
    """Every test starts with an empty sliding window — the suite shares one process."""
    ratelimit._hits.clear()
    ratelimit.ENABLED = True
    yield


@pytest.fixture(scope="module", autouse=True)
def db_ready():
    """Entering the app runs lifespan/init_db once; later TestClient(app) instances reuse that schema."""
    with TestClient(app):
        yield


def _email(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4)}@example.com"


def signup(prefix: str = "acct") -> tuple[TestClient, str, str, str]:
    """-> client (with bearer), email, access token, workspace slug."""
    email = _email(prefix)
    c = TestClient(app)
    r = c.post("/api/auth/signup", json={"name": "Account Tester", "email": email, "password": PW})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    c.headers["Authorization"] = f"Bearer {token}"
    ws = c.get("/api/me").json()["workspaces"][0]["slug"]
    return c, email, token, ws


def mail_to(kind: str, to: str) -> dict:
    rows = [m for m in mailer.outbox() if m["kind"] == kind and m["to"] == to]
    assert rows, f"no {kind} mail for {to}: {[m['subject'] for m in mailer.outbox()]}"
    return rows[-1]


def token_from_link(link: str) -> str:
    return link.rstrip("/").rsplit("/", 1)[-1]


def login(c: TestClient, email: str, pw: str = PW):
    return c.post("/api/auth/login", json={"email": email, "password": pw})


# --- TOTP --------------------------------------------------------------------------

def test_totp_matches_rfc6238_vectors():
    # Appendix B: ASCII secret "12345678901234567890", 6-digit truncation.
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert totp.code_at(secret, 59) == "287082"
    assert totp.verify(secret, "287082", at=59)
    assert totp.verify(secret, "287082", at=89)          # one step of drift is accepted
    assert not totp.verify(secret, "287082", at=149)
    assert not totp.verify(secret, "000000", at=59)


# --- password reset ----------------------------------------------------------------

def test_password_reset_token_is_single_use():
    c, email, _, _ = signup("reset")
    assert c.post("/api/auth/password/forgot", json={"email": email}).status_code == 200
    token = token_from_link(mail_to("reset", email)["link"])

    r = c.post("/api/auth/password/reset", json={"token": token, "password": "brand-new-pass1"})
    assert r.status_code == 200, r.text
    assert login(c, email, "brand-new-pass1").status_code == 200

    again = c.post("/api/auth/password/reset", json={"token": token, "password": "another-pass1"})
    assert again.status_code == 400
    assert "invalid or expired" in again.text


def test_password_reset_token_expires():
    from app.db import SessionLocal
    from app.models import EmailToken, User

    c, email, _, _ = signup("expired")
    with SessionLocal() as db:
        uid = db.query(User).filter_by(email=email).one().id
        raw = "expired-" + secrets.token_urlsafe(12)
        db.add(EmailToken(token=token_hash(raw), user_id=uid, kind="reset", expires=time.time() - 1))
        db.commit()

    r = c.post("/api/auth/password/reset", json={"token": raw, "password": "another-pass1"})
    assert r.status_code == 400


def test_forgot_password_does_not_reveal_accounts():
    known, email, _, _ = signup("enum-known")
    anon = TestClient(app)
    a = anon.post("/api/auth/password/forgot", json={"email": email})
    b = anon.post("/api/auth/password/forgot", json={"email": _email("enum-ghost")})
    assert a.status_code == b.status_code == 200
    assert a.json() == b.json()
    assert mail_to("reset", email)


def test_reset_revokes_existing_sessions():
    c, email, _, _ = signup("revoke")
    assert c.post("/api/auth/password/forgot", json={"email": email}).status_code == 200
    token = token_from_link(mail_to("reset", email)["link"])
    rt = login(c, email).json()["refresh_token"]

    assert c.post("/api/auth/password/reset", json={"token": token, "password": "brand-new-pass1"}).status_code == 200
    assert c.post("/api/auth/refresh", json={"refresh_token": rt}).status_code == 401


# --- email verification ------------------------------------------------------------

def test_email_verification_link_verifies_and_is_single_use():
    c, email, _, _ = signup("verify")
    assert c.get("/api/me").json()["email_verified"] is None
    token = token_from_link(mail_to("verify", email)["link"])

    r = c.post("/api/auth/email/verify", json={"token": token})
    assert r.status_code == 200, r.text
    assert c.get("/api/me").json()["email_verified"]
    assert c.post("/api/auth/email/verify", json={"token": token}).status_code == 400
    assert c.post("/api/auth/email/resend").status_code == 200


# --- MFA ---------------------------------------------------------------------------

def enrol(c: TestClient, password: str = PW) -> tuple[dict, list[str]]:
    setup = c.post("/api/auth/mfa/setup", json={"password": password})
    assert setup.status_code == 200, setup.text
    data = setup.json()
    assert data["secret"] and data["otpauth"].startswith("otpauth://totp/") and data["qr"].startswith("data:image/svg+xml")
    enabled = c.post("/api/auth/mfa/enable", json={"code": totp.code_at(data["secret"])})
    assert enabled.status_code == 200, enabled.text
    codes = enabled.json()["recovery_codes"]
    assert len(codes) == 8 and len(set(codes)) == 8
    # The enrolment code is spent. The suite runs inside one 30 s step, so pretend that step passed.
    from app.db import SessionLocal
    from app.models import User
    from app.security import verify_access
    from sqlalchemy import select
    uid = verify_access(c.headers["Authorization"].removeprefix("Bearer "))["sub"]
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.id == uid))
        u.totp_last_step = 0
        db.commit()
    return data, codes


def test_mfa_required_when_workspace_enforces_it():
    a, email_a, _, ws = signup("mfa-admin")
    anon = TestClient(app)

    # Can't lock the workspace behind MFA before securing your own account.
    assert a.patch(f"/api/ws/{ws}", json={"require_mfa": True}).status_code == 400
    setup, codes = enrol(a)
    assert a.get("/api/me").json()["mfa_enabled"] is True
    assert a.patch(f"/api/ws/{ws}", json={"require_mfa": True}).status_code == 200
    assert a.get("/api/me").json()["workspaces"][0]["mfa_required"] is True

    # Password alone no longer logs in; only a TOTP (or recovery) code completes it.
    first = login(anon, email_a)
    assert first.status_code == 200
    assert first.json()["mfa_required"] is True and first.json()["mfa_token"]
    assert "token" not in first.json()
    mfa_token = first.json()["mfa_token"]
    assert anon.post("/api/auth/mfa/verify", json={"mfa_token": mfa_token, "code": "000000"}).status_code == 401
    # an MFA-pending token is not an access token
    assert anon.get("/api/me", headers={"Authorization": f"Bearer {mfa_token}"}).status_code == 401

    ok = anon.post("/api/auth/mfa/verify", json={"mfa_token": mfa_token, "code": totp.code_at(setup["secret"])})
    assert ok.status_code == 200, ok.text
    admin = {"Authorization": f"Bearer {ok.json()['token']}"}
    assert anon.get(f"/api/ws/{ws}", headers=admin).status_code == 200

    # Recovery codes work once each.
    rec = login(anon, email_a).json()["mfa_token"]
    used = anon.post("/api/auth/mfa/verify", json={"mfa_token": rec, "code": codes[0]})
    assert used.status_code == 200, used.text
    again = login(anon, email_a).json()["mfa_token"]
    assert anon.post("/api/auth/mfa/verify", json={"mfa_token": again, "code": codes[0]}).status_code == 401

    # A member without MFA is blocked from the workspace but can still enrol.
    b_email = _email("mfa-member")
    invite = a.post(f"/api/ws/{ws}/invites", json={"email": b_email, "role": "annotator"}).json()["token"]
    b = TestClient(app)
    rb = b.post("/api/auth/signup", json={"name": "Member", "email": b_email, "password": PW, "invite": invite})
    assert rb.status_code == 200, rb.text
    b.headers["Authorization"] = f"Bearer {rb.json()['token']}"
    blocked = b.get(f"/api/ws/{ws}")
    assert blocked.status_code == 403 and "two-factor" in blocked.text

    enrol(b)
    assert b.get(f"/api/ws/{ws}").status_code == 200


def test_mfa_disable_needs_password():
    c, _, _, _ = signup("mfa-off")
    assert c.post("/api/auth/mfa/setup", json={"password": "wrong-password"}).status_code == 400
    enrol(c)
    assert c.post("/api/auth/mfa/disable", json={"password": "wrong-password"}).status_code == 400
    assert c.get("/api/me").json()["mfa_enabled"] is True
    assert c.post("/api/auth/mfa/disable", json={"password": PW}).status_code == 200
    assert c.get("/api/me").json()["mfa_enabled"] is False


# --- sessions & login history -------------------------------------------------------

def test_totp_code_cannot_be_replayed():
    c, email, _, _ = signup("mfa-replay")
    data, _ = enrol(c)
    anon = TestClient(app)
    step_code = totp.code_at(data["secret"])

    first = anon.post("/api/auth/mfa/verify", json={"mfa_token": login(anon, email).json()["mfa_token"], "code": step_code})
    assert first.status_code == 200, first.text
    second = anon.post("/api/auth/mfa/verify", json={"mfa_token": login(anon, email).json()["mfa_token"], "code": step_code})
    assert second.status_code == 401


def test_dev_inbox_is_closed_when_disabled(monkeypatch):
    monkeypatch.setattr(mailer, "INBOX_ENABLED", False)
    assert TestClient(app).get("/__mail").status_code == 404


def test_session_list_and_revoke():
    c, email, token, _ = signup("sessions")
    second = login(c, email).json()

    rows = c.get("/api/me/sessions").json()
    assert len(rows) >= 2
    assert all({"id", "created", "last_seen", "ip", "user_agent"} <= set(r) for r in rows)

    assert c.delete(f"/api/me/sessions/{second['session']}").status_code == 200
    assert c.post("/api/auth/refresh", json={"refresh_token": second["refresh_token"]}).status_code == 401
    # the caller's own session survives
    assert c.get("/api/me").status_code == 200

    # another user's session id is a 404, not a revocation
    other, _, other_token, _ = signup("sessions-other")
    other_sid = other.get("/api/me/sessions").json()[0]["id"]
    assert c.delete(f"/api/me/sessions/{other_sid}").status_code == 404


def test_login_history_records_success_and_failure():
    c, email, _, _ = signup("history")
    assert login(c, email, "wrong-password").status_code == 401
    assert login(c, email).status_code == 200

    rows = c.get("/api/me/logins").json()
    assert rows and rows[0]["created"] >= rows[-1]["created"]
    assert any(r["ok"] for r in rows) and any(not r["ok"] for r in rows)
    assert all({"method", "ok", "ip", "user_agent", "created"} <= set(r) for r in rows)


# --- rate limits & dev mail ---------------------------------------------------------

def test_auth_rate_limits_kept():
    anon = TestClient(app)
    codes = [anon.post("/api/auth/password/forgot", json={"email": _email("spam")}).status_code for _ in range(7)]
    assert codes[0] == 200 and 429 in codes

    email = _email("bruteforce")
    login(anon, email, "x")
    codes = [login(anon, email, "x").status_code for _ in range(9)]
    assert 429 in codes


def test_dev_mail_page_shows_last_mail():
    c, email, _, _ = signup("mailpage")
    c.post("/api/auth/password/forgot", json={"email": email})
    r = TestClient(app).get("/__mail")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert email in r.text and "Reset your LabelDesk password" in r.text


def test_invite_sends_a_mail():
    c, _, _, ws = signup("invite-mail")
    email = _email("invitee")
    c.post(f"/api/ws/{ws}/invites", json={"email": email, "role": "annotator"})
    mail = mail_to("invite", email)
    assert "/invite/" in mail["link"]
