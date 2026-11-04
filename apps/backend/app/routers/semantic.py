"""Task 27: semantic image search and saved collections, both behind the `task_27` flag."""

from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..deps import Ctx, audit, project_ctx
from ..services import collections as collection_service
from ..services import semantic_search
from ..services.flags import require_flag

router = APIRouter(
    prefix="/api/ws/{ws}/projects/{project}",
    tags=["search"],
    dependencies=[Depends(require_flag("task_27"))],
)


class CollectionIn(BaseModel):
    name: str
    image_ids: list[str] = Field(default_factory=list)
    query: str = ""


class CollectionPatch(BaseModel):
    name: str


class ItemsIn(BaseModel):
    image_ids: list[str] = Field(default_factory=list)


def _bad_request(exc: Exception) -> NoReturn:
    if isinstance(exc, collection_service.Conflict):
        raise HTTPException(409, str(exc)) from None
    raise HTTPException(400, str(exc)) from None


def _collection(c: Ctx, collection_id: str):
    try:
        return collection_service.get(c.db, c.project, collection_id)
    except LookupError:
        raise HTTPException(404, "collection not found") from None


@router.get("/search")
def search(
    q: str = "",
    class_id: str = "",
    tag: str = "",
    split: str = "",
    status: str = "",
    review: str = "",
    annotated: str = "",
    limit: int = Query(200, ge=1, le=500),
    c: Ctx = Depends(project_ctx),
):
    """Rank images by CLIP similarity; a blank query browses the filtered dataset."""
    return semantic_search.search(
        c.db,
        c.project,
        q,
        project_role=c.project_role or c.role,
        user_id=c.user.id,
        class_id=class_id,
        tag=tag,
        split=split,
        status=status,
        review=review,
        annotated=annotated,
        limit=limit,
    )


@router.get("/collections")
def list_collections(c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    return collection_service.listing(c.db, c.project)


@router.post("/collections")
def create_collection(body: CollectionIn, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    try:
        out = collection_service.create(c.db, c.project, body.name, image_ids=body.image_ids,
                                        query=body.query, user_id=c.user.id)
    except (ValueError, LookupError) as exc:
        _bad_request(exc)
    audit(c.db, c.ws.id, c.user.id, "collection.create", out["id"], name=out["name"], count=out["count"])
    c.db.commit()
    return out


@router.get("/collections/{collection_id}")
def get_collection(collection_id: str, limit: int = Query(100, ge=1, le=500),
                   offset: int = Query(0, ge=0), c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    _collection(c, collection_id)
    return collection_service.detail(c.db, c.project, collection_id, limit=limit, offset=offset)


@router.patch("/collections/{collection_id}")
def rename_collection(collection_id: str, body: CollectionPatch, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    _collection(c, collection_id)
    try:
        out = collection_service.rename(c.db, c.project, collection_id, body.name)
    except (ValueError, LookupError) as exc:
        _bad_request(exc)
    audit(c.db, c.ws.id, c.user.id, "collection.update", collection_id, name=out["name"])
    c.db.commit()
    return out


@router.delete("/collections/{collection_id}")
def delete_collection(collection_id: str, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    _collection(c, collection_id)
    try:
        out = collection_service.remove(c.db, c.project, collection_id)
    except LookupError:
        raise HTTPException(404, "collection not found") from None
    audit(c.db, c.ws.id, c.user.id, "collection.delete", collection_id)
    c.db.commit()
    return out


@router.post("/collections/{collection_id}/items")
def add_collection_items(collection_id: str, body: ItemsIn, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    _collection(c, collection_id)
    try:
        out = collection_service.add_items(c.db, c.project, collection_id, body.image_ids)
    except (ValueError, LookupError) as exc:
        _bad_request(exc)
    audit(c.db, c.ws.id, c.user.id, "collection.items", collection_id, added=len(body.image_ids))
    c.db.commit()
    return out


@router.delete("/collections/{collection_id}/items")
def remove_collection_items(collection_id: str, body: ItemsIn, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    _collection(c, collection_id)
    try:
        out = collection_service.remove_items(c.db, c.project, collection_id, body.image_ids)
    except LookupError:
        raise HTTPException(404, "collection not found") from None
    audit(c.db, c.ws.id, c.user.id, "collection.items", collection_id, removed=len(body.image_ids))
    c.db.commit()
    return out
