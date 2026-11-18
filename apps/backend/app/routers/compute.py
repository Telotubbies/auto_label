"""The Compute page: who is working, what is running and what waits, for one workspace.

Workers serve every workspace, so a workspace sees counts and hardware (GPU name, VRAM) but never a host
name or another workspace's job.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select

from ..deps import Ctx, ws_ctx
from ..gpu import scheduler
from ..models import Job, Project, TrainedModel, Worker, now
from ..services import heartbeat
from ..services.compute_state import GPU_KINDS, eta_seconds, headline

router = APIRouter(prefix="/api/ws/{ws}", tags=["compute"])
MAX_JOBS = 12


def _job_row(db, job: Job, project_names: dict[str, str], t: float) -> dict:
    model = db.get(TrainedModel, job.params.get("model_id")) if job.params.get("model_id") else None
    epochs = (job.params.get("options") or {}).get("epochs")
    return {"id": job.id, "kind": job.kind, "status": job.status, "progress": round(job.progress or 0, 1),
            "project": project_names.get(job.project_id or "", ""), "name": model.name if model else "",
            "epochs": epochs, "started": job.started, "created": job.created,
            "eta_s": eta_seconds(job.progress, job.started, t) if job.status == "running" else None}


@router.get("/compute")
def compute(c: Ctx = Depends(ws_ctx)):
    db, t = c.db, now()
    live = db.scalars(select(Job).where(Job.workspace_id == c.ws.id, Job.kind.in_(GPU_KINDS),
                                        Job.status.in_(("queued", "running", "cancelling")))
                      .order_by(Job.status.desc(), Job.created)).all()
    names = dict(db.execute(select(Project.id, Project.name).where(Project.workspace_id == c.ws.id)).all())
    jobs = [_job_row(db, j, names, t) for j in live][:MAX_JOBS]
    workers = heartbeat.workers(db)
    online = [w for w in workers if w["online"]]
    gpus = []
    for w in online:
        row = db.get(Worker, w["id"])
        for g in ((row.inventory or {}).get("gpus") or []) if row else []:
            gpus.append({"name": g.get("name", "GPU"), "vram_mb": g.get("vram_mb")})
    state = scheduler.state()
    waiting = [j for j in live if j.status == "queued"]
    return {**headline(workers_online=len(online), jobs=jobs, api_holder=state["holder"]),
            "workers": {"online": len(online), "total": len(workers), "busy": sum(1 for w in online if w["current_job"])},
            "gpus": gpus,
            "api_gpu": {"holder": state["holder"], "used_mb": state["used_mb"], "budget_mb": state["budget_mb"],
                        "models": state["leases"]},
            "queue": {"running": len(live) - len(waiting), "queued": len(waiting),
                      "oldest_wait_s": round(t - min(j.created for j in waiting), 1) if waiting else None},
            "jobs": jobs}
