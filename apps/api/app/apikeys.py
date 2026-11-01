"""API-key authentication + scopes for the developer API (`/api/v1`).

A key is accepted as `Authorization: Bearer <key>`, `x-api-key: <key>` or `?api_key=`.
Scopes: read | upload | train | infer. A NULL/empty scope list means every scope, which keeps
keys issued before scopes existed working unchanged. Publishable keys are always infer-only.
"""
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import API_SCOPES, ApiKey, Workspace
from .ratelimit import client_ip, limit
from .security import api_key_hash


def scopes_of(key: ApiKey) -> tuple[str, ...]:
    return tuple(API_SCOPES) if not key.scopes else tuple(s for s in key.scopes if s in API_SCOPES)


@dataclass
class KeyCtx:
    key: ApiKey
    ws: Workspace
    db: Session

    @property
    def scopes(self) -> tuple[str, ...]:
        return scopes_of(self.key)

    def need(self, scope: str) -> "KeyCtx":
        if scope not in self.scopes:
            raise HTTPException(403, f"api_key lacks the '{scope}' scope")
        return self

    def project(self, slug: str):
        from .models import Project
        p = self.db.scalar(select(Project).where(Project.workspace_id == self.ws.id, Project.slug == slug,
                                                 Project.deleted_at.is_(None)))
        if not p:
            raise HTTPException(404, "project not found")
        return p


def _token(request: Request, api_key: Optional[str]) -> str:
    if api_key:
        return api_key
    header = request.headers.get("x-api-key")
    if header:
        return header
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    raise HTTPException(401, "api_key required")


def resolve_key(request: Request, token: str | None, db: Session) -> KeyCtx:
    """Shared lookup for routes that accept `?api_key` or `x-api-key` outside the dependency graph."""
    limit(f"apikey:{client_ip(request)}", 600, 60)          # caps key guessing and abusive clients
    token = _token(request, token)
    k = db.scalar(select(ApiKey).where(ApiKey.hash == api_key_hash(token)))
    if not k:
        raise HTTPException(401, "invalid api_key")
    k.last_used = time.time()
    db.commit()                       # read-only routes never commit later; the key list must show use
    return KeyCtx(key=k, ws=db.get(Workspace, k.workspace_id), db=db)


def key_ctx(request: Request, api_key: str | None = Query(None), db: Session = Depends(get_db)) -> KeyCtx:
    return resolve_key(request, api_key, db)
