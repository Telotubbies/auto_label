"""Background job runner. The DB `jobs` table is the queue — no Redis needed.

Run standalone (`python -m app.worker`) on the GPU host, or embedded in the api
process (LD_EMBEDDED_WORKER=1, the dev default).
"""
import logging
import threading
import time
import traceback

from sqlalchemy import select, update

from .adapters import ADAPTERS
from .config import DATA_DIR, LOCAL_JOB_KINDS
from .db import SessionLocal
from .gpu import scheduler
from .models import Image, Job, LabelClass, Project, TrainedModel, Version, now, set_annotations
from .services import exporters, ml, segment, versioning, imaging

log = logging.getLogger("labeldesk.worker")
POLL = 1.5


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


def run_train(job: Job):
    with SessionLocal() as db:
        tm = db.get(TrainedModel, job.params["model_id"])
        v = db.get(Version, tm.version_id)
        p = db.get(Project, tm.project_id)
        tm.status = "training"; db.commit()
        history: list[dict] = []

        def on_epoch(ep, total, metrics):
            history[:] = [h for h in history if h["epoch"] != ep] + [{"epoch": ep, **metrics}]   # final val re-fires the last epoch
            with SessionLocal() as s:
                s.execute(update(TrainedModel).where(TrainedModel.id == tm.id).values(history=history))
                s.execute(update(Job).where(Job.id == job.id).values(progress=round(ep / total * 100, 1)))
                s.commit()
        try:
            variant = tm.variant or tm.arch
            with scheduler.exclusive(f"training {variant}"):
                res = ADAPTERS[tm.family or "ultralytics"].train(
                    variant, versioning.version_dir(v), ml.TASK[p.type],
                    {**job.params.get("options", {}), "model_id": tm.id}, on_epoch, lambda: _cancelled(job.id))
        except Exception:
            tm.status = "failed"; db.commit(); raise
        db.refresh(tm)
        tm.weights, tm.status = res.weights, "ready"
        tm.history = history
        tm.metrics = ml.final_metrics(history, tm.task)
        db.commit()
        return {"model_id": tm.id, **tm.metrics}


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
        conf = float(P.get("confidence", 0.4))
        model = db.get(TrainedModel, P["model_id"]) if P.get("method") == "model" else None
        if P.get("method") == "model" and (not model or model.status != "ready"):
            raise RuntimeError("selected model is not ready")
        wanted = [c for c in classes if not P.get("class_ids") or c.id in P["class_ids"]]
        by_name = {c.name: c.id for c in classes}
        done = 0
        for i, img in enumerate(rows):
            if _cancelled(job.id):
                break
            im = imaging.load(img.path)
            if model:
                anns = ml.to_annotations(ml.predict(model.weights, im, conf), by_name)
            else:
                import secrets
                prompts = [c.name for c in wanted]
                anns = [{"id": "a" + secrets.token_hex(5), "classId": wanted[ci].id, "confidence": round(sc, 4),
                         "shape": {"kind": "polygon", "points": poly} if p.type != "object-detection" else
                                  dict(kind="bbox", **dict(zip("xywh", _poly_box(poly))))}
                        for ci, poly, sc in segment.sam_text(im, prompts, conf)]
            if anns:
                set_annotations(db, img, (img.annotations or []) + anns)
                if img.status == "unassigned":
                    img.status = "review" if P.get("send_to_review", True) else "annotating"
                img.updated = now()
                done += 1
            db.commit()
            _set(job.id, progress=round((i + 1) / max(1, len(rows)) * 100, 1))
        return {"images": len(rows), "labeled": done}


def _poly_box(poly):
    xs, ys = poly[0::2], poly[1::2]
    return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)


HANDLERS = {"version": run_version, "export": run_export, "train": run_train, "autolabel": run_autolabel}


def run_one(jid: str):
    with SessionLocal() as db:
        job = db.get(Job, jid)
        db.expunge(job)
    try:
        result = HANDLERS[job.kind](job)
        final = "cancelled" if _cancelled(jid) else "done"
        _set(jid, status=final, progress=100.0 if final == "done" else job.progress, result=result, finished=now())
    except Exception as e:
        log.error("job %s (%s) failed\n%s", jid, job.kind, traceback.format_exc())
        _set(jid, status="failed", error=f"{type(e).__name__}: {e}", finished=now())


def recover():
    """Jobs left 'running' by a crashed process go back to the queue."""
    with SessionLocal() as db:
        db.execute(update(Job).where(Job.status.in_(("running", "cancelling")), Job.kind.in_(LOCAL_JOB_KINDS))
                   .values(status="queued"))
        db.commit()


def loop(stop: threading.Event | None = None):
    recover()
    while not (stop and stop.is_set()):
        jid = _claim()
        if jid:
            run_one(jid)
        else:
            time.sleep(POLL)


def start_background() -> threading.Event:
    stop = threading.Event()
    threading.Thread(target=loop, args=(stop,), daemon=True, name="labeldesk-worker").start()
    return stop


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from .bootstrap import init_db
    init_db()
    log.info("worker started")
    loop()
