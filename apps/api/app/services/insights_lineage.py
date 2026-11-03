"""Pipeline lineage: batches -> versions -> training runs -> models -> streams.

Read-only. A version's source images come from its manifest, so the batch -> version edge is the
same frozen lineage the exported dataset uses; streams attach to the trained model they serve.
"""

from __future__ import annotations

import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    Batch,
    Image,
    Job,
    Project,
    Stream,
    StreamEvent,
    TrainedModel,
    Version,
)
from . import insights


def _batches(db: Session, project: Project) -> dict[str, Batch]:
    return {
        b.id: b
        for b in db.scalars(select(Batch).where(Batch.project_id == project.id)).all()
    }


def _image_nodes(db: Session, project: Project) -> tuple[dict, dict]:
    """image id -> batch id (history, deleted rows included), and batch id -> live image count.

    A manifest keeps naming an image after the dataset soft-deletes it, so the batch mapping must
    stay historical or a normal edit would rewrite the version's frozen lineage.
    """
    rows = db.execute(
        select(Image.id, Image.batch_id, Image.deleted_at).where(
            Image.project_id == project.id
        )
    ).all()
    batch_of = {iid: bid for iid, bid, _deleted in rows if bid}
    counts: dict = {}
    for _iid, bid, deleted in rows:
        if bid and deleted is None:
            counts[bid] = counts.get(bid, 0) + 1
    return batch_of, counts


def _version_edges(
    db: Session, version: Version, batch_of: dict
) -> tuple[set, int, int]:
    """(batch ids reached, image count, annotation count) from the version's frozen manifest."""
    manifest = insights.version_manifest(version) or {}
    items = [i for i in manifest.get("items") or [] if isinstance(i, dict)]
    sources = {i.get("source") for i in items if i.get("source")}
    images = (
        len(sources) if sources else len(items)
    )  # augmented copies share one source image
    anns = sum(len(i.get("anns") or []) for i in items)
    return {batch_of[s] for s in sources if s in batch_of}, images, anns


def _ap(value) -> float | None:
    """A model without a stored evaluation has unknown AP; 0.0 would read as a real score."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def build(db: Session, project: Project, include_streams: bool = True) -> dict:
    """The project's lineage. ``include_streams=False`` omits camera nodes for roles without
    ``project.streams``; the rest of the pipeline stays readable instead of 403-ing the page."""
    batches = _batches(db, project)
    batch_of, batch_counts = _image_nodes(db, project)
    versions = db.scalars(
        select(Version)
        .where(Version.project_id == project.id)
        .order_by(Version.created, Version.id)
    ).all()
    jobs = db.scalars(
        select(Job)
        .where(Job.project_id == project.id, Job.kind == "train")
        .order_by(Job.created, Job.id)
    ).all()
    models = db.scalars(
        select(TrainedModel)
        .where(TrainedModel.project_id == project.id)
        .order_by(TrainedModel.created, TrainedModel.id)
    ).all()
    streams = (
        db.scalars(
            select(Stream)
            .where(Stream.project_id == project.id)
            .order_by(Stream.created, Stream.id)
        ).all()
        if include_streams
        else []
    )
    event_counts = (
        dict(
            db.execute(
                select(StreamEvent.stream_id, func.count(StreamEvent.id))
                .join(Stream, Stream.id == StreamEvent.stream_id)
                .where(Stream.project_id == project.id)
                .group_by(StreamEvent.stream_id)
            ).all()
        )
        if include_streams
        else {}
    )

    nodes: list[dict] = []
    edges: list[dict] = []

    version_edges = {v.id: _version_edges(db, v, batch_of) for v in versions}
    referenced_batches = (
        set().union(*(reached for reached, _i, _a in version_edges.values()))
        if version_edges
        else set()
    )

    for bid in sorted(
        set(batch_counts) | referenced_batches,
        key=lambda k: batches[k].created if k in batches else 0,
    ):
        b = batches.get(bid)
        if b is None:
            continue  # batch row deleted, image already re-pointed by SET NULL in practice
        count = batch_counts.get(bid, 0)
        nodes.append(
            {
                "id": f"batch:{b.id}",
                "kind": "batch",
                "label": b.name,
                "sub": f"{count} images",
                "created": b.created,
                "counts": {"images": count},
                "metrics": {},
                "detail": {"source": b.source, "created_by": b.created_by},
                "artifacts": [],
                "log": "",
            }
        )

    for v in versions:
        reached, images, anns = version_edges[v.id]
        stats = v.stats or {}
        nodes.append(
            {
                "id": f"version:{v.id}",
                "kind": "version",
                "label": v.name or f"v{v.number}",
                "sub": f"v{v.number} · {v.status}",
                "created": v.created,
                "counts": {
                    "images": images,
                    "annotations": anns,
                    "splits": sum((stats.get("splits") or {}).values()) or images,
                },
                "metrics": {"leakage_moved": stats.get("leakage_moved")},
                "detail": {
                    "number": v.number,
                    "status": v.status,
                    "version_hash": stats.get("version_hash")
                    or (insights.version_manifest(v) or {}).get("version_hash"),
                    "classes": stats.get("classes") or {},
                },
                "artifacts": [{"label": "manifest.json"}, {"label": "recipe.json"}],
                "log": "",
            }
        )
        for bid in sorted(reached):
            edges.append(
                {
                    "source": f"batch:{bid}",
                    "target": f"version:{v.id}",
                    "kind": "images",
                }
            )

    known_versions = {v.id for v in versions}
    job_models = {m.job_id for m in models if m.job_id}
    for j in jobs:
        version_id = (j.params or {}).get("version_id")
        options = (j.params or {}).get("options") or {}
        model_id = (j.params or {}).get("model_id")
        label = next((m.name for m in models if m.id == model_id), "")
        nodes.append(
            {
                "id": f"run:{j.id}",
                "kind": "run",
                "label": label or f"Run {j.id[:6]}",
                "sub": f"{j.status} · {round((j.progress or 0) * 100)}%",
                "created": j.created,
                "counts": {"epochs": int(options.get("epochs") or 0)},
                "metrics": {},
                "detail": {
                    "status": j.status,
                    "progress": j.progress,
                    "error": j.error or "",
                    "params": {"version_id": version_id, "model_id": model_id},
                    "started": j.started,
                    "finished": j.finished,
                },
                "artifacts": [],
                "log": j.error or "",
            }
        )
        if version_id in known_versions:
            edges.append(
                {
                    "source": f"version:{version_id}",
                    "target": f"run:{j.id}",
                    "kind": "training",
                }
            )

    for m in models:
        ev = (m.metrics or {}).get("eval") or {}
        coco = ev.get("coco") or {}
        nodes.append(
            {
                "id": f"model:{m.id}",
                "kind": "model",
                "label": m.name,
                "sub": f"{m.task} · {m.arch} · {m.status}",
                "created": m.created,
                "counts": {"classes": len(m.classes or [])},
                "metrics": {
                    "AP": _ap(coco.get("AP")),
                    "AP50": _ap(coco.get("AP50")),
                },
                "detail": {
                    "classes": list(m.classes or []),
                    "task": m.task,
                    "arch": m.arch,
                    "status": m.status,
                    "version_id": m.version_id,
                    "family": m.family,
                    "variant": m.variant,
                    "license": m.license,
                },
                "artifacts": [{"label": "weights"}] if m.weights else [],
                "log": "",
            }
        )
        if m.job_id and m.job_id in job_models:
            edges.append(
                {
                    "source": f"run:{m.job_id}",
                    "target": f"model:{m.id}",
                    "kind": "training",
                }
            )
        elif m.version_id in known_versions:
            # a model imported or trained outside the job queue still descends from its version
            edges.append(
                {
                    "source": f"version:{m.version_id}",
                    "target": f"model:{m.id}",
                    "kind": "training",
                }
            )

    for s in streams:
        count = int(event_counts.get(s.id, 0))
        nodes.append(
            {
                "id": f"stream:{s.id}",
                "kind": "stream",
                "label": s.name,
                "sub": f"{s.status} · {s.model_ref}",
                "created": s.created,
                "counts": {"events": count},
                "metrics": {},
                "detail": {
                    "model_ref": s.model_ref,
                    "status": s.status,
                    "zones": len(s.zones or []),
                    "rules": len(s.rules or []),
                    "sample_fps": s.sample_fps,
                },
                "artifacts": [],
                "log": s.last_error or "",
            }
        )
        if s.model_ref.startswith("trained:"):
            edges.append(
                {
                    "source": f"model:{s.model_ref.split(':', 1)[1]}",
                    "target": f"stream:{s.id}",
                    "kind": "deployment",
                }
            )

    node_ids = {n["id"] for n in nodes}
    edges = [e for e in edges if e["source"] in node_ids and e["target"] in node_ids]
    return {"nodes": nodes, "edges": edges, "generated": time.time()}
