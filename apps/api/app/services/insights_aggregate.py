"""SQL aggregation for dataset/version widgets (I11).

A widget is a small aggregate: annotations or images grouped by at most two dimensions, with
optional filters. The previous implementation hydrated every ``Image`` row (annotations JSON
included) into Python on each cache miss, so one reviewer could OOM the single API worker with a
handful of distinct specs. This module pushes the same rules into SQL: annotation rows are
unnested with the dialect's JSON table function, and images are counted with ``COUNT(DISTINCT
image_id)`` so a heatmap never double-counts an image.

The returned ``(Counter[(key, group)], total)`` matches ``insights_query._payload`` exactly; the
caller owns caching and response shaping.
"""

from __future__ import annotations

from collections import Counter

from sqlalchemy import and_, case, distinct, exists, func, literal, select, true
from sqlalchemy.orm import Session

from ..models import Batch, Image, LabelClass, Project


def _dialect(db: Session) -> str:
    return db.get_bind().dialect.name


def _object_rows(dialect: str, column, alias: str):
    """One row per annotation object; non-dict legacy entries are filtered out."""
    if dialect == "postgresql":
        tv = func.json_array_elements(column).table_valued("value").alias(alias)
        is_object = func.json_typeof(tv.c.value) == "object"
    else:
        # json_each exposes its own `type`; json_type(value) would fail on scalar elements.
        tv = func.json_each(column).table_valued("value", "type").alias(alias)
        is_object = tv.c.type == "object"
    return tv, is_object


def _text_rows(dialect: str, column, alias: str):
    """One row per JSON string element (tags), as text on both backends."""
    if dialect == "postgresql":
        tv = func.json_array_elements_text(column).table_valued("value").alias(alias)
    else:
        # json_each's value column is already SQL text for string elements.
        tv = func.json_each(column).table_valued("value").alias(alias)
    return tv, tv.c.value


def _field(dialect: str, tv, name: str):
    if dialect == "postgresql":
        return tv.c.value.op("->>")(name)
    return func.json_extract(tv.c.value, f"$.{name}")


def _source(dialect: str, tv):
    """The labeler's stored source, defaulting to human exactly like the Python reader did."""
    raw = _field(dialect, tv, "source")
    return func.coalesce(func.nullif(func.trim(raw), ""), "human")


def _class_ids(project: Project, name: str):
    return select(LabelClass.id).where(
        LabelClass.project_id == project.id, LabelClass.name == name
    )


def _ann_conditions(dialect, tv, is_object, project, filters):
    """Filters that apply to one annotation, matching ``ann_ok`` in the old reader."""
    conds = [is_object]
    if filters.get("class"):
        conds.append(_field(dialect, tv, "classId").in_(_class_ids(project, filters["class"])))
    if filters.get("source"):
        conds.append(_source(dialect, tv) == filters["source"])
    return conds


def _split_expr(project: Project, version, split_of: dict | None):
    """A dataset read scoped to a version uses the manifest's frozen split, not today's column."""
    if version is None or not split_of:
        return Image.split
    return case(split_of, value=Image.id, else_=Image.split)


def _image_where(project, filters, version, split_of, dialect):
    """Filters on the image row, independent of whether annotations are unnested."""
    where = [Image.project_id == project.id, Image.deleted_at.is_(None)]
    if version is not None and split_of:
        where.append(Image.id.in_(list(split_of)))
    if filters.get("split"):
        where.append(_split_expr(project, version, split_of) == filters["split"])
    if filters.get("batch"):
        where.append(Image.batch_id == filters["batch"])
    if filters.get("tag"):
        tv, value = _text_rows(dialect, Image.tags, "filter_tag")
        where.append(
            exists(select(literal(1)).select_from(tv).where(value == filters["tag"]))
        )
    return where


def _has_annotation_filter(filters) -> bool:
    return bool(filters.get("class") or filters.get("source"))


def _annotations(
    db, project, query, where, filters, dialect, version, split_of
) -> tuple[Counter, int]:
    """Annotation count per dimension (or image count) with the annotation-level filters."""
    tv, is_object = _object_rows(dialect, Image.annotations, "fact_ann")
    conds = _ann_conditions(dialect, tv, is_object, project, filters)
    dim, dim2 = query["dimension"], query["dimension2"]
    dims = {dim, dim2}

    base = select(Image.id.label("image_id")).select_from(Image).join(tv, true())
    base = base.where(*where, *conds)
    total = int(db.scalar(select(func.count()).select_from(base.subquery())) or 0)

    stmt = select().select_from(Image).join(tv, true())
    stmt = stmt.where(*where, *conds)
    if "tag" in dims:
        tag_tv, _tag_value = _text_rows(dialect, Image.tags, "dim_tag")
        stmt = stmt.join(tag_tv, true())
    if "batch" in dims:
        stmt = stmt.outerjoin(
            Batch, and_(Batch.id == Image.batch_id, Batch.project_id == project.id)
        )
    if "class" in dims:
        stmt = stmt.outerjoin(
            LabelClass,
            and_(
                LabelClass.id == _field(dialect, tv, "classId"),
                LabelClass.project_id == project.id,
            ),
        )

    split_expr = _split_expr(project, version, split_of)
    key = _ann_dim_expr(
        dialect, dim, tv, tag_tv if "tag" in dims else None, split_expr
    )
    group = _ann_dim_expr(
        dialect, dim2, tv, tag_tv if "tag" in dims else None, split_expr
    )
    stmt = stmt.add_columns(key.label("k"), group.label("g"), func.count().label("n"))
    stmt = stmt.group_by(key, group)
    counts = _collect(db.execute(stmt), dim, dim2)
    return counts, total


def _ann_dim_expr(dialect, dim: str | None, tv, tag_tv, split_expr):
    if dim in (None, "none"):
        return literal("Total")
    if dim == "class":
        return LabelClass.name
    if dim == "source":
        return _source(dialect, tv)
    if dim == "split":
        return split_expr
    if dim == "batch":
        return func.coalesce(Batch.name, "No batch")
    if dim == "tag":
        return tag_tv.c.value
    return literal("Total")


def _image_dim(filtered, dim, project, where, filters, dialect):
    """One row per (image, dimension value); a heatmap joins two of these."""
    if dim in (None, "none"):
        return select(
            filtered.c.image_id, literal("Total").label("v")
        ).select_from(filtered).subquery()
    if dim == "split":
        return select(filtered.c.image_id, filtered.c.split.label("v")).subquery()
    if dim == "batch":
        return (
            select(filtered.c.image_id, func.coalesce(Batch.name, "No batch").label("v"))
            .select_from(filtered)
            .outerjoin(
                Batch, and_(Batch.id == filtered.c.batch_id, Batch.project_id == project.id)
            )
            .subquery()
        )
    if dim == "tag":
        tag_tv, value = _text_rows(dialect, filtered.c.tags, "dim_tag")
        return (
            select(filtered.c.image_id, value.label("v"))
            .select_from(filtered)
            .join(tag_tv, true())
            .where(value.is_not(None), value != "")
            .distinct()
            .subquery()
        )

    tv, is_object = _object_rows(dialect, Image.annotations, "dim_ann")
    conds = _ann_conditions(dialect, tv, is_object, project, filters)
    stmt = select(Image.id.label("image_id")).select_from(Image).join(tv, true())
    stmt = stmt.where(*where, *conds)
    if dim == "class":
        stmt = stmt.add_columns(LabelClass.name.label("v")).outerjoin(
            LabelClass,
            and_(
                LabelClass.id == _field(dialect, tv, "classId"),
                LabelClass.project_id == project.id,
            ),
        )
    else:  # source
        stmt = stmt.add_columns(_source(dialect, tv).label("v"))
    return stmt.distinct().subquery()


def _images(
    db, project, query, where, filters, dialect, version, split_of
) -> tuple[Counter, int]:
    columns = (
        Image.id.label("image_id"),
        Image.batch_id.label("batch_id"),
        Image.tags.label("tags"),
        _split_expr(project, version, split_of).label("split"),
    )
    filtered_stmt = select(*columns).where(*where)
    if _has_annotation_filter(filters):
        tv, is_object = _object_rows(dialect, Image.annotations, "filter_ann")
        conds = _ann_conditions(dialect, tv, is_object, project, filters)
        filtered_stmt = filtered_stmt.where(
            exists(select(literal(1)).select_from(tv).where(*conds))
        )
    filtered = filtered_stmt.subquery("filtered")
    total = int(db.scalar(select(func.count()).select_from(filtered)) or 0)
    dim, dim2 = query["dimension"], query["dimension2"]
    d1 = _image_dim(filtered, dim, project, where, filters, dialect)
    d2 = _image_dim(filtered, dim2, project, where, filters, dialect)
    stmt = (
        select(
            d1.c.v.label("k"),
            d2.c.v.label("g"),
            func.count(distinct(d1.c.image_id)).label("n"),
        )
        .select_from(d1)
        .join(d2, d1.c.image_id == d2.c.image_id)
        .group_by(d1.c.v, d2.c.v)
    )
    return _collect(db.execute(stmt), dim, dim2), total


def _collect(rows, dim, dim2) -> Counter:
    counts: Counter = Counter()
    for key, group, n in rows:
        if dim == "class" and key is None:
            continue
        if dim2 == "class" and group is None:
            continue
        if dim == "tag" and not key:
            continue
        if dim2 == "tag" and not group:
            continue
        counts[(key, group)] += int(n)
    return counts


def dataset_counts(
    db: Session,
    project: Project,
    query: dict,
    version=None,
    split_of: dict | None = None,
) -> tuple[Counter, int]:
    """Aggregate one dataset widget in SQL; returns (counts, total)."""
    dialect = _dialect(db)
    filters = query["filters"]
    where = _image_where(project, filters, version, split_of, dialect)
    if query["measure"] == "annotations":
        return _annotations(db, project, query, where, filters, dialect, version, split_of)
    return _images(db, project, query, where, filters, dialect, version, split_of)
