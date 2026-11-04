"""Dev-only mail inbox. Never mounted when SMTP is configured or LD_MAIL_DEV=0."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from .. import mailer

router = APIRouter(tags=["dev"])


@router.get("/__mail", include_in_schema=False)
def dev_mail():
    if not mailer.INBOX_ENABLED:
        raise HTTPException(404, "not found")
    return HTMLResponse(mailer.page(), headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})
