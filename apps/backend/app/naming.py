"""Safe display names that may become file-system path segments.

Class names reach the folder exporter, so they are the one user string that must never
contain a path separator, a traversal segment or a control character. Letters, combining
marks (Thai vowels/tone marks), numbers, spaces and ``. ( ) - _`` stay allowed.
"""
import re
import unicodedata

_MAX = 120
_ALLOWED_PUNCT = frozenset(" .()-_")
_MESSAGE = "class names may contain letters, numbers, spaces and . ( ) - only"


def clean_class_name(raw: str) -> str:
    """Return the stripped class name or raise ``ValueError`` for anything path-like."""
    name = (raw or "").strip()
    if not name or len(name) > _MAX or name in (".", "..") or ".." in name:
        raise ValueError(_MESSAGE)
    for ch in name:
        if ch in _ALLOWED_PUNCT or unicodedata.category(ch)[0] in "LMN":
            continue
        raise ValueError(_MESSAGE)
    return name


def path_segment(name: str, fallback: str = "_unlabeled") -> str:
    """The last path component of ``name``; empty/traversal names fall back to a safe constant."""
    segment = re.split(r"[\\/]", name or "")[-1].strip()
    if not segment or segment in (".", ".."):
        return fallback
    return segment
