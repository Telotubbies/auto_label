"""Ultralytics family: YOLO, RT-DETR, YOLO-World. Training + cached inference."""
import importlib.util
import shutil
import threading
import time
from collections import OrderedDict
from pathlib import Path

from PIL import Image as PImage

from ..config import DATA_DIR, PRETRAINED_DIR, TRAIN_DEVICE
from ..services import exporters
from .base import Availability, register

TASK = {"object-detection": "detect", "instance-segmentation": "segment", "classification": "classify"}


def base_weights(task: str, size: str, family: str = "yolo26") -> str:
    """Local pretrained checkpoint when present (yolo26_ppe/models/pretrained), else an ultralytics hub name."""
    suffix = {"detect": "", "segment": "-seg", "classify": "-cls"}[task]
    local = PRETRAINED_DIR / f"{family}{size}{suffix}.pt"
    if local.exists():
        return str(local)
    return f"yolo11{size}{suffix}.pt"


def train(model_id: str, version_dir: Path, project_type: str, opts: dict, on_epoch, should_stop) -> dict:
    """Train on a generated version. on_epoch(epoch, total, metrics) streams progress."""
    from ultralytics import YOLO

    task = TASK[project_type]
    fmt = "folder" if task == "classify" else "yolo"
    ds = DATA_DIR / "train_data" / model_id
    exporters.export(fmt, version_dir, ds)
    data = str(ds) if task == "classify" else str(ds / "data.yaml")
    if task == "classify" and (ds / "valid").exists() and not (ds / "val").exists():
        (ds / "valid").rename(ds / "val")     # ultralytics classify expects train/ + val/

    run_dir = DATA_DIR / "runs" / model_id
    model = YOLO(base_weights(task, opts.get("size", "n")))
    epochs = int(opts.get("epochs", 30))

    def _cb(trainer):
        m = {k: float(v) for k, v in (trainer.metrics or {}).items() if isinstance(v, (int, float))}
        loss = getattr(trainer, "tloss", None)
        if loss is not None:
            try:
                m["train/loss"] = float(loss.sum()) if hasattr(loss, "sum") else float(loss)
            except Exception:
                pass
        on_epoch(trainer.epoch + 1, epochs, m)
        if should_stop():
            trainer.stop = True        # honoured by ultralytics at epoch end

    model.add_callback("on_fit_epoch_end", _cb)
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
    return {"weights": str(dst.relative_to(DATA_DIR).as_posix()), "run_dir": str(run_dir)}


# --- inference ------------------------------------------------------------------

_cache: "OrderedDict[str, object]" = OrderedDict()
_lock = threading.Lock()


def _cls_name(variant: str) -> str:
    v = variant.lower()
    if v.startswith("rtdetr"):
        return "RTDETR"
    if "world" in v:
        return "YOLOWorld"
    return "YOLO"


def _load(weights: str, cls_name: str = "YOLO"):
    import ultralytics
    key = f"{cls_name}|{weights}"
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
        m = getattr(ultralytics, cls_name)(weights)
        _cache[key] = m
        while len(_cache) > 4:
            _cache.popitem(last=False)
        return m


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
        caps = {"segment"} if variant.endswith("-seg") else {"detect"}
        if "world" in variant:
            caps.add("open-vocab")
        return caps

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
