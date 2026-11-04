"""Short-lived, in-process lasso selections. The URL carries only the token, never image ids."""

import secrets
import threading
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Image, Project

SELECTION_TTL_S = 900.0
SELECTION_MAX = 256
SELECTION_ITEMS_MAX = 5000

_SELECTIONS: dict[str, tuple[float, str, list[str]]] = {}   # token -> (expires, project_id, image ids)
_SELECTION_LOCK = threading.Lock()


def _purge_selections(now_ts: float) -> None:
    for token in [t for t, (expires, _p, _i) in _SELECTIONS.items() if expires <= now_ts]:
        _SELECTIONS.pop(token, None)


def _selection_entry(token: str, project: Project) -> tuple[float, list[str]] | None:
    hit = _SELECTIONS.get(token)
    if hit is None:
        return None
    expires, project_id, image_ids = hit
    if expires <= time.time():
        _SELECTIONS.pop(token, None)
        return None
    if project_id != project.id:      # another project/tenant must never resolve it
        return None
    return expires, list(image_ids)


def save_selection(db: Session, project: Project, image_ids: list[str]) -> dict:
    """Short-lived lasso hand-off kept in process memory; ids must be live images of this project."""
    wanted = list(dict.fromkeys(i for i in image_ids if isinstance(i, str) and i))[:SELECTION_ITEMS_MAX]
    live = set(
        db.scalars(
            select(Image.id).where(
                Image.project_id == project.id,
                Image.deleted_at.is_(None),
                Image.id.in_(wanted),
            )
        )
    )
    ids = [i for i in wanted if i in live]
    token = secrets.token_urlsafe(12)
    expires = time.time() + SELECTION_TTL_S
    with _SELECTION_LOCK:
        _purge_selections(time.time())
        _SELECTIONS[token] = (expires, project.id, ids)
        while len(_SELECTIONS) > SELECTION_MAX:
            _SELECTIONS.pop(next(iter(_SELECTIONS)))
    return {"token": token, "count": len(ids), "expires": expires}


def resolve_selection(db: Session, project: Project, token: str) -> list[str] | None:
    """None for unknown/expired tokens and tokens saved under another project."""
    entry = _selection_entry(token, project)
    return entry[1] if entry else None


def selection_info(db: Session, project: Project, token: str) -> dict | None:
    entry = _selection_entry(token, project)
    if entry is None:
        return None
    expires, image_ids = entry
    return {"token": token, "image_ids": image_ids, "count": len(image_ids), "expires": expires}

