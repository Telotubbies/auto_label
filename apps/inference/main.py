"""LabelDesk self-hosted inference service (single-tenant, CPU or GPU container).

Mount exported model files at LD_INFERENCE_MODELS (default /models) and call POST /predict.
There is deliberately no workspace auth and no secret handling: one container serves one tenant.
The service refuses to start when the model directory contains no supported files.
"""

from __future__ import annotations

import io
import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from PIL import Image, ImageOps

from detect import (
    SERVICE_VERSION,
    ModelFile,
    backend_availability,
    backend_versions,
    build_detector,
    missing_dependencies,
    scan_models,
)

log = logging.getLogger("labeldesk.inference")

DEFAULT_MODELS_DIR = "/models"
MAX_BYTES = 20 * 1024 * 1024
DEFAULT_CONFIDENCE = 0.4


def create_app(models_dir: Path | str | None = None) -> FastAPI:
    root = Path(models_dir or os.environ.get("LD_INFERENCE_MODELS", DEFAULT_MODELS_DIR))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.catalog = scan_models(root)  # empty or missing dir -> startup fails
        log.info("serving %d model file(s) from %s", len(app.state.catalog), root)
        yield

    app = FastAPI(title="LabelDesk inference", version=SERVICE_VERSION, lifespan=lifespan)
    app.state.root = root
    app.state.catalog = []
    app.state.detectors = {}
    app.state.detector_lock = threading.Lock()

    def _select(name: str | None) -> ModelFile:
        catalog: list[ModelFile] = app.state.catalog
        if not catalog:
            raise HTTPException(503, "no model files found")
        if name:
            for entry in catalog:
                if entry.name == name:
                    return entry
            raise HTTPException(404, f"unknown model {name!r}; GET /models lists the mounted files")
        if len(catalog) == 1:
            return catalog[0]
        raise HTTPException(400, "several models are mounted; pass model=<name> (see GET /models)")

    def _detector(entry: ModelFile):
        with app.state.detector_lock:
            cached = app.state.detectors.get(entry.name)
            if cached is not None:
                return cached
            missing = missing_dependencies(entry)
            if missing:
                raise HTTPException(503, f"{entry.backend} backend unavailable; this image needs {', '.join(missing)}")
            try:
                detector = build_detector(entry)
            except Exception:
                log.exception("could not load model %s", entry.name)
                raise HTTPException(503, f"could not load model {entry.name}; see the container logs")
            app.state.detectors[entry.name] = detector
            return detector

    @app.get("/healthz")
    def healthz() -> dict:
        catalog: list[ModelFile] = app.state.catalog
        if not catalog:
            raise HTTPException(503, "no model files found")
        return {
            "status": "ok",
            "models": {"count": len(catalog), "files": [entry.name for entry in catalog]},
            "backends": backend_availability(),
            "versions": backend_versions(),
            "model_dir": str(app.state.root),
        }

    @app.get("/models")
    def models() -> dict:
        rows = []
        for entry in app.state.catalog:
            missing = missing_dependencies(entry)
            rows.append(entry.as_dict(available=not missing, reason=f"missing {', '.join(missing)}" if missing else ""))
        return {"models": rows}

    @app.post("/predict")
    def predict(
        file: UploadFile = File(...),
        confidence: float = Form(DEFAULT_CONFIDENCE, ge=0.0, le=1.0),
        model: str | None = Form(None),
    ) -> dict:
        entry = _select(model)
        data = file.file.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "image too large (max 20 MB)")
        try:
            im = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
            im.load()  # decode now: reject truncated/non-image uploads here
        except Exception:
            raise HTTPException(400, "not a valid image") from None
        detector = _detector(entry)
        try:
            out = detector.predict(im, confidence)
        except Exception:
            log.exception("inference failed for %s", entry.name)
            raise HTTPException(500, "inference failed") from None
        out["model"] = entry.name
        return out

    return app


app = create_app()
