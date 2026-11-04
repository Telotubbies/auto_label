"""Audit log export (CSV/JSON) for compliance hand-off."""
import csv
import io
import json
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import Ctx, audit, ws_ctx
from ..models import Audit, User

router = APIRouter(prefix="/api/ws/{ws}", tags=["audit"])
CSV_HEADER = ["id", "created", "user", "action", "target", "meta"]
FORMULA_PREFIXES = ("=", "+", "-", "@")
MAX_ROWS = 50_000


def _can_audit(c: Ctx) -> bool:
    """RBAC agents add Ctx.can(); until then only owner/admin roles may export."""
    can = getattr(c, "can", None)
    if callable(can):
        return bool(can("workspace.audit"))
    return c.role in ("owner", "admin") or getattr(c, "ws_role", "") in ("owner", "admin")


def _query(db: Session, ws_id: str, *, action: str, user: str, since: float | None, until: float | None,
           q: str, limit: int, offset: int) -> list[tuple[Audit, str | None]]:
    stmt = (select(Audit, User.name).outerjoin(User, User.id == Audit.user_id)
            .where(Audit.workspace_id == ws_id))
    if action:
        # "member" is a prefix (member.*); "member.invite" is exact.
        if "." in action:
            stmt = stmt.where(Audit.action == action)
        else:
            stmt = stmt.where((Audit.action == action) | Audit.action.like(action + ".%"))
    if user:
        if user.lower() == "api":
            stmt = stmt.where(Audit.user_id.is_(None))
        else:
            term = f"%{user.lower()}%"
            stmt = stmt.where(func.lower(User.name).like(term) | func.lower(User.email).like(term))
    if since is not None:
        stmt = stmt.where(Audit.created >= since)
    if until is not None:
        stmt = stmt.where(Audit.created <= until)
    if q:
        needle = f"%{q}%"
        stmt = stmt.where(Audit.target.ilike(needle) | cast(Audit.meta, String).ilike(needle))
    stmt = (stmt.order_by(Audit.created.desc(), Audit.id.desc())
            .limit(min(max(limit, 1), MAX_ROWS)).offset(max(offset, 0)))
    return db.execute(stmt).all()


def _user_label(a: Audit, name: str | None) -> str:
    return name or ("API" if a.user_id is None else a.user_id)


def _cell(value) -> str:
    """CSV formula-injection guard: spreadsheet apps must never execute an exported cell."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in FORMULA_PREFIXES else text


def _csv(rows: list[tuple[Audit, str | None]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")            # RFC 4180
    writer.writerow(CSV_HEADER)
    for a, name in rows:
        writer.writerow([_cell(a.id), _cell(a.created), _cell(_user_label(a, name)), _cell(a.action),
                         _cell(a.target), _cell(json.dumps(a.meta or {}, ensure_ascii=False))])
    return "\ufeff" + buf.getvalue()                            # BOM so Excel reads Thai correctly


def _json(rows: list[tuple[Audit, str | None]]) -> list[dict]:
    return [{"id": a.id, "action": a.action, "target": a.target, "meta": a.meta, "created": a.created,
             "user": _user_label(a, name)} for a, name in rows]


@router.get("/audit/export")
def export_audit(format: str = "csv", action: str = "", user: str = "", since: float | None = None,
                 until: float | None = None, q: str = "", limit: int = 10_000, offset: int = 0,
                 c: Ctx = Depends(ws_ctx), db: Session = Depends(get_db)):
    if not _can_audit(c):
        raise HTTPException(403, "requires workspace.audit")
    fmt = (format or "csv").lower()
    if fmt not in ("csv", "json"):
        raise HTTPException(400, "format must be csv or json")
    rows = _query(db, c.ws.id, action=action, user=user, since=since, until=until, q=q,
                  limit=limit, offset=offset)
    audit(db, c.ws.id, c.uid, "audit.export", f"format={fmt}", rows=len(rows))
    db.commit()
    if fmt == "json":
        return _json(rows)
    name = f"audit-{c.ws.slug}-{time.strftime('%Y%m%d')}.csv"
    return Response(_csv(rows), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
