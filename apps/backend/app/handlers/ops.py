"""Scheduled and maintenance jobs: ``connector_sync``, ``retention``, ``drift``, ``active_learning``.

Each body lives in the service that owns it; this module only names the kind the queue can claim.
"""
from ..models import Job
from ..services import active_learning, connectors, drift


def run_retention(job: Job):
    """PDPA cleanup. Imported lazily so the worker starts even on a build without the privacy extra."""
    from ..services.retention import run_retention as cleanup
    return cleanup(job)


HANDLERS = {"connector_sync": connectors.sync_job, "retention": run_retention,
            "drift": drift.run_job, "active_learning": active_learning.run_job}
