"""Train, models, test inference, auto-label, and the API-key hosted inference/upload API."""
import base64
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..adapters import ADAPTERS, engine_ref, resolve
from ..adapters.refine import label_image, sam_available
from ..apikeys import resolve_key
from ..config import CREDIT_COST, LOCAL_JOB_KINDS, runs_locally
from ..db import get_db
from ..deps import Ctx, audit, charge, project_ctx
from ..errors import safe_error, safe_reason
from ..models import DeploymentAlias, Image, Job, LabelClass, Project, TrainedModel, Version, Workspace
from ..security import sign_path
from ..services import active_learning, deployments, drift, imaging, metering, ml, safefetch
from .projects import job_out

router = APIRouter(tags=["training"])
P = "/api/ws/{ws}/projects/{project}"
LICENSE = "AGPL-3.0"       # the ultralytics families
log = logging.getLogger(__name__)
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
    # HF models store a directory (models/<id>/), which the single-file route cannot serve — no download.
    weights_url = sign_path(m.weights) if m.weights and m.family != "hf" else None
    engine = engine_ref(m)
    return {"id": m.id, "name": m.name, "arch": m.arch, "task": m.task, "status": m.status, "metrics": m.metrics,
            "history": m.history, "classes": m.classes, "versionId": m.version_id, "jobId": m.job_id,
            "family": m.family, "variant": m.variant, "license": m.license,
            "runtimeRefs": {"engine": engine} if engine else {},
            "created": m.created, "weightsUrl": weights_url}


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
    # Labelers need the ready-model list for label assist; weights and eval payloads stay
    # behind project.models (I14/I15).
    c.perm("project.infer")
    show_models = c.can("project.models")
    rows = c.db.scalars(select(TrainedModel).where(TrainedModel.project_id == c.project.id)
                        .order_by(TrainedModel.created.desc())).all()
    out = []
    for m in rows:
        d = model_out(m)
        d["metrics"] = _lean_metrics(m.metrics)
        v = c.db.get(Version, m.version_id)
        d["version"] = v.number if v else None
        j = c.db.get(Job, m.job_id) if m.job_id else None
        d["job"] = job_out(j, lean=not show_models) if j else None
        if not show_models:                 # AI-assist list: no weights, eval or runtime artefacts
            d["weightsUrl"], d["metrics"], d["runtimeRefs"] = None, {}, {}
        out.append(d)
    return out


@router.get(P + "/leaderboard")
def leaderboard(c: Ctx = Depends(project_ctx)):
    """Every model of the project, best eval COCO AP first; comparable = same dataset version as the winner."""
    c.perm("project.models")
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
                     "available": ok, "reason": safe_reason(reason),
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


def _gpu_estimate(train_images: int, epochs: int, imgsz: int) -> float:
    """Seconds behind the Train page estimate: images × epochs × (imgsz/640)² at 600 images/minute."""
    return max(60.0, train_images * max(1, epochs) * (imgsz / 640) ** 2 / 600 * 60)


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
    if not runs_locally("train"):           # remote pip worker: v1 cli only understands YOLO + size
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
    metering.check(c.db, c.ws, "gpu_seconds",      # reserve the whole estimated run, not one second
                   _gpu_estimate(int((v.stats or {}).get("splits", {}).get("train") or 0), body.epochs, body.imgsz))
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
    j = Job(workspace_id=c.ws.id, project_id=c.project.id, kind="train", created_by=c.uid,
            params={"model_id": m.id, "version_id": v.id, "options": options})
    c.db.add(j); c.db.flush()
    m.job_id = j.id
    audit(c.db, c.ws.id, c.uid, "train.start", m.name, epochs=body.epochs, variant=variant)
    c.db.commit()
    return model_out(m)


def _model(c: Ctx, mid: str) -> TrainedModel:
    m = c.db.get(TrainedModel, mid)
    if not m or m.project_id != c.project.id:
        raise HTTPException(404, "model not found")
    return m


@router.get(P + "/models/{mid}")
def get_model(mid: str, c: Ctx = Depends(project_ctx)):
    c.perm("project.models")
    m = _model(c, mid)
    v = c.db.get(Version, m.version_id)
    j = c.db.get(Job, m.job_id) if m.job_id else None
    return {**model_out(m), "version": v.number if v else None, "job": job_out(j) if j else None,
            "evalImages": _eval_images(m)}


@router.delete(P + "/models/{mid}")
def delete_model(mid: str, c: Ctx = Depends(project_ctx)):
    c.need("admin")
    m = _model(c, mid)
    from ..services.erasure import delete_model_files
    _, ok = delete_model_files(m)                           # weights survive the row otherwise (I3)
    if not ok:
        raise HTTPException(409, "some files could not be deleted; retry")
    audit(c.db, c.ws.id, c.user.id, "model.delete", m.name)
    c.db.delete(m); c.db.commit()
    return {"ok": True}


@router.post(P + "/models/{mid}/predict")
async def test_predict(mid: str, file: UploadFile = File(...), confidence: float | None = Form(None),
                       overlap: float = Form(0.5), c: Ctx = Depends(project_ctx)):
    c.perm("project.infer")
    m = _model(c, mid)
    if m.status != "ready":
        raise HTTPException(409, "model is not ready")
    charge(c.db, c.ws, CREDIT_COST["infer"]); c.db.commit()
    im = imaging.open_image(await file.read())
    kw = {"iou": overlap, "classes": m.classes}
    if confidence is not None:                     # no slider value: Resolved uses the model's best-F1 threshold
        kw["conf"] = confidence
    return resolve(f"trained:{m.id}", c.db, workspace_id=c.ws.id).predict(im, **kw)


class ExportModelIn(BaseModel):
    format: str = "engine"


@router.post(P + "/models/{mid}/export")
def export_model(mid: str, body: ExportModelIn, c: Ctx = Depends(project_ctx)):
    """Queue a TensorRT engine build; the worker caches it and registers runtime_refs.engine."""
    c.need("admin")
    m = _model(c, mid)
    if body.format != "engine":
        raise HTTPException(400, "only format=engine is supported")
    if m.status != "ready" or not m.weights:
        raise HTTPException(409, "model is not ready")
    if (m.family or "ultralytics") != "ultralytics":
        raise HTTPException(400, "TensorRT export is available for ultralytics models only")
    if "world" in (m.variant or ""):
        raise HTTPException(400, "TensorRT export is not available for open-vocabulary models")
    trt = ADAPTERS.get("tensorrt")
    if trt is None or not trt.probe().ok:
        raise HTTPException(503, "TensorRT is not available on this worker")
    if "export_engine" not in LOCAL_JOB_KINDS:
        raise HTTPException(503, "no worker claims TensorRT engine builds")
    active = c.db.scalars(select(Job).where(Job.project_id == c.project.id, Job.kind == "export_engine",
                                          Job.status.in_(("queued", "running")))).all()
    existing = next((j for j in active if j.params.get("model_id") == m.id), None)
    if existing is not None:                       # a double click must not queue a second multi-minute build
        return job_out(existing)
    j = Job(workspace_id=c.ws.id, project_id=c.project.id, kind="export_engine", created_by=c.user.id,
            params={"model_id": m.id, "format": "engine"})
    c.db.add(j)
    audit(c.db, c.ws.id, c.user.id, "model.export", m.name, format="engine")
    c.db.commit()
    return job_out(j)


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
    if not runs_locally("autolabel"):
        # the pip worker only knows trained ultralytics weights and SAM text prompts (Phase 7 ports adapters)
        remote_ok = not (body.prompt or "").strip() and not body.vlm_verify and (
            r.adapter.family == "sam3"
            or (r.adapter.family in ("ultralytics", "tensorrt") and r.ref.startswith("trained:")))
        if not remote_ok:
            raise HTTPException(400, _REMOTE_UNSUPPORTED)
    return r


def _autolabel_query(c: Ctx, body: AutoLabelIn):
    q = select(Image).where(Image.project_id == c.project.id, Image.deleted_at.is_(None))
    if body.image_ids:
        q = q.where(Image.id.in_(body.image_ids))
    if body.batch_id:
        q = q.where(Image.batch_id == body.batch_id)
    if body.only_unannotated:
        q = q.where(Image.n_annotations == 0)
    return q


def _autolabel_images(c: Ctx, body: AutoLabelIn, limit: int):
    return c.db.scalars(_autolabel_query(c, body).order_by(Image.created.desc()).limit(limit)).all()


def _autolabel_target_count(c: Ctx, body: AutoLabelIn) -> int:
    """How many images the job will call the model on — the AI-call amount to reserve."""
    return int(c.db.scalar(select(func.count()).select_from(_autolabel_query(c, body).subquery())) or 0)


@router.post(P + "/autolabel")
def autolabel(body: AutoLabelIn, c: Ctx = Depends(project_ctx)):
    c.need("reviewer")
    _autolabel_target(c, body)
    metering.check(c.db, c.ws, "ai_calls",      # one call per processed image, reserved up front
                   _autolabel_target_count(c, body))
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
            raise HTTPException(503, safe_error(e, "autolabel"))
        except ValueError as e:        # our own adapter validation, e.g. YOLO-World without classes
            raise HTTPException(400, str(e))
        for a in anns:
            name = names.get(a["classId"])
            if name:
                counts[name] = counts.get(name, 0) + 1
        images.append({"id": img.id, "url": image_out(img)["url"], "annotations": anns})
    return {"images": images, "counts": counts}


# --- hosted API (api_key auth, Roboflow-style) ------------------------------------------------

def key_ws(db: Session, api_key: str | None, request: Request, scope: str) -> Workspace:
    """Resolve the key and enforce its scope before anything else runs."""
    token = api_key or request.headers.get("x-api-key")
    return resolve_key(request, token, db, from_query=api_key is not None).need(scope).ws


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


def _hosted_model(db: Session, ws: Workspace, ref: str) -> TrainedModel:
    """A model id or a deployment alias: `production` (unique) or `production@project-slug`."""
    m = db.get(TrainedModel, ref)
    if m:
        if m.workspace_id != ws.id or m.status != "ready":
            raise HTTPException(404, "model not found")
        return m
    project, alias = None, ref
    if "@" in ref:
        alias, _, slug = ref.partition("@")
        project = db.scalar(select(Project).where(Project.workspace_id == ws.id, Project.slug == slug,
                                                  Project.deleted_at.is_(None)))
        if not project:
            raise HTTPException(404, "project not found")
    elif ref in deployments.ALIASES:
        rows = db.scalars(select(Project).join(DeploymentAlias, DeploymentAlias.project_id == Project.id)
                          .where(Project.workspace_id == ws.id, Project.deleted_at.is_(None),
                                 DeploymentAlias.alias == ref)).all()
        if len(rows) > 1:
            raise HTTPException(409, f"alias '{ref}' exists in several projects — use {ref}@<project>")
        if not rows:
            raise HTTPException(404, "model not found")
        project = rows[0]
    else:
        raise HTTPException(404, "model not found")
    m = deployments.alias_model(db, project, alias)
    if not m:
        raise HTTPException(404, f"alias '{alias}' is not deployed")
    return m


async def _hosted_infer(db: Session, ws: Workspace, m: TrainedModel, request: Request, confidence: float | None,
                        overlap: float, image: str | None, file: UploadFile | None) -> dict:
    """Shared path for id-based and alias-based hosted prediction: meter, infer, feed drift/AL."""
    metering.check(db, ws, "ai_calls", 1)
    charge(db, ws, CREDIT_COST["infer"])
    data = await _image_from_request(request, file, image)
    im = imaging.open_image(data)
    kw = {"iou": overlap, "classes": m.classes}
    if confidence is not None:                     # omitted: the model's evaluated best-F1 threshold
        kw["conf"] = confidence
    out = resolve(f"trained:{m.id}", db, workspace_id=ws.id).predict(im, **kw)
    audit(db, ws.id, None, "infer.hosted", m.name, n=len(out["predictions"]))
    metering.record(db, ws.id, "ai_calls", 1, project_id=m.project_id, model_id=m.id, kind="hosted")
    db.commit()                                    # the paid inference is safe before any monitoring work
    p = db.get(Project, m.project_id)
    if p is not None and (p.settings or {}).get("drift_monitor", True):
        try:                                       # sampling is best-effort: it must never 500 a good prediction
            drift.record_sample(db, ws.id, p, m.id, data, source="api")
            active_learning.auto_offer(db, ws, p, data, out)
            db.commit()
        except Exception:                          # noqa: BLE001 - a full disk or DB error is not an infer failure
            log.exception("drift/active-learning sampling failed for model %s", m.id)
            db.rollback()
    return out


@router.post("/api/v1/models/{model_id}/predict", operation_id="predict",
             openapi_extra={"x-scopes": ["infer"]})
async def hosted_predict(model_id: str, request: Request, api_key: str | None = Query(None), confidence: float | None = None,
                         overlap: float = 0.5, image: str | None = None, file: UploadFile | None = File(None),
                         db: Session = Depends(get_db)):
    ws = key_ws(db, api_key, request, "infer")
    return await _hosted_infer(db, ws, _hosted_model(db, ws, model_id), request, confidence, overlap, image, file)


@router.post("/api/v1/{ws_slug}/{project}/upload", operation_id="upload_images_v1",
             openapi_extra={"x-scopes": ["upload"]})
async def hosted_upload(ws_slug: str, project: str, request: Request, api_key: str | None = Query(None),
                        split: str = "auto", batch: str = "API Upload", tag: str = "", name: str = "upload.jpg",
                        image: str | None = None, file: UploadFile | None = File(None), db: Session = Depends(get_db)):
    ws = key_ws(db, api_key, request, "upload")
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
