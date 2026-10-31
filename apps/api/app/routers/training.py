"""Train, models, test inference, auto-label, and the API-key hosted inference/upload API."""
import base64
import random
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..adapters import ADAPTERS, resolve
from ..config import CREDIT_COST, LOCAL_JOB_KINDS
from ..db import get_db
from ..deps import Ctx, audit, charge, project_ctx
from ..ratelimit import client_ip, limit
from ..models import ApiKey, Job, LabelClass, Project, TrainedModel, Version, Workspace, now
from ..security import api_key_hash, sign_path
from ..services import imaging, ml, safefetch
from .projects import job_out

router = APIRouter(tags=["training"])
P = "/api/ws/{ws}/projects/{project}"
LICENSE = "AGPL-3.0"       # every trainable family runs on the ultralytics adapter
_SIZES = {"n": "Nano — fastest", "s": "Small", "m": "Medium — balanced", "l": "Large", "x": "X-Large — most accurate"}


def _yolo(prefix: str, label: str, sizes: str) -> list[dict]:
    return [{"id": f"{prefix}{s}", "label": f"{label} {_SIZES[s]}"} for s in sizes]


# UI display groups over the single `ultralytics` adapter. detect_only families can't train seg/cls projects.
FAMILIES = [
    {"family": "yolo", "label": "YOLO", "detect_only": False,
     "variants": _yolo("yolo26", "YOLO26", "nsmlx") + _yolo("yolo11", "YOLO11", "nsmlx") + _yolo("yolov8", "YOLOv8", "nsmlx")},
    {"family": "rtdetr", "label": "RT-DETR", "detect_only": True,
     "variants": [{"id": "rtdetr-l", "label": "RT-DETR Large"}, {"id": "rtdetr-x", "label": "RT-DETR X-Large"}]},
    {"family": "yolo-world", "label": "YOLO-World", "detect_only": True,
     "variants": [{"id": "yolov8s-worldv2", "label": "YOLO-World v2 Small"}, {"id": "yolov8m-worldv2", "label": "YOLO-World v2 Medium"}]},
]
_BASE_VARIANTS = {v["id"] for f in FAMILIES for v in f["variants"]}
_YOLO26 = {f"yolo26{s}" for s in "nsmlx"}
_SUFFIX = {"detect": "", "segment": "-seg", "classify": "-cls"}
_REMOTE_UNSUPPORTED = "not supported on remote GPU workers yet"


def _family_of(variant: str) -> str:
    return next(f["family"] for f in FAMILIES if any(v["id"] == variant for v in f["variants"]))


def _base_variant(variant: str) -> str:
    for suf in ("-seg", "-cls"):
        if variant.endswith(suf):
            return variant[:-len(suf)]
    return variant


def model_out(m: TrainedModel) -> dict:
    return {"id": m.id, "name": m.name, "arch": m.arch, "task": m.task, "status": m.status, "metrics": m.metrics,
            "history": m.history, "classes": m.classes, "versionId": m.version_id, "jobId": m.job_id,
            "family": m.family, "variant": m.variant, "license": m.license,
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
    av = ADAPTERS["ultralytics"].probe() if "ultralytics" in ADAPTERS else None
    suffix = {"detect": "", "segment": "-seg", "classify": "-cls"}[task]
    fams = []
    for f in FAMILIES:
        ok, reason = (av.ok, av.reason) if av else (False, "ultralytics adapter not installed")
        if ok and f["detect_only"] and task != "detect":
            ok, reason = False, "detection projects only"
        sfx = "" if f["detect_only"] else suffix
        fams.append({"family": f["family"], "label": f["label"], "license": LICENSE, "available": ok, "reason": reason,
                     "variants": [{"id": v["id"], "label": v["label"], "weights": v["id"] + sfx + ".pt"} for v in f["variants"]]})
    return {"supported": True, "task": task, "families": fams}


class TrainIn(BaseModel):
    version_id: str
    name: str = ""
    size: str | None = None          # legacy: n|s|m|l|x -> variant yolo26<size>
    family: str = "ultralytics"
    variant: str = "yolo26n"
    max_minutes: int | None = None
    resume_from: str | None = None   # trained model id to continue from
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
    variant = f"yolo26{body.size}" if body.size else body.variant
    base = _base_variant(variant)
    if body.family != "ultralytics" or base not in _BASE_VARIANTS or not (1 <= body.epochs <= 500) \
            or (body.max_minutes is not None and body.max_minutes < 1):
        raise HTTPException(400, "bad training options")
    task = ml.TASK[c.project.type]
    fam = next(f for f in FAMILIES if f["family"] == _family_of(base))
    if fam["detect_only"] and task != "detect":
        raise HTTPException(400, f"{fam['label']} trains detection projects only")
    if not fam["detect_only"]:
        variant = base + _SUFFIX[task]
    if "train" not in LOCAL_JOB_KINDS:      # remote pip worker: v1 cli only understands YOLO + size
        if variant not in {v + _SUFFIX[task] for v in _YOLO26} \
                or body.max_minutes is not None or body.resume_from:
            raise HTTPException(400, _REMOTE_UNSUPPORTED)
    resume = None
    if body.resume_from:
        resume = c.db.get(TrainedModel, body.resume_from)
        if not resume or resume.workspace_id != c.ws.id or resume.project_id != c.project.id \
                or resume.status != "ready" or resume.task != task:
            raise HTTPException(400, "resume_from must be a ready model of the same task in this project")
        if resume.variant != variant:
            raise HTTPException(400, f"resume_from is a {resume.variant} model; pick the same variant")
    charge(c.db, c.ws, CREDIT_COST["train"])
    m = TrainedModel(workspace_id=c.ws.id, project_id=c.project.id, version_id=v.id, task=task,
                     name=body.name.strip() or f"{c.project.slug}/{v.number}-{variant}",
                     arch=variant, family="ultralytics", variant=variant, license=LICENSE,
                     status="queued", classes=v.stats.get("class_names", []))
    c.db.add(m); c.db.flush()
    options = {"family": "ultralytics", "variant": variant, "epochs": body.epochs, "imgsz": body.imgsz,
               "batch": body.batch, "max_minutes": body.max_minutes, "resume_from": body.resume_from}
    if base in _YOLO26:
        options["size"] = base[len("yolo26"):]      # v1 remote worker still reads size
    j = Job(workspace_id=c.ws.id, project_id=c.project.id, kind="train", created_by=c.user.id,
            params={"model_id": m.id, "version_id": v.id, "options": options})
    c.db.add(j); c.db.flush()
    m.job_id = j.id
    audit(c.db, c.ws.id, c.user.id, "train.start", m.name, epochs=body.epochs, variant=variant)
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
    return resolve(f"trained:{m.id}", c.db).predict(im, conf=confidence, iou=overlap, classes=m.classes)


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
    out = resolve(f"trained:{m.id}", db).predict(im, conf=confidence, iou=overlap, classes=m.classes)
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
