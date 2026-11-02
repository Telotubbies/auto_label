"""GPU VRAM ledger: LRU model leases and exclusive training (spec 3.6).

One API process sees every loaded model, so a single in-process scheduler can
keep the 12 GB card safe: vLLM caps itself at 6.6 GB, and the remaining budget
(default 4.5 GB) is shared by SAM 3.1 and inference models.
"""
from __future__ import annotations

import logging
import os
import threading
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Iterator

from .adapters.base import ADAPTERS

if TYPE_CHECKING:
    from .adapters.vlm_ad import VlmAdapter

log = logging.getLogger("labeldesk.gpu")


class GpuBusy(RuntimeError):
    """A model lease was refused because something else holds the GPU."""


def gpu_label(holder: str | None, vlm_sleeping: bool | None) -> str:
    """Human-readable badge text for GET /api/gpu (the web GpuBadge renders `label` verbatim)."""
    if holder:
        return f"GPU: {holder}"
    if vlm_sleeping:
        return "vLLM asleep"
    return "GPU idle"


@dataclass
class _Lease:
    obj: Any
    vram_mb: int
    unloader: Callable[[Any], None]


class GpuScheduler:
    def __init__(self, budget_mb: int, vlm: "VlmAdapter | None" = None):
        self.budget_mb = int(budget_mb)
        self.vlm = vlm
        self._leases: "OrderedDict[str, _Lease]" = OrderedDict()     # oldest first
        self._used_mb = 0
        self.holder: str | None = None
        self.vlm_stopped = False                                     # sleep failed: training continued anyway
        self._vlm_sleeping: bool | None = None
        self._pause: Callable[[], None] = lambda: None
        self._resume: Callable[[], None] = lambda: None
        self._lock = threading.RLock()
        self._local = threading.local()                              # training_scope marker

    @property
    def vlm_sleeping(self) -> bool | None:
        return self._vlm_sleeping

    def register_pause_hooks(self, pause: Callable[[], None], resume: Callable[[], None]) -> None:
        """StreamManager wires pause_all/resume_all here in Task 10; no-op until then."""
        self._pause, self._resume = pause, resume

    # ---- leases
    def lease(self, key: str, vram_mb: int, loader: Callable[[], Any],
              unloader: Callable[[Any], None], *, evict: bool = True) -> Any:
        """Return the cached object for `key`, loading it after LRU-evicting other leases.

        `evict=False` is for optional models: they may only use free ledger room and are refused
        with GpuBusy when they would have to displace a live lease, so a failed optional load never
        costs another model. A loader that returns None loaded nothing: no VRAM is charged for it.
        """
        with self._lock:
            # the holder check comes before the cache hit: while training owns the card, API requests
            # must get GpuBusy even if evaluation cached the very same model a moment ago
            if self.holder is not None and not getattr(self._local, "training", False):
                raise GpuBusy(f"GPU busy: {self.holder}")
            hit = self._leases.get(key)
            if hit is not None:
                self._leases.move_to_end(key)
                return hit.obj
            if vram_mb > self.budget_mb:
                raise RuntimeError(f"{key} needs {vram_mb} MiB but the GPU budget is {self.budget_mb} MiB")
            if evict:
                while self._used_mb + vram_mb > self.budget_mb:
                    self._evict(next(iter(self._leases)))
            elif self._used_mb + vram_mb > self.budget_mb:
                raise GpuBusy(f"GPU busy: no room for {key} in the {self.budget_mb} MiB budget")
            obj = loader()
            if obj is None:
                return None              # nothing was loaded, so nothing is leased or unloaded
            self._leases[key] = _Lease(obj, int(vram_mb), unloader)
            self._used_mb += int(vram_mb)
            return obj

    def _evict(self, key: str) -> None:
        lease = self._leases.pop(key)
        self._used_mb -= lease.vram_mb
        try:
            lease.unloader(lease.obj)
        except Exception:                    # an unloader must never corrupt the ledger
            log.exception("GPU unload failed for %s", key)

    def release(self, key: str) -> bool:
        """Unload one lease now (an optional model that must not outlive the job that loaded it).

        Returns True when a lease was released, so a caller can unload the model exactly once.
        """
        with self._lock:
            if key not in self._leases:
                return False
            self._evict(key)
            return True

    def state(self) -> dict:
        with self._lock:
            return {"used_mb": self._used_mb, "budget_mb": self.budget_mb, "holder": self.holder,
                    "leases": [{"key": k, "vram_mb": l.vram_mb} for k, l in self._leases.items()]}

    # ---- exclusive access (training)
    @contextmanager
    def training_scope(self) -> Iterator[None]:
        """Let the training thread load models through the normal lease path.

        Training evaluates the model it just produced while it still owns the card. Only this
        thread-local scope bypasses the holder check, so API requests keep getting GpuBusy.
        """
        previous = getattr(self._local, "training", False)
        self._local.training = True
        try:
            yield
        finally:
            self._local.training = previous

    @contextmanager
    def exclusive(self, reason: str) -> Iterator[None]:
        """Unload every model, pause streams and put vLLM to sleep while `reason` owns the GPU."""
        with self._lock:
            if self.holder is not None:
                raise RuntimeError(f"GPU is already held by {self.holder}")
            for key in list(self._leases):
                self._evict(key)
            self.holder = reason
            self.vlm_stopped = False
        self._run_hook(self._pause, "pause streams")
        if self.vlm is not None:
            try:
                self.vlm.sleep(1)
                self._vlm_sleeping = True
            except Exception as e:            # vLLM down / sleep unsupported: train anyway (spec 3.6 fallback)
                self.vlm_stopped = True
                self._vlm_sleeping = False
                log.warning("vLLM sleep failed during %s: %s", reason, e)
        try:
            yield
        finally:
            if self.vlm is not None:
                try:
                    self.vlm.wake()
                    self._vlm_sleeping = False
                except Exception as e:
                    log.warning("vLLM wake failed after %s: %s", reason, e)
            with self._lock:
                self.holder = None               # release before streams resume, so they can lease again
            self._run_hook(self._resume, "resume streams")

    @staticmethod
    def _run_hook(hook: Callable[[], None], what: str) -> None:
        try:
            hook()
        except Exception:
            log.exception("GPU scheduler could not %s", what)


# 4.5 GB left after vLLM's --gpu-memory-utilization 0.55 cap (spec 3.6). One process sees every
# loaded model, so this lives in the embedded worker (global constraint: single uvicorn, no reload).
def budget_from_env() -> int:
    return int(os.environ.get("LD_GPU_BUDGET_MB") or 4500)


scheduler = GpuScheduler(budget_mb=budget_from_env(), vlm=ADAPTERS.get("vlm"))
