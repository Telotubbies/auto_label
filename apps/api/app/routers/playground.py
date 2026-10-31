"""Playground: run 1-3 models on one uploaded image, side by side. No credits; any workspace member."""
import io
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image as PImage

from ..adapters import resolve, validate_prediction
from ..deps import Ctx, ws_ctx

router = APIRouter(prefix="/api/ws/{ws}/playground", tags=["playground"])
MAX_MODELS = 3
MAX_BYTES = 20 * 1024 * 1024


def _run(ref: str, im: PImage.Image, db, classes: list[str], prompt: str | None, conf: float) -> dict:
    t0 = time.perf_counter()
    out = {"ref": ref, "prediction": None, "latency_ms": 0.0, "error": None}
    try:
        r = resolve(ref, db)
        is_vlm = r.adapter.family == "vlm"
        needs_classes = (is_vlm and not prompt) or "world" in r.variant
        if needs_classes and not classes:
            raise ValueError("this model needs classes (comma-separated) to detect")
        kw: dict = {"conf": conf}
        if prompt and is_vlm:
            kw["prompt"] = prompt
        if needs_classes:
            kw["classes"] = classes
        pred = r.predict(im, **kw)
        validate_prediction(pred)
        out["prediction"] = pred
    except Exception as e:  # one model failing must not fail the others
        out["error"] = str(e) or type(e).__name__
    out["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return out


@router.post("/predict")
def predict(file: UploadFile = File(...), model_refs: str = Form(""), prompt: str | None = Form(None),
            classes: str | None = Form(None), confidence: float = Form(0.25), c: Ctx = Depends(ws_ctx)):
    refs = [r.strip() for r in model_refs.split(",") if r.strip()]
    if not 1 <= len(refs) <= MAX_MODELS:
        raise HTTPException(400, f"choose 1 to {MAX_MODELS} models")
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "image too large (max 20 MB)")
    try:
        im = PImage.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        raise HTTPException(400, "not a valid image")
    cls = [x.strip() for x in (classes or "").split(",") if x.strip()]
    q = (prompt or "").strip() or None
    return {"results": [_run(r, im, c.db, cls, q, confidence) for r in refs]}
