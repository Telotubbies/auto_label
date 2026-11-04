"""Webhook subscriptions and deliveries (job.done / model.ready / stream.event)."""
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..deps import Ctx, audit, ws_ctx
from ..models import WEBHOOK_EVENTS, Webhook, WebhookDelivery
from ..services import safefetch, secretbox
from ..services import webhooks as svc

router = APIRouter(prefix="/api/ws/{ws}/webhooks", tags=["webhooks"])

TEST_DATA = {"source": "test", "message": "LabelDesk webhook test"}


def _validate(url: str | None, events: list[str] | None):
    """Shared create/update rules: public http(s) URL, known non-empty events."""
    if events is not None:
        events = list(dict.fromkeys(events))
        if not events or any(e not in WEBHOOK_EVENTS for e in events):
            raise HTTPException(400, f"events must be a non-empty subset of {list(WEBHOOK_EVENTS)}")
    if url is not None:
        url = url.strip()
        if len(url) > 1024 or not (url.startswith("http://") or url.startswith("https://")):
            raise HTTPException(400, "url must be an http:// or https:// URL of at most 1024 characters")
        try:
            safefetch.check_url(url)                 # public IPs only; blocks metadata/loopback/RFC1918
        except safefetch.BlockedURL as e:
            raise HTTPException(400, f"url is not allowed: {e}")
    return url, events


def _preview(_secret: str) -> str:
    return "whsec_…"                    # prefix only: never leak the random part of a signing secret


def _out(w: Webhook) -> dict:
    """Subscription as the UI sees it — the signing secret never leaves creation."""
    return {"id": w.id, "url": w.url, "events": list(w.events or []), "active": bool(w.active),
            "created": w.created, "secret_preview": _preview(w.secret)}


def _delivery_out(d: WebhookDelivery) -> dict:
    return {"id": d.id, "event": d.event, "status": d.status, "attempts": d.attempts,
            "next_attempt": d.next_attempt, "last_status": d.last_status, "last_error": d.last_error,
            "created": d.created, "payload": d.payload}


def _get(c: Ctx, wid: str) -> Webhook:
    w = c.db.get(Webhook, wid)
    if not w or w.workspace_id != c.ws.id:
        raise HTTPException(404, "webhook not found")
    return w


@router.get("")
def list_webhooks(c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    rows = c.db.scalars(select(Webhook).where(Webhook.workspace_id == c.ws.id)
                        .order_by(Webhook.created.desc())).all()
    return [_out(w) for w in rows]


class WebhookIn(BaseModel):
    url: str
    events: list[str]


@router.post("")
def create_webhook(body: WebhookIn, c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    url, events = _validate(body.url, body.events)
    secret = "whsec_" + secrets.token_urlsafe(24)
    w = Webhook(workspace_id=c.ws.id, url=url, secret=secretbox.encrypt(secret), events=events, active=True,
                created_by=c.uid)
    c.db.add(w)
    audit(c.db, c.ws.id, c.uid, "webhook.create", url, events=events)
    c.db.commit()
    return {**_out(w), "secret": secret}          # the only time the secret is returned


class WebhookPatch(BaseModel):
    url: str | None = None
    events: list[str] | None = None
    active: bool | None = None


@router.patch("/{wid}")
def update_webhook(wid: str, body: WebhookPatch, c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    w = _get(c, wid)
    url, events = _validate(body.url, body.events)
    if url is not None:
        w.url = url
    if events is not None:
        w.events = events
    if body.active is not None:
        w.active = body.active
    audit(c.db, c.ws.id, c.uid, "webhook.update", w.url, active=bool(w.active), events=list(w.events or []))
    c.db.commit()
    return _out(w)


@router.delete("/{wid}")
def delete_webhook(wid: str, c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    w = _get(c, wid)
    for d in c.db.scalars(select(WebhookDelivery).where(WebhookDelivery.webhook_id == w.id)):
        c.db.delete(d)
    audit(c.db, c.ws.id, c.uid, "webhook.delete", w.url)
    c.db.delete(w)
    c.db.commit()
    return {"ok": True}


@router.get("/{wid}/deliveries")
def deliveries(wid: str, c: Ctx = Depends(ws_ctx)):
    c.need("admin")
    w = _get(c, wid)
    rows = c.db.scalars(select(WebhookDelivery).where(WebhookDelivery.webhook_id == w.id)
                        .order_by(WebhookDelivery.created.desc()).limit(100)).all()
    return [{k: v for k, v in _delivery_out(d).items() if k != "payload"} for d in rows]


@router.post("/{wid}/test")
def test_webhook(wid: str, c: Ctx = Depends(ws_ctx)):
    """Deliver one synthetic event synchronously; a dead endpoint is a report, not a 5xx."""
    c.need("admin")
    w = _get(c, wid)
    d = svc.delivery_for(w, "stream.event", TEST_DATA)
    c.db.add(d)
    svc.deliver(c.db, d)
    audit(c.db, c.ws.id, c.uid, "webhook.test", w.url, status=d.status)
    c.db.commit()
    return _delivery_out(d)
