"""RTSP credentials encrypted at rest (PDPA: camera passwords are secrets, not metadata).

The column in ``Stream.source`` holds the full URL; when it contains ``://user:pass@`` the whole
URL is sealed with the Task 24 secretbox (``enc:v1:`` prefix). Credential-free URLs and values that
are already sealed are returned unchanged, so sealing is idempotent.

Task 10b MUST call ``seal_source()`` on stream create/update and ``mask_source()`` in every API
response — never return a stored source verbatim, or the ciphertext (or password) leaks.
"""

import logging
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select

from .. import models
from ..services import secretbox

log = logging.getLogger("labeldesk.streams.creds")


def is_sealed(value) -> bool:
    """True for a secretbox ciphertext (``enc:v1:`` prefix)."""
    return secretbox.is_encrypted(value)


def _has_userinfo(url: str) -> bool:
    """True when the URL carries a username and/or password (both are credentials)."""
    parts = urlsplit(url)
    return "@" in parts.netloc and bool(parts.netloc.rpartition("@")[0])


def seal_source(url: str) -> str:
    """Encrypt a URL that carries credentials; leave plain, credential-free and sealed values as-is."""
    if not isinstance(url, str) or not url or is_sealed(url):
        return url
    return secretbox.encrypt(url) if _has_userinfo(url) else url


def open_source(value: str) -> str:
    """Decrypt a stored source (legacy plaintext passes through); ValueError when a key is missing."""
    return secretbox.decrypt(value)


def mask_source(value: str) -> str:
    """A display-safe URL: password replaced by ``****``; ciphertext is never returned."""
    try:
        url = open_source(value)
    except ValueError:
        return ""
    parts = urlsplit(url)
    if "@" not in parts.netloc:
        return url
    userinfo, _, host = parts.netloc.rpartition("@")
    user, sep, _password = userinfo.partition(":")
    if not sep:
        return url
    return urlunsplit((parts.scheme, f"{user}:****@{host}", parts.path, parts.query, parts.fragment))


def seal_existing(db) -> int:
    """Seal every stored stream source (and finish a key rotation); returns the rows changed.

    When ``LD_SECRET_OLD`` is set, already-sealed rows are re-encrypted under the current key.
    Without that step the documented rotation would leave every camera under the old key and
    removing ``LD_SECRET_OLD`` would make the ciphertext permanently unreadable.
    """
    stream = getattr(models, "Stream", None)
    if stream is None or db is None:
        return 0
    changed = 0
    for row in db.scalars(select(stream)):
        current = getattr(row, "source", "") or ""
        try:
            sealed = (secretbox.reencrypt(current)
                      if secretbox.SECRET_OLD and is_sealed(current) else seal_source(current))
        except ValueError:                     # a row under an unknown key: never abort startup
            log.warning("stream %s: stored source cannot be decrypted; leaving it unchanged", row.id)
            continue
        if sealed != current:
            row.source = sealed
            changed += 1
    if changed:
        db.commit()
    return changed
