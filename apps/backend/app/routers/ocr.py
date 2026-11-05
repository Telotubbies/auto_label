"""OCR annotation helpers: templates per project and image/dataset exports."""

import os
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import DATA_DIR
from ..db import get_db
from ..deps import Ctx, audit, current_user, image_ctx, project_ctx
from ..models import Image, User
from ..security import sign_path
from ..services import ocr
from ..services.flags import is_enabled, require_flag
from .projects import ensure_class

router = APIRouter(tags=["ocr"])
P = "/api/ws/{ws}/projects/{project}/ocr"
OCR_CLASSES = ("text-line", "key-value", "table")


@router.get(P + "/templates", dependencies=[Depends(require_flag("task_32"))])
def list_templates(c: Ctx = Depends(project_ctx)):
    return {
        "templates": [{"id": key, **value} for key, value in ocr.TEMPLATES.items()],
        "current": (c.project.settings or {}).get("ocr_template"),
    }


class OcrTemplateIn(BaseModel):
    template: str


@router.put(P + "/template", dependencies=[Depends(require_flag("task_32"))])
def set_template(body: OcrTemplateIn, c: Ctx = Depends(project_ctx)):
    c.perm("project.classes")
    if body.template not in ocr.TEMPLATES:
        raise HTTPException(404, "unknown OCR template")
    for name in OCR_CLASSES:  # the three annotation kinds need a class each
        ensure_class(c.db, c.project, name)
    c.project.settings = {**(c.project.settings or {}), "ocr_template": body.template}
    audit(
        c.db, c.ws.id, c.user.id, "ocr.template", c.project.name, template=body.template
    )
    c.db.commit()
    return {"current": body.template}


class OcrExportIn(BaseModel):
    format: str = "markdown"
    mask_pii: bool = True


def _items(c: Ctx) -> list[dict]:
    rows = c.db.scalars(
        select(Image).where(
            Image.project_id == c.project.id, Image.deleted_at.is_(None)
        )
    ).all()
    return [
        {
            "name": row.name,
            "width": row.width,
            "height": row.height,
            "path": row.path,
            "annotations": row.annotations or [],
        }
        for row in rows
        if any(ocr.ocr_of(a) for a in row.annotations or [])
    ]


def _zip(out: Path) -> Path:
    """Zip a built export tree into place atomically, so a download never sees a half archive."""
    tmp = out.with_name(f".{out.name}.{uuid.uuid4().hex}")
    archive = out.with_name(out.name + ".zip")
    os.replace(Path(shutil.make_archive(str(tmp), "zip", out)), archive)
    return archive


@router.post(P + "/export", dependencies=[Depends(require_flag("task_32"))])
def export_dataset(body: OcrExportIn, c: Ctx = Depends(project_ctx)):
    c.perm("project.export")
    if body.format not in ocr.EXPORT_FORMATS:
        raise HTTPException(
            400, f"format must be one of {', '.join(ocr.EXPORT_FORMATS)}"
        )
    items = _items(c)
    if not items:
        raise HTTPException(400, "this project has no OCR annotations to export yet")
    out = DATA_DIR / "exports" / "ocr" / f"{c.project.id}-{body.format}"
    ocr.build_export(body.format, out, items, DATA_DIR, body.mask_pii)
    archive = _zip(out)
    rel = archive.relative_to(DATA_DIR).as_posix()
    audit(
        c.db,
        c.ws.id,
        c.user.id,
        "ocr.export",
        c.project.name,
        format=body.format,
        images=len(items),
    )
    c.db.commit()
    return {
        "format": body.format,
        "images": len(items),
        "annotations": sum(
            sum(1 for a in it["annotations"] if ocr.ocr_of(a)) for it in items
        ),
        "url": sign_path(rel),
    }


@router.get("/api/images/{image_id}/ocr/export")
def export_image(
    image_id: str,
    format: str = Query("markdown"),
    mask_pii: bool = Query(True),
    u: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    c, img = image_ctx(db, u, image_id)
    if not is_enabled("task_32", db, c.ws.id):
        raise HTTPException(404, "not found")
    if format not in ("markdown", "json"):
        raise HTTPException(400, "format must be markdown or json")
    item = {
        "name": img.name,
        "width": img.width,
        "height": img.height,
        "annotations": img.annotations or [],
    }
    if format == "json":
        return JSONResponse(ocr.json_for([item], mask_pii))
    return PlainTextResponse(
        ocr.markdown_for(img.name, item["annotations"], mask_pii),
        media_type="text/plain; charset=utf-8",
    )
