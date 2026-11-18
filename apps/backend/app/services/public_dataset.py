"""The anonymous projection of a published dataset (T-035).

Only public, live projects are reachable, and every refusal is the same 404 so a visitor
cannot tell a private project from a missing one. `payload` is an explicit key list: a new
project or image column never reaches the public page by simply existing.
"""
import time

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import DATA_DIR
from ..models import Image, ImageClass, LabelClass, Project, Workspace
from .flags import is_enabled

FLAG = "task_a1_public_page"
SAMPLE_LIMIT = 12


def _missing() -> HTTPException:
    return HTTPException(404, "Not found")


def resolve(db: Session, ws_slug: str, project_slug: str) -> tuple[Workspace, Project]:
    """The only rows a visitor can reach: flag on, workspace allows public, project live and public."""
    ws = db.scalar(select(Workspace).where(Workspace.slug == ws_slug))
    if ws is None or not getattr(ws, "allow_public_projects", True):
        raise _missing()
    project = db.scalar(select(Project).where(Project.workspace_id == ws.id, Project.slug == project_slug,
                                              Project.visibility == "public", Project.deleted_at.is_(None)))
    if project is None or not is_enabled(FLAG, db, ws.id):
        raise _missing()
    return ws, project


def payload(db: Session, project: Project) -> dict:
    """What the page may show, in one key list. Nothing else leaves this function."""
    live = (Image.project_id == project.id, Image.deleted_at.is_(None))
    ws = db.get(Workspace, project.workspace_id)
    counts = dict(db.execute(select(ImageClass.class_id, func.sum(ImageClass.n))
                             .join(Image, Image.id == ImageClass.image_id)
                             .where(*live).group_by(ImageClass.class_id)).all())
    classes = [{"name": c.name, "count": int(counts.get(c.id) or 0)}
               for c in db.scalars(select(LabelClass).where(LabelClass.project_id == project.id)
                                   .order_by(LabelClass.created)).all()]
    samples = db.scalars(select(Image).where(*live).order_by(Image.created, Image.id)
                         .limit(SAMPLE_LIMIT)).all()
    return {
        "name": project.name,
        "description": project.description,
        "type": project.type,
        "workspace": ws.name,
        "license": project.license,
        "images": db.scalar(select(func.count(Image.id)).where(*live)),
        "classes": classes,
        "citation": " · ".join((project.name, ws.name, str(time.gmtime(project.created).tm_year),
                                project.license)),
        "samples": [{"id": i.id, "width": i.width, "height": i.height,
                     "url": f"/api/public/datasets/{ws.slug}/{project.slug}/images/{i.id}"}
                    for i in samples],
    }


def thumb_path(project: Project, image: Image):
    """The cached ingest thumbnail (≤480 px, so ≤512), never the original file."""
    return DATA_DIR / image.thumb
