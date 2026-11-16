"""Alert sink for stream events: LINE Messaging API, Slack incoming webhook, email.

`dispatch` is the integration point for the stream manager. It fans one event out to every
active channel, attaches the event snapshot as a signed URL, and suppresses storms with a
per-channel throttle plus optional quiet hours. Provider credentials are encrypted by
`secretbox`; every outbound URL (Slack) is vetted by `safefetch` on each attempt.

LINE Notify was retired on 2025-03-31; the current path is the Messaging API push endpoint
(`POST https://api.line.me/v2/bot/message/push`). Image messages require public HTTPS URLs,
so LINE receives the image message only when PUBLIC_URL is HTTPS and a snapshot exists.
"""

import html
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from sqlalchemy import select

from .. import mailer, security
from ..config import DATA_DIR, PUBLIC_URL
from ..models import ALERT_KINDS, AlertChannel, AlertDelivery, new_id, now
from . import flags, safefetch, secretbox

log = logging.getLogger("labeldesk.alerts")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
TIMEOUT_S = 5.0
DEFAULT_THROTTLE_S = 60
MASK = "••••"
MAX_SNAPSHOT_BYTES = 10 * 1024 * 1024
SNAPSHOT_TTL = 24 * 3600
LOCAL_TZ = ZoneInfo("Asia/Bangkok")
_EMAIL_RE = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

SECRET_FIELDS = {"line": ("channel_token",), "slack": ("webhook_url",), "email": ()}


# --- configuration -------------------------------------------------------------------


def check_url(url: str) -> str:
    """Public-http(s) validation at send time; tests replace this module attribute."""
    return safefetch.check_url(url)


def _post(url: str, body: bytes, headers: dict, timeout: float) -> int:
    """The only network call; returns the status code (the body is never read or stored)."""
    return safefetch.post(url, body, headers, timeout)


def _text(value, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _has_control(value: str) -> bool:
    """Reject anything that could smuggle a second line into a header or JSON target."""
    return any(ord(ch) < 32 or ord(ch) == 127 for ch in value)


def _valid_email(value) -> bool:
    return isinstance(value, str) and len(value) <= 254 and bool(_EMAIL_RE.match(value.strip()))


def validate(kind: str, config: dict) -> None:
    """Raise ValueError when a channel config is unusable. Never echoes secret values."""
    if kind not in ALERT_KINDS:
        raise ValueError(f"unknown alert kind {kind!r} (expected one of: {', '.join(ALERT_KINDS)})")
    cfg = config if isinstance(config, dict) else {}
    if kind == "line":
        token = _text(cfg.get("channel_token"), 1024)
        to = _text(cfg.get("to"), 128)
        if not token:
            raise ValueError("LINE channel access token is required")
        if _has_control(token):
            raise ValueError("LINE channel access token contains control characters")
        if not to:
            raise ValueError("LINE target ID is required")
        if _has_control(to):
            raise ValueError("LINE target ID contains control characters")
    elif kind == "slack":
        url = _text(cfg.get("webhook_url"), 1024)
        if not url:
            raise ValueError("Slack webhook URL is required")
        if _has_control(url):
            raise ValueError("Slack webhook URL contains control characters")
        if not url.startswith("https://"):
            raise ValueError("Slack webhook URL must be an https URL")
        try:
            check_url(url)
        except safefetch.BlockedURL as e:
            raise ValueError(f"Slack webhook url is not allowed: {e}") from e
    else:
        recipients = cfg.get("recipients")
        if not isinstance(recipients, list) or not recipients:
            raise ValueError("at least one email recipient is required")
        if len(recipients) > 20:
            raise ValueError("at most 20 email recipients are allowed")
        for address in recipients:
            if not _valid_email(address):
                raise ValueError("invalid email recipient")


def validate_settings(settings: dict | None) -> dict:
    """Normalise `{throttle_s, quiet_hours}` and reject impossible values."""
    s = settings if isinstance(settings, dict) else {}
    throttle = s.get("throttle_s", DEFAULT_THROTTLE_S)
    if isinstance(throttle, bool) or not isinstance(throttle, int) or not 0 <= throttle <= 86_400:
        raise ValueError("throttle_s must be an integer between 0 and 86400")
    quiet = s.get("quiet_hours")
    if quiet is None:
        return {"throttle_s": throttle, "quiet_hours": None}
    if not isinstance(quiet, dict):
        raise ValueError("quiet_hours must be an object")
    start, end = quiet.get("start"), quiet.get("end")
    if not isinstance(start, str) or not _TIME_RE.match(start):
        raise ValueError("quiet_hours.start must be HH:MM")
    if not isinstance(end, str) or not _TIME_RE.match(end):
        raise ValueError("quiet_hours.end must be HH:MM")
    tz = quiet.get("tz") or LOCAL_TZ.key
    try:
        ZoneInfo(str(tz))
    except Exception as e:
        raise ValueError("quiet_hours.tz is not a known time zone") from e
    return {
        "throttle_s": throttle,
        "quiet_hours": {"start": start, "end": end, "tz": str(tz)},
    }


def decrypted_config(channel: AlertChannel) -> dict:
    cfg = dict(channel.config or {})
    for field in SECRET_FIELDS[channel.kind]:
        if cfg.get(field):
            cfg[field] = secretbox.decrypt(str(cfg[field]))
    return cfg


def encrypted_config(kind: str, config: dict) -> dict:
    return secretbox.encrypt_config(config, SECRET_FIELDS[kind])


def is_masked(value) -> bool:
    """An echoed mask is not a new secret; update keeps the stored value."""
    return isinstance(value, str) and MASK in value


def public_config(kind: str, config: dict) -> dict:
    """Masked view for the API; signing tokens and webhook URLs never leave the API."""
    cfg = dict(config or {})
    if kind == "line":
        return {
            "to": cfg.get("to", ""),
            "channel_token": MASK if cfg.get("channel_token") else "",
        }
    if kind == "slack":
        try:
            u = urlsplit(str(cfg.get("webhook_url") or ""))
            return {"webhook_url": f"{u.scheme}://{u.hostname}/{MASK}" if u.hostname else MASK}
        except ValueError:
            return {"webhook_url": MASK}
    return {"recipients": list(cfg.get("recipients") or [])}


# --- snapshot ------------------------------------------------------------------------


def snapshot_url(snapshot_path: str) -> str | None:
    """Signed URL for a snapshot inside DATA_DIR; anything else is omitted, never served."""
    rel = str(snapshot_path or "").replace("\\", "/").strip()
    if not rel or rel.startswith("/") or Path(rel).is_absolute() or ".." in Path(rel).parts:
        return None
    if Path(rel).suffix.lower() not in (".jpg", ".jpeg", ".png"):
        return None
    root = DATA_DIR.resolve()
    f = (root / rel).resolve()
    if root not in f.parents or not f.is_file() or f.stat().st_size > MAX_SNAPSHOT_BYTES:
        return None
    return f"{PUBLIC_URL}{security.sign_path(rel, SNAPSHOT_TTL)}"


# --- delivery ------------------------------------------------------------------------


def _when(ts) -> str:
    try:
        value = float(ts)
    except (TypeError, ValueError):
        value = now()
    return datetime.fromtimestamp(value, LOCAL_TZ).strftime("%Y-%m-%d %H:%M")


def _message(event: dict, url: str | None) -> str:
    title = _text(event.get("title") or "Stream alert", 200)
    summary = _text(event.get("summary"), 1000)
    stream = _text(event.get("stream_name") or event.get("stream_id"), 200)
    lines = [f"[LabelDesk] {title}"]
    if stream:
        lines.append(f"Stream: {stream}")
    if summary:
        lines.append(summary)
    lines.append(f"When: {_when(event.get('created'))} (Asia/Bangkok)")
    if url:
        lines.append(f"Snapshot: {url}")
    return "\n".join(lines)


def _https(url: str | None) -> bool:
    return bool(url and url.lower().startswith("https://"))


def _send_line(cfg: dict, text: str, url: str | None) -> int:
    messages = [{"type": "text", "text": text[:5000]}]
    if _https(url):
        messages.append({"type": "image", "originalContentUrl": url, "previewImageUrl": url})
    body = json.dumps({"to": cfg["to"], "messages": messages}, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg['channel_token']}",
    }
    return _post(LINE_PUSH_URL, body, headers, TIMEOUT_S)


def _slack_text(text: str) -> str:
    """Escape Slack markup so event text cannot inject @channel mentions or links."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _send_slack(cfg: dict, text: str, url: str | None) -> int:
    url_target = cfg["webhook_url"]
    check_url(url_target)  # DNS can move: re-vet every attempt
    payload = {"text": _slack_text(text)}
    if _https(url):
        payload["attachments"] = [{"title": "Snapshot", "image_url": url, "alt_text": "Stream alert snapshot"}]
    return _post(
        url_target,
        json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        {"Content-Type": "application/json"},
        TIMEOUT_S,
    )


def _send_email(cfg: dict, text: str, url: str | None) -> tuple[None, str]:
    title = text.splitlines()[0].removeprefix("[LabelDesk] ")
    body = f"<p>{html.escape(text).replace(chr(10), '<br>')}</p>"
    if _https(url):
        body += f'<p><img src="{html.escape(url, quote=True)}" alt="Stream alert snapshot" style="max-width:100%"></p>'
    ok = True
    for to in cfg["recipients"]:
        ok = (
            mailer.send(
                to,
                f"[LabelDesk] {title}",
                text,
                link=url or "",
                kind="alert",
                html_body=body,
            )
            and ok
        )
    return None, "" if ok else "email not delivered"


def _in_quiet_hours(quiet: dict, ts: float) -> bool:
    try:
        start_h, start_m = (int(x) for x in quiet["start"].split(":"))
        end_h, end_m = (int(x) for x in quiet["end"].split(":"))
        local = datetime.fromtimestamp(ts, ZoneInfo(str(quiet.get("tz") or LOCAL_TZ.key)))
    except (KeyError, TypeError, ValueError):
        return False
    start, end, minute = (
        start_h * 60 + start_m,
        end_h * 60 + end_m,
        local.hour * 60 + local.minute,
    )
    if start == end:
        return False
    if start < end:
        return start <= minute < end
    return minute >= start or minute < end


def _skip_reason(channel: AlertChannel, ts: float) -> str:
    settings = channel.settings if isinstance(channel.settings, dict) else {}
    quiet = settings.get("quiet_hours")
    if isinstance(quiet, dict) and _in_quiet_hours(quiet, ts):
        return "quiet_hours"
    throttle = settings.get("throttle_s", DEFAULT_THROTTLE_S)
    if (
        isinstance(throttle, int)
        and not isinstance(throttle, bool)
        and throttle > 0
        and channel.last_sent
        and ts - channel.last_sent < throttle
    ):
        return "throttled"
    return ""


def _event_summary(event: dict) -> dict:
    keys = (
        "title",
        "summary",
        "stream_name",
        "stream_id",
        "project_id",
        "event_id",
        "created",
    )
    return {k: event[k] for k in keys if event.get(k) not in (None, "")}


def send(db, channel: AlertChannel, event: dict, ignore_limits: bool = False) -> AlertDelivery:
    """Attempt one delivery and return the (unsaved) history row. Never raises."""
    ts = now()
    snapshot = str(event.get("snapshot_path") or "")
    delivery = AlertDelivery(
        id=new_id(),
        channel_id=channel.id,
        workspace_id=channel.workspace_id,
        event=_event_summary(event),
        snapshot_path=snapshot,
        status="pending",
        created=ts,
        updated=ts,
    )
    reason = "" if ignore_limits else _skip_reason(channel, ts)
    if reason:
        delivery.status, delivery.reason = "skipped", reason
        return delivery

    url = snapshot_url(snapshot) if snapshot else None
    text = _message(event, url)
    status, error = None, ""
    try:
        cfg = decrypted_config(channel)
        if channel.kind == "line":
            status = _send_line(cfg, text, url)
        elif channel.kind == "slack":
            status = _send_slack(cfg, text, url)
        elif channel.kind == "email":
            status, error = _send_email(cfg, text, url)
        else:
            error = "unknown channel kind"
    except safefetch.BlockedURL:
        error = "channel URL is not allowed"
    except Exception:
        log.exception("alert delivery %s failed", delivery.id)
        error = "delivery failed"

    delivery.last_status = status
    delivery.updated = now()
    if not error and (status is None or 200 <= int(status) < 300):
        delivery.status = "ok"
        channel.last_sent = ts
    else:
        delivery.status = "failed"
        delivery.reason = error or f"HTTP {status}"
    return delivery


def dispatch(db, workspace_id: str, event: dict, ignore_limits: bool = False) -> list[AlertDelivery]:
    """Fan one stream event out to every active channel. The caller commits."""
    if not flags.is_enabled("task_33", db, workspace_id):
        return []
    channels = db.scalars(
        select(AlertChannel).where(AlertChannel.workspace_id == workspace_id, AlertChannel.active.is_(True))
    ).all()
    rows = []
    for channel in channels:
        delivery = send(db, channel, event, ignore_limits)
        db.add(delivery)
        rows.append(delivery)
    return rows


def test_channel(db, channel: AlertChannel) -> AlertDelivery:
    """Send a synthetic alert the user explicitly asked for (bypasses throttle/quiet hours)."""
    event = {
        "title": "Test alert",
        "summary": "LabelDesk alert channel test",
        "created": now(),
    }
    delivery = send(db, channel, event, ignore_limits=True)
    db.add(delivery)
    return delivery
