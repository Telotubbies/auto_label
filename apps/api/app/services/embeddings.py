"""One image-embedding seam: CLIP ViT-B/32 vectors for drift and insights.

The model is optional — a CPU-only or offline install simply reports `available() == False` and
callers fall back to their own cheap features. When Task 20a's `insights_embedding` module is
importable its loaded backend is reused, so the process holds at most one CLIP model; vectors are
cached per sha256 in this seam's own `clip-full` namespace (20a caches 64 px thumbnails, this seam
embeds the full frame). `LD_CLIP=0` forces the fallback (deterministic tests).

The backend is a scheduler lease: a CUDA load goes through `app.gpu.scheduler`, so the VRAM ledger
counts it and training's exclusive lease unloads it like any other model. The lease is optional
(`evict=False`): a load that would need to displace a live model is skipped instead, so a missing or
failing CLIP never costs another model its place. A CPU-only install needs no VRAM and is pinned to
the CPU by 20a's `clip_available()`. `release()` (called from the drift and active-learning jobs)
drops the lease and 20a's cached copy, so CLIP never outlives the work that loaded it; it is
idempotent and waits for an in-flight `embed_image` before unloading.
"""

import logging
import os
import threading

import numpy as np
from PIL import Image as PImage

from ..config import DATA_DIR

log = logging.getLogger(__name__)

CLIP_MODEL_ID = "openai/clip-vit-base-patch32"
FEATURE_DIR = DATA_DIR / "embeddings" / "clip"
LEASE_KEY = "clip-embeddings"
VRAM_MB = 900  # ViT-B/32 fp32, upper end of spec 3.6
_LOCK = threading.RLock()
_COND = threading.Condition(_LOCK)  # _LOCK + the in-flight counter, so release() waits for the last user
_STATE: tuple | bool | None = None  # None = untried, False = unavailable, else (torch, model, processor, device)
_INFLIGHT = 0  # embed_image calls holding the current backend
_RELEASING = False  # release() is unloading: new uses wait until the lease is gone


def _insights():
    """Task 20a's embedding module when it is installed; None on the plain API-only install."""
    try:
        from . import insights_embedding
    except Exception:  # noqa: BLE001 - the module is optional
        return None
    return insights_embedding


def _own_clip() -> tuple | None:
    """(torch, model, processor, device) or None; the same weights the insights map uses."""
    try:
        import torch
        from transformers import CLIPModel, CLIPProcessor

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = CLIPModel.from_pretrained(CLIP_MODEL_ID)
        processor = CLIPProcessor.from_pretrained(CLIP_MODEL_ID)
        model.eval()
        model.to(device)
    except Exception:  # noqa: BLE001 - not installed, offline or out of memory
        log.info("CLIP embeddings are not available; callers fall back to cheap features", exc_info=True)
        return None
    return (torch, model, processor, device)


def _load_clip() -> tuple | None:
    """Lease loader: reuse Task 20a's backend when it exists, else load our own copy."""
    insights = _insights()
    if insights is not None:
        try:
            return insights._clip_backend()
        except Exception:  # noqa: BLE001 - a broken 20a install must not break drift
            log.info("Task 20a could not load CLIP; callers fall back to cheap features", exc_info=True)
            return None
    return _own_clip()


def _drop_clip(_state=None) -> None:
    """Scheduler unloader: forget the model here and in Task 20a so no stale tuple keeps it alive.

    Runs inside the scheduler lock (eviction), so it must never take `_COND`: `_backend()` holds
    `_COND` while calling the scheduler. `release()` is the coordinated path that waits for the last
    in-flight embed before the lease is evicted.
    """
    global _STATE
    _STATE = None
    insights = _insights()
    if insights is not None:
        try:
            insights.release_clip()
        except Exception:  # noqa: BLE001 - releasing must never raise
            log.debug("Task 20a release_clip failed", exc_info=True)
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:  # noqa: BLE001 - torch missing: nothing was placed on a card
        pass


def _cuda_expected() -> bool:
    """True when loading CLIP will place it on CUDA, i.e. it needs a lease in the ledger."""
    if isinstance(_STATE, tuple):
        return _STATE[3] == "cuda"
    insights = _insights()
    probe = getattr(insights, "clip_available", None)
    if probe is not None:
        try:
            return bool(probe())
        except Exception:  # noqa: BLE001 - an unknown backend is treated as CPU-only
            return False
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001 - no torch: the load will fail into the fallback
        return False


def _backend() -> tuple | None:
    """The loaded CLIP backend; a CUDA model is held as a scheduler lease (evictable by training).

    Call only while holding `_COND`: the lease and `_STATE` must change together.
    """
    global _STATE
    if _STATE is not None:
        return _STATE or None
    if _cuda_expected():
        try:
            from ..gpu import scheduler  # lazy: app.gpu imports the adapters package

            # optional lease: never displace a live model for an embedder that may not even load
            state = scheduler.lease(LEASE_KEY, VRAM_MB, _load_clip, _drop_clip, evict=False)
        except Exception:  # noqa: BLE001 - GpuBusy is transient: never cache "unavailable"
            log.info("CLIP embeddings are waiting for the GPU; using cheap features this run")
            return None
    else:
        state = _load_clip()  # CPU-pinned: no VRAM to account for
    _STATE = state or False
    return _STATE or None


def _begin_use() -> tuple | None:
    """Take an in-flight reference to the backend; `release()` waits for these to drain."""
    global _INFLIGHT
    with _COND:
        while _RELEASING:
            _COND.wait()
        state = _backend()
        if state is None:
            return None
        _INFLIGHT += 1
        return state


def _end_use() -> None:
    global _INFLIGHT
    with _COND:
        _INFLIGHT -= 1
        if _INFLIGHT == 0:
            _COND.notify_all()


def release() -> None:
    """Drop the shared backend once: evict the lease or release Task 20a's copy, never both.

    Safe to call twice (a second call is a no-op) and while an embed is running: it waits for the
    last in-flight `embed_image`, then evicts, so a request never loses the model mid-inference.
    """
    global _RELEASING, _STATE
    with _COND:
        while _INFLIGHT:
            _COND.wait()
        loaded = isinstance(_STATE, tuple)
        _RELEASING = True
    try:
        had_lease = False
        try:
            from ..gpu import scheduler

            had_lease = bool(scheduler.release(LEASE_KEY))
        except Exception:  # noqa: BLE001 - no scheduler (tests, import order): still drop the model
            log.debug("could not release the CLIP GPU lease", exc_info=True)
        if had_lease:
            _STATE = None  # the lease unloader (_drop_clip) already dropped the model
        elif loaded and isinstance(_STATE, tuple):
            _drop_clip()  # CPU-pinned backend, or the lease was already evicted elsewhere
    finally:
        with _COND:
            _RELEASING = False
            _COND.notify_all()


def available() -> bool:
    """True when `embed_image` can run (cheap: no model load, just the module/flag check)."""
    if os.environ.get("LD_CLIP", "auto") == "0":
        return False
    if isinstance(_STATE, tuple):
        return True
    if _STATE is False:
        return False
    if _insights() is not None:
        return True
    return _importable("torch") and _importable("transformers")


def _importable(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _cache_path(sha: str):
    insights = _insights()
    if insights is not None:
        # "clip-full" (not 20a's "clip"): this seam embeds the full frame, 20a a 64 px thumbnail.
        return insights._feature_path("clip-full", sha)
    return FEATURE_DIR / sha[:2] / f"{sha}.npy"


def _load_cached(sha: str) -> list[float] | None:
    insights = _insights()
    if insights is not None:
        vector = insights._load_feature("clip-full", sha)
        return [float(v) for v in vector] if vector is not None else None
    try:
        return [float(v) for v in np.load(_cache_path(sha))]
    except Exception:  # noqa: BLE001 - missing/corrupt cache entry: recompute
        return None


def _store_cached(sha: str, vector: np.ndarray) -> None:
    insights = _insights()
    if insights is not None:
        insights._store_feature("clip-full", sha, vector)
        return
    try:
        path = _cache_path(sha)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(path, vector)
    except Exception:  # noqa: BLE001 - an unwritable cache must not lose the vector
        log.debug("could not cache the CLIP vector for %s", sha, exc_info=True)


def embed_image(im: PImage.Image, sha: str | None = None) -> list[float]:
    """One L2-normalised CLIP vector (list of float); `sha` enables the shared per-image cache.

    Raises when CLIP is not installed — callers keep their own fallback so a missing encoder only
    costs quality, never the job.
    """
    if sha:
        cached = _load_cached(sha)
        if cached is not None:
            return cached
    state = _begin_use()
    if state is None:
        raise RuntimeError("CLIP embeddings are not available")
    try:
        torch, model, processor, device = state
        inputs = processor(images=[im.convert("RGB")], return_tensors="pt")
        inputs = {name: value.to(device) for name, value in inputs.items()}
        with torch.no_grad():
            out = model.get_image_features(**inputs)
        vector = out.detach().cpu().numpy().astype(np.float32)[0]
        norm = float(np.linalg.norm(vector)) or 1.0
        vector = vector / norm
    finally:
        _end_use()
    if sha:
        _store_cached(sha, vector)
    return [float(v) for v in vector]
