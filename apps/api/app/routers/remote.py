"""HTTP protocol for remote GPU workers (`pip install labeldesk-worker`).

Workers only make outbound HTTPS calls, so a home GPU box, Kaggle or Colab can
serve a cloud deployment. Auth: header `X-Worker-Token: $LD_WORKER_TOKEN`.
"""
import hmac
import json
import shutil

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config import DATA_DIR, WORKER_TOKEN, REMOTE_JOB_KINDS
from ..db import get_db
from ..models import Image, Job, LabelClass, Project, TrainedModel, Version, now, set_annotations
from ..security import sign_path
from ..services import exporters, ml, versioning

router = APIRouter(prefix="/api/worker", tags=["worker"])


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
        classes = db.scalars(select(LabelClass).where(LabelClass.project_id == j.project_id).order_by(LabelClass.created)).all()
        q = select(Image).where(Image.project_id == j.project_id, Image.deleted_at.is_(None))
        if P.get("image_ids"):
            q = q.where(Image.id.in_(P["image_ids"]))
        if P.get("batch_id"):
            q = q.where(Image.batch_id == P["batch_id"])
        if P.get("only_unannotated", True):
            q = q.where(Image.n_annotations == 0)
        m = db.get(TrainedModel, P["model_id"]) if P.get("method") == "model" else None
        wanted = [c for c in classes if not P.get("class_ids") or c.id in P["class_ids"]]
        return {"method": P.get("method"), "confidence": P.get("confidence", 0.4),
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
                j.status, j.error, j.finished = "failed", f"{type(e).__name__}: {e}", now()
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
        set_annotations(db, img, (img.annotations or []) + body.annotations)
        if img.status == "unassigned":
            img.status = "review" if j.params.get("send_to_review", True) else "annotating"
        img.updated = now()
    db.commit()
    return {"ok": True}


@router.post("/jobs/{jid}/complete", dependencies=[Depends(worker_auth)])
async def complete(jid: str, result: str = Form("{}"), weights: UploadFile | None = File(None),
                   db: Session = Depends(get_db)):
    j = db.get(Job, jid)
    if not j:
        raise HTTPException(404, "job not found")
    res = json.loads(result or "{}")
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
        tm.metrics = ml.final_metrics(tm.history, tm.task)
        tm.status = "ready"
        res = {"model_id": tm.id, **tm.metrics}
    j.status = "cancelled" if j.status == "cancelling" else "done"
    j.progress, j.result, j.finished = 100.0, {**(j.result or {}), **res}, now()
    db.commit()
    return {"ok": True}


class FailIn(BaseModel):
    error: str


@router.post("/jobs/{jid}/fail", dependencies=[Depends(worker_auth)])
def fail(jid: str, body: FailIn, db: Session = Depends(get_db)):
    j = db.get(Job, jid)
    if not j:
        raise HTTPException(404, "job not found")
    j.status, j.error, j.finished = "failed", body.error[:4000], now()
    if j.kind == "train":
        tm = db.get(TrainedModel, j.params["model_id"])
        if tm:
            tm.status = "failed"
    db.commit()
    return {"ok": True}
