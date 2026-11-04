"""Dataset and Insights scans: the ``health``, ``insights_images``, ``insights_leakage`` and
``insights_embedding`` kinds.

Handlers resolve their runner dependencies through ``app.worker`` (``w.scheduler``) so the process
that swaps one of them at runtime keeps working.
"""
from ..db import SessionLocal
from ..models import Job, Project
from ..services import health, insights_embedding, insights_jobs


def run_health(job: Job):
    """Leakage + missing-box scan (needs the model): cached on the job row for the analytics page."""
    from .. import jobs
    jobs.check(job)
    with SessionLocal() as db:
        p = db.get(Project, job.project_id)
        return health.scan_health(db, p, should_stop=lambda: jobs.is_cancelled(job.id))


def run_insights_images(job: Job):
    from .. import jobs
    jobs.check(job)
    with SessionLocal() as db:
        return insights_jobs.scan_images(db, db.get(Project, job.project_id),
                                         should_stop=lambda: jobs.is_cancelled(job.id))


def run_insights_leakage(job: Job):
    from .. import jobs
    jobs.check(job)
    with SessionLocal() as db:
        version = (job.params or {}).get("version") or None
        return insights_jobs.scan_leakage(db, db.get(Project, job.project_id), version,
                                          should_stop=lambda: jobs.is_cancelled(job.id))


def run_insights_embedding(job: Job):
    from .. import jobs, worker as w
    jobs.check(job)
    with SessionLocal() as db:
        project = db.get(Project, job.project_id)

        def should_stop() -> bool:
            return jobs.is_cancelled(job.id)

        needs_card = insights_embedding.clip_available()     # false: CV features never touch the GPU
        try:
            if needs_card:
                with w.scheduler.exclusive("insights embedding"):
                    return insights_jobs.scan_embedding(db, project, should_stop=should_stop)
            return insights_jobs.scan_embedding(db, project, should_stop=should_stop)
        finally:
            insights_embedding.release_clip()                # CLIP never outlives the scan


HANDLERS = {"health": run_health, "insights_images": run_insights_images,
            "insights_leakage": run_insights_leakage, "insights_embedding": run_insights_embedding}
