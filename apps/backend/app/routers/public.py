"""Anonymous public dataset payload and sample thumbnails (T-035), mounted after the app routers."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Image
from ..ratelimit import client_ip, limit
from ..services import public_dataset

router = APIRouter(prefix="/api/public/datasets", tags=["public"])
IMAGE_LIMIT = 120


@router.get("/{ws}/{project}")
def dataset(ws: str, project: str, db: Session = Depends(get_db)):
    workspace, row = public_dataset.resolve(db, ws, project)
    return public_dataset.payload(db, row)


@router.get("/{ws}/{project}/images/{image_id}")
def sample(ws: str, project: str, image_id: str, request: Request, db: Session = Depends(get_db)):
    try:
        limit(f"public-image:{client_ip(request)}", IMAGE_LIMIT, 60)
    except HTTPException as e:
        raise HTTPException(429, "Too many requests — try again shortly.", headers=e.headers) from None
    _workspace, row = public_dataset.resolve(db, ws, project)
    image = db.scalar(select(Image).where(Image.id == image_id, Image.project_id == row.id,
                                         Image.deleted_at.is_(None)))
    path = public_dataset.thumb_path(row, image) if image is not None else None
    if path is None or not path.is_file():
        raise HTTPException(404, "Not found")
    return FileResponse(path, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=3600"})
