"""Ultralytics training + cached inference."""
import shutil
import threading
import time
from collections import OrderedDict
from pathlib import Path

from PIL import Image as PImage

from ..config import DATA_DIR, PRETRAINED_DIR, TRAIN_DEVICE
from . import exporters

TASK = {"object-detection": "detect", "instance-segmentation": "segment", "classification": "classify"}
SIZES = ("n", "s", "m", "l", "x")


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


def final_metrics(history: list[dict], task: str) -> dict:
    """Pick headline metrics from the best epoch."""
    if not history:
        return {}
    if task == "classify":
        best = max(history, key=lambda h: h.get("metrics/accuracy_top1", 0))
        return {"accuracy_top1": best.get("metrics/accuracy_top1"), "accuracy_top5": best.get("metrics/accuracy_top5")}
    k = "(M)" if task == "segment" else "(B)"
    best = max(history, key=lambda h: h.get(f"metrics/mAP50-95{k}", h.get("metrics/mAP50-95(B)", 0)))
    return {"map50": best.get(f"metrics/mAP50{k}", best.get("metrics/mAP50(B)")),
            "map5095": best.get(f"metrics/mAP50-95{k}", best.get("metrics/mAP50-95(B)")),
            "precision": best.get(f"metrics/precision{k}", best.get("metrics/precision(B)")),
            "recall": best.get(f"metrics/recall{k}", best.get("metrics/recall(B)"))}


# --- inference ------------------------------------------------------------------

_cache: "OrderedDict[str, object]" = OrderedDict()
_lock = threading.Lock()


def _model(weights_rel: str):
    from ultralytics import YOLO
    with _lock:
        if weights_rel in _cache:
            _cache.move_to_end(weights_rel)
            return _cache[weights_rel]
        m = YOLO(str(DATA_DIR / weights_rel))
        _cache[weights_rel] = m
        while len(_cache) > 4:
            _cache.popitem(last=False)
        return m


def predict(weights_rel: str, im: PImage.Image, confidence: float = 0.4, overlap: float = 0.5) -> dict:
    """Roboflow-style response: centre-based boxes in pixels + optional polygon points."""
    t0 = time.time()
    m = _model(weights_rel)
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


def to_annotations(pred: dict, class_ids: dict[str, str]) -> list[dict]:
    """Convert a predict() response to editor annotations (normalized); class_ids maps name -> project class id."""
    import secrets
    W, H = pred["image"]["width"], pred["image"]["height"]
    out = []
    if "top" in pred:
        top = pred["predictions"][0]["class"] if pred["predictions"] else None
        if top in class_ids:
            out.append({"id": "a" + secrets.token_hex(5), "classId": class_ids[top], "shape": {"kind": "class"}})
        return out
    for p in pred["predictions"]:
        cid = class_ids.get(p["class"])
        if not cid:
            continue
        aid = "a" + secrets.token_hex(5)
        if p.get("points") and len(p["points"]) >= 3:
            shape = {"kind": "polygon", "points": [v for pt in p["points"] for v in (pt["x"] / W, pt["y"] / H)]}
        else:
            shape = {"kind": "bbox", "x": (p["x"] - p["width"] / 2) / W, "y": (p["y"] - p["height"] / 2) / H,
                     "w": p["width"] / W, "h": p["height"] / H}
        out.append({"id": aid, "classId": cid, "shape": shape, "confidence": p["confidence"]})
    return out
