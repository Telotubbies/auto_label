"""Engine job rows: one queue, one record, one payload for the worker (T-1006).

The API never runs an installer. It writes a queued ``engine_apply`` row and the audit that says
who asked, and only a worker that advertises the kind claims it. A host runs one engine job at a
time. ``payload`` is the one place a job's parameters become a worker instruction, so
``routers/remote.py`` gains a dispatch line rather than a branch per job kind.
"""
from sqlalchemy import select

from .. import deps
from ..models import Job

ENGINE_KINDS = ("engine_apply", "model_pull")     # one at a time, and both install on a host


def running_for_host(db, host: str):
    """The queued or running engine job for ``host``, if any; another host never blocks it."""
    rows = db.scalars(select(Job).where(Job.kind.in_(ENGINE_KINDS),
                                        Job.status.in_(("queued", "running")))
                      .order_by(Job.created)).all()
    return next((job for job in rows if (job.params or {}).get("host") == host), None)


def enqueue_engine(db, c, host: str, action: str, engines: list[dict], plan_id: str) -> Job:
    """Queue one confirmed job and record who asked, for what and which job it became."""
    job = Job(workspace_id=c.ws.id, project_id=None, kind="engine_apply", status="queued",
              params={"host": host, "action": action, "engines": engines, "plan_id": plan_id},
              created_by=c.user.id)
    db.add(job)
    db.flush()                                   # the audit names the id this row just got
    deps.audit(db, c.ws.id, c.user.id, f"inference.engine_{action}", host,
               engines=[engine["id"] for engine in engines], plan_id=plan_id, job_id=job.id)
    db.commit()
    return job


def payload(db, job: Job) -> dict:
    """What a worker needs: catalogue ids and argv, no workspace data, no URL and no token."""
    params = job.params or {}
    return {"host": params.get("host", ""), "action": params.get("action", "install"),
            "engines": params.get("engines") or [], "plan_id": params.get("plan_id", "")}
