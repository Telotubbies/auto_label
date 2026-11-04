"""Per-model runtime state for the Playground preflight (G1 / gap M1).

The answer reuses the run path's own sources — the registry (catalog plus the adapters' 15 s probe
cache), the GPU lease ledger and vLLM's sleep flag. It never loads a model and never echoes an
adapter reason: probe strings can contain machine paths.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..adapters import catalog, resolve
from ..config import DATA_DIR
from ..gpu import scheduler

READY = "ready"            # weights resident, a run starts immediately
COLD = "cold"              # available, but the first run loads the weights
LOADING = "loading"        # a load for this key is in flight right now
SLEEPING = "sleeping"      # vLLM is asleep; the run wakes it
GPU_BUSY = "gpu_busy"      # training (or another exclusive job) owns the card
UNAVAILABLE = "unavailable"  # no adapter, no weights, or not visible to this workspace

_MESSAGES = {
    READY: "Loaded and ready.",
    COLD: "Loads on the first run; the first result can be slower.",
    LOADING: "The weights are loading now. Try again in a moment.",
    SLEEPING: "The vision model is asleep. Try again to wake it.",
    GPU_BUSY: "The GPU is busy with another job. Try again when it finishes.",
}
_UNKNOWN = "Not available in this workspace."
_UNRUNNABLE = "Not available on this server right now."
_RETRY = {SLEEPING, GPU_BUSY}


def describe(ref: str, item: dict | None, *, lease_key: str | None, gpu: dict,
             vlm_sleeping: bool | None, missing_weights: bool = False) -> dict:
    """Map one registry item plus the scheduler snapshot to a state the Playground can explain."""
    if item is None or missing_weights:
        state = UNAVAILABLE
    elif not item.get("available"):
        state = UNAVAILABLE
    elif gpu.get("holder"):
        state = GPU_BUSY
    elif item.get("family") == "vlm" and vlm_sleeping:
        state = SLEEPING
    elif lease_key and lease_key in (gpu.get("loading") or ()):
        state = LOADING
    elif item.get("family") == "vlm" or _resident(lease_key, gpu):
        state = READY            # vLLM keeps its weights on the model server, outside our ledger
    else:
        state = COLD
    # "in this workspace" is only honest when the catalog did not list the ref at all.
    message = _MESSAGES.get(state) or (_UNKNOWN if item is None else _UNRUNNABLE)
    return {"ref": ref, "state": state, "message": message, "retry": state in _RETRY}


def _resident(lease_key: str | None, gpu: dict) -> bool:
    return bool(lease_key) and any(lease.get("key") == lease_key for lease in gpu.get("leases") or ())


def preflight(db: Session, workspace_id: str, refs: list[str]) -> list[dict]:
    """Describe each ref in the order the caller picked them."""
    items = {item["ref"]: item for item in catalog(db, workspace_id)}
    gpu = {**scheduler.state(), "loading": scheduler.inflight()}
    sleeping = scheduler.vlm_sleeping
    out = []
    for ref in refs:
        item = items.get(ref)
        key = None
        missing = False
        if item is not None and item.get("available"):
            try:
                resolved = resolve(ref, db, workspace_id=workspace_id)
                if ref.startswith("trained:") and not _weights_present(resolved.weights):
                    missing = True   # the catalog only probes the family; this model has no weights
                else:
                    runtime_key = getattr(resolved.adapter, "runtime_key", None)
                    key = runtime_key(resolved.variant, resolved.weights) if runtime_key else None
            except ValueError:
                item = None          # resolve() rejected it: treat it exactly like an unknown ref
        out.append(describe(ref, item, lease_key=key, gpu=gpu, vlm_sleeping=sleeping,
                            missing_weights=missing))
    return out


def _weights_present(weights: str | None) -> bool:
    """A checkpoint is a file; HF training saves models/<id>/ as a directory with config.json."""
    if not weights:
        return False
    path = DATA_DIR / weights
    return path.is_file() or (path.is_dir() and (path / "config.json").is_file())
