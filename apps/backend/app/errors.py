"""User-facing error text.

Only messages we wrote ourselves may reach a customer. Exception internals, absolute
machine paths and model-server URLs stay in the server log (STANDARDS §2).
"""
import re

from fastapi import HTTPException

GENERIC = "the job failed — see the server log"
GENERIC_REASON = "unavailable on this server — see the server log"
_BY_KIND = {
    "train": "training failed — see the job log",
    "autolabel": "auto-label failed — see the job log",
    "export": "export failed — see the job log",
    "extract_frames": "video extraction failed — see the job log",
    "track_forward": "tracking failed — see the job log",
    "drift": "drift analysis failed — see the job log",
    "connector_sync": "connector sync failed — see the job log",
}
_URL = re.compile(r"[a-z][a-z0-9+.-]*://\S+", re.IGNORECASE)
_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|/(?:home|tmp|var|data|mnt|root|Users)/)\S*")


def _internal(text: str) -> bool:
    return bool(_URL.search(text) or _PATH.search(text))


def safe_error(exc: BaseException, kind: str = "job", limit: int = 500) -> str:
    """A message safe to show for ``exc``; internals collapse to a kind-specific sentence."""
    if isinstance(exc, HTTPException):
        return str(exc.detail)[:limit]
    if isinstance(exc, ValueError):          # our own validation messages
        return str(exc)[:limit]
    if isinstance(exc, RuntimeError):
        msg = str(exc)
        if msg.startswith("vLLM not reachable"):
            return "vLLM not reachable"          # keep the ruled phrase, drop the internal URL
        if msg.startswith("SAM 3.1 is not available"):
            return "SAM 3.1 is not available on this worker"
        if msg and len(msg) <= limit and not _internal(msg):
            return msg
    return _BY_KIND.get(kind, GENERIC)


def safe_reason(text: str | None, limit: int = 200) -> str:
    """Sanitise an adapter/catalog reason before it reaches a user-facing payload."""
    if not text:
        return text or ""
    return GENERIC_REASON if _internal(text) else text[:limit]


def safe_text(text: str | None, kind: str = "job", limit: int = 500) -> str:
    """Sanitise already-formatted error text (e.g. a remote worker's report)."""
    if not text:
        return ""
    return _BY_KIND.get(kind, GENERIC) if _internal(text) else text[:limit]
