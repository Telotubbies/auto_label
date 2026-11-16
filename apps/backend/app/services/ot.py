"""PLC / OT reject-signal dispatch with a latency budget and a fail-safe release.

A stream rule firing produces a short pulse on one binary output. The contract is:

* assert the signal only when the event is younger than the output's latency budget;
* measure event-to-assert latency (queueing included) and report ``late`` rather than
  pretending a missed part was rejected;
* always return the line to the de-energised (fail-safe) level, including after
  transport errors; never raise into the stream worker.

``dispatch_event`` is the seam the stream worker calls with the same event dict the rule
engine returns (``rule`` fields merged in, so ``class`` is available for filtering).
"""
from __future__ import annotations

import ipaddress
import logging
import queue
import socket
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config, models
from ..db import SessionLocal
from ..ot import drivers
from . import flags

log = logging.getLogger("labeldesk.ot")

PROTOCOLS = ("modbus", "opcua", "mqtt", "gpio")
EVENT_KINDS = ("count", "zone", "line", "dwell", "vlm")
DEFAULT_LATENCY_BUDGET_MS = 250
DEFAULT_PULSE_MS = 100
MIN_LATENCY_BUDGET_MS, MAX_LATENCY_BUDGET_MS = 10, 10_000
MIN_PULSE_MS, MAX_PULSE_MS = 10, 5_000


def _now() -> float:
    return time.time()


def _mono() -> float:
    return time.monotonic()


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


@dataclass(frozen=True)
class Result:
    """Outcome of one pulse attempt; status is ok, late or failed."""

    status: str
    latency_ms: int | None
    detail: str = ""


def _bounded_int(value, low: int, high: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{label} must be an integer between {low} and {high}")
    return value


def _text(value, label: str, max_len: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} is required")
    text = value.strip()
    if not text or len(text) > max_len:
        raise ValueError(f"{label} must be 1-{max_len} characters")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise ValueError(f"{label} must not contain control characters")
    return text


def _host(value) -> str:
    host = _text(value, "host", 253)
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in host):
        raise ValueError("host must not contain whitespace or control characters")
    return host


def _only(endpoint: dict, allowed: set[str]) -> None:
    extra = set(endpoint) - allowed
    if extra:
        raise ValueError(f"unknown endpoint fields: {sorted(extra)}")


def validate_endpoint(protocol: str, endpoint: dict) -> dict:
    """Validate and normalise one protocol endpoint; returns a fresh dict."""
    if protocol not in PROTOCOLS:
        raise ValueError(f"protocol must be one of {list(PROTOCOLS)}")
    if not isinstance(endpoint, dict):
        raise ValueError("endpoint must be an object")

    if protocol == "modbus":
        _only(endpoint, {"host", "port", "unit_id", "register", "address"})
        register = endpoint.get("register", "coil")
        if register not in ("coil", "holding"):
            raise ValueError("register must be coil or holding")
        return {
            "host": _host(endpoint.get("host")),
            "port": _bounded_int(endpoint.get("port", 502), 1, 65535, "port"),
            "unit_id": _bounded_int(endpoint.get("unit_id", 1), 1, 247, "unit_id"),
            "register": register,
            "address": _bounded_int(endpoint.get("address"), 0, 65535, "address"),
        }

    if protocol == "mqtt":
        _only(endpoint, {"host", "port", "topic"})
        topic = _text(endpoint.get("topic"), "topic", 256)
        if any(ch in topic for ch in ("+", "#")) or any(ord(ch) < 32 or ord(ch) == 127 for ch in topic):
            raise ValueError("topic must not contain wildcards or control characters")
        return {
            "host": _host(endpoint.get("host")),
            "port": _bounded_int(endpoint.get("port", 1883), 1, 65535, "port"),
            "topic": topic,
        }

    if protocol == "opcua":
        _only(endpoint, {"endpoint_url", "node_id"})
        url = _text(endpoint.get("endpoint_url"), "endpoint_url", 512)
        parts = urlsplit(url)
        if parts.scheme != "opc.tcp" or not parts.netloc:
            raise ValueError("endpoint_url must be an opc.tcp://host URL")
        if parts.username or parts.password:
            raise ValueError("endpoint_url must not embed credentials")
        return {"endpoint_url": url, "node_id": _text(endpoint.get("node_id"), "node_id", 256)}

    _only(endpoint, {"line", "active_high"})
    active_high = endpoint.get("active_high", True)
    if not isinstance(active_high, bool):
        raise ValueError("active_high must be true or false")
    return {
        "line": _bounded_int(endpoint.get("line"), 0, 1023, "line"),
        "active_high": active_high,
    }


def validate_event_filter(value: dict | None) -> dict:
    """Normalise ``{"kinds": [...], "classes": [...]}``; an empty filter matches every event."""
    if value is None:
        return {"kinds": [], "classes": []}
    if not isinstance(value, dict):
        raise ValueError("event_filter must be an object")
    extra = set(value) - {"kinds", "classes"}
    if extra:
        raise ValueError(f"unknown event_filter fields: {sorted(extra)}")

    kinds = value.get("kinds") or []
    if not isinstance(kinds, list) or any(k not in EVENT_KINDS for k in kinds):
        raise ValueError(f"kinds must be a subset of {list(EVENT_KINDS)}")
    classes = value.get("classes") or []
    if not isinstance(classes, list) or len(classes) > 64:
        raise ValueError("classes must be a list of at most 64 names")
    names = []
    for name in classes:
        clean = _text(name, "class", 120)
        if clean not in names:
            names.append(clean)
    return {"kinds": list(dict.fromkeys(kinds)), "classes": names}


def check_limits(name: str, latency_budget_ms: int, pulse_ms: int) -> tuple[str, int, int]:
    """Validate the shared output fields and return them normalised."""
    return (_text(name, "name", 120),
            _bounded_int(latency_budget_ms, MIN_LATENCY_BUDGET_MS, MAX_LATENCY_BUDGET_MS, "latency_budget_ms"),
            _bounded_int(pulse_ms, MIN_PULSE_MS, MAX_PULSE_MS, "pulse_ms"))


def check_target(protocol: str, endpoint: dict) -> None:
    """Refuse a target outside ``LD_OT_ALLOW_CIDR``.

    An admin-supplied host makes the API open a TCP connection and report the outcome through
    ``last_status``, so an unguarded output is a blind SSRF oracle into the LAN. Every resolved
    address must sit inside the operator's allowlist, which is empty by default: no target is
    reachable until an operator names the plant network.
    """
    if protocol == "gpio":
        return                                      # the path is confined to LD_GPIO_ROOT instead
    if protocol == "opcua":
        host, port = urlsplit(endpoint["endpoint_url"]).hostname or "", 4840
    else:
        host, port = endpoint["host"], endpoint["port"]
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise ValueError(f"cannot resolve {host}") from e
    allow = config.OT_ALLOW_CIDR                    # read at call time so a test can narrow it
    blocked = []
    for *_, addr in infos:
        ip = ipaddress.ip_address(addr[0])
        if not any(ip in net for net in allow):
            blocked.append(str(ip))
    if blocked:
        shown = ", ".join(str(net) for net in allow) or "none"
        # shortcut: the target is vetted at save time only, so a hostname later re-pointed at
        # another network is not re-checked; upgrade if outputs ever take an untrusted name.
        raise ValueError(f"OT target must be inside LD_OT_ALLOW_CIDR; currently {shown}")


def matches(output: models.OtOutput, event: dict) -> bool:
    """True when this output is allowed to actuate for the event.

    A class filter never matches an event without a known class: an unidentified object must
    not trip a reject gate.
    """
    rules = output.event_filter if isinstance(output.event_filter, dict) else {}
    kinds = rules.get("kinds") or []
    classes = rules.get("classes") or []
    if kinds and event.get("kind") not in kinds:
        return False
    if classes:
        return bool(event.get("class")) and event["class"] in classes
    return True


_OUTPUT_LOCKS: dict[str, threading.Lock] = {}
_OUTPUT_LOCKS_GUARD = threading.Lock()


def output_lock(output_id: str) -> threading.Lock:
    """One lock per output: a second pulse must not cut the first one's reject window short."""
    with _OUTPUT_LOCKS_GUARD:
        return _OUTPUT_LOCKS.setdefault(output_id, threading.Lock())


def _safe_release(protocol: str, endpoint: dict, write: Callable) -> bool:
    """Best-effort fail-safe release; returns False when the line may still be asserted.

    A second transport failure must not escape into the stream worker, but it must not be
    hidden either: the caller reports ``failed`` instead of claiming a clean late signal.
    """
    try:
        write(protocol, endpoint, False, timeout=drivers.TIMEOUT_S)
        return True
    except drivers.DriverError as e:
        log.warning("OT fail-safe release failed for %s: %s", protocol, e)
    except Exception as e:
        log.error("OT fail-safe release raised %s", type(e).__name__)
    return False


def deliver(protocol: str, endpoint: dict, *, budget_ms: int, pulse_ms: int, event_ts: float,
            write: Callable | None = None, wall: Callable[[], float] | None = None,
            mono: Callable[[], float] | None = None, sleep: Callable[[float], None] | None = None) -> Result:
    """Send one reject pulse and always leave the output de-energised.

    ``latency_ms`` is event-to-assert time, not the pulse duration; a signal that misses its
    budget is released immediately and reported ``late``. The assert wait is capped by the
    remaining budget so a black-holed PLC cannot actuate after the part has passed.
    """
    write = write or drivers.write
    wall = wall or _now
    mono = mono or _mono
    sleep = sleep or _sleep

    start = mono()
    age_ms = max(0.0, (wall() - event_ts) * 1000.0)
    if age_ms > budget_ms:
        released = _safe_release(protocol, endpoint, write)
        detail = "fail-safe write failed" if not released else "event older than the latency budget"
        return Result("late" if released else "failed", int(round(age_ms)), detail)

    remaining_s = max(0.01, (budget_ms - age_ms) / 1000.0)
    try:
        write(protocol, endpoint, True, timeout=remaining_s)
    except drivers.DriverError as e:
        elapsed = age_ms + (mono() - start) * 1000.0
        released = _safe_release(protocol, endpoint, write)
        detail = str(e) if released else f"{e}; fail-safe write failed"
        return Result("failed", int(round(elapsed)), detail)
    except Exception as e:
        elapsed = age_ms + (mono() - start) * 1000.0
        released = _safe_release(protocol, endpoint, write)
        log.error("OT driver raised unexpectedly (%s)", type(e).__name__)
        detail = "driver error" if released else "driver error; fail-safe write failed"
        return Result("failed", int(round(elapsed)), detail)

    latency_ms = int(round(age_ms + (mono() - start) * 1000.0))
    if latency_ms > budget_ms:
        released = _safe_release(protocol, endpoint, write)
        detail = "signal exceeded the latency budget" if released else "fail-safe write failed"
        return Result("late" if released else "failed", latency_ms, detail)

    if pulse_ms:
        sleep(pulse_ms / 1000.0)
    try:
        write(protocol, endpoint, False, timeout=drivers.TIMEOUT_S)
    except drivers.DriverError as e:
        log.error("OT fail-safe release failed for %s: %s", protocol, e)
        return Result("failed", latency_ms, f"fail-safe write failed: {e}")
    except Exception as e:
        log.error("OT fail-safe release raised %s", type(e).__name__)
        return Result("failed", latency_ms, "fail-safe write failed")
    return Result("ok", latency_ms, "")


def record_delivery(db: Session, output: models.OtOutput, event: dict, result: Result, *,
                    stream_id: str = "") -> models.OtDelivery:
    """Persist one attempt and update the output's last-known health (caller commits)."""
    created = _now()
    output.last_status = result.status
    output.last_latency_ms = result.latency_ms
    output.last_error = result.detail[:500]
    output.updated = created
    delivery = models.OtDelivery(
        id=models.new_id(), output_id=output.id, workspace_id=output.workspace_id,
        project_id=output.project_id, stream_id=(stream_id or "")[:32],
        rule_kind=str(event.get("kind") or "")[:16],
        event={"summary": str(event.get("summary") or "")[:500],
               "class": str(event.get("class") or "")[:120]},
        status=result.status, latency_ms=result.latency_ms, detail=result.detail[:500], created=created)
    db.add(delivery)
    return delivery


def dispatch_event(db: Session, project_id: str, event: dict, *, workspace_id: str,
                   event_ts: float | None = None, stream_id: str = "",
                   write: Callable | None = None) -> list[models.OtDelivery]:
    """Fan one rule event out to matching enabled outputs; the caller commits.

    ``workspace_id`` is required and filtered alongside ``project_id``: a truncated or replayed
    event must never reach another tenant's actuator. Returns the attempted deliveries. Disabled
    outputs and filter misses produce no row, so a busy camera cannot flood the log with signals
    that were never meant to fire.
    """
    event = event if isinstance(event, dict) else {}
    sent_at = _now() if event_ts is None else event_ts
    outputs = db.scalars(select(models.OtOutput).where(models.OtOutput.project_id == project_id,
                                                     models.OtOutput.workspace_id == workspace_id,
                                                     models.OtOutput.enabled.is_(True))).all()
    deliveries = []
    for output in outputs:
        if not matches(output, event):
            continue
        with output_lock(output.id):
            result = deliver(output.protocol, output.endpoint, budget_ms=output.latency_budget_ms,
                             pulse_ms=output.pulse_ms, event_ts=sent_at, write=write)
        deliveries.append(record_delivery(db, output, event, result, stream_id=stream_id))
        if result.status != "ok":
            log.warning("OT output %s (%s): %s", output.id, output.protocol, result.detail)
    return deliveries


class AsyncDispatcher:
    """Bounded producer/consumer for the stream worker: the camera thread never waits on a PLC.

    Every job opens its own session and re-checks the workspace flag, so turning ``task_40`` off
    stops actuation even if a stream keeps running. A full queue drops the firing (the line
    stays safe) instead of blocking capture.
    """

    def __init__(self, maxsize: int = 128):
        self._queue: queue.Queue = queue.Queue(maxsize=maxsize)
        self._thread: threading.Thread | None = None
        self._start_guard = threading.Lock()

    def submit(self, workspace_id: str, project_id: str, event: dict, event_ts: float,
               stream_id: str = "") -> bool:
        with self._start_guard:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run, name="ot-actuator", daemon=True)
                self._thread.start()
        try:
            self._queue.put_nowait((workspace_id, project_id, event, event_ts, stream_id))
            return True
        except queue.Full:
            log.warning("OT actuator queue full; dropping event for project %s", project_id)
            return False

    def join(self) -> None:
        """Wait for queued jobs (used by tests; the API never waits)."""
        self._queue.join()

    def _run(self) -> None:
        while True:
            workspace_id, project_id, event, event_ts, stream_id = self._queue.get()
            try:
                with SessionLocal() as db:
                    if not flags.is_enabled("task_40", db, workspace_id):
                        continue
                    dispatch_event(db, project_id, event, workspace_id=workspace_id, event_ts=event_ts,
                                   stream_id=stream_id)
                    db.commit()
            except Exception:
                log.exception("OT dispatch failed for project %s", project_id)
            finally:
                self._queue.task_done()


_DISPATCHER = AsyncDispatcher()


def enqueue(workspace_id: str, project_id: str, event: dict, event_ts: float, stream_id: str = "") -> bool:
    """Queue one firing for the actuator thread; never blocks the caller."""
    return _DISPATCHER.submit(workspace_id, project_id, event, event_ts, stream_id)
