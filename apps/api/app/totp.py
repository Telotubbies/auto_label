"""TOTP (RFC 6238, SHA-1 / 6 digits / 30 s) and QR enrolment — no third-party OTP dependency."""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

STEP = 30
DIGITS = 6
ISSUER = "LabelDesk"


def new_secret() -> str:
    """20 random bytes, base32 without padding — what authenticator apps expect."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _counter(at: float | None = None) -> int:
    return int((time.time() if at is None else at) // STEP)


def _hotp(secret: str, counter: int) -> str:
    key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    mac = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    value = struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 10 ** DIGITS:0{DIGITS}d}"


def code_at(secret: str, at: float | None = None) -> str:
    return _hotp(secret, _counter(at))


def matching_step(secret: str | None, code: str, at: float | None = None, window: int = 1) -> int | None:
    """The step a code matches, or None. Accepts the current step plus `window` neighbours for clock drift."""
    if not secret or not code:
        return None
    code = code.strip().replace(" ", "")
    if not code.isdigit() or len(code) != DIGITS:
        return None
    base = _counter(at)
    for d in range(-window, window + 1):
        step = base + d
        if hmac.compare_digest(_hotp(secret, step), code):
            return step
    return None


def verify(secret: str | None, code: str, at: float | None = None, window: int = 1) -> bool:
    return matching_step(secret, code, at, window) is not None


def provisioning_uri(secret: str, email: str, issuer: str = ISSUER) -> str:
    label = quote(f"{issuer}:{email}", safe="")
    return (f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}"
            f"&algorithm=SHA1&digits={DIGITS}&period={STEP}")


def qr_data_uri(text: str) -> str:
    """SVG data URI for <img src>; empty string if segno is not installed (manual key entry still works)."""
    try:
        import segno
    except ImportError:                                   # pragma: no cover - dependency is in requirements
        return ""
    return segno.make(text, error="m").svg_data_uri()


def new_recovery_codes(n: int = 8) -> list[str]:
    """Human-copyable one-time codes; only their hashes are stored."""
    return ["-".join(secrets.token_hex(2) for _ in range(2)) for _ in range(n)]


def normalize_recovery_code(code: str) -> str:
    return code.strip().lower().replace("-", "").replace(" ", "")
