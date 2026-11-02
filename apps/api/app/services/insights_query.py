"""One aggregation engine behind the dashboard builder.

A widget is a spec: source + measure + dimension (+ optional second dimension for a heatmap).
Everything is computed server-side from project rows, cached by the source's data signature, and
returned as uniform `{key, group, value}` rows so the client only has to pick a chart type.
"""

from __future__ import annotations

import json
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Batch, Image, Project, Version
from . import insights, insights_stream
from .insights_common import (
    cached,
    data_stamp,
    model_in_project,
    signature as model_signature,
)

SOURCES = ("dataset", "version", "model", "streams")
MEASURES = {
    "dataset": ("annotations", "images"),
    "version": ("annotations", "images"),
    "model": ("ap",),
    "streams": ("events", "dwell_seconds"),
}
DIMENSIONS = {
    "dataset": ("class", "split", "source", "batch", "tag", "none"),
    "version": ("class", "split", "source", "batch", "tag", "none"),
    "model": ("class", "none"),
    "streams": ("day", "hour", "rule", "zone", "class", "stream", "none"),
}
# Only filters a source's aggregation actually reads; anything else would look applied but be ignored.
FILTERS = {
    "dataset": ("version", "class", "split", "source", "tag", "batch"),
    "version": ("version", "class", "split", "source", "tag", "batch"),
    "model": ("model", "class"),
    "streams": ("stream", "rule", "class", "days", "tz_offset"),
}
MAX_DAYS = 365
MAX_TZ_OFFSET = 840  # UTC−14:00 … UTC+14:00, in minutes
UNIT = {
    "annotations": "annotations",
    "images": "images",
    "ap": "AP",
    "events": "events",
    "dwell_seconds": "seconds",
}


def validate(spec: dict) -> dict:
    """Normalise a widget query and reject measures/dimensions that do not belong to its source."""
    source = spec.get("source")
    if source not in SOURCES:
        raise ValueError(f"source must be one of {list(SOURCES)}")
    measure = spec.get("measure")
    if measure not in MEASURES[source]:
        raise ValueError(f"{source} supports measures {list(MEASURES[source])}")
    dimension = spec.get("dimension") or "none"
    if dimension not in DIMENSIONS[source]:
        raise ValueError(f"{source} supports dimensions {list(DIMENSIONS[source])}")
    dimension2 = spec.get("dimension2") or None
    if dimension2 is not None and dimension2 not in DIMENSIONS[source]:
        raise ValueError(f"{source} supports dimensions {list(DIMENSIONS[source])}")
    if dimension2 == dimension:
        raise ValueError("the two heatmap dimensions must differ")
    filters = spec.get("filters") or {}
    if not isinstance(filters, dict):
        raise ValueError("filters must be an object")
    unknown = set(filters) - set(FILTERS[source])
    if unknown:
        raise ValueError(f"{source} does not support filters: {sorted(unknown)}")
    clean: dict = {}
    for key, value in filters.items():
        if value is None or value == "":
            continue
        if key == "days":
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or not 1 <= value <= MAX_DAYS
            ):
                raise ValueError(f"days must be an integer between 1 and {MAX_DAYS}")
            clean[key] = value
        elif key == "tz_offset":
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or not -MAX_TZ_OFFSET <= value <= MAX_TZ_OFFSET
            ):
                raise ValueError(
                    f"tz_offset must be an integer between {-MAX_TZ_OFFSET} and {MAX_TZ_OFFSET} minutes"
                )
            clean[key] = value
        elif key == "split":
            if value not in ("train", "valid", "test"):
                raise ValueError("split must be train, valid or test")
            clean[key] = value
        else:
            if not isinstance(value, str):
                raise ValueError(f"{key} must be a string")
            clean[key] = value[:120]
    if source == "version" and not clean.get("version"):
        raise ValueError("the version source needs a version filter")
    if source == "model" and not clean.get("model"):
        raise ValueError("the model source needs a model filter")
    return {
        "source": source,
        "measure": measure,
        "dimension": dimension,
        "dimension2": dimension2,
        "filters": clean,
    }


def run(db: Session, project: Project, spec: dict) -> dict:
    query = validate(spec)
    filters = query["filters"]

    if query["source"] in ("dataset", "version"):
        version = (
            _version(db, project, filters.get("version"))
            if filters.get("version")
            else None
        )
        if filters.get("version") and version is None:
            raise LookupError("version not found")
        stamp = str(insights.signature(db, project, version))
        key = f"query:{project.id}:{json.dumps(query, sort_keys=True)}"
        payload, _hit = cached(
            key, stamp, lambda: _dataset(db, project, query, version)
        )
    elif query["source"] == "model":
        model = model_in_project(db, project.id, filters["model"])
        stamp = f"{model_signature(model)}:{data_stamp(db, project.id)}"
        key = f"query:{project.id}:{json.dumps(query, sort_keys=True)}"
        payload, _hit = cached(key, stamp, lambda: _model(model, query))
    else:
        days = filters.get("days") or insights_stream.DEFAULT_DAYS
        tz_offset = filters.get("tz_offset") or 0
        stamp = insights_stream._stamp(db, project, days, tz_offset)
        key = f"query:{project.id}:{json.dumps(query, sort_keys=True)}"
        payload, _hit = cached(
            key, f"{stamp}:{days}", lambda: _streams(db, project, query)
        )
    payload["filters"] = query["filters"]
    return payload


def _version(db: Session, project: Project, version_id: str) -> Version | None:
    version = db.get(Version, version_id)
    return version if version and version.project_id == project.id else None


def _labeled(row) -> list:
    return [a for a in (row.annotations or []) if isinstance(a, dict)]


def _source(ann: dict) -> str:
    value = ann.get("source")
    return value if isinstance(value, str) and value.strip() else "human"


def _row_split(row, split_of: dict | None) -> str:
    return (split_of or {}).get(row.id, row.split)


def _dataset(
    db: Session, project: Project, query: dict, version: Version | None
) -> dict:
    if query["source"] == "version":
        return _version_dataset(db, project, query, version)
    rows, split_of = insights.dataset_rows(db, project, version)
    classes = {c.id: c.name for c in insights.classes(db, project)}
    batches = {
        b.id: b.name for b in db.query(Batch).filter(Batch.project_id == project.id)
    }
    filters = query["filters"]

    def row_ok(row) -> bool:
        if filters.get("split") and _row_split(row, split_of) != filters["split"]:
            return False
        if filters.get("tag") and filters["tag"] not in (row.tags or []):
            return False
        if filters.get("batch") and row.batch_id != filters["batch"]:
            return False
        if filters.get("class") and filters["class"] not in _image_classes(
            row, classes
        ):
            return False
        return True

    def ann_ok(ann: dict) -> bool:
        if filters.get("class") and classes.get(ann.get("classId")) != filters["class"]:
            return False
        if filters.get("source") and _source(ann) != filters["source"]:
            return False
        return True

    counts: Counter = Counter()
    total = 0
    for row in rows:
        if not row_ok(row):
            continue
        if query["measure"] == "images":
            # The label-source filter describes annotations, so an image counts only when at least
            # one of its annotations matches class and source; the dimensions use that same subset.
            anns = [a for a in _labeled(row) if ann_ok(a)]
            if (filters.get("class") or filters.get("source")) and not anns:
                continue
            present: list[str] = []
            sources: list[str] = []
            for ann in anns:
                name = classes.get(ann.get("classId"))
                if name and name not in present:
                    present.append(name)
                src = _source(ann)
                if src not in sources:
                    sources.append(src)
            if filters.get("class"):
                present = [c for c in present if c == filters["class"]]
            total += 1
            for key, _unit in _values(
                query["dimension"],
                row,
                None,
                split_of,
                classes,
                batches,
                present,
                sources,
            ):
                for group, _g in _values(
                    query["dimension2"],
                    row,
                    None,
                    split_of,
                    classes,
                    batches,
                    present,
                    sources,
                ):
                    counts[(key, group)] += 1
            continue
        anns = [a for a in _labeled(row) if ann_ok(a)]
        total += len(anns)
        for ann in anns:
            for key, _unit in _values(
                query["dimension"], row, ann, split_of, classes, batches
            ):
                for group, _g in _values(
                    query["dimension2"], row, ann, split_of, classes, batches
                ):
                    counts[(key, group)] += 1
    return _payload(query, counts, total)


def _image_classes(row, classes: dict) -> list[str]:
    seen: list[str] = []
    for ann in _labeled(row):
        name = classes.get(ann.get("classId"))
        if name and name not in seen:
            seen.append(name)
    return seen


def _values(
    dim: str | None,
    row,
    ann: dict | None,
    split_of,
    classes,
    batches,
    present=None,
    sources=None,
) -> list[tuple]:
    """One (value, unit-label) pair per dimension member the annotation/image belongs to."""
    if dim in (None, "none"):
        return [("Total", "Total")]
    if dim == "class":
        if ann is not None:
            name = classes.get(ann.get("classId"))
            return [(name, name)] if name else []
        return [(name, name) for name in (present or [])]
    if dim == "source":
        if ann is not None:
            src = _source(ann)
            return [(src, src)]
        if sources is not None:
            return [(src, src) for src in sources]
        seen = []
        for a in _labeled(row):
            src = _source(a)
            if src not in seen:
                seen.append(src)
        return [(src, src) for src in seen]
    if dim == "split":
        value = _row_split(row, split_of)
        return [(value, value)]
    if dim == "batch":
        value = batches.get(row.batch_id) if row.batch_id else None
        return [(value or "No batch", value or "No batch")]
    if dim == "tag":
        tags = [t for t in (row.tags or []) if isinstance(t, str) and t]
        return [(t, t) for t in tags]
    return []


def _version_dataset(
    db: Session, project: Project, query: dict, version: Version | None
) -> dict:
    """Frozen version widgets read the manifest, not today's live annotations.

    The manifest records each generated item's split and class ids, plus the annotation source
    written by versioning; batch and tag stay upload metadata resolved through the source image.
    A version whose manifest is not written yet has no frozen data, so it fails loudly instead of
    reporting the whole live dataset under the version's name.
    """
    manifest = insights.version_manifest(version) if version else None
    if not manifest:
        raise LookupError("version has no manifest yet")
    names = [str(n) for n in manifest.get("classes") or []]
    items = [i for i in manifest.get("items") or [] if isinstance(i, dict)]
    images = {
        i.id: i for i in db.scalars(select(Image).where(Image.project_id == project.id))
    }
    batches = {
        b.id: b.name for b in db.query(Batch).filter(Batch.project_id == project.id)
    }
    filters = query["filters"]

    def ann_name(ann: dict) -> str | None:
        idx = ann.get("cls")
        if isinstance(idx, int) and not isinstance(idx, bool) and 0 <= idx < len(names):
            return names[idx]
        return None

    def clean_anns(item: dict) -> list[dict]:
        out = []
        for ann in item.get("anns") or []:
            if not isinstance(ann, dict):
                continue
            name = ann_name(ann)
            if name:
                out.append({"class": name, "source": _source(ann)})
        return out

    def image_ok(image) -> bool:
        if filters.get("batch") and (
            image is None or image.batch_id != filters["batch"]
        ):
            return False
        if filters.get("tag") and (
            image is None or filters["tag"] not in (image.tags or [])
        ):
            return False
        return True

    records: dict = {}
    for item in items:
        src = item.get("source") or item.get("file")
        record = records.setdefault(
            src,
            {"split": item.get("split"), "anns": [], "image": images.get(src)},
        )
        record["anns"].extend(clean_anns(item))

    def ann_ok(ann: dict) -> bool:
        if filters.get("class") and ann["class"] != filters["class"]:
            return False
        if filters.get("source") and ann["source"] != filters["source"]:
            return False
        return True

    counts: Counter = Counter()
    total = 0
    if query["measure"] == "images":
        for record in records.values():
            if filters.get("split") and record["split"] != filters["split"]:
                continue
            if not image_ok(record["image"]):
                continue
            anns = [a for a in record["anns"] if ann_ok(a)]
            if (filters.get("class") or filters.get("source")) and not anns:
                continue
            present = list(dict.fromkeys(a["class"] for a in anns))
            sources = list(dict.fromkeys(a["source"] for a in anns))
            total += 1
            for key, _unit in _version_values(
                query["dimension"], record, None, present, sources, batches
            ):
                for group, _g in _version_values(
                    query["dimension2"], record, None, present, sources, batches
                ):
                    counts[(key, group)] += 1
    else:
        for item in items:
            if filters.get("split") and item.get("split") != filters["split"]:
                continue
            record = records[item.get("source") or item.get("file")]
            if not image_ok(record["image"]):
                continue
            anns = [a for a in clean_anns(item) if ann_ok(a)]
            total += len(anns)
            for ann in anns:
                for key, _unit in _version_values(
                    query["dimension"], record, ann, None, None, batches
                ):
                    for group, _g in _version_values(
                        query["dimension2"], record, ann, None, None, batches
                    ):
                        counts[(key, group)] += 1
    return _payload(query, counts, total)


def _version_values(
    dim: str | None,
    record: dict,
    ann: dict | None,
    present: list[str] | None,
    sources: list[str] | None,
    batches: dict,
) -> list[tuple]:
    if dim in (None, "none"):
        return [("Total", "Total")]
    if dim == "class":
        if ann is not None:
            return [(ann["class"], ann["class"])]
        return [(name, name) for name in (present or [])]
    if dim == "source":
        if ann is not None:
            return [(ann["source"], ann["source"])]
        return [(src, src) for src in (sources or [])]
    if dim == "split":
        value = record.get("split")
        return [(value, value)] if value else []
    if dim == "batch":
        image = record.get("image")
        value = (
            batches.get(image.batch_id)
            if image is not None and image.batch_id
            else None
        )
        return [(value or "No batch", value or "No batch")]
    if dim == "tag":
        image = record.get("image")
        tags = (image.tags or []) if image is not None else []
        return [(t, t) for t in tags if isinstance(t, str) and t]
    return []


def _payload(query: dict, counts: Counter, total: float) -> dict:
    dim = query["dimension"]
    rows = [
        {
            "key": str(key),
            "group": (None if group in (None, "Total") else str(group)),
            "value": value,
        }
        for (key, group), value in counts.items()
    ]
    if dim in ("day", "hour"):
        rows.sort(key=lambda r: r["key"])
    else:
        rows.sort(key=lambda r: (-r["value"], r["key"]))
    return {
        "source": query["source"],
        "measure": query["measure"],
        "dimension": dim,
        "dimension2": query["dimension2"],
        "unit": UNIT[query["measure"]],
        "rows": rows,
        "total": total,
    }


def _model(model, query: dict) -> dict:
    ev = (model.metrics or {}).get("eval") or {}
    evaluated = [
        c for c in ev.get("per_class") or [] if isinstance(c, dict) and c.get("class")
    ]
    # No evaluation is unknown AP, not 0.0; a real zero is a measurement the model page would show.
    if not ev.get("coco") and not evaluated:
        raise LookupError("model has no stored evaluation")
    wanted = query["filters"].get("class")
    per_class = (
        [c for c in evaluated if c.get("class") == wanted] if wanted else evaluated
    )
    if wanted and not per_class:
        raise LookupError(f"class '{wanted}' is not in the stored evaluation")
    counts: Counter = Counter()
    overall = float((ev.get("coco") or {}).get("AP") or 0.0)
    # A class filter narrows the KPI as well as the breakdown; overall AP only describes the whole eval.
    total = (
        float(per_class[0].get("AP") or 0.0)
        if wanted and per_class
        else 0.0
        if wanted
        else overall
    )
    if query["dimension"] == "class":
        for item in per_class:
            counts[(str(item["class"]), "Total")] += float(item.get("AP") or 0.0)
    else:
        # "none" is the whole evaluation (the KPI tile), not a class breakdown
        counts[("Total", "Total")] = total
    return _payload(query, counts, total)


def _streams(db: Session, project: Project, query: dict) -> dict:
    filters = query["filters"]
    days = filters.get("days") or insights_stream.DEFAULT_DAYS
    tz_offset = filters.get("tz_offset") or 0
    rows, _streams = insights_stream.fetch(
        db, project, days, filters.get("stream"), tz_offset
    )
    if filters.get("class"):
        rows = [r for r in rows if filters["class"] in r["classes"]]
    if filters.get("rule"):
        rows = [r for r in rows if r["rule"] == filters["rule"]]
    counts: Counter = Counter()
    total = 0.0
    for row in rows:
        if query["measure"] == "dwell_seconds":
            if row["seconds"] is None:
                continue
            amount = float(row["seconds"])
        else:
            amount = 1.0
        total += amount
        for key, _unit in _stream_values(query["dimension"], row):
            for group, _g in _stream_values(query["dimension2"], row):
                counts[(key, group)] += amount
    payload = _payload(query, counts, total)
    if query["measure"] == "dwell_seconds":
        payload["total"] = round(payload["total"], 1)
        for row in payload["rows"]:
            row["value"] = round(row["value"], 1)
    return payload


def _stream_values(dim: str | None, row: dict) -> list[tuple]:
    if dim in (None, "none"):
        return [("Total", "Total")]
    if dim == "class":
        return [(c, c) for c in row["classes"]]
    if dim == "day":
        return [(row["day"], row["day"])]
    if dim == "hour":
        # Zero-padded: the client orders groups lexically, so "9" would sort after "23".
        return [(f"{row['hour']:02d}", f"{row['hour']:02d}")]
    if dim == "rule":
        return [(row["rule"], row["rule"])]
    if dim == "zone":
        return [(row["zone"], row["zone"])] if row["zone"] else []
    if dim == "stream":
        return [(row["stream_name"], row["stream_name"])]
    return []
