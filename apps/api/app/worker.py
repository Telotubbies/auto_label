"""Background job runner. The DB `jobs` table is the queue — no Redis needed.

Run standalone (`python -m app.worker`) on the GPU host, or embedded in the api
process (LD_EMBEDDED_WORKER=1, the dev default).
"""
import gc
import hashlib
import io
import logging
import shutil
import statistics
import threading
import time
import traceback
from pathlib import Path

import cv2
from PIL import Image as PImage
from sqlalchemy import select, update

from .adapters import ADAPTERS, Cancelled
from .adapters.refine import label_image, sam_available
from .adapters.ultralytics_ad import _start_weights
from .config import CREDIT_COST, DATA_DIR, LOCAL_JOB_KINDS
from .db import SessionLocal
from .deps import charge
from .gpu import scheduler
from .models import (Batch, Image, Job, LabelClass, Project, TrainedModel, Version, Video, Workspace, new_id, now,
                     set_annotations)
from .services import (
    active_learning,
    connectors,
    drift,
    exporters,
    health,
    imaging,
    insights_embedding,
    insights_jobs,
    metering,
    ml,
    segment,
    track,
    versioning,
    webhooks,
)
from .services.evaluate import evaluate
from .services.video import DEFAULT_SCENE_THRESHOLD, is_scene_change, plan_frames

log = logging.getLogger("labeldesk.worker")
POLL = 1.5
WATCHDOG_MIN_S = 120.0                      # later epochs: never call a run stalled sooner than this
FIRST_EPOCH_MIN_S = 600.0                   # the first epoch also pays for export + model load
WATCHDOG_POLL_S = 0.01                      # floor for the adaptive poll (tests shrink the limit)
MAX_EPOCH_SAMPLES = 50                      # median over the recent epochs only
MIN_TRAIN_GPU_S = 60.0                      # the /train estimate floor: less cannot fund a minimal run


class QuotaExhausted(RuntimeError):
    """A job stopped at the workspace allowance; it must fail instead of reporting a truncated result."""


def _stall_limit(epoch_secs: list[float]) -> float:
    """Later epochs: stalled after 3x the median epoch, but never sooner than WATCHDOG_MIN_S."""
    return max(WATCHDOG_MIN_S, 3 * statistics.median(epoch_secs)) if epoch_secs else WATCHDOG_MIN_S


def _first_limit(train_images: int, epochs: int, imgsz: int) -> float:
    """First-epoch grace: max(600 s, 2x the estimate the Train page shows).

    The Train page estimates `train_images * epochs * (imgsz/640)^2 / 600` minutes; the first epoch
    also pays for the dataset export and the model load, so it gets the larger of the two budgets."""
    estimate_s = train_images * max(1, epochs) * (imgsz / 640) ** 2 / 600 * 60
    return max(FIRST_EPOCH_MIN_S, 2 * estimate_s)


class _Watchdog:
    """Daemon thread that flips `stalled` when on_epoch callbacks stop arriving."""

    def __init__(self, first_limit: float = FIRST_EPOCH_MIN_S):
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="labeldesk-train-watchdog")
        self.first_limit = float(first_limit)
        self.last = self.last_epoch = time.monotonic()   # last = any progress; last_epoch = the last epoch
        self.epoch_secs: list[float] = []
        self._seen_epoch = False
        self.limit = self.first_limit
        self.stalled = False

    def start(self) -> "_Watchdog":
        # The first-epoch grace runs from the first epoch, not from construction: dataset export
        # and weight resolution happen in between and must not eat the training budget.
        with self._lock:
            self.last = self.last_epoch = time.monotonic()
        self._thread.start()
        return self

    def tick(self) -> None:
        """Record an on_epoch callback; the gap since the previous one feeds the limit."""
        now = time.monotonic()
        with self._lock:
            self.epoch_secs.append(now - self.last_epoch)  # the first gap includes load/export: a generous seed
            del self.epoch_secs[:-MAX_EPOCH_SAMPLES]       # old epochs must not pin the limit forever
            self._seen_epoch = True
            self.last = self.last_epoch = now
            self.stalled = False                           # an epoch is progress: clear a pre-epoch false alarm

    def beat(self) -> None:
        """Refresh liveness only (a polling adapter saw real progress); never an epoch sample."""
        with self._lock:
            self.last = time.monotonic()

    def reset(self) -> None:
        with self._lock:
            self.last = self.last_epoch = time.monotonic()
            self.epoch_secs.clear()
            self._seen_epoch = False
            self.limit = self.first_limit
            self.stalled = False

    def _run(self) -> None:
        while True:
            with self._lock:
                self.limit = _stall_limit(self.epoch_secs) if self._seen_epoch else self.first_limit
                limit = self.limit
                if time.monotonic() - self.last > limit:
                    self.stalled = True
            # poll a few times per limit (max 1 s) so a long run does not spin
            if self._stop.wait(min(1.0, max(WATCHDOG_POLL_S, limit / 4))):
                return

    def stop(self) -> None:
        self._stop.set()


def _claim():
    with SessionLocal() as db:
        for jid in db.scalars(select(Job.id).where(Job.status == "queued", Job.kind.in_(LOCAL_JOB_KINDS)).order_by(Job.created).limit(5)):
            # compare-and-set so two workers never run the same job
            n = db.execute(update(Job).where(Job.id == jid, Job.status == "queued")
                           .values(status="running", started=now())).rowcount
            db.commit()
            if n:
                return jid
    return None


def _set(jid: str, **kw):
    with SessionLocal() as db:
        db.execute(update(Job).where(Job.id == jid).values(**kw)); db.commit()
    try:                                          # long jobs keep the admin console green
        from .services import heartbeat
        done = kw.get("status") in ("done", "failed", "cancelled")
        heartbeat.beat(LOCAL_JOB_KINDS, current_job=None if done else jid)
    except Exception:                             # a heartbeat failure must never fail a job
        log.exception("worker heartbeat failed")


def _cancelled(jid: str) -> bool:
    with SessionLocal() as db:
        return db.scalar(select(Job.status).where(Job.id == jid)) == "cancelling"


# --- handlers ---------------------------------------------------------------------

def run_version(job: Job):
    with SessionLocal() as db:
        v = db.get(Version, job.params["version_id"])
        v.status = "generating"; db.commit()
        try:
            stats = versioning.generate(db, v, lambda f: _set(job.id, progress=round(f * 100, 1)))
            v.status, v.stats = "ready", stats
        except Exception:
            v.status = "failed"; db.commit(); raise
        db.commit()
        return {"version_id": v.id, **stats}


def run_export(job: Job):
    with SessionLocal() as db:
        v = db.get(Version, job.params["version_id"])
        fmt = job.params["format"]
        out = DATA_DIR / "exports" / v.id / fmt
        z = exporters.export(fmt, versioning.version_dir(v), out)
        import shutil
        shutil.rmtree(out, ignore_errors=True)
        return {"version_id": v.id, "format": fmt, "file": z.relative_to(DATA_DIR).as_posix(), "bytes": z.stat().st_size}


def run_export_engine(job: Job):
    """Build a TensorRT engine for a ready model, cache it under engines/, and register the runtime."""
    with SessionLocal() as db:
        tm = db.get(TrainedModel, job.params["model_id"])
        if tm is None or tm.status != "ready" or not tm.weights:
            raise RuntimeError("model is not ready")
        mid, family, variant, weights = tm.id, tm.family or "ultralytics", tm.variant or tm.arch, tm.weights
    src = DATA_DIR / weights
    if not src.exists():
        raise RuntimeError("model weights are missing")
    dest = DATA_DIR / "engines" / f"{mid}.engine"
    adapter = ADAPTERS.get(family)
    build = getattr(adapter, "export", None)
    if build is None:
        raise RuntimeError(f"{family} models cannot be exported to TensorRT")
    _set(job.id, progress=10.0)
    with scheduler.exclusive(f"engine export {variant}"):         # the build owns the whole card
        out = build(str(src), "engine", half=True, dest=dest)
    rel = out.relative_to(DATA_DIR).as_posix()
    with SessionLocal() as db:                                    # fresh row: the build ran for minutes
        tm = db.get(TrainedModel, mid)
        if tm is None:
            raise RuntimeError("model was deleted during the export")
        tm.runtime_refs = {**(tm.runtime_refs or {}), "pt": weights, "engine": rel}
        db.commit()
    return {"model_id": mid, "format": "engine", "engine": rel, "bytes": out.stat().st_size}


def _is_oom(exc: BaseException) -> bool:
    """torch.cuda.OutOfMemoryError, matched by name so tests need no torch import."""
    if type(exc).__name__ == "OutOfMemoryError":
        return True
    try:
        import torch
    except ImportError:
        return False
    return isinstance(exc, torch.cuda.OutOfMemoryError)


def _over_budget(started: float, budget: float, now_m: float) -> bool:
    """True when a lease has run longer than the GPU allowance the job started with."""
    return now_m - started > budget


def run_train(job: Job):
    """Train, evaluate and register one model, recording progress stages for the UI."""
    t0 = time.monotonic()
    stages: dict[str, dict] = {}

    def mark(name: str, status: str = "done", note: str | None = None):
        entry = {"status": status, "t": round(time.monotonic() - t0, 2)}
        if note:
            entry["note"] = note
        stages[name] = entry
        _set(job.id, result={"stages": stages})     # the UI polls job.result mid-run

    mark("queue")
    with SessionLocal() as db:
        tm = db.get(TrainedModel, job.params["model_id"])
        v = db.get(Version, tm.version_id)
        p = db.get(Project, tm.project_id)
        previous = (tm.status, tm.weights)      # what the row keeps when a run is cut short
        # The enqueue already reserved the estimate; this is the belt: if the allowance shrank
        # while the job waited, refuse rather than register a zero-epoch model.
        budget = metering.remaining(db, db.get(Workspace, job.workspace_id), "gpu_seconds")
        if budget < MIN_TRAIN_GPU_S:
            tm.status = "ready" if previous[0] == "ready" else "failed"     # never a promoted stub
            db.commit()
            raise QuotaExhausted(
                f"GPU time allowance exhausted: {budget:.0f} s left, a training run needs at least "
                f"{MIN_TRAIN_GPU_S:.0f} s"
            )
        tm.status = "training"; db.commit()
        history: list[dict] = []
        variant = tm.variant or tm.arch
        family = tm.family or "ultralytics"
        opts = {**job.params.get("options", {}), "model_id": tm.id}
        opts.update(batch=int(opts.get("batch", 8)), epochs=int(opts.get("epochs", 30)),
                    imgsz=int(opts.get("imgsz", 640)), max_minutes=opts.get("max_minutes"),
                    resume_from=opts.get("resume_from"))
        train_images = int((v.stats or {}).get("splits", {}).get("train") or 0)
        watchdog = _Watchdog(_first_limit(train_images, opts["epochs"], opts["imgsz"]))
        opts["stalled"] = lambda: watchdog.stalled     # read by the adapter's per-batch callbacks
        opts["heartbeat"] = watchdog.beat              # polling adapters call it only on real progress
        train_note = None
        lease_start: float | None = None
        budget_stop = False

        def on_epoch(ep, total, metrics):
            watchdog.tick()
            history[:] = [h for h in history if h["epoch"] != ep] + [{"epoch": ep, **metrics}]   # final val re-fires the last epoch
            with SessionLocal() as s:
                s.execute(update(TrainedModel).where(TrainedModel.id == tm.id).values(history=history))
                s.execute(update(Job).where(Job.id == job.id).values(progress=round(ep / total * 100, 1)))
                s.commit()

        def should_stop():
            nonlocal budget_stop
            if _cancelled(job.id) or watchdog.stalled:
                return True
            if lease_start is not None and _over_budget(lease_start, budget, time.monotonic()):
                budget_stop = True
                return True
            return False

        try:
            mark("acquire_gpu", "running")
            with scheduler.exclusive(f"training {variant}"):
                lease_start = time.monotonic()
                mark("acquire_gpu")
                mark("materialise", "running")
                versioning.cached_export(v, "coco")      # also proves the dataset is readable
                mark("materialise")
                mark("resolve_weights", "running")
                if family == "ultralytics":
                    start = _start_weights(variant, tm.task, job.params.get("options", {}).get("resume_from"))
                    mark("resolve_weights", note=str(start))
                else:
                    mark("resolve_weights", note="adapter default")
                mark("build_config", "running")
                mark("build_config")
                mark("train", "running")
                watchdog.start()
                try:
                    attempts = 0
                    while True:
                        try:
                            res = ADAPTERS[family].train(variant, versioning.version_dir(v), ml.TASK[p.type],
                                                         opts, on_epoch, should_stop)
                            break
                        except Exception as e:
                            if watchdog.stalled:
                                raise RuntimeError(f"no training progress for {watchdog.limit:g} s") from e
                            if not (_is_oom(e) and attempts == 0 and not history and opts["batch"] >= 2):
                                raise
                            attempts += 1
                            opts["batch"] //= 2
                            train_note = f"retried with batch={opts['batch']}"
                            gc.collect()                       # drop the failed attempt's tensors first
                            try:
                                import torch
                                torch.cuda.empty_cache()
                            except Exception:                  # CPU-only installs have nothing to free
                                pass
                            watchdog.reset()
                finally:
                    watchdog.stop()
                if watchdog.stalled:
                    raise RuntimeError(f"no training progress for {watchdog.limit:g} s")
                if budget_stop and len(history) < opts["epochs"]:
                    # The adapter stopped cleanly and kept best.pt, but that checkpoint covers only
                    # part of the run: never register it as a ready (deployable) model.
                    mark("train", "failed", note="GPU allowance exhausted; model not registered")
                    raise QuotaExhausted(
                        f"GPU time allowance exhausted after {len(history)} of {opts['epochs']} epochs "
                        f"({budget:g} s was left when the run started); model not registered"
                    )
                mark("train", note=train_note)
                mark("evaluate", "running")
                tm.weights, tm.status = res.weights, "ready"     # resolve() only accepts ready models
                db.commit()
                base = ml.final_metrics(history, tm.task)
                try:
                    with scheduler.training_scope():              # the holder may load its own model for eval
                        ev = evaluate(f"trained:{tm.id}", versioning.version_dir(v), tm.task,
                                      db=db, workspace_id=tm.workspace_id)
                    tm.metrics = {**base, "eval": ev}
                    mark("evaluate")
                except Exception as e:                            # a broken eval must not discard good weights
                    log.exception("evaluation failed for model %s", tm.id)
                    tm.metrics = {**base, "eval_error": f"{type(e).__name__}: {e}"}
                    mark("evaluate", "failed", note="model kept ready without evaluation")
                tm.history = history
                mark("register", "running")
                webhooks.emit(db, tm.workspace_id, "model.ready", {
                    "model_id": tm.id, "project_id": tm.project_id, "name": tm.name,
                    "variant": tm.variant, "task": tm.task})
                db.commit()
                mark("register")
            mark("release")
        except Exception as e:
            if isinstance(e, QuotaExhausted):
                # Keep a previously good checkpoint deployable; a fresh (queued) model simply fails.
                tm.status = "ready" if previous[0] == "ready" else "failed"
                tm.weights = previous[1]
            else:
                tm.status = "cancelled" if isinstance(e, Cancelled) else "failed"
            db.commit()
            shutil.rmtree(DATA_DIR / "train_data" / tm.id, ignore_errors=True)   # adapter only cleans on success
            for name, entry in list(stages.items()):
                if entry["status"] == "running":
                    mark(name, "failed")
            mark("release")                 # the exclusive context has already released the GPU
            _meter_gpu(db, job, time.monotonic() - t0)   # failed runs still held the card
            raise
        _meter_gpu(db, job, time.monotonic() - t0)
        return {"model_id": tm.id, **tm.metrics, "stages": stages}


def _meter_gpu(db, job: Job, seconds: float) -> None:
    """Meter wall-clock seconds a training lease held the card (spec 7.1)."""
    if seconds > 0:
        metering.record(db, job.workspace_id, "gpu_seconds", round(seconds, 2), project_id=job.project_id,
                        job_id=job.id)
        db.commit()


def run_autolabel(job: Job):
    P = job.params
    with SessionLocal() as db:
        p = db.get(Project, job.project_id)
        classes = db.scalars(select(LabelClass).where(LabelClass.project_id == p.id).order_by(LabelClass.created)).all()
        q = select(Image).where(Image.project_id == p.id, Image.deleted_at.is_(None))
        if P.get("image_ids"):
            q = q.where(Image.id.in_(P["image_ids"]))
        if P.get("batch_id"):
            q = q.where(Image.batch_id == P["batch_id"])
        if P.get("only_unannotated", True):
            q = q.where(Image.n_annotations == 0)
        rows = db.scalars(q).all()
        sam_ok = sam_available()
        ws = db.get(Workspace, job.workspace_id)
        labeled = total = processed = 0
        clamped = False
        for i, img in enumerate(rows):
            if _cancelled(job.id):
                break
            if metering.remaining(db, ws, "ai_calls") <= 0:
                clamped = True            # an enqueued job stops at the allowance instead of overrunning it
                break
            processed += 1
            anns = label_image(imaging.load(img.path), project_type=p.type, params=P, classes=classes,
                               db=db, workspace_id=job.workspace_id, sam_ok=sam_ok)
            if anns:
                set_annotations(db, img, (img.annotations or []) + anns)
                if img.status == "unassigned":
                    img.status = "review" if P.get("send_to_review", True) else "annotating"
                img.updated = now()
                labeled += 1
                total += len(anns)
                db.commit()          # keep earlier images even if a later VLM call dies
                # bill per committed image: a run that dies midway is still charged for what it labeled
                charge(db, ws, CREDIT_COST["autolabel_image"])
            # every processed image called the model, even when it produced no annotation
            metering.record(db, job.workspace_id, "ai_calls", 1, project_id=job.project_id, kind="autolabel")
            db.commit()
            _set(job.id, progress=round((i + 1) / max(1, len(rows)) * 100, 1))
        return {"images": processed, "selected": len(rows), "labeled": labeled,
                "annotations": total, "quota_clamped": clamped}


def run_health(job: Job):
    """Leakage + missing-box scan (needs the model): cached on the job row for the analytics page."""
    with SessionLocal() as db:
        p = db.get(Project, job.project_id)
        return health.scan_health(db, p)


def run_extract_frames(job: Job):
    """Sample a video into a batch of JPEG frames (fps / every N seconds / scene cuts)."""
    P = job.params
    with SessionLocal() as db:
        v = db.get(Video, P["video_id"])
        if v is None or v.deleted_at:
            raise RuntimeError("video not found")
        p = db.get(Project, v.project_id)
        db.get(Workspace, v.workspace_id)
        v.status, v.error = "extracting", ""
        db.commit()

        cap = cv2.VideoCapture(str(DATA_DIR / v.path))
        out_w = out_h = 0
        try:
            if not cap.isOpened():
                v.status, v.error = "failed", "video could not be opened"
                db.commit()
                raise RuntimeError("video could not be opened")

            # Trust the row when an earlier probe filled it; otherwise read it from the container.
            frame_count = v.frame_count or int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            fps = v.fps or float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            width = v.width or int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = v.height or int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            mode = P.get("mode", "fps")
            target_fps = float(P.get("target_fps") or 1.0)
            every_s = float(P.get("every_s") or 1.0)
            threshold = float(P.get("scene_threshold") or DEFAULT_SCENE_THRESHOLD)
            planned = set(plan_frames(frame_count, fps, mode, target_fps, every_s)) if (
                mode != "scene" and frame_count > 0 and fps > 0) else None
            step = max(1, round(fps * every_s) if mode == "every" else round(fps / target_fps)) if fps > 0 else 1

            batch = Batch(project_id=p.id, name=f"Video · {v.name}", source="video", created_by=P.get("created_by"))
            db.add(batch)
            db.flush()
            known = set(db.scalars(select(Image.sha256).where(Image.project_id == p.id, Image.deleted_at.is_(None))))
            stem = Path(v.name).stem or "video"
            kept = read = 0
            last_kept_time = -1.0
            prev_hist = None
            while True:
                if _cancelled(job.id):
                    break
                ok, frame = cap.read()
                if not ok or frame is None:
                    break
                index = read
                read += 1
                if mode == "scene":
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    hist = cv2.calcHist([gray], [0], None, [64], [0, 256])
                    cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
                    at = index / fps if fps > 0 else float(index)
                    keep = prev_hist is None or (at - last_kept_time >= 0.5
                                                 and is_scene_change(prev_hist, hist, threshold))
                    prev_hist = hist
                elif planned is not None:
                    keep = index in planned
                else:
                    keep = index % step == 0           # container did not report a frame count
                if not keep or kept >= 2000:
                    continue

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                im = PImage.fromarray(rgb)
                buf = io.BytesIO()
                im.save(buf, "JPEG", quality=92)
                data = buf.getvalue()
                digest = hashlib.sha256(data).hexdigest()
                if digest in known:                     # identical frame (long still, duplicate upload)
                    continue
                known.add(digest)
                im = imaging.open_image(data)
                out_w, out_h = out_w or im.width, out_h or im.height
                img = Image(id=new_id(), project_id=p.id, batch_id=batch.id, video_id=v.id, frame_index=index,
                            name=f"{stem}_f{index:06d}.jpg", sha256=digest, width=im.width, height=im.height,
                            size=len(data), path="", thumb="", split="train", status="unassigned", tags=[],
                            assignee_id=P.get("created_by"))
                img.path, img.thumb = imaging.store(f"projects/{p.id}/images", img.id, im)
                db.add(img)
                set_annotations(db, img, [])
                kept += 1
                if mode == "scene" and fps > 0:
                    last_kept_time = index / fps
                if kept % 10 == 0:                    # commit + report progress in one pause
                    db.commit()
                    _set(job.id, progress=round(min(99.0, (index + 1) / frame_count * 100), 1)
                         if frame_count else 0.0)

            v.status = "ready"
            v.error = ""
            v.frame_count = frame_count or read
            v.fps = fps
            v.duration = v.frame_count / fps if fps > 0 else 0.0
            v.width, v.height = width or out_w, height or out_h
            v.batch_id = batch.id
            db.commit()
            return {"video_id": v.id, "frames": kept, "batch_id": batch.id}
        except Exception as exc:
            if v.status != "failed":
                v.status, v.error = "failed", f"{type(exc).__name__}: {exc}"[:500]
                db.commit()
            raise
        finally:
            cap.release()


def run_track_forward(job: Job):
    """SAM box-prompt tracking: copy one annotation onto the next N frames of its video."""
    P = job.params
    with SessionLocal() as db:
        src = db.get(Image, P["image_id"])
        if src is None or src.deleted_at:
            raise RuntimeError("image not found")
        ann = next((a for a in src.annotations or [] if a.get("id") == P["annotation_id"]), None)
        if ann is None:
            raise RuntimeError("annotation not found")
        v = db.get(Video, src.video_id) if src.video_id else None
        if v is None:
            raise RuntimeError("image is not part of a video")
        p = db.get(Project, src.project_id)
        limit = max(1, min(int(P.get("frames") or 30), 120))
        start = src.frame_index if src.frame_index is not None else -1
        targets = db.scalars(select(Image).where(
            Image.project_id == p.id, Image.video_id == v.id, Image.frame_index > start,
            Image.deleted_at.is_(None)).order_by(Image.frame_index.asc()).limit(120)).all()[:limit]
        pairs = []
        for target in targets:
            try:
                pairs.append((target, imaging.load(target.path)))
            except Exception as e:                      # a missing file must not stop the whole track
                log.warning("track-forward skipped unreadable frame %s: %s", target.id, e)
        adapter = ADAPTERS.get("sam3")
        sam_box = adapter.segment_box if adapter is not None else None
        shapes = track.track_forward([im for _, im in pairs], ann.get("shape") or {}, sam_box=sam_box,
                                     project_type=p.type)
        track_id = ann.get("trackId") or f"t{new_id()}"
        # The seed joins its own track as a keyframe, so a later "Set start" is a real interpolation start.
        seed_anns = [{**a, "trackId": track_id, "keyframe": True} if a.get("id") == ann.get("id") else a
                     for a in src.annotations or []]
        set_annotations(db, src, seed_anns)
        db.commit()
        written = 0
        for (target, _im), shape in zip(pairs, shapes):
            anns, keep = track.merge_track(target.annotations or [], {
                "id": "a" + new_id(), "classId": ann["classId"], "shape": shape, "source": "sam3",
                "trackId": track_id, "keyframe": False}, track_id)
            if keep:
                set_annotations(db, target, anns)
                db.commit()
                written += 1
            _set(job.id, progress=round((written + 1) / max(1, len(pairs)) * 100, 1))
        return {"image_id": src.id, "tracked": written, "track_id": track_id}


HANDLERS = {"version": run_version, "export": run_export, "export_engine": run_export_engine,
            "train": run_train, "autolabel": run_autolabel, "health": run_health,
            "connector_sync": connectors.sync_job, "extract_frames": run_extract_frames,
            "track_forward": run_track_forward}


def run_insights_images(job: Job):
    with SessionLocal() as db:
        return insights_jobs.scan_images(db, db.get(Project, job.project_id))


def run_insights_leakage(job: Job):
    with SessionLocal() as db:
        version = (job.params or {}).get("version") or None
        return insights_jobs.scan_leakage(db, db.get(Project, job.project_id), version)


def run_insights_embedding(job: Job):
    with SessionLocal() as db:
        project = db.get(Project, job.project_id)
        needs_card = insights_embedding.clip_available()     # false: CV features never touch the GPU
        try:
            if needs_card:
                with scheduler.exclusive("insights embedding"):
                    return insights_jobs.scan_embedding(db, project)
            return insights_jobs.scan_embedding(db, project)
        finally:
            insights_embedding.release_clip()                # CLIP never outlives the scan
def run_retention(job: Job):
    """PDPA cleanup. Imported lazily so the worker starts even on a build without the privacy extra."""
    from .services.retention import run_retention as cleanup
    return cleanup(job)


HANDLERS = {"version": run_version, "export": run_export, "export_engine": run_export_engine,
            "train": run_train, "autolabel": run_autolabel, "health": run_health,
            "connector_sync": connectors.sync_job, "retention": run_retention,
            "extract_frames": run_extract_frames, "track_forward": run_track_forward,
            "drift": drift.run_job, "active_learning": active_learning.run_job,
            "insights_images": run_insights_images, "insights_leakage": run_insights_leakage,
            "insights_embedding": run_insights_embedding}


def _notify(job: Job, status: str, error: str = ""):
    """Fan the terminal job status out to webhooks; failures to notify never fail the job."""
    try:
        with SessionLocal() as db:
            webhooks.emit(db, job.workspace_id, "job.done", {
                "job_id": job.id, "kind": job.kind, "status": status, "project_id": job.project_id,
                "error": error})
            db.commit()
    except Exception:
        log.exception("could not enqueue job.done webhook for %s", job.id)


def run_one(jid: str):
    with SessionLocal() as db:
        job = db.get(Job, jid)
        db.expunge(job)
    try:
        result = HANDLERS[job.kind](job)
        final = "cancelled" if _cancelled(jid) else "done"
        _set(jid, status=final, progress=100.0 if final == "done" else job.progress, result=result, finished=now())
        _notify(job, final)
    except Cancelled:
        _set(jid, status="cancelled", finished=now())     # stopped on purpose before anything was produced
    except Exception as e:
        log.error("job %s (%s) failed\n%s", jid, job.kind, traceback.format_exc())
        _set(jid, status="failed", error=f"{type(e).__name__}: {e}", finished=now())
        _notify(job, "failed", f"{type(e).__name__}: {e}")


def recover():
    """Jobs left 'running' by a crashed process go back to the queue."""
    with SessionLocal() as db:
        db.execute(update(Job).where(Job.status.in_(("running", "cancelling")), Job.kind.in_(LOCAL_JOB_KINDS))
                   .values(status="queued"))
        db.commit()


OPS_SCHEDULE_S = 900           # check for due daily drift runs every 15 minutes
_last_ops_schedule = time.monotonic()


def _schedule_ops() -> None:
    """Queue the daily drift job for projects that have a ready model and no run in 24 h."""
    global _last_ops_schedule
    if time.monotonic() - _last_ops_schedule < OPS_SCHEDULE_S:
        return
    _last_ops_schedule = time.monotonic()
    try:
        with SessionLocal() as db:
            drift.schedule_daily(db)
    except Exception:                  # a scheduler failure must never stop the job loop
        log.exception("could not schedule drift jobs")


def loop(stop: threading.Event | None = None):
    from .config import RETENTION_CHECK_S
    from .services import heartbeat, retention
    recover()
    heartbeat.beat(LOCAL_JOB_KINDS)
    next_cleanup = 0.0
    while not (stop and stop.is_set()):
        if time.monotonic() >= next_cleanup:
            try:
                retention.enqueue_if_due()
            except Exception:                    # a broken retention pass must not stop every job
                log.exception("could not enqueue the retention job")
            next_cleanup = time.monotonic() + RETENTION_CHECK_S
        _schedule_ops()           # self-throttled; long jobs must not starve the daily drift check
        jid = _claim()
        if jid:
            heartbeat.beat(LOCAL_JOB_KINDS, current_job=jid)
            try:
                run_one(jid)
            finally:
                heartbeat.beat(LOCAL_JOB_KINDS)
        else:
            heartbeat.beat(LOCAL_JOB_KINDS)
            time.sleep(POLL)


def start_background() -> threading.Event:
    stop = threading.Event()
    threading.Thread(target=loop, args=(stop,), daemon=True, name="labeldesk-worker").start()
    threading.Thread(target=webhooks.flush_loop, args=(stop,), daemon=True, name="labeldesk-webhooks").start()
    return stop


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from .bootstrap import init_db
    init_db()
    # Production runs the worker as its own process (LD_EMBEDDED_WORKER=0), so retries need a flusher here too.
    threading.Thread(target=webhooks.flush_loop, args=(threading.Event(),), daemon=True,
                     name="labeldesk-webhooks").start()
    log.info("worker started")
    loop()
