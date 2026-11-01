"""Symmetric encryption for secrets stored in the DB (connector credentials, webhook signing keys, TOTP seeds).

The Fernet key is derived from `config.SECRET` with SHA-256. Ciphertext carries the `enc:v1:`
prefix; values without it are legacy plaintext and are encrypted once by `migrate()` at startup.

Rotating LD_SECRET: set LD_SECRET to the new value and LD_SECRET_OLD to the previous one(s)
(comma-separated), then restart. MultiFernet still decrypts rows written with the old key, and the
startup migration re-encrypts them under the new key. Remove LD_SECRET_OLD once the logs show a
clean startup. Dropping an old secret before its rows are re-encrypted makes those rows unreadable.
"""
import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from ..config import SECRET, SECRET_OLD

PREFIX = "enc:v1:"


def _key(secret: str) -> bytes:
    return base64.urlsafe_b64encode(hashlib.sha256(f"labeldesk-secretbox:{secret}".encode()).digest())


@lru_cache(maxsize=1)
def _fernet() -> MultiFernet:
    secrets = [SECRET] + [s.strip() for s in (SECRET_OLD or "").split(",") if s.strip()]
    return MultiFernet([Fernet(_key(s)) for s in secrets])


def is_encrypted(value) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


def encrypt(value: str) -> str:
    if is_encrypted(value):
        return value
    return PREFIX + _fernet().encrypt(str(value).encode()).decode()


def decrypt(value: str) -> str:
    """Decrypt a stored value; legacy plaintext is returned unchanged (migration has not run yet)."""
    if not is_encrypted(value):
        return value
    try:
        return _fernet().decrypt(value[len(PREFIX):].encode()).decode()
    except InvalidToken as e:
        raise ValueError("stored secret cannot be decrypted (LD_SECRET changed?)") from e


def _reencrypt(value: str) -> str:
    """Move a ciphertext to the current key (used while LD_SECRET_OLD is set)."""
    return PREFIX + _fernet().rotate(value[len(PREFIX):].encode()).decode()


def encrypt_config(config: dict, fields: tuple[str, ...]) -> dict:
    """Copy `config` with every present secret field encrypted (empty values stay empty)."""
    out = dict(config or {})
    for field in fields:
        if out.get(field):
            out[field] = encrypt(str(out[field]))
    return out


def migrate() -> None:
    """Encrypt existing plaintext secrets (connectors, webhooks, TOTP seeds) and finish a key rotation. Idempotent."""
    from sqlalchemy import select

    from ..config import SECRET_OLD
    from ..db import SessionLocal
    from ..models import Connector, User, Webhook
    from .connectors import SECRET_FIELDS

    with SessionLocal() as db:
        for conn in db.scalars(select(Connector)):
            config = dict(conn.config or {})
            changed = False
            for field in SECRET_FIELDS:
                value = config.get(field)
                if not value:
                    continue
                if not is_encrypted(value):
                    config[field] = encrypt(str(value))
                    changed = True
                elif SECRET_OLD:
                    config[field] = _reencrypt(str(value))      # finish a key rotation
                    changed = True
            if changed:
                conn.config = config
        for hook in db.scalars(select(Webhook)):
            if not hook.secret:
                continue
            if not is_encrypted(hook.secret):
                hook.secret = encrypt(hook.secret)
            elif SECRET_OLD:
                hook.secret = _reencrypt(hook.secret)
        for user in db.scalars(select(User).where(User.totp_secret.is_not(None))):
            if not user.totp_secret:
                continue
            if not is_encrypted(user.totp_secret):
                user.totp_secret = encrypt(user.totp_secret)
            elif SECRET_OLD:
                user.totp_secret = _reencrypt(user.totp_secret)
        db.commit()
