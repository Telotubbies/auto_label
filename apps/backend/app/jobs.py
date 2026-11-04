"""Job-queue cancellation seam shared by worker handlers."""
from sqlalchemy import select

from .adapters.base import Cancelled
from .db import SessionLocal
from .models import Job


def is_cancelled(job_id: str) -> bool:
    with SessionLocal() as db:
        return db.scalar(select(Job.status).where(Job.id == job_id)) == "cancelling"


def check(job) -> None:
    """Raise ``Cancelled`` when the user asked this job to stop."""
    if is_cancelled(getattr(job, "id", "")):
        raise Cancelled("job cancelled")
