"""Saved collections: project-scoped image sets with stable insertion order.

Collections only store membership; the heavy curation actions ("send to annotate", tag, delete)
reuse the existing `/images/bulk` endpoint so there is one write path for image state.
"""

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Collection, CollectionItem, Image, Project, now
from ..security import sign_path

MAX_ITEMS = 5000
MAX_NAME = 255
MAX_QUERY = 2000


class Conflict(ValueError):
    """A collection name that already exists in this project (HTTP 409)."""


def _clean_name(name: str) -> str:
    value = (name or "").strip()
    if not value:
        raise ValueError("collection name is required")
    if len(value) > MAX_NAME:
        raise ValueError("collection name is too long")
    return value


def _check_name(db: Session, project: Project, name: str, *, exclude: str = "") -> None:
    hit = db.scalar(
        select(Collection.id).where(
            Collection.project_id == project.id,
            func.lower(Collection.name) == name.casefold(),
            Collection.id != exclude,
        )
    )
    if hit:
        raise Conflict("collection name already exists")


def _validated_ids(db: Session, project: Project, image_ids: list[str]) -> list[str]:
    """Requested ids in caller order; anything outside this project or deleted is a validation error."""
    wanted = list(dict.fromkeys(i for i in image_ids or [] if isinstance(i, str) and i))
    if not wanted:
        return []
    rows = db.execute(
        select(Image.id, Image.project_id, Image.deleted_at)
        .where(Image.id.in_(wanted), Image.project_id == project.id)
    ).all()
    # A foreign or unknown id is "not found" on purpose: a cross-tenant id must not reveal that it
    # exists in another project.
    found = {row.id for row in rows}
    if any(image_id not in found for image_id in wanted):
        raise ValueError("image not found")
    live = {image_id for image_id, _project_id, deleted in rows if deleted is None}
    if any(image_id not in live for image_id in wanted):
        raise ValueError("image was deleted; restore it before adding it to a collection")
    return wanted


def get(db: Session, project: Project, collection_id: str) -> Collection:
    row = db.get(Collection, collection_id)
    if not row or row.project_id != project.id or row.workspace_id != project.workspace_id:
        raise LookupError("collection not found")
    return row


def _count(db: Session, row: Collection) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(CollectionItem)
            .join(Image, Image.id == CollectionItem.image_id)
            .where(
                CollectionItem.collection_id == row.id,
                CollectionItem.project_id == row.project_id,
                Image.deleted_at.is_(None),
            )
        )
        or 0
    )


def summary(db: Session, row: Collection) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "query": row.query,
        "count": _count(db, row),
        "created": row.created,
        "updated": row.updated,
    }


def _append(db: Session, row: Collection, image_ids: list[str]) -> None:
    if not image_ids:
        return
    existing = set(
        db.scalars(
            select(CollectionItem.image_id).where(CollectionItem.collection_id == row.id)
        )
    )
    position = int(
        db.scalar(
            select(func.max(CollectionItem.position)).where(CollectionItem.collection_id == row.id)
        )
        or 0
    )
    for image_id in image_ids:
        if image_id in existing:
            continue
        position += 1
        db.add(CollectionItem(collection_id=row.id, image_id=image_id, project_id=row.project_id,
                              position=position))
    row.updated = now()


def create(db: Session, project: Project, name: str, *, image_ids: list[str] | None = None,
           query: str = "", user_id: str | None = None) -> dict:
    clean = _clean_name(name)
    _check_name(db, project, clean)
    ids = _validated_ids(db, project, image_ids or [])
    if len(ids) > MAX_ITEMS:
        raise ValueError(f"a collection holds at most {MAX_ITEMS} images")
    row = Collection(workspace_id=project.workspace_id, project_id=project.id, name=clean,
                     query=(query or "")[:MAX_QUERY], created_by=user_id)
    db.add(row)
    try:
        db.flush()
        _append(db, row, ids)
        db.commit()
    except IntegrityError:  # two requests raced past the pre-check
        db.rollback()
        raise Conflict("collection name already exists") from None
    db.refresh(row)
    return summary(db, row)


def listing(db: Session, project: Project) -> dict:
    rows = db.scalars(
        select(Collection)
        .where(Collection.project_id == project.id, Collection.workspace_id == project.workspace_id)
        .order_by(Collection.created.desc(), Collection.id)
    ).all()
    return {"collections": [summary(db, row) for row in rows]}


def detail(db: Session, project: Project, collection_id: str, *, limit: int = 100,
           offset: int = 0) -> dict:
    row = get(db, project, collection_id)
    ids = list(
        db.scalars(
            select(CollectionItem.image_id)
            .join(Image, Image.id == CollectionItem.image_id)
            .where(
                CollectionItem.collection_id == row.id,
                CollectionItem.project_id == project.id,
                Image.deleted_at.is_(None),
            )
            .order_by(CollectionItem.position, CollectionItem.image_id)
        )
    )
    page = ids[max(0, offset): max(0, offset) + max(1, min(limit, 500))]
    images = {image.id: image for image in db.scalars(select(Image).where(Image.id.in_(page)))} if page else {}
    items = [
        {
            "id": image.id,
            "name": image.name,
            "thumbnail": sign_path(image.thumb or image.path),
            "split": image.split,
            "status": image.status,
            "tags": [tag for tag in (image.tags or []) if isinstance(tag, str)],
        }
        for image_id in page
        if (image := images.get(image_id)) is not None
    ]
    return {**summary(db, row), "total": len(ids), "items": items}


def rename(db: Session, project: Project, collection_id: str, name: str) -> dict:
    row = get(db, project, collection_id)
    clean = _clean_name(name)
    _check_name(db, project, clean, exclude=row.id)
    row.name = clean
    row.updated = now()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflict("collection name already exists") from None
    db.refresh(row)
    return summary(db, row)


def add_items(db: Session, project: Project, collection_id: str, image_ids: list[str]) -> dict:
    row = get(db, project, collection_id)
    present = set(
        db.scalars(select(CollectionItem.image_id).where(CollectionItem.collection_id == row.id))
    )
    new = [image_id for image_id in _validated_ids(db, project, image_ids) if image_id not in present]
    if len(new) > MAX_ITEMS - _count(db, row):
        raise ValueError(f"a collection holds at most {MAX_ITEMS} images")
    _append(db, row, new)
    db.commit()
    db.refresh(row)
    return summary(db, row)


def remove_items(db: Session, project: Project, collection_id: str, image_ids: list[str]) -> dict:
    row = get(db, project, collection_id)
    wanted = list(dict.fromkeys(i for i in image_ids or [] if isinstance(i, str) and i))
    if wanted:
        db.execute(
            sa_delete(CollectionItem).where(
                CollectionItem.collection_id == row.id, CollectionItem.image_id.in_(wanted)
            )
        )
        row.updated = now()
        db.commit()
        db.refresh(row)
    return summary(db, row)


def remove(db: Session, project: Project, collection_id: str) -> dict:
    row = get(db, project, collection_id)
    db.execute(sa_delete(CollectionItem).where(CollectionItem.collection_id == row.id))
    db.delete(row)
    db.commit()
    return {"ok": True}
