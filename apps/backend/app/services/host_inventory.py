"""Host inventory: what each worker reports about its own machine.

The report comes from a host, so it is an input boundary, not trusted config: :func:`sanitise`
keeps the known keys, caps every list, truncates every string and drops non-finite numbers before
the row is written. A report carries engine/model **ids**, byte sizes and a token-present boolean
— never a path and never a secret.
"""
import math

from sqlalchemy import select

from ..config import WORKER_STALE_S
from ..models import Worker, now
from . import heartbeat

MAX_GPUS = 8
MAX_ENGINES = 8
MAX_MODELS = 200
MAX_TEXT = 120
MAX_REASONS = 8                                  # one per probe the worker runs
_NUMBERS = frozenset({"vram_mb", "bytes", "models_free_gb", "models_total_gb"})
_LISTS = (("gpus", ("name", "vram_mb", "driver", "cuda"), MAX_GPUS),
          ("engines", ("id", "version", "runtime", "ok", "bytes"), MAX_ENGINES),
          ("models", ("id", "variant", "bytes"), MAX_MODELS))


def _text(value) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip()[:MAX_TEXT] or None


def _num(value) -> int | float | None:
    """A finite number; a bool or NaN is not something a host may report."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) else None


def _records(items, keys: tuple[str, ...], cap: int) -> list[dict]:
    rows = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        row = {}
        for key in keys:
            value = item.get(key)
            if key in _NUMBERS:
                value = _num(value)
            elif key == "ok":
                value = value if isinstance(value, bool) else None
            else:
                value = _text(value)
            if value is not None:
                row[key] = value
        if row:
            rows.append(row)
        if len(rows) >= cap:
            break
    return rows


def _disk(value) -> dict | None:
    if not isinstance(value, dict):
        return None
    out = {key: num for key in ("models_free_gb", "models_total_gb")
           if (num := _num(value.get(key))) is not None}
    return out or None


def _reasons(value) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    out = {}
    for key, why in list(value.items())[:MAX_REASONS]:
        if (text := _text(why)) is not None:
            out[str(key)[:32]] = text
    return out


def sanitise(inventory) -> dict | None:
    """The known, bounded part of a worker report; None when the payload is not an object."""
    if not isinstance(inventory, dict):
        return None
    out = {key: text for key in ("os", "arch", "python", "cuda")
           if (text := _text(inventory.get(key))) is not None}
    for key in ("hf_token", "allow_install"):
        if isinstance(inventory.get(key), bool):
            out[key] = inventory[key]
    if (disk := _disk(inventory.get("disk"))) is not None:
        out["disk"] = disk
    for key, keys, cap in _LISTS:
        if isinstance(inventory.get(key), list):    # an empty list is a fact: "CPU only", "none installed"
            out[key] = _records(inventory[key], keys, cap)
    if reasons := _reasons(inventory.get("reasons")):
        out["reasons"] = reasons
    return out


def record(db, worker_id: str, host: str, inventory: dict | None) -> None:
    """Upsert the host row from a claim; a worker that sends nothing keeps its last report."""
    wid = (worker_id or "worker")[:80]
    w = db.get(Worker, wid)
    if w is None:
        w = Worker(id=wid, host=(host or "")[:120], started=now())
        db.add(w)
    w.host = (host or "")[:120]
    w.last_seen = now()
    if (clean := sanitise(inventory)) is not None:
        w.inventory = clean
    db.commit()


def hosts(db, stale_after: float = WORKER_STALE_S) -> list[dict]:
    """Every host with its inventory, online first and then by name."""
    reported = dict(db.execute(select(Worker.id, Worker.inventory)).all())
    rows = [{**w, "inventory": reported.get(w["id"])} for w in heartbeat.workers(db, stale_after)]
    return sorted(rows, key=lambda r: (not r["online"], r["host"] or r["id"]))
