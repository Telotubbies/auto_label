"""Signed webhook delivery with retry.

`emit` fans a workspace event out to every active subscription and queues one
`WebhookDelivery` per subscription; the caller commits. `flush_due` (driven by
the worker's `flush_loop`) posts the queued rows with exponential backoff.

Delivery contract: `sha256=HMAC(secret, "<ts>." + body)` over the canonical JSON
body, sent as `X-LabelDesk-Signature` next to the timestamp and delivery id.
"""
import hashlib
import hmac
import json
import logging
import os
import time

from sqlalchemy import select

from .. import models
from ..db import SessionLocal
from . import safefetch, secretbox

log = logging.getLogger("labeldesk.webhooks")

EVENTS = models.WEBHOOK_EVENTS
MAX_ATTEMPTS = 3
RETRY_DELAYS = (10, 60)               # seconds before attempt 2 and 3 (MAX_ATTEMPTS = 3)
TIMEOUT_S = 5.0


def canonical(payload: dict) -> bytes:
    """Stable bytes for signing: sorted keys, no whitespace, UTF-8 kept as-is."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sign(secret: str, body: bytes, ts: int) -> str:
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return "sha256=" + mac


def verify(secret: str, body: bytes, ts: int, signature: str, max_age: int = 300) -> bool:
    """Constant-time check of a timestamp-bound signature; stale/future timestamps are rejected.

    Receivers should also dedupe on `X-LabelDesk-Delivery` (retries reuse the same id).
    """
    try:
        ts = int(ts)
    except (TypeError, ValueError):
        return False
    if ts - int(time.time()) > 60 or int(time.time()) - ts > max_age:
        return False
    given = (signature or "").removeprefix("sha256=")
    try:
        return hmac.compare_digest(sign(secret, body, ts), "sha256=" + given)
    except TypeError:                            # non-ASCII garbage in the header
        return False


def check_url(url: str) -> str:
    """Public-http(s) validation at delivery time; tests replace this module attribute."""
    return safefetch.check_url(url)


def _post(url: str, content: bytes, headers: dict, timeout: float) -> int:
    """The only network call; returns the status code (the body is never read or stored)."""
    return safefetch.post(url, content, headers, timeout)


def delivery_for(wh: models.Webhook, event: str, data: dict) -> models.WebhookDelivery:
    """Build (but do not add) one pending delivery for a subscription."""
    if event not in EVENTS:
        raise ValueError(f"unknown webhook event: {event}")
    ts = models.now()
    d = models.WebhookDelivery(id=models.new_id(), webhook_id=wh.id, workspace_id=wh.workspace_id,
                               event=event, status="pending", attempts=0, next_attempt=ts)
    d.payload = {"id": d.id, "event": event, "created": ts, "data": data}
    return d


def emit(db, workspace_id: str, event: str, data: dict) -> int:
    """Queue one delivery per active subscription that listens to `event`.

    Returns how many deliveries were queued. The caller commits.
    """
    if event not in EVENTS:
        raise ValueError(f"unknown webhook event: {event}")
    subs = db.scalars(select(models.Webhook).where(models.Webhook.workspace_id == workspace_id,
                                                   models.Webhook.active.is_(True))).all()
    queued = 0
    for wh in subs:
        if event in (wh.events or []):
            db.add(delivery_for(wh, event, data))
            queued += 1
    return queued


def deliver(db, d: models.WebhookDelivery) -> bool:
    """POST one delivery. Updates `d` in place and never raises.

    Only the status code and a generic error are stored: the receiver's response body (which may
    echo request data or contain internal details) never enters our DB or API responses.
    """
    wh = db.get(models.Webhook, d.webhook_id)
    if not wh or not wh.active:
        d.status, d.last_error, d.updated = "failed", "webhook disabled", models.now()
        return False

    status: int | None = None
    error = ""
    try:
        check_url(wh.url)                       # DNS may have changed since creation: re-vet every attempt
        ts = int(models.now())
        body = canonical(d.payload or {})
        headers = {
            "Content-Type": "application/json",
            "X-LabelDesk-Event": d.event,
            "X-LabelDesk-Delivery": d.id,
            "X-LabelDesk-Timestamp": str(ts),
            "X-LabelDesk-Signature": sign(secretbox.decrypt(wh.secret), body, ts),
        }
        status = int(_post(wh.url, body, headers, TIMEOUT_S))
        if not 200 <= status < 300:
            error = f"HTTP {status}"
    except safefetch.BlockedURL:
        d.status, d.last_error, d.updated = "failed", "webhook URL is not allowed", models.now()
        return False
    except Exception:                        # transport error: retry, do not fail the worker
        error = "delivery failed"

    d.attempts += 1
    d.last_status = status
    d.updated = models.now()
    if status is not None and 200 <= status < 300:
        d.status, d.last_error = "ok", ""
        return True

    d.status = "failed" if d.attempts >= MAX_ATTEMPTS else "pending"
    if d.status == "pending":
        d.next_attempt = d.updated + RETRY_DELAYS[min(d.attempts - 1, len(RETRY_DELAYS) - 1)]
    d.last_error = error[:500]
    return False


def flush_due(limit: int = 20) -> int:
    """Deliver pending rows whose backoff has elapsed. Returns how many were tried."""
    attempted = 0
    with SessionLocal() as db:
        rows = db.scalars(select(models.WebhookDelivery)
                          .where(models.WebhookDelivery.status == "pending",
                                 models.WebhookDelivery.next_attempt <= models.now())
                          .order_by(models.WebhookDelivery.created).limit(limit)).all()
        for d in rows:
            attempted += 1
            try:
                deliver(db, d)
                db.commit()
            except Exception:                    # one bad row must not stop the queue
                log.exception("webhook delivery %s failed unexpectedly", d.id)
                db.rollback()
    return attempted


def flush_loop(stop) -> None:
    """Daemon loop used by the embedded worker; wakes every few seconds to retry deliveries."""
    if os.environ.get("LD_WEBHOOK_FLUSH", "1") != "1":
        return                                    # tests call flush_due() themselves
    while not stop.is_set():
        try:
            flush_due()
        except Exception:
            log.exception("webhook flush loop iteration failed")
        time.sleep(2.0)
