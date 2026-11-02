"""HTTP protocol for remote GPU workers (`pip install labeldesk-worker`).

Workers only make outbound HTTPS calls, so a home GPU box, Kaggle or Colab can
serve a cloud deployment. Auth: header `X-Worker-Token: $LD_WORKER_TOKEN`.
"""
import hmac
import json
import logging
import shutil

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..adapters import model_conf
from ..config import CREDIT_COST, DATA_DIR, WORKER_TOKEN, REMOTE_JOB_KINDS
from ..db import SessionLocal, get_db
from ..deps import charge
from ..errors import safe_error, safe_text
from ..gpu import scheduler
from ..models import Image, Job, LabelClass, Project, TrainedModel, Version, Workspace, now, set_annotations
from ..security import sign_path
from ..services import exporters, metering, ml, versioning
from ..services import finalize

router = APIRouter(prefix="/api/worker", tags=["worker"])
log = logging.getLogger("labeldesk.remote")

TERMINAL = ("done", "failed", "cancelled")     # a job that already reported its outcome to the worker


def worker_auth(x_worker_token: str = Header("")):
    if not WORKER_TOKEN or not hmac.compare_digest(x_worker_token, WORKER_TOKEN):
        raise HTTPException(401, "bad worker token")


class ClaimIn(BaseModel):
    name: str = "worker"
    kinds: list[str] = ["train", "autolabel"]


def _payload(db: Session, j: Job) -> dict:
    if j.kind == "train":
        tm = db.get(TrainedModel, j.params["model_id"])
        v = db.get(Version, tm.version_id)
        p = db.get(Project, tm.project_id)
        task = ml.TASK[p.type]
        fmt = "folder" if task == "classify" else "yolo"
        out = DATA_DIR / "exports" / v.id / fmt
        zp = out.with_suffix(".zip")
        if not zp.exists():
            exporters.export(fmt, versioning.version_dir(v), out)
            shutil.rmtree(out, ignore_errors=True)
        tm.status = "training"
        return {"model_id": tm.id, "task": task, "options": j.params.get("options", {}),
                "dataset_url": sign_path(zp.relative_to(DATA_DIR).as_posix(), ttl=24 * 3600)}
    if j.kind == "autolabel":
        P = j.params
        ref = P.get("model_ref") or ""
        mid = P.get("model_id") or (ref[len("trained:"):] if ref.startswith("trained:") else None)
        m = db.get(TrainedModel, mid) if mid else None
        if mid and (not m or not m.weights):
            raise HTTPException(400, "trained model has no weights")
        classes = db.scalars(select(LabelClass).where(LabelClass.project_id == j.project_id).order_by(LabelClass.created)).all()
        q = select(Image).where(Image.project_id == j.project_id, Image.deleted_at.is_(None))
        if P.get("image_ids"):
            q = q.where(Image.id.in_(P["image_ids"]))
        if P.get("batch_id"):
            q = q.where(Image.batch_id == P["batch_id"])
        if P.get("only_unannotated", True):
            q = q.where(Image.n_annotations == 0)
        wanted = [c for c in classes if not P.get("class_ids") or c.id in P["class_ids"]]
        conf = P.get("confidence")
        if conf is None:                     # no explicit threshold: the model's best-F1 confidence
            conf = model_conf(m) if m else None
        return {"method": "model" if m else "sam", "confidence": 0.4 if conf is None else float(conf),
                "project_type": db.get(Project, j.project_id).type,
                "weights_url": sign_path(m.weights, ttl=24 * 3600) if m else None,
                "classes": {c.name: c.id for c in classes}, "prompts": [{"id": c.id, "name": c.name} for c in wanted],
                "images": [{"id": i.id, "url": sign_path(i.path, ttl=24 * 3600)} for i in db.scalars(q)]}
    raise HTTPException(400, f"job kind {j.kind} is not remote-capable")


@router.post("/claim", dependencies=[Depends(worker_auth)])
def claim(body: ClaimIn, db: Session = Depends(get_db)):
    kinds = [k for k in body.kinds if k in REMOTE_JOB_KINDS]
    for jid in db.scalars(select(Job.id).where(Job.status == "queued", Job.kind.in_(kinds)).order_by(Job.created).limit(5)):
        if db.execute(update(Job).where(Job.id == jid, Job.status == "queued")
                      .values(status="running", started=now(), result={"worker": body.name})).rowcount:
            db.commit()
            j = db.get(Job, jid)
            try:
                payload = _payload(db, j)
            except Exception as e:
                j.status, j.error, j.finished = "failed", safe_error(e, j.kind), now()
                db.commit(); continue
            db.commit()
            return {"job": {"id": j.id, "kind": j.kind, "payload": payload}}
    return {"job": None}


class ProgressIn(BaseModel):
    progress: float
    history: list[dict] | None = None


@router.post("/jobs/{jid}/progress", dependencies=[Depends(worker_auth)])
def progress(jid: str, body: ProgressIn, db: Session = Depends(get_db)):
    j = db.get(Job, jid)
    if not j:
        raise HTTPException(404, "job not found")
    j.progress = round(body.progress, 1)
    if body.history is not None and j.kind == "train":
        tm = db.get(TrainedModel, j.params["model_id"])
        tm.history = body.history
    db.commit()
    return {"cancel": j.status == "cancelling"}


class AnnIn(BaseModel):
    image_id: str
    annotations: list[dict]
    send_to_review: bool = True


@router.post("/jobs/{jid}/annotations", dependencies=[Depends(worker_auth)])
def annotations(jid: str, body: AnnIn, db: Session = Depends(get_db)):
    j = db.get(Job, jid)
    img = db.get(Image, body.image_id)
    if not j or not img or img.project_id != j.project_id:
        raise HTTPException(404, "not found")
    if body.annotations:
        ids = {a.get("classId") for a in body.annotations if isinstance(a, dict) and a.get("classId")}
        known = set(db.scalars(select(LabelClass.id).where(LabelClass.project_id == j.project_id,
                                                          LabelClass.id.in_(ids)))) if ids else set()
        if ids - known:
            raise HTTPException(400, "annotation class does not belong to this project")
        P = j.params
        src = P.get("model_ref") or (f"trained:{P['model_id']}" if P.get("model_id") else "sam3")
        set_annotations(db, img, (img.annotations or []) + [{**a, "source": a.get("source") or src}
                                                            for a in body.annotations])
        if img.status == "unassigned":
            img.status = "review" if j.params.get("send_to_review", True) else "annotating"
        img.updated = now()
        # remote runs charge per labeled image as the work lands (the embedded worker charges at the end)
        charge(db, db.get(Workspace, j.workspace_id), CREDIT_COST["autolabel_image"])
    # every processed image called the model, even when it produced no annotation
    mid = j.params.get("model_id")
    metering.record(db, j.workspace_id, "ai_calls", 1, project_id=j.project_id,
                    model_id=mid, kind="autolabel")
    db.commit()
    return {"ok": True}


def _keep_model_id(db: Session, j: Job) -> None:
    """Keep the trained model id on a job that already reached a terminal status."""
    if j.kind != "train":
        return
    model_id = (j.params or {}).get("model_id")
    if not model_id:
        return
    tm = db.get(TrainedModel, model_id)
    if tm and (j.result or {}).get("model_id") != tm.id:
        j.result = {**(j.result or {}), "model_id": tm.id}
        db.commit()


def _finalize_remote_model(model_id: str) -> None:
    """Evaluate and announce a remote model after the complete response.

    Runs in Starlette's threadpool with a fresh session (the request session is closed by then)
    and a training lease, because ``resolve()`` may load the model onto the card. A broken lease
    or eval records ``eval_error``; the ready weights were committed by the request handler.
    """
    with SessionLocal() as db:
        tm = db.get(TrainedModel, model_id)
        if tm is None:
            return
        try:
            with scheduler.training_scope():
                finalize.evaluate_and_announce(db, tm)
        except Exception as e:
            log.exception("remote finalisation failed for model %s", model_id)
            tm.metrics = {**ml.final_metrics(tm.history, tm.task), "eval_error": safe_error(e, "train")}
        db.commit()


@router.post("/jobs/{jid}/complete", dependencies=[Depends(worker_auth)])
async def complete(jid: str, background_tasks: BackgroundTasks, result: str = Form("{}"),
                   weights: UploadFile | None = File(None), db: Session = Depends(get_db)):
    j = db.get(Job, jid)
    if not j:
        raise HTTPException(404, "job not found")
    if j.status in TERMINAL:        # a retried complete must not re-meter, re-evaluate or re-announce
        _keep_model_id(db, j)
        return {"ok": True}
    res = json.loads(result or "{}")
    # Every kind that reaches the remote worker held the GPU; meter it before any kind-specific work.
    elapsed = max(0.0, now() - (j.started or now()))
    metering.record(db, j.workspace_id, "gpu_seconds", round(elapsed, 2),
                    project_id=j.project_id, job_id=j.id)
    if j.kind == "train":
        tm = db.get(TrainedModel, j.params["model_id"])
        if not weights:
            raise HTTPException(400, "weights file required")
        dst = DATA_DIR / "models" / tm.id / "best.pt"
        dst.parent.mkdir(parents=True, exist_ok=True)
        with open(dst, "wb") as f:
            shutil.copyfileobj(weights.file, f)
        tm.weights = dst.relative_to(DATA_DIR).as_posix()
        tm.history = res.get("history", tm.history)
        tm.status = "ready"         # resolve() only accepts ready models
        res = {"model_id": tm.id}
        # Eval resolves (loads) the model and runs pycocotools on the test split: never inline here,
        # where it would stall the single uvicorn loop and skip the GPU lease.
        background_tasks.add_task(_finalize_remote_model, tm.id)
    j.status = "cancelled" if j.status == "cancelling" else "done"
    j.progress, j.result, j.finished = 100.0, {**(j.result or {}), **res}, now()
    finalize.job_done(db, j, j.status)
    db.commit()
    return {"ok": True}


class FailIn(BaseModel):
    error: str


@router.post("/jobs/{jid}/fail", dependencies=[Depends(worker_auth)])
def fail(jid: str, body: FailIn, db: Session = Depends(get_db)):
    j = db.get(Job, jid)
    if not j:
        raise HTTPException(404, "job not found")
    if j.status in TERMINAL:        # complete already landed: a late timeout must not undo it
        _keep_model_id(db, j)
        return {"ok": True}
    j.status, j.error, j.finished = "failed", safe_text(body.error, j.kind), now()
    if j.kind == "train":
        tm = db.get(TrainedModel, j.params["model_id"])
        if tm:
            tm.status = "failed"
    elapsed = max(0.0, now() - (j.started or now()))
    metering.record(db, j.workspace_id, "gpu_seconds", round(elapsed, 2),
                    project_id=j.project_id, job_id=j.id)       # a failed run still held the card
    finalize.job_done(db, j, "failed", j.error)
    db.commit()
    return {"ok": True}
