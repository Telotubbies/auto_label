"""Ultralytics family: YOLO, RT-DETR, YOLO-World. Training + cached inference."""
import importlib.util
import os
import shutil
import threading
import time
from pathlib import Path

from PIL import Image as PImage

from ..config import DATA_DIR, PRETRAINED_DIR, TRAIN_DEVICE
from ..services import exporters
from .base import Availability, TrainResult, register

TASK = {"object-detection": "detect", "instance-segmentation": "segment", "classification": "classify"}


def base_weights(task: str, size: str, family: str = "yolo26") -> str:
    """Local pretrained checkpoint when present (yolo26_ppe/models/pretrained), else an ultralytics hub name."""
    suffix = {"detect": "", "segment": "-seg", "classify": "-cls"}[task]
    local = PRETRAINED_DIR / f"{family}{size}{suffix}.pt"
    if local.exists():
        return str(local)
    return f"yolo11{size}{suffix}.pt"


_now = time.monotonic      # indirection so tests can fake the run-cap clock


class TrainingStalled(RuntimeError):
    """Raised from a batch callback when the worker's watchdog stopped seeing progress."""


def _stop_probe(trainer, should_stop, stalled) -> None:
    """Per-batch check: a stall aborts immediately, a cancel stops cleanly at the next checkpoint.

    Ultralytics only consults `trainer.stop` between epochs, so a run that stops making progress
    mid-epoch (slow batch, hung dataloader) needs a callback that raises instead."""
    if stalled is not None and stalled():
        raise TrainingStalled("training stalled")
    if should_stop():
        trainer.stop = True


def _start_weights(variant: str, task: str, resume_from: str | None = None) -> str:
    """Starting checkpoint: a previous run's last.pt (fine-tune continuation), a local pretrained copy, else the hub name."""
    if resume_from:
        for rel in (Path("runs") / resume_from / "weights" / "last.pt", Path("models") / resume_from / "best.pt"):
            if (DATA_DIR / rel).exists():
                return str(DATA_DIR / rel)
        raise FileNotFoundError(f"no saved weights for model {resume_from}")
    suffix = {"detect": "", "segment": "-seg", "classify": "-cls"}[task]
    plain = variant.startswith("rtdetr") or "world" in variant
    name = variant if plain or not suffix or variant.endswith(suffix) else variant + suffix
    local = PRETRAINED_DIR / f"{name}.pt"
    if local.exists():
        return str(local)
    if name.startswith("yolo26"):                    # no local yolo26 checkpoint: keep the v1 yolo11 fallback
        return "yolo11" + name[len("yolo26"):] + ".pt"
    return f"{name}.pt"


def train(model_id: str, version_dir: Path, project_type: str, opts: dict, on_epoch, should_stop) -> dict:
    """v1 wrapper over UltralyticsAdapter.train. Returns {weights, run_dir}."""
    task = TASK[project_type]
    variant = opts.get("variant") or f"yolo26{opts.get('size', 'n')}"
    res = UltralyticsAdapter().train(variant, version_dir, task, {**opts, "model_id": model_id}, on_epoch, should_stop)
    return {"weights": res.weights, "run_dir": res.run_dir}


# --- inference ------------------------------------------------------------------

VRAM_MB = 1400                                    # YOLO / RT-DETR inference, upper end of spec 3.6
_lock = threading.Lock()                          # serialises YOLO-World vocabulary changes (the scheduler may evict between calls)


def _cls_name(variant: str) -> str:
    v = variant.lower()
    if v.startswith("rtdetr"):
        return "RTDETR"
    if "world" in v:
        return "YOLOWorld"
    return "YOLO"


def caps_for(variant: str) -> set[str]:
    """Capabilities shared by the .pt and TensorRT runtimes of the same variant."""
    caps = {"segment"} if variant.endswith("-seg") else {"detect"}
    if "world" in variant:
        caps.add("open-vocab")
    return caps


def _load(weights: str, cls_name: str = "YOLO"):
    """Load through the GPU scheduler so its VRAM ledger can evict the LRU model."""
    from ..gpu import scheduler                  # lazy: keeps app.gpu importable before the adapters package

    def _make():
        import ultralytics
        return getattr(ultralytics, cls_name)(weights)

    def _drop(_model):
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:                         # CPU-only installs have nothing to free
            pass

    return scheduler.lease(f"{cls_name}|{weights}", VRAM_MB, _make, _drop)


def _run(m, im: PImage.Image, confidence: float, overlap: float) -> dict:
    """Roboflow-style response: centre-based boxes in pixels + optional polygon points."""
    t0 = time.time()
    r = m.predict(im, conf=confidence, iou=overlap, verbose=False)[0]
    names = r.names or {}                     # model's own index -> class name
    name = lambda i: names.get(i, str(i))
    preds = []
    if getattr(r, "probs", None) is not None:
        probs = r.probs.data.float().cpu().tolist()
        order = sorted(range(len(probs)), key=lambda i: -probs[i])
        preds = [{"class": name(i), "class_id": i, "confidence": round(probs[i], 4)}
                 for i in order[:5]]
        top = preds[0]["class"] if preds else None
        return {"predictions": preds, "top": top, "time": round(time.time() - t0, 4),
                "image": {"width": im.width, "height": im.height}}
    boxes = r.boxes
    polys = r.masks.xyn if getattr(r, "masks", None) is not None else None
    for i in range(len(boxes)):
        x1, y1, x2, y2 = boxes.xyxy[i].tolist()
        ci = int(boxes.cls[i])
        p = {"x": round((x1 + x2) / 2, 1), "y": round((y1 + y2) / 2, 1), "width": round(x2 - x1, 1),
             "height": round(y2 - y1, 1), "confidence": round(float(boxes.conf[i]), 4), "class_id": ci,
             "class": name(ci)}
        if polys is not None and i < len(polys):
            p["points"] = [{"x": round(float(px) * im.width, 1), "y": round(float(py) * im.height, 1)} for px, py in polys[i]]
        preds.append(p)
    return {"predictions": preds, "time": round(time.time() - t0, 4), "image": {"width": im.width, "height": im.height}}


def predict(weights_rel: str, im: PImage.Image, confidence: float = 0.4, overlap: float = 0.5) -> dict:
    """v1 entry point: trained weights relative to DATA_DIR."""
    return _run(_load(str(DATA_DIR / weights_rel)), im, confidence, overlap)


class UltralyticsAdapter:
    family = "ultralytics"

    def probe(self) -> Availability:
        if importlib.util.find_spec("ultralytics") is None:
            return Availability(False, "ultralytics not installed")
        return Availability(True)      # zoo weights download on first use

    def capabilities(self, variant: str) -> set[str]:
        return caps_for(variant)

    def train(self, variant, dataset_dir, task, opts, on_epoch, should_stop) -> TrainResult:
        """Train on a generated version dir. opts: model_id, epochs, imgsz, batch, patience, max_minutes, resume_from."""
        import ultralytics

        model_id = opts["model_id"]
        fmt = "folder" if task == "classify" else "yolo"
        ds = DATA_DIR / "train_data" / model_id
        exporters.export(fmt, dataset_dir, ds)
        data = str(ds) if task == "classify" else str(ds / "data.yaml")
        if task == "classify" and (ds / "valid").exists() and not (ds / "val").exists():
            (ds / "valid").rename(ds / "val")     # ultralytics classify expects train/ + val/

        run_dir = DATA_DIR / "runs" / model_id
        start = _start_weights(variant, task, opts.get("resume_from"))
        model = getattr(ultralytics, _cls_name(variant))(start)
        epochs = int(opts.get("epochs", 30))
        deadline = _now() + float(opts["max_minutes"]) * 60 if opts.get("max_minutes") else None
        history: list[dict] = []
        started = [0]

        def _started(trainer):
            started[0] = trainer.epoch + 1

        def _cb(trainer):
            _stop_probe(trainer, should_stop, opts.get("stalled"))
            if trainer.epoch + 1 > started[0]:
                return       # ultralytics re-fires this hook as epoch N+1 for its post-training best.pt validation
            m = {k: float(v) for k, v in (trainer.metrics or {}).items() if isinstance(v, (int, float))}
            loss = getattr(trainer, "tloss", None)
            if loss is not None:
                try:
                    m["train/loss"] = float(loss.sum()) if hasattr(loss, "sum") else float(loss)
                except Exception:
                    pass
            ep = trainer.epoch + 1
            history.append({"epoch": ep, **m})
            on_epoch(ep, epochs, m)
            if should_stop() or (deadline is not None and _now() > deadline):
                trainer.stop = True        # honoured by ultralytics at epoch end; best.pt is kept

        def _batch(trainer):
            _stop_probe(trainer, should_stop, opts.get("stalled"))

        model.add_callback("on_train_epoch_start", _started)
        model.add_callback("on_fit_epoch_end", _cb)
        # a stall must end the run mid-epoch, not at the next epoch boundary
        model.add_callback("on_train_batch_end", _batch)
        model.add_callback("on_val_batch_end", _batch)
        kw = dict(data=data, epochs=epochs, imgsz=int(opts.get("imgsz", 640)), batch=int(opts.get("batch", 8)),
                  project=str(run_dir.parent), name=run_dir.name, exist_ok=True, verbose=False, plots=True,
                  workers=0, patience=int(opts.get("patience", 50)))
        if TRAIN_DEVICE:
            kw["device"] = TRAIN_DEVICE
        model.train(**kw)

        best = run_dir / "weights" / "best.pt"
        if not best.exists():
            best = run_dir / "weights" / "last.pt"
        dst = DATA_DIR / "models" / model_id / "best.pt"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(best, dst)
        shutil.rmtree(ds, ignore_errors=True)
        return TrainResult(weights=dst.relative_to(DATA_DIR).as_posix(), run_dir=str(run_dir), history=history)

    def export(self, weights: str, fmt: str = "engine", *, half: bool = True, dest: Path | None = None) -> Path:
        """Build a runtime artifact from a checkpoint. TensorRT needs a CUDA GPU and the tensorrt package."""
        if fmt != "engine":
            raise ValueError(f"unsupported export format {fmt!r}")
        import ultralytics

        kw = {"format": fmt, "half": half}
        if TRAIN_DEVICE:
            kw["device"] = TRAIN_DEVICE
        onnx = Path(weights).with_suffix(".onnx")
        try:
            out = Path(ultralytics.YOLO(str(weights)).export(**kw))
        finally:
            onnx.unlink(missing_ok=True)                  # ultralytics leaves the intermediate ONNX behind
        if dest is None:
            return out
        dest.parent.mkdir(parents=True, exist_ok=True)
        if out.resolve() == dest.resolve():
            return dest
        tmp = dest.with_name(dest.name + ".tmp")          # atomic swap: a failed rebuild keeps the old engine
        shutil.move(str(out), str(tmp))
        try:
            os.replace(tmp, dest)
        except OSError:
            tmp.unlink(missing_ok=True)
            raise
        return dest

    def predict(self, variant, im, *, classes=None, prompt=None, weights=None, conf=0.4, iou=0.5) -> dict:
        cls = _cls_name(variant)
        if cls == "YOLOWorld" and not classes:
            raise ValueError("YOLO-World needs classes")
        if weights:                                    # trained model: DATA_DIR-relative path
            path = str(DATA_DIR / weights)
        else:
            local = PRETRAINED_DIR / f"{variant}.pt"
            path = str(local) if local.exists() else f"{variant}.pt"
        m = _load(path, cls)
        if cls == "YOLOWorld":
            with _lock:                                # vocabulary lives on the cached model: set + run atomically
                m.set_classes(list(classes))
                out = _run(m, im, conf, iou)
        else:
            out = _run(m, im, conf, iou)
        out["model"] = f"{self.family}:{variant}"
        return out


register(UltralyticsAdapter())
