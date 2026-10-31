"""Passwords, JWTs, signed file URLs, API keys."""
import base64
import hashlib
import hmac
import secrets
import time

import jwt

from .config import SECRET

ALG = "HS256"
ACCESS_TTL = 15 * 60
REFRESH_TTL = 30 * 24 * 3600
FILE_URL_TTL = 6 * 3600
_PBKDF2_ROUNDS = 260_000


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2${_PBKDF2_ROUNDS}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, rounds, salt, dk = stored.split("$")
        got = hashlib.pbkdf2_hmac("sha256", pw.encode(), base64.b64decode(salt), int(rounds))
        return hmac.compare_digest(got, base64.b64decode(dk))
    except Exception:
        return False


def issue_access(user_id: str) -> str:
    t = int(time.time())
    return jwt.encode({"sub": user_id, "iat": t, "exp": t + ACCESS_TTL}, SECRET, algorithm=ALG)


def verify_access(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET, algorithms=[ALG])
    except jwt.PyJWTError:
        return None


def token_hash(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


def new_refresh() -> tuple[str, float]:
    return secrets.token_urlsafe(32), time.time() + REFRESH_TTL


# --- signed file urls: <img src> can't send bearer headers ------------------

def sign_path(rel: str, ttl: int = FILE_URL_TTL) -> str:
    # expiry is rounded up to the hour so the same file keeps the same URL for a while —
    # otherwise every API response mints new URLs and the browser can never cache thumbnails
    exp = (int(time.time()) // 3600 + 1) * 3600 + ttl
    sig = hmac.new(SECRET.encode(), f"{rel}:{exp}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"/api/files/{rel}?exp={exp}&sig={sig}"


def check_signature(rel: str, exp: int, sig: str) -> bool:
    if exp < time.time():
        return False
    want = hmac.new(SECRET.encode(), f"{rel}:{exp}".encode(), hashlib.sha256).hexdigest()[:32]
    return hmac.compare_digest(want, sig)


# --- api keys ----------------------------------------------------------------

def new_api_key() -> tuple[str, str, str]:
    """-> (plaintext shown once, display prefix, sha256 stored)."""
    key = "ld_" + secrets.token_urlsafe(30)
    return key, key[:10], hashlib.sha256(key.encode()).hexdigest()


def api_key_hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()
