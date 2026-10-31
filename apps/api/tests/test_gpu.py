"""GPU scheduler: VRAM leases, LRU eviction, exclusive training, probe cache, /api/gpu."""
import os
import tempfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-test-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient

from app.adapters.base import Availability
from app.gpu import GpuScheduler, gpu_label
from app.main import app


class FakeVlm:
    def __init__(self, fail_sleep: bool = False, fail_wake: bool = False):
        self.calls: list[str] = []
        self.fail_sleep = fail_sleep
        self.fail_wake = fail_wake

    def sleep(self, level: int = 1):
        self.calls.append(f"sleep:{level}")
        if self.fail_sleep:
            raise RuntimeError("sleep failed")

    def wake(self):
        self.calls.append("wake")
        if self.fail_wake:
            raise RuntimeError("wake failed")


def test_lru_evicts_oldest():
    s = GpuScheduler(100, None)
    dropped: list[str] = []

    def load(name):
        return lambda: {"name": name}

    def drop(name):
        return lambda _obj: dropped.append(name)

    a = s.lease("a", 30, load("a"), drop("a"))
    s.lease("b", 30, load("b"), drop("b"))
    s.lease("c", 30, load("c"), drop("c"))
    assert s.lease("a", 30, load("a"), drop("a")) is a          # touching a refreshes its LRU slot
    s.lease("d", 30, load("d"), drop("d"))                       # 3 x 30 + 30 > 100: evict the LRU, b
    assert dropped == ["b"]
    assert [x["key"] for x in s.state()["leases"]] == ["c", "a", "d"]
    assert s.state()["used_mb"] == 90


def test_lease_larger_than_budget_raises():
    s = GpuScheduler(100, None)
    with pytest.raises(RuntimeError, match="budget"):
        s.lease("huge", 200, lambda: object(), lambda _o: None)


def test_exclusive_sleeps_and_wakes_vlm():
    vlm = FakeVlm()
    s = GpuScheduler(100, vlm)
    dropped: list[str] = []
    s.lease("model", 40, lambda: object(), lambda _o: dropped.append("model"))
    with s.exclusive("training rtdetr-l"):
        assert vlm.calls == ["sleep:1"]
        assert s.vlm_sleeping is True
        assert s.state()["used_mb"] == 0 and s.state()["leases"] == []
    assert vlm.calls == ["sleep:1", "wake"]
    assert s.vlm_sleeping is False
    assert dropped == ["model"]


def test_exclusive_pauses_and_resumes_streams():
    s = GpuScheduler(100, None)
    events: list[str] = []
    s.register_pause_hooks(lambda: events.append("pause"), lambda: events.append("resume"))
    with s.exclusive("training yolo26n"):
        assert events == ["pause"]
    assert events == ["pause", "resume"]


def test_exclusive_survives_sleep_failure():
    vlm = FakeVlm(fail_sleep=True)
    s = GpuScheduler(100, vlm)
    with s.exclusive("training yolo26n"):
        assert True                                                # training still runs
    assert s.vlm_stopped is True
    assert vlm.calls == ["sleep:1", "wake"]                       # wake is still attempted


def test_exclusive_survives_wake_failure():
    vlm = FakeVlm(fail_wake=True)
    s = GpuScheduler(100, vlm)
    with s.exclusive("training yolo26n"):
        pass
    assert s.state()["holder"] is None


def test_state_reports_holder():
    s = GpuScheduler(4500, None)
    assert s.state() == {"used_mb": 0, "budget_mb": 4500, "holder": None, "leases": []}
    s.lease("yolo", 1200, lambda: object(), lambda _o: None)
    st = s.state()
    assert st["used_mb"] == 1200 and st["leases"] == [{"key": "yolo", "vram_mb": 1200}]
    with s.exclusive("training rtdetr-l"):
        assert s.state()["holder"] == "training rtdetr-l"
    assert s.state()["holder"] is None


def test_lease_refused_while_exclusive():
    s = GpuScheduler(100, None)
    with s.exclusive("training yolo26n"):
        with pytest.raises(RuntimeError, match="busy"):
            s.lease("model", 10, lambda: object(), lambda _o: None)


def test_exclusive_is_not_reentrant():
    s = GpuScheduler(100, FakeVlm())
    with s.exclusive("outer"):
        with pytest.raises(RuntimeError, match="already held"):
            with s.exclusive("inner"):
                pass
    assert s.state()["holder"] is None


def test_unloader_failure_does_not_corrupt_ledger():
    def boom(_obj):
        raise RuntimeError("boom")

    s = GpuScheduler(100, None)
    s.lease("a", 30, lambda: object(), boom)
    s.lease("b", 80, lambda: object(), lambda _o: None)            # evicts a despite its broken unloader
    assert s.state()["used_mb"] == 80
    assert [x["key"] for x in s.state()["leases"]] == ["b"]


def test_exclusive_cleans_up_on_body_exception():
    vlm = FakeVlm()
    s = GpuScheduler(100, vlm)
    events: list[str] = []
    s.register_pause_hooks(lambda: events.append("pause"), lambda: events.append("resume"))
    with pytest.raises(ZeroDivisionError):
        with s.exclusive("training yolo26n"):
            1 / 0
    assert vlm.calls == ["sleep:1", "wake"]
    assert events == ["pause", "resume"]
    assert s.state()["holder"] is None


def test_gpu_label_examples():
    assert gpu_label(None, None) == "GPU idle"
    assert gpu_label("training rtdetr-l", None) == "GPU: training rtdetr-l"
    assert gpu_label(None, True) == "vLLM asleep"
    assert gpu_label("training rtdetr-l", True) == "GPU: training rtdetr-l"


def test_budget_from_env(monkeypatch):
    from app.gpu import budget_from_env
    monkeypatch.delenv("LD_GPU_BUDGET_MB", raising=False)
    assert budget_from_env() == 4500
    monkeypatch.setenv("LD_GPU_BUDGET_MB", "9999")
    assert budget_from_env() == 9999


def test_gpu_module_imports_first():
    import subprocess
    import sys
    from pathlib import Path
    api_root = Path(__file__).resolve().parents[1]
    r = subprocess.run([sys.executable, "-c", "import app.gpu; print(app.gpu.scheduler.budget_mb)"],
                       cwd=api_root, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().isdigit()


class _EmptyDb:
    def scalars(self, *_a, **_kw):
        return []


def test_catalog_caches_probes_for_15_seconds(monkeypatch):
    import importlib
    catalog_mod = importlib.import_module("app.adapters.catalog")   # the package exports the catalog *function*

    calls: list[str] = []

    class Fake:
        family = "ultralytics"

        def probe(self):
            calls.append("probe")
            return Availability(True)

        def capabilities(self, _variant):
            return {"detect"}

    clock = [100.0]
    monkeypatch.setattr(catalog_mod, "_now", lambda: clock[0])
    monkeypatch.setattr(catalog_mod, "_probes", {})
    monkeypatch.setattr(catalog_mod, "ADAPTERS", {"ultralytics": Fake()})
    catalog_mod.catalog(_EmptyDb(), "ws")
    clock[0] += 14.9
    catalog_mod.catalog(_EmptyDb(), "ws")                          # still cached
    assert len(calls) == 1
    clock[0] += 0.2                                                # 15.1 s: expired
    catalog_mod.catalog(_EmptyDb(), "ws")
    assert len(calls) == 2


def test_ultralytics_loads_through_scheduler(monkeypatch):
    from app import gpu
    from app.adapters import ultralytics_ad

    seen: dict = {}

    class FakeScheduler:
        def lease(self, key, vram_mb, _loader, _unloader):
            seen.update(key=key, vram_mb=vram_mb)
            return "loaded"

    monkeypatch.setattr(gpu, "scheduler", FakeScheduler())
    assert ultralytics_ad._load("yolo11n.pt", "YOLO") == "loaded"
    assert seen == {"key": "YOLO|yolo11n.pt", "vram_mb": ultralytics_ad.VRAM_MB}


def test_sam3_loads_through_scheduler(monkeypatch):
    from app import gpu
    from app.services import segment

    seen: dict = {}

    class FakeScheduler:
        def lease(self, key, vram_mb, _loader, _unloader):
            seen.update(key=key, vram_mb=vram_mb)
            return object()

    monkeypatch.setattr(gpu, "scheduler", FakeScheduler())
    monkeypatch.setattr(segment, "SAM_ENABLED", "1")
    assert segment.lease_sam() is not None
    assert seen == {"key": "sam3", "vram_mb": segment.SAM_VRAM_MB}


def test_exclusive_unloads_sam_loaded_by_segment(monkeypatch):
    from app import gpu
    from app.services import segment

    s = GpuScheduler(4500, None)
    unloaded: list[int] = []
    monkeypatch.setattr(gpu, "scheduler", s)
    monkeypatch.setattr(segment, "SAM_ENABLED", "1")
    monkeypatch.setattr(segment, "_load_sam", lambda: object())
    monkeypatch.setattr(segment, "unload_sam", lambda: unloaded.append(1))

    segment.lease_sam()
    assert s.state()["used_mb"] == segment.SAM_VRAM_MB
    with s.exclusive("training yolo26n"):
        assert s.state()["used_mb"] == 0
    assert unloaded == [1]


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        tok = c.post("/api/auth/login", json={"email": "demo@labeldesk.dev", "password": "demo1234"}).json()["token"]
        c.headers["Authorization"] = f"Bearer {tok}"
        yield c


def test_get_gpu_requires_login():
    with TestClient(app) as anon:
        assert anon.get("/api/gpu").status_code == 401


def test_get_gpu_reports_state(client, monkeypatch):
    from app.routers import registry

    vlm = FakeVlm()
    s = GpuScheduler(4500, vlm)
    monkeypatch.setattr(registry, "scheduler", s)
    s.lease("yolo26n", 1200, lambda: object(), lambda _o: None)

    body = client.get("/api/gpu").json()
    assert set(body) == {"label", "holder", "used_mb", "budget_mb", "leases", "vlm_sleeping"}
    assert body["label"] == "GPU idle" and body["holder"] is None
    assert body["used_mb"] == 1200 and body["budget_mb"] == 4500
    assert body["vlm_sleeping"] is None

    with s.exclusive("training rtdetr-l"):
        body = client.get("/api/gpu").json()
        assert body["holder"] == "training rtdetr-l"
        assert body["label"] == "GPU: training rtdetr-l"
        assert body["vlm_sleeping"] is True

    body = client.get("/api/gpu").json()
    assert body["label"] == "GPU idle" and body["vlm_sleeping"] is False
