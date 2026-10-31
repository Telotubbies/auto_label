"""Train, models, test inference, auto-label, and the API-key hosted inference/upload API."""
import base64
import random
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import CREDIT_COST
from ..db import get_db
from ..deps import Ctx, audit, charge, project_ctx
from ..ratelimit import client_ip, limit
from ..models import ApiKey, Job, LabelClass, Project, TrainedModel, Version, Workspace, now
from ..security import api_key_hash, sign_path
from ..services import imaging, ml, safefetch
from .projects import job_out

router = APIRouter(tags=["training"])
P = "/api/ws/{ws}/projects/{project}"
ARCHS = {"n": "Nano — fastest", "s": "Small", "m": "Medium — balanced", "l": "Large", "x": "X-Large — most accurate"}


def model_out(m: TrainedModel) -> dict:
    return {"id": m.id, "name": m.name, "arch": m.arch, "task": m.task, "status": m.status, "metrics": m.metrics,
            "history": m.history, "classes": m.classes, "versionId": m.version_id, "jobId": m.job_id,
            "created": m.created, "weightsUrl": sign_path(m.weights) if m.weights else None}


@router.get(P + "/models")
def models(c: Ctx = Depends(project_ctx)):
    rows = c.db.scalars(select(TrainedModel).where(TrainedModel.project_id == c.project.id)
                        .order_by(TrainedModel.created.desc())).all()
    out = []
    for m in rows:
        d = model_out(m)
        v = c.db.get(Version, m.version_id)
        d["version"] = v.number if v else None
        j = c.db.get(Job, m.job_id) if m.job_id else None
        d["job"] = job_out(j) if j else None
        out.append(d)
    return out


@router.get(P + "/train/options")
def train_options(c: Ctx = Depends(project_ctx)):
    if c.project.type not in ml.TASK:
        return {"supported": False, "reason": "training is available for detection, segmentation and classification projects"}
    task = ml.TASK[c.project.type]
    return {"supported": True, "task": task,
            "sizes": [{"id": k, "label": v, "weights": ml.base_weights(task, k).split("/")[-1].split("\\")[-1]} for k, v in ARCHS.items()]}


class TrainIn(BaseModel):
    version_id: str
    name: str = ""
    size: str = "n"
    epochs: int = 30
    imgsz: int = 640
    batch: int = 8


@router.post(P + "/train")
def train(body: TrainIn, c: Ctx = Depends(project_ctx)):
    c.need("admin")
    if c.project.type not in ml.TASK:
        raise HTTPException(400, "this project type can't be trained")
    v = c.db.get(Version, body.version_id)
    if not v or v.project_id != c.project.id or v.status != "ready":
        raise HTTPException(400, "pick a generated version to train on")
    if body.size not in ARCHS or not (1 <= body.epochs <= 500):
        raise HTTPException(400, "bad training options")
    charge(c.db, c.ws, CREDIT_COST["train"])
    task = ml.TASK[c.project.type]
    m = TrainedModel(workspace_id=c.ws.id, project_id=c.project.id, version_id=v.id, task=task,
                     name=body.name.strip() or f"{c.project.slug}/{v.number}-{body.size}",
                     arch=f"yolo-{body.size}{'' if task == 'detect' else '-' + task[:3]}",
                     status="queued", classes=v.stats.get("class_names", []))
    c.db.add(m); c.db.flush()
    j = Job(workspace_id=c.ws.id, project_id=c.project.id, kind="train", created_by=c.user.id,
            params={"model_id": m.id, "version_id": v.id,
                    "options": {"size": body.size, "epochs": body.epochs, "imgsz": body.imgsz, "batch": body.batch}})
    c.db.add(j); c.db.flush()
    m.job_id = j.id
    audit(c.db, c.ws.id, c.user.id, "train.start", m.name, epochs=body.epochs, size=body.size)
    c.db.commit()
    return model_out(m)


def _model(c: Ctx, mid: str) -> TrainedModel:
    m = c.db.get(TrainedModel, mid)
    if not m or m.project_id != c.project.id:
        raise HTTPException(404, "model not found")
    return m


@router.get(P + "/models/{mid}")
def get_model(mid: str, c: Ctx = Depends(project_ctx)):
    return model_out(_model(c, mid))


@router.delete(P + "/models/{mid}")
def delete_model(mid: str, c: Ctx = Depends(project_ctx)):
    c.need("admin")
    m = _model(c, mid)
    audit(c.db, c.ws.id, c.user.id, "model.delete", m.name)
    c.db.delete(m); c.db.commit()
    return {"ok": True}


@router.post(P + "/models/{mid}/predict")
async def test_predict(mid: str, file: UploadFile = File(...), confidence: float = Form(0.4),
                       overlap: float = Form(0.5), c: Ctx = Depends(project_ctx)):
    m = _model(c, mid)
    if m.status != "ready":
        raise HTTPException(409, "model is not ready")
    charge(c.db, c.ws, CREDIT_COST["infer"]); c.db.commit()
    im = imaging.open_image(await file.read())
    return ml.predict(m.weights, im, confidence, overlap)


class AutoLabelIn(BaseModel):
    method: str = "model"           # model | sam
    model_id: str | None = None
    batch_id: str | None = None
    image_ids: list[str] = []
    class_ids: list[str] = []
    confidence: float = 0.4
    only_unannotated: bool = True
    send_to_review: bool = True


@router.post(P + "/autolabel")
def autolabel(body: AutoLabelIn, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    if body.method == "model" and not body.model_id:
        raise HTTPException(400, "choose a trained model")
    if body.method == "sam" and c.project.type == "classification":
        raise HTTPException(400, "SAM auto-label needs a detection or segmentation project")
    if body.method == "sam" and not c.db.scalar(select(LabelClass.id).where(LabelClass.project_id == c.project.id)):
        raise HTTPException(400, "add classes first — SAM uses class names as text prompts")
    charge(c.db, c.ws, CREDIT_COST["autolabel_image"] * max(1, len(body.image_ids) or 100))
    j = Job(workspace_id=c.ws.id, project_id=c.project.id, kind="autolabel", params=body.model_dump(), created_by=c.user.id)
    c.db.add(j)
    audit(c.db, c.ws.id, c.user.id, "autolabel.start", c.project.name, method=body.method)
    c.db.commit()
    return job_out(j)


# --- hosted API (api_key auth, Roboflow-style) ------------------------------------------------

def key_ws(db: Session, api_key: str | None, request: Request | None = None) -> Workspace:
    if request is not None:
        limit(f"apikey:{client_ip(request)}", 600, 60)      # caps key guessing and abusive clients
    if not api_key:
        raise HTTPException(401, "api_key required")
    k = db.scalar(select(ApiKey).where(ApiKey.hash == api_key_hash(api_key)))
    if not k:
        raise HTTPException(401, "invalid api_key")
    k.last_used = time.time()
    return db.get(Workspace, k.workspace_id)


async def _image_from_request(request: Request, file: UploadFile | None, image: str | None):
    if file is not None:
        return await file.read()
    if image and image.startswith(("http://", "https://")):
        try:
            return safefetch.fetch(image)
        except safefetch.BlockedURL as e:
            raise HTTPException(400, str(e))
        except OSError:
            raise HTTPException(400, "could not download the image URL")
    if image:
        try:
            return base64.b64decode(image.split(",")[-1], validate=True)
        except ValueError:
            raise HTTPException(400, "image is not a URL or valid base64")
    body = await request.body()
    if len(body) > 30 * 1024 * 1024:
        raise HTTPException(413, "image too large")
    if body:
        try:
            return base64.b64decode(body)
        except Exception:
            return body
    raise HTTPException(400, "send an image as multipart `file`, `image` (url/base64) or a base64 body")


@router.post("/api/v1/models/{mid}/predict")
async def hosted_predict(mid: str, request: Request, api_key: str | None = Query(None), confidence: float = 0.4,
                         overlap: float = 0.5, image: str | None = None, file: UploadFile | None = File(None),
                         db: Session = Depends(get_db)):
    ws = key_ws(db, api_key or request.headers.get("x-api-key"), request)
    m = db.get(TrainedModel, mid)
    if not m or m.workspace_id != ws.id or m.status != "ready":
        raise HTTPException(404, "model not found")
    charge(db, ws, CREDIT_COST["infer"])
    data = await _image_from_request(request, file, image)
    im = imaging.open_image(data)
    out = ml.predict(m.weights, im, confidence, overlap)
    audit(db, ws.id, None, "infer.hosted", m.name, n=len(out["predictions"]))
    _active_learning(db, ws, db.get(Project, m.project_id), data, out)
    db.commit()
    return out


def _active_learning(db: Session, ws: Workspace, p: Project, data: bytes, pred: dict):
    """Project setting active_learning = {enabled, below: conf threshold, sample_pct}."""
    cfg = (p.settings or {}).get("active_learning") or {}
    if not cfg.get("enabled"):
        return
    confs = [x.get("confidence", 1) for x in pred["predictions"]]
    low = any(cf < float(cfg.get("below", 0.5)) for cf in confs) or (not confs and cfg.get("include_empty", True))
    if low or random.random() * 100 < float(cfg.get("sample_pct", 0)):
        from ..deps import Ctx as _Ctx
        from .images import ingest
        try:
            ingest(db, _Ctx(user=None, ws=ws, role="admin", db=db, project=p), [(f"al_{int(time.time()*1000)}.jpg", data)],
                   "Active Learning", "train", ["active-learning"], source="active-learning", to_dataset=False)
        except HTTPException:
            pass   # plan limit / duplicate: inference result still returned


@router.post("/api/v1/{ws_slug}/{project}/upload")
async def hosted_upload(ws_slug: str, project: str, request: Request, api_key: str | None = Query(None),
                        split: str = "auto", batch: str = "API Upload", tag: str = "", name: str = "upload.jpg",
                        image: str | None = None, file: UploadFile | None = File(None), db: Session = Depends(get_db)):
    ws = key_ws(db, api_key or request.headers.get("x-api-key"), request)
    if ws.slug != ws_slug:
        raise HTTPException(403, "api_key belongs to another workspace")
    p = db.scalar(select(Project).where(Project.workspace_id == ws.id, Project.slug == project, Project.deleted_at.is_(None)))
    if not p:
        raise HTTPException(404, "project not found")
    data = await _image_from_request(request, file, image)
    from .images import ingest
    res = ingest(db, Ctx(user=None, ws=ws, role="admin", db=db, project=p), [(file.filename if file else name, data)],
                 batch, split, [tag] if tag else [], source="api", to_dataset=False)
    return {"success": res["uploaded"] == 1, "duplicate": res["duplicates"] == 1,
            "id": res["images"][0]["id"] if res["images"] else None}
