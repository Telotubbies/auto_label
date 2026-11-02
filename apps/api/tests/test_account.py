"""Account v2: reset/verification tokens, TOTP MFA, workspace enforcement, sessions, history."""
import hashlib
import hmac
import logging
import os
import re
import secrets
import time

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"
os.environ["LD_MAIL_DEV"] = "1"
os.environ["LD_ENV"] = "dev"
os.environ["LD_PUBLIC_URL"] = "http://localhost:5173"   # the inbox also requires a localhost origin
os.environ.pop("LD_SMTP_HOST", None)          # a developer's exported SMTP config must not change these tests
os.environ.pop("LD_SECRET_OLD", None)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import mailer, ratelimit, security, totp
from app.db import SessionLocal
from app.main import app
from app.models import User
from app.security import recovery_hash, recovery_match, token_hash
from app.services import secretbox

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


def test_new_reset_link_invalidates_the_previous_one():
    c, email, _, _ = signup("reset-chain")
    c.post("/api/auth/password/forgot", json={"email": email})
    first = token_from_link(mail_to("reset", email)["link"])
    c.post("/api/auth/password/forgot", json={"email": email})
    second = token_from_link(mail_to("reset", email)["link"])
    assert first != second

    assert c.post("/api/auth/password/reset", json={"token": first, "password": "brand-new-pass1"}).status_code == 400
    assert c.post("/api/auth/password/reset", json={"token": second, "password": "brand-new-pass1"}).status_code == 200


def test_new_verify_link_invalidates_the_previous_one():
    c, email, _, _ = signup("verify-chain")
    first = token_from_link(mail_to("verify", email)["link"])
    assert c.post("/api/auth/email/resend").status_code == 200
    second = token_from_link(mail_to("verify", email)["link"])
    assert first != second

    assert c.post("/api/auth/email/verify", json={"token": first}).status_code == 400
    assert c.post("/api/auth/email/verify", json={"token": second}).status_code == 200


def test_reset_also_verifies_the_email_address():
    c, email, _, _ = signup("reset-verify")
    assert c.get("/api/me").json()["email_verified"] is None
    c.post("/api/auth/password/forgot", json={"email": email})
    token = token_from_link(mail_to("reset", email)["link"])
    assert c.post("/api/auth/password/reset", json={"token": token, "password": "brand-new-pass1"}).status_code == 200
    assert c.get("/api/me").json()["email_verified"] is not None


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


def test_totp_secret_is_encrypted_at_rest():
    c, email, _, _ = signup("sealed")
    setup = c.post("/api/auth/mfa/setup", json={"password": PW})
    assert setup.status_code == 200, setup.text
    plain = setup.json()["secret"]
    with SessionLocal() as db:
        stored = db.scalar(select(User).where(User.email == email)).totp_secret
    assert stored and stored != plain and stored.startswith(secretbox.PREFIX)
    assert secretbox.decrypt(stored) == plain
    # the encrypted seed still verifies codes
    assert c.post("/api/auth/mfa/enable", json={"code": totp.code_at(plain)}).status_code == 200


def test_plaintext_totp_secret_is_encrypted_by_secretbox_migration():
    c, email, _, _ = signup("legacy-totp")
    secret = totp.new_secret()
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == email))
        u.totp_secret = secret
        db.commit()

    secretbox.migrate()                         # TOTP seeds ride the shared secretbox migration
    with SessionLocal() as db:
        stored = db.scalar(select(User).where(User.email == email)).totp_secret
    assert stored.startswith(secretbox.PREFIX) and secretbox.decrypt(stored) == secret

    secretbox.migrate()                         # idempotent: a second boot must not double-encrypt
    with SessionLocal() as db:
        assert db.scalar(select(User).where(User.email == email)).totp_secret == stored


def test_totp_decrypt_failure_logs_a_warning(caplog):
    c, email, _, _ = signup("bad-seed")
    enrol(c)
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == email))
        u.totp_secret = "enc:v1:not-a-valid-token"
        db.commit()

    caplog.set_level(logging.WARNING, logger="labeldesk")
    anon = TestClient(app)
    challenge = login(anon, email).json()["mfa_token"]
    assert anon.post("/api/auth/mfa/verify", json={"mfa_token": challenge, "code": "123456"}).status_code == 401
    assert any("cannot be decrypted" in record.message for record in caplog.records)


def test_recovery_codes_are_10_base32_characters_and_hmac_hashed():
    c, email, _, _ = signup("recovery-format")
    _, codes = enrol(c)
    assert all(re.fullmatch(r"[A-Z2-7]{10}", code) for code in codes)
    with SessionLocal() as db:
        stored = list(db.scalar(select(User).where(User.email == email)).recovery_codes)
    assert stored == [recovery_hash(code) for code in codes]

    anon = TestClient(app)
    challenge = login(anon, email).json()["mfa_token"]
    assert anon.post("/api/auth/mfa/verify", json={"mfa_token": challenge, "code": codes[0]}).status_code == 200


def test_recovery_code_matches_old_secret_during_rotation(monkeypatch):
    code = "ABCDE23456"
    old = "old-secret-rotation-value-0123456789abcdef"
    old_hash = hmac.new(old.encode(), code.encode(), hashlib.sha256).hexdigest()

    assert recovery_match(code, [old_hash]) is None
    monkeypatch.setattr(security, "SECRET_OLD", old)
    assert recovery_match(code, [old_hash]) == old_hash


def test_recovery_code_from_old_secret_signs_in(monkeypatch):
    c, email, _, _ = signup("rotation-recovery")
    _, codes = enrol(c)
    old = "old-secret-rotation-value-0123456789abcdef"
    old_hash = hmac.new(old.encode(), codes[0].encode(), hashlib.sha256).hexdigest()
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == email))
        u.recovery_codes = [old_hash]         # row written before LD_SECRET rotated
        db.commit()

    monkeypatch.setattr(security, "SECRET_OLD", old)
    anon = TestClient(app)
    challenge = login(anon, email).json()["mfa_token"]
    assert anon.post("/api/auth/mfa/verify", json={"mfa_token": challenge, "code": codes[0]}).status_code == 200


def test_mfa_changes_revoke_other_sessions_but_keep_the_caller():
    email = _email("sessions-mfa")
    c = TestClient(app)
    first = c.post("/api/auth/signup", json={"name": "Session Tester", "email": email, "password": PW}).json()
    c.headers["Authorization"] = f"Bearer {first['token']}"
    second = login(c, email).json()
    assert len(c.get("/api/me/sessions").json()) == 2

    setup = c.post("/api/auth/mfa/setup", json={"password": PW}).json()
    enabled = c.post("/api/auth/mfa/enable", json={"code": totp.code_at(setup["secret"])},
                     headers={"X-Session": first["session"]})
    assert enabled.status_code == 200, enabled.text
    assert [r["id"] for r in c.get("/api/me/sessions").json()] == [first["session"]]

    challenge = login(c, email).json()["mfa_token"]
    extra = c.post("/api/auth/mfa/verify", json={"mfa_token": challenge, "code": enabled.json()["recovery_codes"][0]})
    assert extra.status_code == 200
    assert len(c.get("/api/me/sessions").json()) == 2

    disabled = c.post("/api/auth/mfa/disable", json={"password": PW}, headers={"X-Session": first["session"]})
    assert disabled.status_code == 200, disabled.text
    assert [r["id"] for r in c.get("/api/me/sessions").json()] == [first["session"]]


def test_password_change_revokes_other_sessions():
    email = _email("sessions-pw")
    c = TestClient(app)
    first = c.post("/api/auth/signup", json={"name": "Session Tester", "email": email, "password": PW}).json()
    c.headers["Authorization"] = f"Bearer {first['token']}"
    second = login(c, email).json()
    assert len(c.get("/api/me/sessions").json()) == 2

    r = c.patch("/api/me", json={"current_password": PW, "password": "brand-new-pass1"},
                headers={"X-Session": first["session"]})
    assert r.status_code == 200, r.text
    assert [row["id"] for row in c.get("/api/me/sessions").json()] == [first["session"]]
    assert c.post("/api/auth/refresh", json={"refresh_token": second["refresh_token"]}).status_code == 401


def test_refresh_keeps_the_session_created_time():
    email = _email("rotate")
    c = TestClient(app)
    first = c.post("/api/auth/signup", json={"name": "Rotate Tester", "email": email, "password": PW}).json()
    c.headers["Authorization"] = f"Bearer {first['token']}"
    before = c.get("/api/me/sessions").json()[0]

    rotated = c.post("/api/auth/refresh", json={"refresh_token": first["refresh_token"]}).json()
    assert rotated["session"] != before["id"]
    c.headers["Authorization"] = f"Bearer {rotated['token']}"
    after = c.get("/api/me/sessions").json()[0]
    assert after["id"] == rotated["session"] and after["created"] == before["created"]
    assert after["last_seen"] >= before["last_seen"]


def test_refresh_rejects_deleted_user():
    from app.models import RefreshToken
    from app.security import new_refresh

    email = _email("deleted")
    with SessionLocal() as db:
        u = User(email=email, name="Gone Tester", pw_hash="")
        db.add(u); db.flush()
        rt, exp = new_refresh()
        db.add(RefreshToken(token=token_hash(rt), user_id=u.id, expires=exp))
        db.commit()
        uid = u.id
    with SessionLocal() as db:
        db.delete(db.get(User, uid))
        db.commit()
    assert TestClient(app).post("/api/auth/refresh", json={"refresh_token": rt}).status_code == 401


def test_dev_inbox_requires_explicit_flag_and_local_origin():
    assert mailer.inbox_allowed(True, "1", "http://localhost:5173")
    assert mailer.inbox_allowed(True, "1", "http://127.0.0.1:8010")
    assert not mailer.inbox_allowed(True, None, "http://localhost:5173")
    assert not mailer.inbox_allowed(True, "0", "http://localhost:5173")
    assert not mailer.inbox_allowed(True, "1", "https://app.labeldesk.dev")
    assert not mailer.inbox_allowed(False, "1", "http://localhost:5173")


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
