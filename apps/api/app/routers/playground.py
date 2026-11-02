"""Playground: run 1-3 models on one uploaded image, side by side. No credits; any workspace member."""
import logging
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select

from ..adapters import resolve, validate_prediction
from ..deps import Ctx, ws_ctx
from ..gpu import GpuBusy
from ..models import Image, Project
from ..security import sign_path
from ..services import runtime_state
from ..services.imaging import open_image

router = APIRouter(prefix="/api/ws/{ws}/playground", tags=["playground"])
log = logging.getLogger(__name__)
MAX_MODELS = 3
MAX_BYTES = 20 * 1024 * 1024
MAX_SAMPLES = 12


def _message(e: Exception) -> str:
    """Only our own validation messages are safe to show; everything else stays generic."""
    msg = str(e)
    if isinstance(e, ValueError) and not msg.startswith("no adapter for"):
        return msg or type(e).__name__
    if isinstance(e, RuntimeError) or msg.startswith("no adapter for"):
        return "model unavailable"          # vLLM asleep/unreachable, missing dependency
    log.exception("playground inference failed")
    return "inference failed"


def _run(ref: str, im, db, workspace_id: str, classes: list[str], prompt: str | None,
         conf: float | None) -> dict:
    t0 = time.perf_counter()
    out = {"ref": ref, "prediction": None, "latency_ms": 0.0, "error": None}
    try:
        r = resolve(ref, db, workspace_id=workspace_id)
        is_vlm = r.adapter.family == "vlm"
        needs_classes = (is_vlm and not prompt) or "world" in r.variant
        if needs_classes and not classes:
            raise ValueError("this model needs classes (comma-separated) to detect")
        kw: dict = {}
        if conf is not None:
            kw["conf"] = conf
        elif r.conf is None:                # no model default: keep the playground's historical 0.25
            kw["conf"] = 0.25
        if prompt and is_vlm:
            kw["prompt"] = prompt
        if needs_classes:
            kw["classes"] = classes
        pred = r.predict(im, **kw)
        validate_prediction(pred)
        out["prediction"] = pred
    except GpuBusy:         # training owns the card: every model is unavailable, so 503 the request
        raise
    except Exception as e:  # one model failing must not fail the others
        out["error"] = _message(e)
    out["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return out


def _refs(model_refs: list[str]) -> list[str]:
    refs = list(dict.fromkeys(r.strip() for r in model_refs if r.strip()))
    if not 1 <= len(refs) <= MAX_MODELS:
        raise HTTPException(400, f"choose 1 to {MAX_MODELS} models")
    return refs


@router.post("/predict")
def predict(file: UploadFile = File(...), model_refs: str = Form(""), prompt: str | None = Form(None),
            classes: str | None = Form(None), confidence: float | None = Form(None), c: Ctx = Depends(ws_ctx)):
    refs = _refs(model_refs.split(","))
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "image too large (max 20 MB)")
    try:
        im = open_image(data)             # EXIF auto-orient, like the rest of the ingest path
    except Exception:
        raise HTTPException(400, "not a valid image")
    cls = [x.strip() for x in (classes or "").split(",") if x.strip()]
    q = (prompt or "").strip() or None
    return {"results": [_run(r, im, c.db, c.ws.id, cls, q, confidence) for r in refs]}


class PreflightIn(BaseModel):
    model_refs: list[str] = []


@router.post("/preflight")
def preflight(body: PreflightIn, c: Ctx = Depends(ws_ctx)):
    """Explain, per selected model, whether a run can start now (G1 / gap M1)."""
    return {"models": runtime_state.preflight(c.db, c.ws.id, _refs(body.model_refs))}


@router.get("/samples")
def samples(limit: int = 6, c: Ctx = Depends(ws_ctx)):
    """Recent annotated images of this workspace, ready to load into the Playground."""
    limit = max(1, min(limit, MAX_SAMPLES))
    rows = c.db.execute(
        select(Image.id, Image.name, Image.thumb, Image.path, Project.slug, Project.name)
        .join(Project, Project.id == Image.project_id)
        .where(Project.workspace_id == c.ws.id, Project.deleted_at.is_(None),
               Image.deleted_at.is_(None), Image.n_annotations > 0, Image.thumb != "", Image.path != "")
        .order_by(Image.created.desc())
        .limit(limit)
    ).all()
    return {"samples": [
        {"id": image_id, "name": name, "thumbnail": sign_path(thumb), "url": sign_path(path),
         "project": {"slug": slug, "name": project_name}}
        for image_id, name, thumb, path, slug, project_name in rows
    ]}
