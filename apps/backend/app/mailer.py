"""Outbound email. SMTP when LD_SMTP_HOST is set; otherwise mails go to a dev outbox shown at /__mail."""
import html
import logging
import os
import queue
import smtplib
import threading
import time
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from urllib.parse import urlparse

from .config import PUBLIC_URL

log = logging.getLogger("labeldesk.mail")

SMTP_HOST = os.environ.get("LD_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("LD_SMTP_PORT", "587") or 587)
SMTP_USER = os.environ.get("LD_SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("LD_SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("LD_SMTP_FROM") or SMTP_USER or "LabelDesk <no-reply@labeldesk.local>"
SMTP_TLS = os.environ.get("LD_SMTP_TLS", "1") != "0"
SMTP_SSL = os.environ.get("LD_SMTP_SSL", "0") == "1"

DEV = not SMTP_HOST


def inbox_allowed(dev: bool, flag: str | None, public_url: str) -> bool:
    """Fail closed: the inbox needs an explicit LD_MAIL_DEV=1 AND a localhost PUBLIC_URL."""
    host = (urlparse(public_url).hostname or "").lower()
    return dev and flag == "1" and host in {"localhost", "127.0.0.1", "::1"}


# No SMTP in a dev run: keep the last mails in memory so /__mail can show them. Never open by default —
# the page prints live reset links, so both an explicit flag and a localhost origin are required.
INBOX_ENABLED = inbox_allowed(DEV, os.environ.get("LD_MAIL_DEV"), PUBLIC_URL)

if DEV:
    if INBOX_ENABLED:
        log.warning("SMTP is not configured — mail is captured in memory at /__mail (dev only)")
    else:
        log.error("SMTP is not configured and the dev inbox is off — outgoing mail will NOT be delivered")

_outbox: "queue.deque[dict]" = queue.deque(maxlen=100)
_lock = threading.Lock()


def send(to: str, subject: str, text: str, *, link: str = "", kind: str = "mail", html_body: str = "") -> bool:
    """Queue one mail. Never raises: a mail failure must not break sign-up or a password reset."""
    msg = EmailMessage()
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="labeldesk.local")
    msg.set_content(text)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    if DEV:
        if not INBOX_ENABLED:
            # Misconfigured production: fail loudly rather than telling the user a mail is on its way.
            log.error("mail not delivered (no SMTP): to=%s subject=%r", to, subject)
            return False
        with _lock:
            _outbox.append({"to": to, "subject": subject, "text": text, "link": link, "kind": kind,
                            "created": time.time()})
        log.info("mail (dev): to=%s subject=%r link=%s", to, subject, link or "-")
        return True
    threading.Thread(target=_deliver, args=(msg,), daemon=True).start()
    return True


def _deliver(msg: EmailMessage):
    try:
        cls = smtplib.SMTP_SSL if SMTP_SSL else smtplib.SMTP
        with cls(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            if SMTP_TLS and not SMTP_SSL:
                smtp.starttls()
            if SMTP_USER:
                smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(msg)
        log.info("mail sent: to=%s subject=%r", msg["To"], msg["Subject"])
    except Exception:                                     # noqa: BLE001 - delivery must stay best-effort
        log.exception("mail delivery failed: to=%s subject=%r", msg["To"], msg["Subject"])


def outbox() -> list[dict]:
    with _lock:
        return list(_outbox)


def clear():
    with _lock:
        _outbox.clear()


def page() -> str:
    """Dev inbox: every captured mail with its action link and body."""
    rows = []
    for m in reversed(outbox()):
        when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(m["created"]))
        link = f'<p><a href="{html.escape(m["link"])}">{html.escape(m["link"])}</a></p>' if m["link"] else ""
        rows.append(
            '<article style="border:1px solid #d6d6d6;border-radius:10px;padding:16px;margin:12px 0;background:#fff">'
            f'<div style="font:12px/1.4 system-ui;color:#666">{when} · {html.escape(m["kind"])}</div>'
            f'<h2 style="font:600 16px/1.3 system-ui;margin:4px 0">{html.escape(m["subject"])}</h2>'
            f'<div style="font:13px/1.5 system-ui;color:#444">to {html.escape(m["to"])}</div>{link}'
            f'<pre style="white-space:pre-wrap;font:13px/1.5 ui-monospace,monospace;background:#f6f6f6;'
            f'padding:12px;border-radius:8px;margin:12px 0 0">{html.escape(m["text"])}</pre></article>'
        )
    body = "".join(rows) or '<p style="color:#666">No mail yet. Trigger a reset or invite to see it here.</p>'
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        '<meta name="robots" content="noindex"><title>LabelDesk dev mail</title></head>'
        '<body style="margin:0;background:#f1f2f6;font-family:system-ui,sans-serif">'
        '<div style="max-width:760px;margin:0 auto;padding:32px 20px">'
        '<h1 style="font:600 22px/1.2 system-ui;margin:0 0 4px">Dev mail</h1>'
        '<p style="color:#666;font:13px/1.5 system-ui;margin:0 0 20px">Captured locally because SMTP is not configured. '
        'Set <code>LD_SMTP_HOST</code> for real delivery.</p>'
        f'{body}</div></body></html>'
    )
