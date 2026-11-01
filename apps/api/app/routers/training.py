"""Train, models, test inference, auto-label, and the API-key hosted inference/upload API."""
import base64
import random
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..adapters import ADAPTERS, resolve
from ..adapters.refine import label_image, sam_available
from ..config import CREDIT_COST, LOCAL_JOB_KINDS
from ..db import get_db
from ..deps import Ctx, audit, charge, project_ctx
from ..ratelimit import client_ip, limit
from ..models import ApiKey, Image, Job, LabelClass, Project, TrainedModel, Version, Workspace, now
from ..security import api_key_hash, sign_path
from ..services import imaging, ml, safefetch
from .projects import job_out

router = APIRouter(tags=["training"])
P = "/api/ws/{ws}/projects/{project}"
LICENSE = "AGPL-3.0"       # the ultralytics families
_SIZES = {"n": "Nano — fastest", "s": "Small", "m": "Medium — balanced", "l": "Large", "x": "X-Large — most accurate"}


def _yolo(prefix: str, label: str, sizes: str) -> list[dict]:
    return [{"id": f"{prefix}{s}", "label": f"{label} {_SIZES[s]}"} for s in sizes]


def _hf(variants: list[tuple[str, str]]) -> list[dict]:
    """D-FINE / RT-DETRv2 weights are the HuggingFace repo id itself."""
    return [{"id": v, "label": label, "weights": v} for v, label in variants]


# UI display groups over the registered adapters. detect_only families can't train seg/cls projects.
FAMILIES = [
    {"family": "yolo", "label": "YOLO", "adapter": "ultralytics", "license": LICENSE, "detect_only": False,
     "variants": _yolo("yolo26", "YOLO26", "nsmlx") + _yolo("yolo11", "YOLO11", "nsmlx") + _yolo("yolov8", "YOLOv8", "nsmlx")},
    {"family": "rtdetr", "label": "RT-DETR", "adapter": "ultralytics", "license": LICENSE, "detect_only": True,
     "variants": [{"id": "rtdetr-l", "label": "RT-DETR Large"}, {"id": "rtdetr-x", "label": "RT-DETR X-Large"}]},
    {"family": "yolo-world", "label": "YOLO-World", "adapter": "ultralytics", "license": LICENSE, "detect_only": True,
     "variants": [{"id": "yolov8s-worldv2", "label": "YOLO-World v2 Small"}, {"id": "yolov8m-worldv2", "label": "YOLO-World v2 Medium"}]},
    {"family": "rf-detr", "label": "RF-DETR", "adapter": "rfdetr", "license": "Apache-2.0", "detect_only": True,
     "variants": [{"id": "nano", "label": "RF-DETR Nano", "weights": "rf-detr-nano.pth"},
                  {"id": "small", "label": "RF-DETR Small", "weights": "rf-detr-small.pth"},
                  {"id": "medium", "label": "RF-DETR Medium", "weights": "rf-detr-medium.pth"},
                  {"id": "large", "label": "RF-DETR Large", "weights": "rf-detr-large.pth"}]},
    {"family": "d-fine", "label": "D-FINE", "adapter": "hf", "license": "Apache-2.0", "detect_only": True,
     "variants": _hf([("ustc-community/dfine-nano-coco", "D-FINE Nano"),
                      ("ustc-community/dfine-small-coco", "D-FINE Small"),
                      ("ustc-community/dfine-medium-coco", "D-FINE Medium"),
                      ("ustc-community/dfine-large-coco", "D-FINE Large")])},
    {"family": "rt-detr-v2", "label": "RT-DETRv2", "adapter": "hf", "license": "Apache-2.0", "detect_only": True,
     "variants": _hf([("PekingU/rtdetr_v2_r18vd", "RT-DETRv2 R18"),
                      ("PekingU/rtdetr_v2_r34vd", "RT-DETRv2 R34"),
                      ("PekingU/rtdetr_v2_r50vd", "RT-DETRv2 R50"),
                      ("PekingU/rtdetr_v2_r101vd", "RT-DETRv2 R101")])},
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


def _lean_metrics(metrics: dict | None) -> dict:
    """The list endpoint drops per-image detections; /models/{id} carries them for the UI slider."""
    out = dict(metrics or {})
    ev = out.get("eval")
    if isinstance(ev, dict) and "detections" in ev:
        out["eval"] = {k: v for k, v in ev.items() if k != "detections"}
    return out


def model_out(m: TrainedModel) -> dict:
    return {"id": m.id, "name": m.name, "arch": m.arch, "task": m.task, "status": m.status, "metrics": m.metrics,
            "history": m.history, "classes": m.classes, "versionId": m.version_id, "jobId": m.job_id,
            "family": m.family, "variant": m.variant, "license": m.license,
            "created": m.created, "weightsUrl": sign_path(m.weights) if m.weights else None}


def _files_in(obj) -> list[str]:
    """Collect image file names from an eval detail (worst rows, confusion cells, detections)."""
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        if isinstance(obj.get("file"), str):
            return [obj["file"]]
        return [f for value in obj.values() for f in _files_in(value)]
    if isinstance(obj, (list, tuple)):
        return [f for value in obj for f in _files_in(value)]
    return []


def _eval_images(m: TrainedModel) -> dict:
    """Signed URLs for every image the eval report shows (worst, confusion matrix, detections)."""
    ev = (m.metrics or {}).get("eval") or {}
    split = ev.get("split")
    if not split:
        return {}
    files: list[str] = []
    for row in ev.get("worst") or []:
        files += _files_in(row)
    files += _files_in((ev.get("confusion") or {}).get("images"))
    for det in ev.get("detections") or []:
        files += _files_in(det)
    return {f: sign_path(f"versions/{m.version_id}/{split}/{f}") for f in dict.fromkeys(files)}


@router.get(P + "/models")
def models(c: Ctx = Depends(project_ctx)):
    rows = c.db.scalars(select(TrainedModel).where(TrainedModel.project_id == c.project.id)
                        .order_by(TrainedModel.created.desc())).all()
    out = []
    for m in rows:
        d = model_out(m)
        d["metrics"] = _lean_metrics(m.metrics)
        v = c.db.get(Version, m.version_id)
        d["version"] = v.number if v else None
        j = c.db.get(Job, m.job_id) if m.job_id else None
        d["job"] = job_out(j) if j else None
        out.append(d)
    return out


@router.get(P + "/leaderboard")
def leaderboard(c: Ctx = Depends(project_ctx)):
    """Every model of the project, best eval COCO AP first; comparable = same dataset version as the winner."""
    rows = c.db.scalars(select(TrainedModel).where(TrainedModel.project_id == c.project.id)).all()
    out = []
    for m in rows:
        ev = (m.metrics or {}).get("eval") or {}
        note = str(ev.get("note") or "").lower()
        scored = bool(ev.get("coco")) and "not evaluated" not in note and "skipped" not in note
        ap = (ev.get("coco") or {}).get("AP") if scored else None
        latency = ev.get("latency_ms") if scored else None
        v = c.db.get(Version, m.version_id)
        out.append({"id": m.id, "name": m.name, "variant": m.variant, "task": m.task, "status": m.status,
                    "version": v.number if v else None, "versionId": m.version_id,
                    "ap": float(ap) if isinstance(ap, (int, float)) else None,
                    "latency_ms": float(latency) if isinstance(latency, (int, float)) else None,
                    "created": m.created})
    out.sort(key=lambda r: (r["ap"] is None, -(r["ap"] or 0.0), -(r["created"] or 0.0)))
    best = next((r for r in out if r["ap"] is not None), None)
    for r in out:
        # only models scored on the winner's dataset version are directly comparable
        r["comparable"] = bool(best and r["ap"] is not None and r["versionId"] == best["versionId"])
    return out


@router.get(P + "/train/options")
def train_options(c: Ctx = Depends(project_ctx)):
    if c.project.type not in ml.TASK:
        return {"supported": False, "reason": "training is available for detection, segmentation and classification projects"}
    task = ml.TASK[c.project.type]
    suffix = {"detect": "", "segment": "-seg", "classify": "-cls"}[task]
    probes = {}
    for adapter in {f["adapter"] for f in FAMILIES}:
        ad = ADAPTERS.get(adapter)
        probes[adapter] = ad.probe() if ad else None
    fams = []
    for f in FAMILIES:
        av = probes.get(f["adapter"])
        ok, reason = (av.ok, av.reason) if av else (False, f"{f['adapter']} adapter not installed")
        if ok and f["detect_only"] and task != "detect":
            ok, reason = False, "detection projects only"
        sfx = "" if f["detect_only"] else suffix
        fams.append({"family": f["family"], "label": f["label"], "adapter": f["adapter"], "license": f["license"],
                     "available": ok, "reason": reason,
                     "variants": [{"id": v["id"], "label": v["label"], "weights": v.get("weights", v["id"] + sfx + ".pt")}
                                  for v in f["variants"]]})
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
    if base not in _BASE_VARIANTS or not (1 <= body.epochs <= 500) \
            or (body.max_minutes is not None and body.max_minutes < 1):
        raise HTTPException(400, "bad training options")
    task = ml.TASK[c.project.type]
    fam = next(f for f in FAMILIES if f["family"] == _family_of(base))
    if body.family not in (fam["adapter"], fam["family"]):
        raise HTTPException(400, "bad training options")
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
                     arch=variant, family=fam["adapter"], variant=variant, license=fam["license"],
                     status="queued", classes=v.stats.get("class_names", []))
    c.db.add(m); c.db.flush()
    options = {"family": fam["adapter"], "variant": variant, "epochs": body.epochs, "imgsz": body.imgsz,
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
    m = _model(c, mid)
    return {**model_out(m), "evalImages": _eval_images(m)}


@router.delete(P + "/models/{mid}")
def delete_model(mid: str, c: Ctx = Depends(project_ctx)):
    c.need("admin")
    m = _model(c, mid)
    audit(c.db, c.ws.id, c.user.id, "model.delete", m.name)
    c.db.delete(m); c.db.commit()
    return {"ok": True}


@router.post(P + "/models/{mid}/predict")
async def test_predict(mid: str, file: UploadFile = File(...), confidence: float | None = Form(None),
                       overlap: float = Form(0.5), c: Ctx = Depends(project_ctx)):
    m = _model(c, mid)
    if m.status != "ready":
        raise HTTPException(409, "model is not ready")
    charge(c.db, c.ws, CREDIT_COST["infer"]); c.db.commit()
    im = imaging.open_image(await file.read())
    kw = {"iou": overlap, "classes": m.classes}
    if confidence is not None:                     # no slider value: Resolved uses the model's best-F1 threshold
        kw["conf"] = confidence
    return resolve(f"trained:{m.id}", c.db).predict(im, **kw)


class AutoLabelIn(BaseModel):
    method: str = "model"           # model | sam
    model_id: str | None = None
    model_ref: str | None = None    # <family>:<variant> | trained:<id>; wins over method/model_id
    prompt: str | None = None       # free text, parsed into SAM/VLM prompts
    vlm_verify: bool = False
    batch_id: str | None = None
    image_ids: list[str] = []
    class_ids: list[str] = []
    confidence: float | None = None   # None = the model's best-F1 threshold (0.4 when it has no eval)
    only_unannotated: bool = True
    send_to_review: bool = True


class AutoLabelPreviewIn(AutoLabelIn):
    sample: int = 4                 # clamped to 3..5


def _autolabel_target(c: Ctx, body: AutoLabelIn):
    """v1 validation + resolve the ref; 400 for anything the user can fix."""
    if body.method == "model" and not (body.model_id or body.model_ref):
        raise HTTPException(400, "choose a trained model")
    if body.method == "sam" and not c.db.scalar(select(LabelClass.id).where(LabelClass.project_id == c.project.id)):
        raise HTTPException(400, "add classes first — SAM uses class names as text prompts")
    ref = body.model_ref or (f"trained:{body.model_id}" if body.method == "model" else "sam3:sam3.1")
    try:
        r = resolve(ref, c.db, workspace_id=c.ws.id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if r.adapter.family in ("sam3", "vlm") and c.project.type == "classification":
        raise HTTPException(400, f"{'SAM' if r.adapter.family == 'sam3' else 'VLM'} auto-label needs "
                                 "a detection or segmentation project")
    if r.adapter.family == "vlm":
        sam = ADAPTERS.get("sam3")
        if not (sam and sam.probe().ok):
            raise HTTPException(400, "VLM auto-label needs SAM 3.1 to refine its boxes — enable SAM on this worker")
    if r.adapter.family in ("sam3", "vlm") and not c.db.scalar(
            select(LabelClass.id).where(LabelClass.project_id == c.project.id)):
        raise HTTPException(400, "add classes first — auto-label attaches results to a project class")
    if "autolabel" not in LOCAL_JOB_KINDS:
        # the pip worker only knows trained ultralytics weights and SAM text prompts (Phase 7 ports adapters)
        remote_ok = not (body.prompt or "").strip() and not body.vlm_verify and (
            r.adapter.family == "sam3" or (r.adapter.family == "ultralytics" and r.ref.startswith("trained:")))
        if not remote_ok:
            raise HTTPException(400, _REMOTE_UNSUPPORTED)
    return r


def _autolabel_images(c: Ctx, body: AutoLabelIn, limit: int):
    q = select(Image).where(Image.project_id == c.project.id, Image.deleted_at.is_(None))
    if body.image_ids:
        q = q.where(Image.id.in_(body.image_ids))
    if body.batch_id:
        q = q.where(Image.batch_id == body.batch_id)
    if body.only_unannotated:
        q = q.where(Image.n_annotations == 0)
    return c.db.scalars(q.order_by(Image.created.desc()).limit(limit)).all()


@router.post(P + "/autolabel")
def autolabel(body: AutoLabelIn, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    _autolabel_target(c, body)
    j = Job(workspace_id=c.ws.id, project_id=c.project.id, kind="autolabel", params=body.model_dump(), created_by=c.user.id)
    c.db.add(j)
    audit(c.db, c.ws.id, c.user.id, "autolabel.start", c.project.name,
          method=body.method, model_ref=body.model_ref or body.model_id)
    c.db.commit()
    return job_out(j)


@router.post(P + "/autolabel/preview")
def autolabel_preview(body: AutoLabelPreviewIn, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    _autolabel_target(c, body)
    from .images import image_out                      # local import: images imports projects -> no cycle at module load
    classes = c.db.scalars(select(LabelClass).where(LabelClass.project_id == c.project.id)
                           .order_by(LabelClass.created)).all()
    names = {x.id: x.name for x in classes}
    images, counts = [], {}
    sam_ok = sam_available()          # one probe for the whole preview
    for img in _autolabel_images(c, body, max(3, min(5, body.sample))):
        try:
            anns = label_image(imaging.load(img.path), project_type=c.project.type, params=body.model_dump(),
                               classes=classes, db=c.db, workspace_id=c.ws.id, sam_ok=sam_ok)
        except RuntimeError as e:      # model runtime down (vLLM / SAM): a readable 503, not a 500
            raise HTTPException(503, str(e))
        except ValueError as e:        # our own adapter validation, e.g. YOLO-World without classes
            raise HTTPException(400, str(e))
        for a in anns:
            name = names.get(a["classId"])
            if name:
                counts[name] = counts.get(name, 0) + 1
        images.append({"id": img.id, "url": image_out(img)["url"], "annotations": anns})
    return {"images": images, "counts": counts}


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
async def hosted_predict(mid: str, request: Request, api_key: str | None = Query(None), confidence: float | None = None,
                         overlap: float = 0.5, image: str | None = None, file: UploadFile | None = File(None),
                         db: Session = Depends(get_db)):
    ws = key_ws(db, api_key or request.headers.get("x-api-key"), request)
    m = db.get(TrainedModel, mid)
    if not m or m.workspace_id != ws.id or m.status != "ready":
        raise HTTPException(404, "model not found")
    charge(db, ws, CREDIT_COST["infer"])
    data = await _image_from_request(request, file, image)
    im = imaging.open_image(data)
    kw = {"iou": overlap, "classes": m.classes}
    if confidence is not None:                     # omitted: the model's evaluated best-F1 threshold
        kw["conf"] = confidence
    out = resolve(f"trained:{m.id}", db).predict(im, **kw)
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
