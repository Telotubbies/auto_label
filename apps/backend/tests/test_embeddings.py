"""The shared CLIP seam: one lease in the GPU ledger, dropped when the job ends.

N2: monitoring embeddings used to load CLIP straight onto CUDA, outside `app.gpu.scheduler`, and
kept it in a module cache forever. Training could then start with a ledger that under-reported
VRAM, and Task 20a's `release_clip()` left a stale tuple that loaded a second CLIP on the next scan.
"""

import os
import tempfile
import threading

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-embed-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import numpy as np
import pytest
from PIL import Image as PImage

from app import gpu
from app.services import embeddings


class _Out:
    def __init__(self, arr):
        self.arr = arr

    def detach(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return self.arr


class _Model:
    def __init__(self, vector):
        self.arr = np.asarray([vector], dtype=np.float32)

    def get_image_features(self, **kw):
        return _Out(self.arr)


class _Tensor:
    def to(self, device):
        return self


class _Processor:
    def __call__(self, images, return_tensors):
        return {"pixel_values": _Tensor()}


class _Torch:
    class no_grad:
        def __enter__(self):
            return None

        def __exit__(self, *exc):
            return False


def _state(device="cuda", vector=(3.0, 4.0)):
    return (_Torch, _Model(vector), _Processor(), device)


class _Insights:
    """Task 20a's module as the seam sees it: a loader plus `release_clip()`."""

    def __init__(self, device="cuda"):
        self.device = device
        self.loads = 0
        self.releases = 0
        self.alive = 0

    def clip_available(self):
        return self.device == "cuda"

    def _clip_backend(self):
        if self.alive:
            raise AssertionError("a second CLIP was loaded while the first was still resident")
        self.loads += 1
        self.alive = 1
        return _state(self.device)

    def release_clip(self):
        self.releases += 1
        self.alive = 0


class _Scheduler:
    """The lease interface the seam relies on; one resident object per key, unload on release."""

    def __init__(self, budget_mb=4_500):
        self.leases = {}  # key -> (obj, unloader)
        self.vram = {}  # key -> MiB, only while leased
        self.budget_mb = budget_mb
        self.released = 0
        self.busy = False

    def lease(self, key, vram_mb, loader, unloader, *, evict=True):
        if self.busy:
            raise gpu.GpuBusy("GPU busy: training")
        if key in self.leases:
            return self.leases[key][0]
        if not evict and sum(self.vram.values()) + vram_mb > self.budget_mb:
            raise gpu.GpuBusy(f"GPU busy: no room for {key}")
        obj = loader()
        if obj is None:
            return None
        self.leases[key] = (obj, unloader)
        self.vram[key] = vram_mb
        return obj

    def release(self, key):
        hit = self.leases.pop(key, None)
        if hit is None:
            return False
        self.vram.pop(key, None)
        self.released += 1
        hit[1](hit[0])
        return True


@pytest.fixture(autouse=True)
def _fresh_seam():
    embeddings._STATE = None
    yield
    embeddings._STATE = None


def _install(monkeypatch, insights, scheduler):
    monkeypatch.setattr(embeddings, "_insights", lambda: insights)
    monkeypatch.setattr(gpu, "scheduler", scheduler)
    return insights


def test_clip_is_loaded_under_the_scheduler_lease(monkeypatch):
    """N2: the model the seam uses is registered in the VRAM ledger, not loaded behind it."""
    insights = _install(monkeypatch, _Insights(), _Scheduler())
    vector = embeddings.embed_image(PImage.new("RGB", (8, 8)))

    assert vector == pytest.approx([0.6, 0.8])
    assert insights.loads == 1
    assert gpu.scheduler.vram == {embeddings.LEASE_KEY: embeddings.VRAM_MB}


def test_release_evicts_the_lease_and_never_keeps_a_stale_model(monkeypatch):
    """N2: after `release()` (the job's finally) the next scan loads exactly one fresh model."""
    insights = _install(monkeypatch, _Insights(), _Scheduler())
    embeddings.embed_image(PImage.new("RGB", (8, 8)))
    assert insights.loads == 1

    embeddings.release()
    assert embeddings._STATE is None
    assert gpu.scheduler.leases == {}
    assert insights.releases >= 1

    embeddings.embed_image(PImage.new("RGB", (8, 8)))  # _clip_backend raises on a second resident model
    assert insights.loads == 2
    assert list(gpu.scheduler.leases) == [embeddings.LEASE_KEY]


def test_training_evicts_the_embedding_model_and_frees_the_ledger(monkeypatch):
    """N2: a training lease must unload CLIP, so the run does not start over budget."""

    class _Vlm:
        def __init__(self):
            self.slept = 0
            self.woke = 0

        def sleep(self, level=1):
            self.slept += 1

        def wake(self):
            self.woke += 1

    vlm = _Vlm()
    scheduler = gpu.GpuScheduler(budget_mb=2_000, vlm=vlm)
    insights = _install(monkeypatch, _Insights(), scheduler)
    embeddings.embed_image(PImage.new("RGB", (8, 8)))
    assert scheduler.state()["used_mb"] == embeddings.VRAM_MB

    with scheduler.exclusive("training yolo26n"):
        assert scheduler.state()["used_mb"] == 0
        assert embeddings._STATE is None
        assert insights.alive == 0

    assert vlm.slept == 1 and vlm.woke == 1
    embeddings.embed_image(PImage.new("RGB", (8, 8)))
    assert insights.loads == 2  # reloads through the lease instead of reusing a stale tuple
    assert scheduler.state()["used_mb"] == embeddings.VRAM_MB


def test_a_busy_gpu_falls_back_without_caching_an_unavailable_verdict(monkeypatch):
    """N2: GpuBusy during training is transient — the next scan may still use CLIP."""
    scheduler = _Scheduler()
    scheduler.busy = True
    _install(monkeypatch, _Insights(), scheduler)
    with pytest.raises(RuntimeError):
        embeddings.embed_image(PImage.new("RGB", (8, 8)))
    assert embeddings._STATE is None  # not False: a busy card is not "CLIP unavailable"


def test_vectors_do_not_share_20a_thumbnail_cache(monkeypatch):
    """N4: 20a embeds a 64 px thumbnail, this seam the full frame — separate cache namespaces."""
    backends: list[str] = []

    class _CachedInsights(_Insights):
        def _feature_path(self, backend, sha):
            backends.append(backend)
            return "/nonexistent"

        def _load_feature(self, backend, sha):
            backends.append(backend)
            return None

        def _store_feature(self, backend, sha, vector):
            backends.append(backend)

    _install(monkeypatch, _CachedInsights(), _Scheduler())
    embeddings.embed_image(PImage.new("RGB", (8, 8)), sha="deadbeef")
    assert backends and set(backends) == {"clip-full"}


def test_a_failed_cuda_load_never_leases_vram(monkeypatch):
    """R2-1: a loader that produced nothing must not be registered in the VRAM ledger."""
    scheduler = gpu.GpuScheduler(budget_mb=4_500, vlm=None)
    unloaded: list[str] = []
    scheduler.lease("sam", 1_200, lambda: object(), lambda _obj: unloaded.append("sam"))

    class _Dead(_Insights):
        def _clip_backend(self):
            self.loads += 1
            return None

    dead = _install(monkeypatch, _Dead(), scheduler)
    with pytest.raises(RuntimeError, match="not available"):
        embeddings.embed_image(PImage.new("RGB", (8, 8)))

    state = scheduler.state()
    assert dead.loads == 1
    assert unloaded == []  # a live model is not evicted for a load that failed
    assert [x["key"] for x in state["leases"]] == ["sam"]
    assert state["used_mb"] == 1_200  # no phantom 900 MiB clip lease
    assert embeddings._STATE is False  # the dead backend is not retried for every image


def test_an_optional_lease_never_evicts_a_live_model(monkeypatch):
    """R2-1: a CLIP load that needs eviction is refused; the resident model stays leased."""
    scheduler = gpu.GpuScheduler(budget_mb=2_000, vlm=None)
    unloaded: list[str] = []
    scheduler.lease("sam", 1_200, lambda: object(), lambda _obj: unloaded.append("sam"))
    insights = _install(monkeypatch, _Insights(), scheduler)

    with pytest.raises(RuntimeError, match="not available"):
        embeddings.embed_image(PImage.new("RGB", (8, 8)))

    assert unloaded == []
    assert insights.loads == 0  # never loaded: there was no room without displacing sam
    assert [x["key"] for x in scheduler.state()["leases"]] == ["sam"]
    assert scheduler.state()["used_mb"] == 1_200
    assert embeddings._STATE is None  # transient: a busy card is not "CLIP unavailable"


def test_release_is_idempotent(monkeypatch):
    """R2-2: the job's finally may run twice without unloading the backend twice."""
    insights = _install(monkeypatch, _Insights(), _Scheduler())
    embeddings.embed_image(PImage.new("RGB", (8, 8)))

    embeddings.release()
    assert insights.releases == 1

    embeddings.release()
    assert insights.releases == 1


def test_release_waits_for_an_in_flight_embed(monkeypatch):
    """R2-3: a job's finally must not unload the model under an embed that is still using it."""
    inferring = threading.Event()
    finish = threading.Event()

    class _SlowModel(_Model):
        def get_image_features(self, **kwargs):
            inferring.set()
            assert finish.wait(5)
            return super().get_image_features(**kwargs)

    class _SlowInsights(_Insights):
        def _clip_backend(self):
            self.loads += 1
            self.alive = 1
            return (_Torch, _SlowModel((3.0, 4.0)), _Processor(), self.device)

    insights = _install(monkeypatch, _SlowInsights(), _Scheduler())
    vectors: list = []
    embedder = threading.Thread(target=lambda: vectors.append(embeddings.embed_image(PImage.new("RGB", (8, 8)))))
    embedder.start()
    assert inferring.wait(5)

    release_started = threading.Event()
    release_done = threading.Event()

    def _release():
        release_started.set()
        embeddings.release()
        release_done.set()

    releaser = threading.Thread(target=_release)
    releaser.start()
    try:
        assert release_started.wait(5)
        assert release_done.wait(0.2) is False, "release() unloaded the model while an embed was in flight"
        assert insights.releases == 0
    finally:
        finish.set()
        embedder.join(5)
        releaser.join(5)

    assert vectors and vectors[0] == pytest.approx([0.6, 0.8])
    assert insights.releases == 1
    assert embeddings._STATE is None
