"""Live stream workers: capture -> model -> tracker -> rules engine -> events.

One grabber thread per stream keeps only the newest frame (raw BGR + encoded
JPEG, so the MJPEG endpoint never re-encodes), one processor thread samples that
frame at ``sample_fps`` and runs the model through the GPU scheduler. All state
lives in this process (single uvicorn, no ``--reload``), so ``start`` / ``stop`` /
``status`` see the same records.

Threads never share the request's SQLAlchemy session: every DB write opens its
own ``session_scope()``.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
import time
from collections import deque
from urllib.parse import urlsplit, urlunsplit

import cv2
import numpy as np
from PIL import Image as PImage

from ..adapters import ADAPTERS, resolve
from ..config import DATA_DIR
from ..db import session_scope
from ..gpu import GpuBusy
from ..models import Project, Stream, StreamEvent, Workspace, new_id
from ..services import metering
from ..services.safefetch import UnresolvableHost, _public_ip
from .allowlist import allowed_stream_ip
from .creds import mask_query, open_source
from .event_fields import filter_fields
from .guard import GuardedMediaProxy
from .rules import Engine

log = logging.getLogger("labeldesk.streams")

# UDP loses H.264 slices under load; TCP plus a finite socket timeout keeps reconnects bounded.
# `follow_redirects;0` is defence in depth on OpenCV builds that honour the environment (4.12+);
# the loopback guard below is what enforces it for HTTP(S) on every build.
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS",
                      "rtsp_transport;tcp|stimeout;3000000|follow_redirects;0")

_MAX_BACKOFF = 30
_FILE_FAILURES = 3             # consecutive open/read failures on a local file -> fatal, not endless retry
_REOPEN_AFTER = 10.0           # same frame hash (or no frame) this long -> reopen
_JPEG_QUALITY = 85
_METER_EVERY = 300.0           # stream_hours are durable at least every 5 min, not only on a clean stop
_DEFAULT_PORTS = {"rtsp": 554, "rtsps": 322, "http": 80, "https": 443}


# Greedy through the last @, so a raw @ inside the password is masked too.
_CREDENTIALS = re.compile(r"[^/\s]*@")


def display_source(source: str) -> str:
    """Never leak camera credentials into an API response, an error string or a log line."""
    parts = urlsplit(source)
    return urlunsplit((parts.scheme, _CREDENTIALS.sub("***@", parts.netloc),
                       parts.path, mask_query(parts.query), parts.fragment))


ALLOWED_SCHEMES = ("rtsp", "rtsps", "http", "https")


class SourceTransient(ValueError):
    """The source host could not be resolved; the worker should retry, not fail."""


def canonical_source(source: str) -> str:
    """Allowlist every string that may reach OpenCV/FFmpeg (PM ruling, 2026-11-02).

    Remote sources must be rtsp/rtsps/http/https with a host; local files are limited to a flat
    name under the uploaded `videos/` folder. FFmpeg accepts far more protocols (concat:, data:,
    subfile:, …), so this runs in the router *and* again in the worker before `VideoCapture`.
    Returns the canonical source (lower-case scheme, canonical file prefix). No DNS here: the
    worker must be able to create its row even when the camera is briefly unresolvable.
    """
    if not isinstance(source, str):
        raise ValueError("invalid source")
    s = source.strip()
    if not s:
        raise ValueError("invalid source: a URL or an uploaded video is required")
    if len(s) > 1024:
        raise ValueError("invalid source: longer than 1024 characters")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in s):
        raise ValueError("invalid source: control characters are not allowed")
    if s.lower().startswith("file:"):
        rest = s[len("file:"):]
        if not rest.lower().startswith("videos/"):
            raise ValueError("invalid source: local files must be uploaded videos (file:videos/<name>)")
        name = rest[len("videos/"):]
        if (not name or name in (".", "..") or name != name.strip()
                or any(ch in name for ch in '/\\:%?#|*<>"')):
            raise ValueError("invalid source: local files must be uploaded videos (file:videos/<name>)")
        return "file:videos/" + name
    parts = urlsplit(s)
    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise ValueError("invalid source: use rtsp, rtsps, http, https or an uploaded video")
    if not parts.netloc:
        raise ValueError("invalid source: the URL needs a host")
    return scheme + s[len(parts.scheme):]


def resolve_source(source: str) -> tuple[str, str]:
    """Canonicalise and resolve a remote source; returns ``(canonical, vetted IP)``.

    The IP is pinned by the caller (loopback guard for HTTP(S), URL rewrite for RTSP) so
    libavformat cannot re-resolve the name into the internal network. A resolver failure is
    ``SourceTransient``; a resolved private/loopback/link-local address stays a hard ValueError
    unless the operator named its network in ``LD_STREAM_ALLOW_CIDR`` (I-3).
    """
    s = canonical_source(source)
    if s.startswith("file:"):
        return s, ""
    parts = urlsplit(s)
    scheme = parts.scheme.lower()
    try:
        port = parts.port or _DEFAULT_PORTS[scheme]
    except ValueError as e:                          # malformed port keeps the old "invalid source" message
        raise ValueError(f"invalid source: {e}") from e
    ip = allowed_stream_ip(parts.hostname, port)     # operator opt-in for LAN cameras (I-3)
    if ip is None:
        try:
            ip = _public_ip(parts.hostname, port)
        except UnresolvableHost as e:
            raise SourceTransient(f"cannot resolve {parts.hostname}") from e
        except ValueError as e:
            raise ValueError(f"invalid source: {e}") from e
    return s, ip


def check_source(source: str) -> str:
    """Validate a source for the router and the worker; returns the canonical string."""
    return resolve_source(source)[0]


def pinned_url(source: str, ip: str) -> str:
    """Rewrite an RTSP authority to the vetted IP literal (no DNS left for FFmpeg to redo)."""
    parts = urlsplit(source)
    host = f"[{ip}]" if ":" in ip else ip
    netloc = f"{host}:{parts.port}" if parts.port else host
    if "@" in parts.netloc:
        netloc = parts.netloc.rpartition("@")[0] + "@" + netloc
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def rule_label(rule: dict, index: int) -> str:
    """Short human label for an event timeline row."""
    kind = rule.get("kind")
    cls = rule.get("class") or "object"
    if kind == "count":
        return f"{cls} count {rule.get('op', '>=')} {rule.get('k')}"
    if kind == "zone":
        return f"{cls} in {rule.get('zone_id')}"
    if kind == "line":
        return f"line {index + 1}: {cls}"
    if kind == "dwell":
        return f"{cls} dwells in {rule.get('zone_id')} ({rule.get('seconds')}s)"
    if kind == "vlm":
        return f"VLM: {rule.get('question', '')}"
    return str(kind)


def _iou(a: dict, b: dict) -> float:
    ax1, ay1 = a["x"] - a["width"] / 2, a["y"] - a["height"] / 2
    bx1, by1 = b["x"] - b["width"] / 2, b["y"] - b["height"] / 2
    ix = max(0.0, min(ax1 + a["width"], bx1 + b["width"]) - max(ax1, bx1))
    iy = max(0.0, min(ay1 + a["height"], by1 + b["height"]) - max(ay1, by1))
    inter = ix * iy
    union = a["width"] * a["height"] + b["width"] * b["height"] - inter
    return inter / union if union > 0 else 0.0


class _Tracker:
    """Greedy IoU tracker: same class, IoU >= 0.3, ids never repeat, tracks expire after ttl."""

    def __init__(self, ttl: float = 2.0, iou_min: float = 0.3):
        self.ttl = ttl
        self.iou_min = iou_min
        self._tracks: dict[int, tuple[dict, float, str]] = {}
        self._next = 0

    def update(self, ts: float, preds: list[dict]) -> None:
        # One-to-one assignment: collect every plausible match, strongest first, and consume both
        # the track and the prediction. Without this two people walking together can share one id.
        pairs = []
        for pi, p in enumerate(preds):
            for tid, (box, seen, cls) in self._tracks.items():
                if cls == p.get("class"):
                    score = _iou(box, p)
                    if score >= self.iou_min:
                        pairs.append((score, tid, pi))
        used_tracks: set[int] = set()
        used_preds: set[int] = set()
        for score, tid, pi in sorted(pairs, reverse=True):
            if tid in used_tracks or pi in used_preds:
                continue
            used_tracks.add(tid)
            used_preds.add(pi)
            preds[pi]["track_id"] = tid
            self._tracks[tid] = (preds[pi], ts, preds[pi].get("class"))
        for pi, p in enumerate(preds):
            if pi in used_preds:
                continue
            self._next += 1
            p["track_id"] = self._next
            self._tracks[self._next] = (p, ts, p.get("class"))
        for tid in [k for k, (_, seen, _) in self._tracks.items() if ts - seen > self.ttl]:
            del self._tracks[tid]


class _Worker:
    def __init__(self, row: Stream):
        self.id = row.id
        self.workspace_id = row.workspace_id
        self.project_id = row.project_id
        self.name = row.name
        # Stored sources may be sealed (secretbox). Open once, here: every consumer (OpenCV,
        # status text, logs) must see the real URL, never `enc:v1:...`.
        self._source_error = ""
        try:
            raw_source = open_source(row.source)
        except ValueError:
            raw_source = ""
            self._source_error = "stream credentials cannot be decrypted"
        if not self._source_error:
            try:
                self.source = canonical_source(raw_source)
            except ValueError as e:
                self.source = ""
                self._source_error = str(e)
        else:
            self.source = ""
        self.model_ref = row.model_ref
        self.sample_fps = min(30.0, max(0.5, float(row.sample_fps or 5.0)))
        self.zones = list(row.zones or [])
        self.rules = list(row.rules or [])

        self.status = "connecting"
        self.last_error = ""
        self.paused = False
        self.gpu_busy = False
        self.fatal = False
        self._state_lock = threading.Lock()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._reopen = threading.Event()        # processor asks the grabber to reopen; it owns the capture
        self._stopped = False
        self._frame = None
        self._jpeg = None
        self._frame_ts = 0.0
        self._frames = 0
        self._inferences = 0
        self._detections = 0
        self._fps_times: deque[float] = deque()
        self._threads: list[threading.Thread] = []
        self._quota_error = ""                  # I8-R: visible when event snapshots are quota-blocked
        self._metered_until = time.time()
        self._active_proxy: GuardedMediaProxy | None = None
        self._open_error = ""

    # ---- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        if self._source_error:
            self._fail(self._source_error)
            return
        self._set("connecting")
        for target, name in ((self._grab, "grabber"), (self._process, "processor")):
            t = threading.Thread(target=self._guard, args=(target,),
                                 name=f"stream-{self.id}-{name}", daemon=True)
            self._threads.append(t)
            t.start()

    def _guard(self, fn) -> None:
        """An unexpected worker exception must surface as `error`, never as a silently dead thread."""
        try:
            fn()
        except Exception:
            log.exception("stream %s: worker crashed", self.id)
            self._fail("stream worker failed")

    def _fail(self, message: str) -> None:
        """Fatal exit. `fatal` is flipped under the state lock: a concurrent grabber `live` write loses."""
        with self._state_lock:
            self.fatal = True
        self._set("error", message)

    def signal_stop(self) -> None:
        """Flag both loops to exit without waiting; safe to call from any thread and repeat."""
        self._stopped = True
        self._stop.set()

    def join(self, budget: float) -> bool:
        """Wait at most ``budget`` in total for both threads; returns True once they have exited.

        The grabber releases its own VideoCapture in its finally clause, so a worker that is still
        draining keeps its threads and proxy; it exits on its own stop event.
        """
        threads = list(self._threads)
        deadline = time.monotonic() + max(0.0, budget)
        for t in reversed(threads):          # processor leaves first, the grabber may be in a read timeout
            t.join(max(0.0, deadline - time.monotonic()))
        if any(t.is_alive() for t in threads):
            return False
        self._threads.clear()
        self._close_proxy()
        self._meter()
        return True

    def stop(self, budget: float = 4.0) -> bool:
        """Signal and join within ``budget`` (the old 2.0 s per thread); repeat calls are no-ops.

        VideoCapture is not thread-safe: releasing it here while the grabber sits in read() races
        the decoder and can crash the process. A blocking read returns through its 3 s timeout, and
        the grabber's finally clause then releases the handle on the thread that opened it.
        """
        self.signal_stop()
        if not self._threads:                # a repeat stop must not meter (or join) twice
            return True
        return self.join(budget)

    # ---- metering ----------------------------------------------------------
    def _meter(self, now: float | None = None) -> None:
        """Record the wall-clock time since the last sample as stream_hours (crash-safe granularity)."""
        now = time.time() if now is None else now
        hours = (now - self._metered_until) / 3600.0
        if hours <= 0:
            return
        self._metered_until = now
        try:
            with session_scope() as db:
                metering.record(db, self.workspace_id, "stream_hours", hours,
                                project_id=self.project_id, stream_id=self.id)
        except Exception:                      # metering must never kill a worker
            log.exception("stream %s: could not meter stream hours", self.id)

    def _project_gone(self) -> bool:
        """True when the owning project was trashed or purged under a still-running worker."""
        try:
            with session_scope() as db:
                project = db.get(Project, self.project_id)
                return project is None or project.deleted_at is not None
        except Exception:
            log.exception("stream %s: could not read the project state", self.id)
            return False

    def running(self) -> bool:
        return not self._stopped and any(t.is_alive() for t in self._threads)

    def dead(self) -> bool:
        return self._stopped or not any(t.is_alive() for t in self._threads)

    def pause(self) -> None:
        if not self.running():
            return
        self.paused = True
        self._paused.set()
        self._set("paused (GPU busy)")

    def resume(self) -> None:
        self.paused = False
        self._paused.clear()
        if not self.fatal:
            self._set("live", "")

    def status_out(self) -> dict:
        with self._lock:
            now = time.time()
            times = [t for t in self._fps_times if now - t < 2.0]
            status = "paused (GPU busy)" if (self.paused or self.gpu_busy) else self.status
            return {"status": status, "last_error": self._quota_error or self.last_error,
                    "fps": round(len(times) / 2.0, 1) if times else 0.0,
                    "frames": self._frames, "inferences": self._inferences,
                    "detections": self._detections, "last_frame": self._frame_ts}

    def latest_jpeg(self) -> bytes | None:
        with self._lock:
            return self._jpeg

    # ---- status persistence ------------------------------------------------
    def _set(self, status: str, error: str | None = None) -> None:
        if self._stopped:
            return
        with self._state_lock:
            if self.fatal and status == "live":   # a fatal exit must never be overwritten as healthy
                return
            error = self.last_error if error is None else error
            if status == self.status and error == self.last_error:
                return
            self.status, self.last_error = status, error
        try:
            with session_scope() as db:
                row = db.get(Stream, self.id)
                if row is not None:
                    row.status, row.last_error = status, error
        except Exception:                         # a DB hiccup must never kill the worker
            log.exception("stream %s: could not persist status", self.id)

    # ---- capture -----------------------------------------------------------
    @property
    def _is_file(self) -> bool:
        return self.source.startswith("file:")

    def _file_path(self):
        """Resolve `file:videos/x` and refuse anything outside DATA_DIR/videos."""
        rel = self.source[len("file:"):].lstrip("/\\")
        base = (DATA_DIR / "videos").resolve()
        path = (DATA_DIR / rel).resolve()
        return path if base in path.parents else None

    def _close_proxy(self) -> None:
        proxy, self._active_proxy = self._active_proxy, None
        if proxy is not None:
            proxy.stop()

    def _open(self):
        self._open_error = ""
        self._close_proxy()
        source, ip = resolve_source(self.source)   # second gate: nothing unlisted reaches FFmpeg
        self.source = source
        if source.startswith("file:"):
            path = self._file_path()
            if path is None:
                return None
            cap = cv2.VideoCapture(str(path))
        else:
            parts = urlsplit(source)
            if parts.scheme in ("http", "https"):
                # libavformat resolves the host itself and follows redirects; hand it a
                # loopback guard that pins every hop and refuses non-public redirect targets.
                proxy = GuardedMediaProxy(source, ip=ip)
                try:
                    url = proxy.start()
                except OSError as e:
                    raise SourceTransient(f"cannot open source: {display_source(source)}") from e
                self._active_proxy = proxy
                try:
                    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG,
                                           [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 3000,
                                            cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000])
                except Exception:
                    self._close_proxy()
                    raise
                if not cap.isOpened():
                    cap.release()
                    reason, transient = proxy.error, proxy.transient
                    self._close_proxy()
                    if reason and not transient:
                        raise ValueError(f"invalid source: {reason}")
                    self._open_error = reason or f"cannot open source: {display_source(source)}"
                    return None
                return cap
            # RTSP has no proxy support in libavformat: pin the vetted IP so re-resolution
            # cannot rebind. TLS keeps the hostname so certificate validation still applies.
            target = source if parts.scheme == "rtsps" else pinned_url(source, ip)
            cap = cv2.VideoCapture(target, cv2.CAP_FFMPEG,
                                   [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 3000,
                                    cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000])
        if not cap.isOpened():
            cap.release()
            return None
        return cap

    def _publish(self, frame, ts: float) -> None:
        ok, enc = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_QUALITY])
        with self._lock:
            self._frame = frame
            if ok:
                self._jpeg = enc.tobytes()
            self._frame_ts = ts
            self._fps_times.append(ts)
            while self._fps_times and ts - self._fps_times[0] > 2.0:
                self._fps_times.popleft()

    @staticmethod
    def _pacing_fps(cap) -> float:
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        if not np.isfinite(fps) or fps <= 0:
            return 10.0
        return min(60.0, max(1.0, float(fps)))

    def _missing_file(self) -> str | None:
        """Error text for a missing / out-of-DATA_DIR file source, else None."""
        if not self._is_file:
            return None
        path = self._file_path()
        if path is not None and path.is_file():
            return None
        return f"video file not found: {path.name if path is not None else display_source(self.source)}"

    def _grab(self) -> None:
        missing = self._missing_file()
        if missing:
            self._fail(missing)
            return
        backoff = 1
        failures = 0                            # consecutive open/read failures (files get a budget)
        while not self._stop.is_set():
            if self.fatal:
                return
            missing = self._missing_file()
            if missing:
                self._fail(missing)
                return
            self._reopen.clear()
            try:
                cap = self._open()
            except SourceTransient as e:
                # A DNS hiccup is not a camera fault: back off and retry, like any lost source.
                self._set("reconnecting", display_source(str(e)))
                if self._stop.wait(backoff):
                    return
                backoff = min(backoff * 2, _MAX_BACKOFF)
                continue
            except ValueError as e:
                self._fail(str(e))              # an allowlist/policy rejection is fatal
                return
            if cap is None:
                failures += 1
                if self._is_file and failures >= _FILE_FAILURES:
                    self._fail(f"cannot open video file: {display_source(self.source)}")
                    return
                self._set("reconnecting", self._open_error
                          or f"cannot open source: {display_source(self.source)}")
                if self._stop.wait(backoff):
                    return
                backoff = min(backoff * 2, _MAX_BACKOFF)
                continue
            backoff = 1
            interval = 1.0 / self._pacing_fps(cap) if self._is_file else 0.0
            last_hash, last_change = None, time.time()
            read_failed = False
            try:
                while not self._stop.is_set():
                    if self.fatal:
                        return
                    t0 = time.monotonic()
                    ok, frame = cap.read()
                    if not ok:
                        if not self._is_file:
                            break
                        try:                      # file sources loop forever at EOF
                            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        except Exception:
                            pass
                        ok, frame = cap.read()
                        if not ok:
                            read_failed = True
                            break
                    if self._reopen.is_set():     # processor watchdog asked for a fresh capture
                        break
                    failures = 0                  # frames are flowing: the file budget starts over
                    ts = time.time()
                    # A paused / GPU-busy stream keeps capturing so its live view stays warm; do not let the
                    # grabber overwrite the status the scheduler asked for. A fatal processor exit (e.g. an
                    # unknown model) must never be turned back into a healthy "live".
                    if (not self.fatal and self.status not in ("live", "error")
                            and not self.paused and not self.gpu_busy):
                        self._set("live", "")
                    self._publish(frame, ts)
                    with self._lock:
                        self._frames += 1
                    digest = hashlib.blake2b(frame[::8, ::8].tobytes(), digest_size=16).hexdigest()
                    if digest != last_hash:
                        last_hash, last_change = digest, ts
                    elif ts - last_change > _REOPEN_AFTER:
                        self._set("reconnecting", f"watchdog: no new frame from {display_source(self.source)}")
                        break
                    if interval:
                        left = interval - (time.monotonic() - t0)
                        if left > 0 and self._stop.wait(left):
                            break
            finally:
                # only this thread ever touches the capture: cross-thread release races the decoder
                try:
                    cap.release()
                except Exception:
                    log.exception("stream %s: capture release failed", self.id)
                finally:
                    self._close_proxy()
            if self._stop.is_set():
                return
            if read_failed:
                failures += 1
                if self._is_file and failures >= _FILE_FAILURES:
                    # A corrupt / mislabelled upload opens or reads badly forever; say so instead.
                    self._fail(f"cannot read video file: {display_source(self.source)}")
                    return
            if self._is_file:
                # a looping file only gets here on a real read failure: retry with backoff
                self._set("reconnecting", f"cannot read source: {display_source(self.source)}")
            else:
                self._set("reconnecting", f"lost source: {display_source(self.source)}")
            if self._stop.wait(backoff):
                return
            backoff = min(backoff * 2, _MAX_BACKOFF)

    # ---- inference ---------------------------------------------------------
    def _process(self) -> None:
        try:
            with session_scope() as db:
                resolved = resolve(self.model_ref, db, workspace_id=self.workspace_id)
        except ValueError as e:
            self._fail(f"model unavailable: {e}")     # our own validation text (ruling, progress.md:148)
            return
        except Exception:
            log.exception("stream %s: resolve failed", self.id)
            self._fail("model unavailable")
            return

        variant = getattr(resolved, "variant", "") or ""
        is_world = "world" in variant.lower()
        classes = sorted({r["class"] for r in self.rules if r.get("class")}) if is_world else None
        if is_world and not classes:
            # Open-vocabulary models have no vocabulary without a class-bearing rule: never report "live".
            self._fail("YOLO-World needs at least one rule with a class")
            return
        engine = Engine(self.rules, self.zones, 30, 2.0)
        tracker = _Tracker(2.0)
        vlm_last: dict[int, float] = {}
        period = 1.0 / self.sample_fps
        last_proc, last_seq = 0.0, -1

        while not self._stop.is_set():
            if self.fatal:
                return
            if self._paused.is_set():
                self._stop.wait(0.2)
                continue
            with self._lock:
                frame, seq, ts = self._frame, self._frames, self._frame_ts
                has_frame = self._frame_ts > 0
            now = time.time()
            if now - self._metered_until >= _METER_EVERY:
                self._meter(now)
            # No-new-frame watchdog: a capture stack can hang inside read() without raising. The
            # processor cannot release the handle (the grabber owns it), so it asks the grabber to
            # reopen; a blocked read returns through its own timeout and the grabber then recycles it.
            if has_frame and not self._paused.is_set() and now - self._frame_ts > _REOPEN_AFTER:
                self._reopen.set()
                self._set("reconnecting", f"watchdog: no new frame from {display_source(self.source)}")
                self._stop.wait(0.5)
                continue
            if frame is None or seq == last_seq or now - last_proc < period:
                self._stop.wait(min(0.1, max(0.01, period / 4)))
                continue
            last_proc, last_seq = now, seq
            im = PImage.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            try:
                out = resolved.predict(im, **({"classes": classes} if classes else {}))
            except GpuBusy:
                self.gpu_busy = True
                self._set("paused (GPU busy)", "GPU busy: training owns the card")
                self._stop.wait(2.0)
                continue
            except Exception:
                log.exception("stream %s: inference failed", self.id)
                self._set("live", "inference failed")
                self._stop.wait(0.5)
                continue

            self.gpu_busy = False
            self._set("live", "")                     # a recovered stream must not keep a stale warning
            preds = self._normalize(out, im)
            tracker.update(ts, preds)
            with self._lock:
                self._inferences += 1
                self._detections += len(preds)
            try:
                events = engine.step(ts, preds)
            except Exception:                     # router validation should prevent this; never kill the stream
                log.exception("stream %s: rule engine failed", self.id)
                events = []
            for ev in events:
                try:
                    self._record(ev, ts, preds, frame)
                except Exception:
                    log.exception("stream %s: could not record event", self.id)

            for i, rule in enumerate(self.rules):
                if rule.get("kind") != "vlm":
                    continue
                every = max(1.0, float(rule.get("every_s") or 30))
                if now - vlm_last.get(i, 0.0) < every:
                    continue
                vlm_last[i] = now
                self._ask_vlm(i, rule, ts, preds, im, frame)

    @staticmethod
    def _normalize(out: dict, im: PImage.Image) -> list[dict]:
        size = out.get("image") or {}
        w = size.get("width") or im.width
        h = size.get("height") or im.height
        preds = []
        for p in out.get("predictions") or []:
            if not all(k in p for k in ("x", "y", "width", "height")):
                continue                          # classification rows carry no box
            preds.append({"class": p.get("class"), "class_id": p.get("class_id"),
                          "confidence": float(p.get("confidence") or 0.0),
                          "x": p["x"] / w, "y": p["y"] / h,
                          "width": p["width"] / w, "height": p["height"] / h})
        return preds

    def _ask_vlm(self, i: int, rule: dict, ts: float, preds: list[dict], im: PImage.Image, frame) -> None:
        adapter = ADAPTERS.get("vlm")
        if adapter is None:
            return
        try:
            if adapter.is_sleeping():
                return
            # Only a "yes" is an event: the rule is a question, not a caption.
            if not adapter.ask_yes_no(im, rule.get("question", "")):
                return
        except Exception:                         # unreachable/loading VLM: skip silently
            return
        try:
            self._record({"rule": i, "kind": "vlm",
                          "summary": f"{rule.get('question', '')} → yes"}, ts, preds, frame)
        except Exception:
            log.exception("stream %s: could not record VLM event", self.id)

    # ---- events ------------------------------------------------------------
    def _record(self, ev: dict, ts: float, preds: list[dict], frame) -> None:
        if self._project_gone():
            # C2: a purge can race a rule firing. Stop the threads here instead of recreating
            # identifiable footage under a project the operator already deleted.
            self._stop.set()
            return
        i = int(ev.get("rule", -1))
        rule = self.rules[i] if 0 <= i < len(self.rules) else {}
        kind = ev.get("kind") or rule.get("kind")
        rule_json = {**rule, "index": i, "kind": kind, "label": rule_label(rule, i)}
        if isinstance(ev.get("seconds"), (int, float)) and not isinstance(ev.get("seconds"), bool):
            rule_json["seconds"] = float(ev["seconds"])
        payload = [{k: p[k] for k in ("class", "class_id", "track_id", "confidence", "x", "y", "width", "height")
                    if k in p} for p in preds[:50]]
        eid = new_id()
        snapshot, clean = "", ""
        snapshot_jpeg = clean_jpeg = b""
        if frame is not None:
            try:
                snapshot_jpeg, clean_jpeg = self._render_frames(frame, preds, ev)
            except Exception:
                log.exception("stream %s: could not draw event snapshot", self.id)
        size = float(len(snapshot_jpeg) + len(clean_jpeg))
        with session_scope() as db:
            # I8-R: event JPEGs are project storage. Check the same meter as uploads before writing,
            # and bill the exact bytes with the event row so retention/purge can refund them.
            project = db.get(Project, self.project_id)
            if project is None or project.deleted_at is not None:
                self._stop.set()
                return
            ws = db.get(Workspace, self.workspace_id)
            room = metering.remaining(db, ws, "storage_bytes") if ws is not None else 0.0
            if size and ws is not None and size <= room:
                try:
                    snapshot, clean = self._save_frames(snapshot_jpeg, clean_jpeg, eid)
                except Exception:
                    log.exception("stream %s: could not save event snapshot", self.id)
            if snapshot and ws is not None:
                metering.record(db, ws.id, "storage_bytes", size, project_id=self.project_id,
                                stream_event=eid)
                with self._state_lock:
                    self._quota_error = ""
            elif size:
                with self._state_lock:
                    self._quota_error = "storage quota reached: event snapshots are not being saved"
            db.add(StreamEvent(id=eid, stream_id=self.id, ts=ts, rule=rule_json,
                               summary=ev.get("summary", ""), snapshot_path=snapshot,
                               clean_path=clean, predictions=payload,
                               **filter_fields(rule_json, payload)))

    def _render_frames(self, frame, preds: list[dict], ev: dict) -> tuple[bytes, bytes]:
        """Draw the annotated review frame and encode it plus the untouched dataset frame."""
        img = frame.copy()
        h, w = img.shape[:2]
        for z in self.zones:
            pts = np.array(z.get("points") or [], dtype=float).reshape(-1, 2)
            if len(pts) < 3:
                continue
            poly = np.column_stack((pts[:, 0] * w, pts[:, 1] * h)).astype(np.int32)
            cv2.polylines(img, [poly], True, (255, 180, 0), 2)
        for r in self.rules:
            if r.get("kind") == "line" and len(r.get("line") or []) == 4:
                x1, y1, x2, y2 = r["line"]
                cv2.line(img, (int(x1 * w), int(y1 * h)), (int(x2 * w), int(y2 * h)), (0, 200, 255), 2)
        trigger = ev.get("track_id")
        for p in preds:
            x1, y1 = int((p["x"] - p["width"] / 2) * w), int((p["y"] - p["height"] / 2) * h)
            x2, y2 = int((p["x"] + p["width"] / 2) * w), int((p["y"] + p["height"] / 2) * h)
            hot = trigger is not None and p.get("track_id") == trigger
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0) if hot else (150, 150, 150), 3 if hot else 1)
            if hot:
                cv2.circle(img, (int(p["x"] * w), int((p["y"] + p["height"] / 2) * h)), 6, (0, 0, 255), -1)
        ok_ann, ann = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_QUALITY])
        ok_clean, clean = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_QUALITY])
        if not (ok_ann and ok_clean):
            raise ValueError("could not encode event snapshot")
        return ann.tobytes(), clean.tobytes()

    def _save_frames(self, snapshot_jpeg: bytes, clean_jpeg: bytes, eid: str) -> tuple[str, str]:
        """Persist the two encoded JPEGs; returns their DATA_DIR-relative paths."""
        folder = DATA_DIR / "snapshots" / self.project_id   # project-keyed: retention can attribute it
        folder.mkdir(parents=True, exist_ok=True)
        snapshot = folder / f"{eid}.jpg"
        clean = folder / f"{eid}.src.jpg"
        try:
            snapshot.write_bytes(snapshot_jpeg)
            clean.write_bytes(clean_jpeg)
        except Exception:
            snapshot.unlink(missing_ok=True)
            clean.unlink(missing_ok=True)
            raise
        return (f"snapshots/{self.project_id}/{eid}.jpg", f"snapshots/{self.project_id}/{eid}.src.jpg")


class StreamManager:
    def __init__(self):
        self._workers: dict[str, _Worker] = {}
        self._lock = threading.Lock()

    def start(self, stream_id: str) -> dict:
        """Spawn the capture + processing threads and return immediately."""
        with self._lock:
            worker = self._workers.get(stream_id)
            if worker is not None and not worker.dead():
                return worker.status_out()
            with session_scope() as db:
                row = db.get(Stream, stream_id)
                if row is None:
                    raise KeyError(stream_id)
                worker = _Worker(row)
            self._workers[stream_id] = worker
            # Start under the lock: two concurrent /start calls must not orphan the first worker's
            # capture/processor threads (duplicate RTSP connections and duplicate events).
            worker.start()
        return worker.status_out()

    def stop(self, stream_id: str, budget: float = 4.0) -> bool:
        """Stop one stream, waiting at most ``budget``; returns False when its threads still drain.

        The row is marked ``stopped`` either way: the operator asked for it and the worker loops
        exit on their own stop event. ``stop_many`` is the bounded path for trash/purge.
        """
        with self._lock:
            worker = self._workers.pop(stream_id, None)
        stopped = True if worker is None else worker.stop(budget)
        self._persist_stopped([stream_id])
        return stopped

    def stop_many(self, stream_ids: list[str], budget: float = 0.25) -> list[str]:
        """Signal every stream, then wait at most ``budget`` in total for all of them (I-4).

        Returns the ids whose threads were still draining. No DB write happens here: the caller
        persists ``stopped`` and audits the draining set in its own transaction, so a request that
        already holds a SQLite write lock cannot deadlock against this manager.
        """
        ids = list(dict.fromkeys(stream_ids))
        with self._lock:
            workers = [(sid, self._workers.pop(sid, None)) for sid in ids]
        workers = [(sid, w) for sid, w in workers if w is not None]
        for _, w in workers:                 # signal first: no worker keeps capturing while we join
            w.signal_stop()
        deadline = time.monotonic() + max(0.0, budget)
        return [sid for sid, w in workers
                if not w.join(max(0.0, deadline - time.monotonic()))]

    def _persist_stopped(self, stream_ids: list[str]) -> None:
        try:
            with session_scope() as db:
                for sid in stream_ids:
                    row = db.get(Stream, sid)
                    if row is not None:
                        row.status, row.last_error = "stopped", ""
        except Exception:
            log.exception("streams %s: could not persist stop", stream_ids)

    def stop_all(self) -> None:
        with self._lock:
            ids = list(self._workers)
        for sid in ids:
            self.stop(sid)

    def active_count(self, workspace_id: str, exclude: str | None = None) -> int:
        """Live workers of one workspace, for the per-plan stream cap."""
        with self._lock:
            workers = list(self._workers.values())
        return sum(1 for w in workers
                   if w.workspace_id == workspace_id and w.id != exclude and w.running())

    def pause_all(self) -> None:
        with self._lock:
            workers = list(self._workers.values())
        for w in workers:
            w.pause()

    def resume_all(self) -> None:
        with self._lock:
            workers = list(self._workers.values())
        for w in workers:
            w.resume()

    def latest_jpeg(self, stream_id: str) -> bytes | None:
        worker = self._workers.get(stream_id)
        return worker.latest_jpeg() if worker is not None else None

    def status(self, stream_id: str) -> dict | None:
        worker = self._workers.get(stream_id)
        if worker is None:
            return None
        return worker.status_out()


manager = StreamManager()
