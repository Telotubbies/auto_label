"""Symmetric encryption for secrets stored in the DB (connector credentials, webhook signing keys).

The Fernet key is derived from `config.SECRET` with SHA-256, so rotating LD_SECRET makes old
ciphertexts undecryptable by design. Ciphertext carries the `enc:v1:` prefix; values without it are
legacy plaintext and are encrypted once by `migrate()` at startup.
"""
import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from ..config import SECRET

PREFIX = "enc:v1:"


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = hashlib.sha256(f"labeldesk-secretbox:{SECRET}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


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


def encrypt_config(config: dict, fields: tuple[str, ...]) -> dict:
    """Copy `config` with every present secret field encrypted (empty values stay empty)."""
    out = dict(config or {})
    for field in fields:
        if out.get(field):
            out[field] = encrypt(str(out[field]))
    return out


def migrate() -> None:
    """Encrypt existing plaintext connector/webhook secrets exactly once. Idempotent."""
    from sqlalchemy import select

    from ..db import SessionLocal
    from ..models import Connector, Webhook
    from .connectors import SECRET_FIELDS

    with SessionLocal() as db:
        for conn in db.scalars(select(Connector)):
            config = dict(conn.config or {})
            changed = False
            for field in SECRET_FIELDS:
                value = config.get(field)
                if value and not is_encrypted(value):
                    config[field] = encrypt(str(value))
                    changed = True
            if changed:
                conn.config = config
        for hook in db.scalars(select(Webhook)):
            if hook.secret and not is_encrypted(hook.secret):
                hook.secret = encrypt(hook.secret)
        db.commit()
