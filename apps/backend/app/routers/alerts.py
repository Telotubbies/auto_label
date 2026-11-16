"""Alert channel API: CRUD, test send and delivery history (admin only, behind task_33)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..deps import Ctx, audit, ws_ctx
from ..models import AlertChannel, AlertDelivery, now
from ..services import alerts
from ..services.flags import require_flag

router = APIRouter(
    prefix="/api/ws/{ws}/alerts",
    tags=["alerts"],
    dependencies=[Depends(require_flag("task_33"))],
)


def _get(c: Ctx, cid: str) -> AlertChannel:
    ch = c.db.get(AlertChannel, cid)
    if not ch or ch.workspace_id != c.ws.id:
        raise HTTPException(404, "alert channel not found")
    return ch


def _out(ch: AlertChannel) -> dict:
    return {
        "id": ch.id,
        "kind": ch.kind,
        "name": ch.name,
        "active": bool(ch.active),
        "config": alerts.public_config(ch.kind, ch.config or {}),
        "settings": ch.settings or {},
        "last_sent": ch.last_sent,
        "created": ch.created,
    }


def _delivery_out(d: AlertDelivery) -> dict:
    return {
        "id": d.id,
        "status": d.status,
        "reason": d.reason,
        "last_status": d.last_status,
        "event": d.event or {},
        "created": d.created,
    }


def _name(value: str) -> str:
    name = (value or "").strip()
    if not name or len(name) > 120:
        raise HTTPException(400, "name must be 1–120 characters")
    return name


@router.get("")
def list_channels(c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    rows = c.db.scalars(
        select(AlertChannel).where(AlertChannel.workspace_id == c.ws.id).order_by(AlertChannel.created.desc())
    ).all()
    return [_out(ch) for ch in rows]


class ChannelIn(BaseModel):
    kind: str
    name: str
    config: dict
    settings: dict | None = None


@router.post("")
def create_channel(body: ChannelIn, c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    try:
        alerts.validate(body.kind, body.config)
        settings = alerts.validate_settings(body.settings)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    ch = AlertChannel(
        workspace_id=c.ws.id,
        kind=body.kind,
        name=_name(body.name),
        config=alerts.encrypted_config(body.kind, body.config),
        settings=settings,
        active=True,
        created_by=c.uid,
    )
    c.db.add(ch)
    audit(c.db, c.ws.id, c.uid, "alert.create", ch.name, kind=ch.kind)
    c.db.commit()
    return _out(ch)


class ChannelPatch(BaseModel):
    name: str | None = None
    active: bool | None = None
    config: dict | None = None
    settings: dict | None = None


@router.patch("/{cid}")
def update_channel(cid: str, body: ChannelPatch, c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    ch = _get(c, cid)
    try:
        if body.config is not None:
            plain = alerts.decrypted_config(ch)
            incoming = dict(body.config)
            for field in alerts.SECRET_FIELDS[ch.kind]:
                if not incoming.get(field) or alerts.is_masked(incoming[field]):
                    incoming.pop(field, None)  # blank or echoed mask keeps the stored secret
            plain.update(incoming)
            alerts.validate(ch.kind, plain)
            ch.config = alerts.encrypted_config(ch.kind, plain)
        if body.settings is not None:
            ch.settings = alerts.validate_settings(body.settings)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if body.name is not None:
        ch.name = _name(body.name)
    if body.active is not None:
        ch.active = body.active
    ch.updated = now()
    audit(
        c.db,
        c.ws.id,
        c.uid,
        "alert.update",
        ch.name,
        active=bool(ch.active),
        kind=ch.kind,
    )
    c.db.commit()
    return _out(ch)


@router.delete("/{cid}")
def delete_channel(cid: str, c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    ch = _get(c, cid)
    for d in c.db.scalars(select(AlertDelivery).where(AlertDelivery.channel_id == ch.id)):
        c.db.delete(d)
    audit(c.db, c.ws.id, c.uid, "alert.delete", ch.name, kind=ch.kind)
    c.db.delete(ch)
    c.db.commit()
    return {"ok": True}


@router.get("/{cid}/deliveries")
def deliveries(cid: str, c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    ch = _get(c, cid)
    rows = c.db.scalars(
        select(AlertDelivery).where(AlertDelivery.channel_id == ch.id).order_by(AlertDelivery.created.desc()).limit(50)
    ).all()
    return [_delivery_out(d) for d in rows]


@router.post("/{cid}/test")
def test_channel(cid: str, c: Ctx = Depends(ws_ctx)):
    """Send one synthetic alert synchronously; a dead provider is a report, not a 5xx."""
    c.need("admin")
    ch = _get(c, cid)
    d = alerts.test_channel(c.db, ch)
    audit(c.db, c.ws.id, c.uid, "alert.test", ch.name, kind=ch.kind, status=d.status)
    c.db.commit()
    return _delivery_out(d)
