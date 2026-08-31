"""SAM 3.1 segmentation — model inference service (FastAPI).

Endpoints:
  GET  /health   — liveness: service status, device, model state
  GET  /config   — current config (categories, prompts, threshold, annotation switches)
  PUT  /config   — update threshold / categories / annotation switches (reloads model)
  POST /segment  — segment one or more uploaded images -> COCO annotations
  GET  /metrics  — per-endpoint latency / throughput stats

Run:
  python src/service.py
  # or: uvicorn service:app --app-dir src --host 0.0.0.0 --port 8000
"""

import io
import logging
import os
import sys
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Request, UploadFile, HTTPException
from pydantic import BaseModel

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

# Ensure src/ is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import load_config, save_config, Category

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "ppe.yaml")

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif"}

# ---------------------------------------------------------------------------
# Performance tracking — in-memory, no external deps
# ---------------------------------------------------------------------------

class PerfStats:
    """Track per-endpoint latency, throughput, and error rates in memory."""
    def __init__(self, window_size: int = 500):
        self.lock = threading.Lock()
        self.window_size = window_size
        self.latencies: dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        self.request_counts: dict[str, int] = defaultdict(int)
        self.error_counts: dict[str, int] = defaultdict(int)
        self.slow_requests: deque = deque(maxlen=50)
        self.total_requests = 0
        self.start_time = time.time()

    def record(self, method: str, path: str, status: int, latency_ms: float):
        key = f"{method} {path}"
        with self.lock:
            self.latencies[key].append(latency_ms)
            self.request_counts[key] += 1
            self.total_requests += 1
            if status >= 400:
                self.error_counts[key] += 1
            if latency_ms > 500:
                self.slow_requests.append({
                    "method": method, "path": path, "status": status,
                    "latency_ms": round(latency_ms, 1), "time": time.strftime("%H:%M:%S"),
                })

    def _percentile(self, sorted_list, p: float) -> float:
        if not sorted_list:
            return 0
        idx = min(int(len(sorted_list) * p), len(sorted_list) - 1)
        return sorted_list[idx]

    def get_stats(self) -> dict:
        with self.lock:
            endpoints = {}
            for key, lats in self.latencies.items():
                s = sorted(lats)
                endpoints[key] = {
                    "count": self.request_counts[key],
                    "errors": self.error_counts[key],
                    "p50_ms": round(self._percentile(s, 0.50), 1),
                    "p95_ms": round(self._percentile(s, 0.95), 1),
                    "p99_ms": round(self._percentile(s, 0.99), 1),
                    "avg_ms": round(sum(s) / len(s), 1) if s else 0,
                    "min_ms": round(s[0], 1) if s else 0,
                    "max_ms": round(s[-1], 1) if s else 0,
                }
            uptime = time.time() - self.start_time
            return {
                "uptime_seconds": round(uptime, 0),
                "total_requests": self.total_requests,
                "avg_rps": round(self.total_requests / uptime, 1) if uptime > 0 else 0,
                "endpoints": endpoints,
                "slow_requests": list(self.slow_requests),
            }

perf = PerfStats()

# ---------------------------------------------------------------------------
# Config cache — avoid reading YAML from disk on every request
# ---------------------------------------------------------------------------

_config_cache = {"mtime": 0, "cfg": None}

def get_cached_config(path: str = None):
    """Load config with file-mtime caching. Reloads when YAML changes."""
    if path is None:
        path = CONFIG_PATH
    mtime = os.path.getmtime(path)
    if _config_cache["cfg"] is None or mtime != _config_cache["mtime"]:
        _config_cache["cfg"] = load_config(path)
        _config_cache["mtime"] = mtime
    return _config_cache["cfg"]

def invalidate_config_cache():
    """Call after save_config to force reload."""
    _config_cache["cfg"] = None

# ---------------------------------------------------------------------------
# Model holder — loads SAM 3.1 in the background at startup
# ---------------------------------------------------------------------------

class ModelHolder:
    """Thread-safe holder for the SAM 3.1 processor (loads async, reloads on config change)."""
    def __init__(self):
        self.processor = None
        self.device = None
        self.status = "idle"       # idle | loading | ready | failed
        self.error = None
        self.load_time_s = None
        self.infer_lock = threading.Lock()   # SAM processor is stateful — serialize inference
        self.load_lock = threading.Lock()    # prevent concurrent (re)loads

    def start_load(self):
        """Kick off background model load (no-op if already loading/ready)."""
        with self.load_lock:
            if self.status == "loading":
                return
            self.status = "loading"
            self.error = None
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        from inference import build_model, resolve_device
        t0 = time.time()
        try:
            cfg = get_cached_config()
            processor = build_model(cfg)
            with self.load_lock:
                self.processor = processor
                self.device = resolve_device(cfg.inference.device)
                self.status = "ready"
                self.load_time_s = round(time.time() - t0, 1)
            log.info(f"model ready on {self.device} in {self.load_time_s}s")
        except Exception as e:
            with self.load_lock:
                self.processor = None
                self.status = "failed"
                self.error = str(e)
            log.error(f"model load failed: {e}")

    def info(self) -> dict:
        with self.load_lock:
            return {
                "status": self.status,
                "device": self.device,
                "error": self.error,
                "load_time_s": self.load_time_s,
            }

model = ModelHolder()

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    model.start_load()
    yield


app = FastAPI(title="SAM 3.1 Segmentation Service", version="2.0.0", lifespan=lifespan)


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Response-Time-ms"] = f"{elapsed_ms:.1f}"
    if request.url.path != "/metrics":
        perf.record(request.method, request.url.path, response.status_code, elapsed_ms)
    if elapsed_ms > 500:
        log.warning(f"SLOW {request.method} {request.url.path} {response.status_code} {elapsed_ms:.0f}ms")
    return response


# ---------------------------------------------------------------------------
# Routes — Health / Metrics
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    info = model.info()
    return {
        "status": "ok" if info["status"] == "ready" else info["status"],
        "version": "2.0.0",
        "model": info,
    }


@app.get("/metrics")
async def get_metrics():
    """Performance metrics — per-endpoint latency, throughput, slow requests."""
    return perf.get_stats()


# ---------------------------------------------------------------------------
# Routes — Config
# ---------------------------------------------------------------------------

@app.get("/config")
async def get_config():
    try:
        cfg = get_cached_config()
        return {
            "inference": {
                "threshold": cfg.inference.confidence_threshold,
                "resolution": cfg.inference.resolution,
                "device": cfg.inference.device,
            },
            "categories": [
                {"id": c.id, "name": c.name, "prompt": c.prompt}
                for c in cfg.categories
            ],
            "annotation": {
                "bbox": cfg.annotation.bbox,
                "segmentation": cfg.annotation.segmentation,
                "segmentation_encoding": cfg.annotation.segmentation_encoding,
            },
            "output": {
                "formats": list(cfg.output.formats),
                "save_viz": cfg.output.save_viz,
                "input_dir": cfg.output.input_dir,
                "output_dir": cfg.output.output_dir,
            },
            "paths": {
                "checkpoint_path": cfg.ckpt_path,
                "bpe_path": cfg.bpe_path,
                "checkpoint_exists": os.path.isfile(cfg.ckpt_path),
                "bpe_exists": os.path.isfile(cfg.bpe_path),
            },
        }
    except Exception as e:
        raise HTTPException(500, str(e))


class CategoryInput(BaseModel):
    id: int
    name: str
    prompt: str


class ConfigUpdate(BaseModel):
    threshold: float | None = None
    device: str | None = None
    categories: list[CategoryInput] | None = None
    bbox: bool | None = None
    segmentation: bool | None = None
    segmentation_encoding: str | None = None
    formats: list[str] | None = None


@app.put("/config")
async def update_config(req: ConfigUpdate):
    """Update inference config. Triggers a background model reload (threshold/device/categories
    are baked into the processor)."""
    try:
        cfg = load_config(CONFIG_PATH)  # Fresh load — we'll mutate and save

        if req.threshold is not None:
            if not 0.0 <= req.threshold <= 1.0:
                raise HTTPException(400, "threshold must be 0-1")
            cfg.inference.confidence_threshold = req.threshold
        if req.device is not None:
            if req.device not in ("auto", "cpu", "cuda", "rocm", "mps"):
                raise HTTPException(400, "device must be one of: auto, cpu, cuda, rocm, mps")
            cfg.inference.device = req.device

        if req.categories is not None:
            ids, names = set(), set()
            for c in req.categories:
                if c.id in ids:
                    raise HTTPException(400, f"Duplicate category id: {c.id}")
                if c.name in names:
                    raise HTTPException(400, f"Duplicate category name: {c.name}")
                ids.add(c.id)
                names.add(c.name)
            cfg.categories = [
                Category(id=c.id, name=c.name, prompt=c.prompt)
                for c in req.categories
            ]

        if req.bbox is not None:
            cfg.annotation.bbox = req.bbox
        if req.segmentation is not None:
            cfg.annotation.segmentation = req.segmentation
        if not cfg.annotation.bbox and not cfg.annotation.segmentation:
            raise HTTPException(400, "at least one of bbox / segmentation must be true")
        if req.segmentation_encoding is not None:
            if req.segmentation_encoding not in ("rle", "polygon"):
                raise HTTPException(400, "segmentation_encoding must be 'rle' or 'polygon'")
            cfg.annotation.segmentation_encoding = req.segmentation_encoding
        if req.formats is not None:
            from config import SUPPORTED_FORMATS
            unknown = [f for f in req.formats if f not in SUPPORTED_FORMATS]
            if unknown:
                raise HTTPException(400, f"unknown format(s): {unknown} — supported: {list(SUPPORTED_FORMATS)}")
            cfg.output.formats = list(dict.fromkeys(req.formats))

        save_config(cfg, CONFIG_PATH)
        invalidate_config_cache()
        model.start_load()  # reload with new settings in background
        return {"message": "Config updated, model reloading", "config": await get_config()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ---------------------------------------------------------------------------
# Routes — Segment
# ---------------------------------------------------------------------------

@app.post("/segment")
async def segment(files: list[UploadFile] = File(...), include_masks: bool = True):
    """Segment one or more uploaded images.

    Returns COCO-style annotations per image.
    Fields honor the `annotation:` config switches (bbox / segmentation /
    segmentation_encoding). `include_masks=false` additionally strips masks
    from the response regardless of config.
    """
    from PIL import Image
    from exporters import annotation_view
    from inference import segment_image

    info = model.info()
    if info["status"] == "loading":
        raise HTTPException(503, "Model is still loading, try again shortly")
    if info["status"] != "ready":
        raise HTTPException(503, f"Model not ready: {info['status']} — {info['error']}")

    cfg = get_cached_config()
    results, errors = [], []

    for idx, f in enumerate(files):
        name = os.path.basename(f.filename or f"image_{idx}")
        ext = os.path.splitext(name)[1].lower()
        if ext not in IMAGE_EXTS:
            errors.append({"image": name, "error": f"unsupported file type: {ext}"})
            continue
        try:
            data = await f.read()
            image = Image.open(io.BytesIO(data)).convert("RGB")
            W, H = image.size

            t0 = time.time()
            # SAM processor keeps internal prompt state — serialize access
            with model.infer_lock:
                annotations, _ = segment_image(model.processor, image, image_id=idx + 1,
                                               start_ann_id=1, cfg=cfg)
            elapsed = round(time.time() - t0, 2)

            annotations = [annotation_view(a, cfg) for a in annotations]
            if not include_masks:
                for ann in annotations:
                    ann.pop("segmentation", None)

            results.append({
                "image": name,
                "width": W,
                "height": H,
                "time_seconds": elapsed,
                "num_annotations": len(annotations),
                "annotations": annotations,
            })
        except Exception as e:
            log.error(f"segment failed for {name}: {e}")
            errors.append({"image": name, "error": str(e)})

    return {
        "results": results,
        "errors": errors,
        "categories": [
            {"id": c.id, "name": c.name, "supercategory": "object"} for c in cfg.categories
        ],
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("service:app", host="0.0.0.0", port=8000, reload=False, workers=1)
