"""Good-only anomaly detection: stations, training jobs, per-station inference and heatmaps."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..config import DATA_DIR
from ..deps import Ctx, audit, project_ctx
from ..models import AnomalyStation, Image, Job, now
from ..security import sign_path
from ..services import anomaly, flags, imaging
from .projects import job_out

P = "/api/ws/{ws}/projects/{project}"
AN = P + "/anomaly"
router = APIRouter(prefix=AN, tags=["anomaly"], dependencies=[Depends(flags.require_flag("task_29"))])
MAX_TRAIN_IMAGES = 300
log = logging.getLogger(__name__)


def station_out(st: AnomalyStation) -> dict:
    return {
        "id": st.id,
        "name": st.name,
        "threshold": st.threshold,
        "status": st.status,
        "artifact": st.artifact or None,
        "metrics": st.metrics or {},
        "error": st.error,
        "created": st.created,
        "updated": st.updated,
    }


def _station(c: Ctx, station_id: str) -> AnomalyStation:
    st = c.db.get(AnomalyStation, station_id)
    if not st or st.project_id != c.project.id or st.workspace_id != c.ws.id:
        raise HTTPException(404, "station not found")
    return st


def _normal_images(c: Ctx, image_ids: list[str] | None) -> list[Image]:
    """Good-only training set: explicitly chosen images or every unannotated project image."""
    if image_ids is not None:
        ids = list(dict.fromkeys(image_ids))
        rows = (
            c.db.scalars(
                select(Image).where(
                    Image.project_id == c.project.id,
                    Image.id.in_(ids),
                    Image.deleted_at.is_(None),
                )
            ).all()
            if ids
            else []
        )
        if len(rows) != len(ids):
            raise HTTPException(400, "every normal image must belong to this project")
    else:
        rows = c.db.scalars(
            select(Image)
            .where(
                Image.project_id == c.project.id,
                Image.deleted_at.is_(None),
                Image.n_annotations == 0,
            )
            .order_by(Image.created.desc())
            .limit(MAX_TRAIN_IMAGES)
        ).all()
    if any(row.n_annotations > 0 for row in rows):
        raise HTTPException(400, "normal images must have no annotations — good-only training")
    if len(rows) < anomaly.MIN_NORMAL_IMAGES:
        raise HTTPException(
            400,
            f"need at least {anomaly.MIN_NORMAL_IMAGES} normal images (images with no annotations) to train a station",
        )
    return rows


@router.get("/stations")
def list_stations(c: Ctx = Depends(project_ctx)):
    c.perm("project.read")
    rows = c.db.scalars(
        select(AnomalyStation)
        .where(AnomalyStation.workspace_id == c.ws.id, AnomalyStation.project_id == c.project.id)
        .order_by(AnomalyStation.created)
    ).all()
    return [station_out(st) for st in rows]


class AnomalyStationIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    # Scores are nearest-normal-neighbour distances in units of the calibration p99, so a
    # glaring defect can sit two orders of magnitude above the default 1.0.
    threshold: float = Field(default=1.0, ge=0, le=1000)


@router.post("/stations")
def create_station(body: AnomalyStationIn, c: Ctx = Depends(project_ctx)):
    c.perm("project.train")
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "station name is required")
    if c.db.scalar(
        select(AnomalyStation.id).where(
            AnomalyStation.workspace_id == c.ws.id,
            AnomalyStation.project_id == c.project.id,
            AnomalyStation.name == name,
        )
    ):
        raise HTTPException(409, "a station with this name already exists")
    st = AnomalyStation(
        workspace_id=c.ws.id,
        project_id=c.project.id,
        name=name,
        threshold=body.threshold,
    )
    c.db.add(st)
    audit(c.db, c.ws.id, c.uid, "anomaly.station.create", name, threshold=body.threshold)
    c.db.commit()
    return station_out(st)


class AnomalyStationPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    threshold: float | None = Field(default=None, ge=0, le=1000)


@router.patch("/stations/{station_id}")
def patch_station(station_id: str, body: AnomalyStationPatch, c: Ctx = Depends(project_ctx)):
    c.perm("project.train")
    st = _station(c, station_id)
    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(400, "station name is required")
        other = c.db.scalar(
            select(AnomalyStation.id).where(
                AnomalyStation.workspace_id == c.ws.id,
                AnomalyStation.project_id == c.project.id,
                AnomalyStation.name == name,
                AnomalyStation.id != st.id,
            )
        )
        if other:
            raise HTTPException(409, "a station with this name already exists")
        st.name = name
    if body.threshold is not None:
        st.threshold = body.threshold
    st.updated = now()
    audit(c.db, c.ws.id, c.uid, "anomaly.station.update", st.name, threshold=st.threshold)
    c.db.commit()
    return station_out(st)


class TrainIn(BaseModel):
    image_ids: list[str] | None = None


def _active_job(c: Ctx, station_id: str) -> Job | None:
    rows = c.db.scalars(
        select(Job)
        .where(
            Job.project_id == c.project.id,
            Job.kind == "anomaly_train",
            Job.status.in_(("queued", "running")),
        )
        .order_by(Job.created.desc())
        .limit(20)
    ).all()
    return next((j for j in rows if (j.params or {}).get("station_id") == station_id), None)


@router.post("/stations/{station_id}/train")
def train_station(station_id: str, body: TrainIn, c: Ctx = Depends(project_ctx)):
    c.perm("project.train")
    st = _station(c, station_id)
    active = _active_job(c, st.id)
    if active:  # double click: return the run already in flight
        return {"station": station_out(st), "job": job_out(active)}
    rows = _normal_images(c, body.image_ids)
    st.status = "queued"
    st.error = ""
    st.updated = now()
    job = Job(
        workspace_id=c.ws.id,
        project_id=c.project.id,
        kind="anomaly_train",
        created_by=c.uid,
        params={"station_id": st.id, "image_ids": [row.id for row in rows]},
    )
    c.db.add(job)
    c.db.flush()
    audit(c.db, c.ws.id, c.uid, "anomaly.station.train", st.name, images=len(rows))
    c.db.commit()
    return {"station": station_out(st), "job": job_out(job)}


class AnomalyPredictIn(BaseModel):
    image_id: str
    compare_vlm: bool = False


@router.post("/stations/{station_id}/predict")
def predict_station(station_id: str, body: AnomalyPredictIn, c: Ctx = Depends(project_ctx)):
    c.perm("project.infer")
    st = _station(c, station_id)
    if st.status != "ready" or not st.artifact:
        raise HTTPException(409, "station is not trained yet")
    artifact = DATA_DIR / st.artifact
    if not artifact.is_file():
        raise HTTPException(409, "station weights are missing — retrain the station")
    img = c.db.get(Image, body.image_id)
    if not img or img.deleted_at or img.project_id != c.project.id:
        raise HTTPException(404, "image not found")
    try:
        model = anomaly.load(artifact)
        im = imaging.load(img.path)
        result = anomaly.score(model, im, st.threshold)
    except (OSError, ValueError):
        log.exception("anomaly inference failed for station %s", st.id)
        raise HTTPException(503, "inference failed") from None
    vlm = anomaly.vlm_compare(im, result["is_anomaly"]) if body.compare_vlm else None
    return {
        **result,
        "station_id": st.id,
        "image_id": img.id,
        "vlm": vlm,
        "image": {
            "id": img.id,
            "name": img.name,
            "width": img.width,
            "height": img.height,
            "url": sign_path(img.path),
        },
    }
