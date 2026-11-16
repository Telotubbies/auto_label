"""Good-only anomaly training: the ``anomaly_train`` kind.

The handler resolves its runner dependency through ``app.worker`` (``w._set``) so the process
that swaps it at runtime keeps working. Training is CPU-only: no GPU lease, no GPU worker kind.
"""

import logging

from sqlalchemy import select

from ..config import DATA_DIR
from ..db import SessionLocal
from ..models import AnomalyStation, Image, now
from ..services import anomaly, imaging

log = logging.getLogger("labeldesk.worker")  # same logger the runner used before the split


def run_anomaly_train(job):
    """Fit a station's normal-patch bank from unannotated images."""
    from .. import worker as w

    station_id = job.params["station_id"]
    with SessionLocal() as db:
        st = db.get(AnomalyStation, station_id)
        if st is None:
            raise RuntimeError("station was deleted before training started")
        st.status, st.error, st.updated = "training", "", now()
        db.commit()
        try:
            rows = db.scalars(
                select(Image)
                .where(
                    Image.project_id == st.project_id,
                    Image.id.in_(job.params.get("image_ids") or []),
                    Image.deleted_at.is_(None),
                )
                .order_by(Image.created)
            ).all()
            images = []
            for n, row in enumerate(rows):
                images.append(imaging.load(row.path))
                w._set(job.id, progress=round((n + 1) / max(1, len(rows)) * 80, 1))
            model = anomaly.train(images)
            rel = f"anomaly/{st.id}.npz"
            anomaly.save(DATA_DIR / rel, model)
            st = db.get(AnomalyStation, station_id)
            if st is None:
                raise RuntimeError("station was deleted during training")
            st.artifact, st.status, st.metrics, st.updated = rel, "ready", model.metrics, now()
            db.commit()
            return {"station_id": st.id, **model.metrics}
        except Exception as e:
            db.rollback()
            log.exception("anomaly training failed for station %s", station_id)
            st = db.get(AnomalyStation, station_id)
            if st is not None:
                # Only our own validation message is user-facing; internals stay in the log.
                message = (
                    str(e)
                    if isinstance(e, anomaly.TrainingError)
                    else "training failed — check that the station's images are readable"
                )
                st.status, st.error, st.updated = "failed", message, now()
                db.commit()
            raise


HANDLERS = {"anomaly_train": run_anomaly_train}
