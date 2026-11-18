"""Publishing: a project goes public only with a licence and an explicit content check.

The public address is never stored — `projects.visibility` is the only switch, and every read
derives `publicPath` from it, so unpublishing hides the page on the next request. Nothing here
touches an image, a class or an annotation, and unpublishing deletes nothing.
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..deps import Ctx, audit
from ..models import Project, now

# The licences a published dataset may carry. `Proprietary` is refused with its own sentence
# rather than the generic "choose one", because the owner should know why it is not offered.
ALLOWED_LICENSES = ("CC BY 4.0", "CC BY-SA 4.0", "CC0 1.0", "MIT", "Public Domain")


def _out(ctx: Ctx, project: Project) -> dict:
    return {"visibility": project.visibility, "license": project.license,
            "publicPath": f"/d/{ctx.ws.slug}/{project.slug}" if project.visibility == "public" else None}


def publish(db: Session, ctx: Ctx, project: Project, license: str, ack: bool) -> dict:
    """Make the project public; one audit row, one commit, or a 4xx that changes nothing."""
    ctx.perm("project.settings")
    licence = (license or "").strip()
    if licence == "Proprietary":
        raise HTTPException(422, "Proprietary datasets cannot be published.")
    if licence not in ALLOWED_LICENSES:
        raise HTTPException(422, "Choose a licence for published data.")
    if not ack:
        raise HTTPException(422, "Confirm the content check before publishing.")
    # 7-F7.60 owns `workspaces.allow_public_projects` and the workspace-level enforcement; read it
    # defensively so this switch obeys the policy as soon as that column lands.
    if not getattr(ctx.ws, "allow_public_projects", True):
        raise HTTPException(403, "This workspace does not allow public projects.")
    project.visibility = "public"
    project.license = licence
    project.updated = now()
    audit(db, ctx.ws.id, ctx.user.id, "project.publish", project.name, license=licence)
    db.commit()
    return _out(ctx, project)


def unpublish(db: Session, ctx: Ctx, project: Project) -> dict:
    """Reverse a publish: the derived address disappears, the data stays."""
    ctx.perm("project.settings")
    project.visibility = "private"
    project.updated = now()
    audit(db, ctx.ws.id, ctx.user.id, "project.unpublish", project.name)
    db.commit()
    return _out(ctx, project)
