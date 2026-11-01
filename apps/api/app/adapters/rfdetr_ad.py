"""RF-DETR (Apache-2.0) detection family: cached inference + fine-tuning.

rfdetr exposes no per-epoch callback, so training progress is read from the PyTorch-Lightning
CSV that it writes to <output_dir>/metrics.csv; a cancel or max_minutes cap therefore lands
only at the end of a run (the worker's no-progress watchdog still covers a hung epoch).
"""
import csv
import importlib.util
import json
import math
import os
import shutil
import threading
import time
from pathlib import Path

from PIL import Image as PImage

from ..config import DATA_DIR, TRAIN_DEVICE
from ..services import exporters
from .base import Availability, TrainResult, register

VARIANTS = {"nano": "RFDETRNano", "small": "RFDETRSmall", "medium": "RFDETRMedium", "large": "RFDETRLarge"}

VRAM_MB = 2600                  # medium/large at 640 px, upper end; inference leases only
_POLL_S = 1.0                   # metrics.csv poll interval while train() runs
_CKPT = ("checkpoint_best_total.pth", "checkpoint_best_ema.pth",
         "checkpoint_best_regular.pth", "checkpoint.pth")
# Lightning CSV column -> common metric key (spec P4)
_METRICS = {"train/loss": "train/loss", "val/mAP_50": "val/map50", "val/mAP_50_95": "val/map5095",
            "val/precision": "val/precision", "val/recall": "val/recall"}


def _require() -> None:
    if importlib.util.find_spec("rfdetr") is None:
        raise RuntimeError("rfdetr not installed")


def _model_class(variant: str):
    """The RFDETR<Size> class; imported lazily because the package is optional."""
    import rfdetr

    name = VARIANTS.get(variant)
    if name is None:
        raise ValueError(f"unknown rfdetr variant {variant!r}")
    return getattr(rfdetr, name)


def _load(variant: str, weights: str | None):
    """Cached model for (variant, weights); weights is an absolute checkpoint or None for the default."""
    from ..gpu import scheduler                  # lazy: keeps app.gpu importable before the adapters package

    def _make():
        cls = _model_class(variant)
        return cls(pretrain_weights=weights) if weights else cls()

    def _drop(_model):
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:                        # CPU-only installs have nothing to free
            pass

    return scheduler.lease(f"rfdetr|{weights or variant}", VRAM_MB, _make, _drop)


def _num(value) -> float | None:
    """A finite float, else None: Lightning leaves blank cells and NaN for early epochs."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _coco_root(dataset_dir: Path, model_id: str) -> Path:
    """The version's cached COCO export. RF-DETR always builds a valid loader, so a version with
    no valid images gets a thin per-run copy whose JSONs point back at the cached files and whose
    valid split mirrors train — without touching the shared export (evaluate()'s fallback stays honest)."""
    root = exporters.cached_export(dataset_dir, "coco")
    if (root / "valid" / "_annotations.coco.json").exists():
        return root
    work = DATA_DIR / "runs" / model_id / "coco"
    if not (work / "train" / "_annotations.coco.json").exists():
        for split in ("train", "valid", "test"):
            src = root / split / "_annotations.coco.json"
            if not src.exists():
                continue
            dst = work / split
            dst.mkdir(parents=True)
            data = json.loads(src.read_text())
            for img in data["images"]:
                img["file_name"] = os.path.relpath(root / split / img["file_name"], dst)
            (dst / "_annotations.coco.json").write_text(json.dumps(data))
    if not (work / "valid" / "_annotations.coco.json").exists():
        shutil.copytree(work / "train", work / "valid")
    return work


def _device(value: str) -> str:
    """Ultralytics-style '0' -> 'cuda:0'; rfdetr (torch.device) rejects a bare index."""
    value = str(value).strip()
    return f"cuda:{value}" if value.isdigit() else value


def _preds(det) -> list[dict]:
    """supervision.Detections -> shared prediction schema (centre boxes in pixels)."""
    names = list(getattr(det, "data", {}).get("class_name") or [])
    out = []
    for i in range(len(det.xyxy)):
        x1, y1, x2, y2 = (float(v) for v in det.xyxy[i])
        ci = int(det.class_id[i])
        out.append({"class": str(names[i]) if i < len(names) else str(ci), "class_id": ci,
                    "confidence": round(float(det.confidence[i]), 4),
                    "x": round((x1 + x2) / 2, 1), "y": round((y1 + y2) / 2, 1),
                    "width": round(x2 - x1, 1), "height": round(y2 - y1, 1)})
    return out


class RFDetrAdapter:
    family = "rfdetr"

    def probe(self) -> Availability:
        if importlib.util.find_spec("rfdetr") is None:
            return Availability(False, "rfdetr not installed")
        return Availability(True)                # zoo checkpoints download on first use

    def capabilities(self, variant: str) -> set[str]:
        return {"detect"}

    def predict(self, variant, im, *, classes=None, prompt=None, weights=None, conf=0.4, iou=0.5) -> dict:
        """weights is a DATA_DIR-relative checkpoint for trained models; None uses the pretrained variant.

        RF-DETR's predict() exposes only the score threshold, so iou stays unused here."""
        _require()
        path = str(DATA_DIR / weights) if weights else None
        m = _load(variant, path)
        t0 = time.time()
        preds = _preds(m.predict(im, threshold=conf))
        if classes:
            preds = [p for p in preds if p["class"] in classes]
        return {"model": f"{self.family}:{variant}", "image": {"width": im.width, "height": im.height},
                "time": round(time.time() - t0, 4), "predictions": preds}

    def train(self, variant, dataset_dir, task, opts, on_epoch, should_stop) -> TrainResult:
        """Fine-tune on a version's cached COCO export. opts: model_id, epochs, batch, lr, patience, device, resume_from."""
        _require()
        model_id = opts["model_id"]
        root = _coco_root(Path(dataset_dir), model_id)        # <dir>/{train,valid,test}/_annotations.coco.json
        output_dir = DATA_DIR / "runs" / model_id
        epochs = int(opts["epochs"])

        init = {}
        if opts.get("resume_from"):
            prev = DATA_DIR / "models" / opts["resume_from"]
            for name in ("best.pth", "checkpoint.pth"):
                if (prev / name).exists():
                    init["pretrain_weights"] = str(prev / name)
                    break
        model = _model_class(variant)(**init)

        kw = dict(dataset_dir=str(root), epochs=epochs, batch_size=int(opts["batch"]),
                  lr=float(opts.get("lr", 1e-4)), output_dir=str(output_dir),
                  early_stopping=True, early_stopping_patience=int(opts.get("patience", 50)),
                  tensorboard=False)
        device = opts.get("device") or TRAIN_DEVICE
        if device:
            kw["device"] = _device(device)

        history: list[dict] = []
        seen = [0]                                   # CSV rows already reported
        by_epoch: dict[int, dict] = {}               # Lightning may split one epoch over several rows
        stop = threading.Event()
        failures: list[BaseException] = []
        lock = threading.Lock()
        csv_path = output_dir / "metrics.csv"

        def _pump():
            with lock:
                if not csv_path.exists():
                    return
                with open(csv_path, newline="", encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))
                for row in rows[seen[0]:]:           # Lightning logs 0-based epochs; the UI counts from 1
                    try:
                        ep = int(float(row.get("epoch") or "")) + 1
                    except (TypeError, ValueError):
                        seen[0] += 1
                        continue                     # a step row (no epoch); a partial line is retried
                    seen[0] += 1
                    metrics = by_epoch.setdefault(ep, {})
                    found = False
                    for col, key in _METRICS.items():
                        value = _num(row.get(col))
                        if value is not None:        # only the keys the CSV actually carries
                            metrics[key] = value; found = True
                    if not found:
                        continue
                    if history and history[-1]["epoch"] == ep:
                        history[-1] = {"epoch": ep, **metrics}
                    else:
                        history.append({"epoch": ep, **metrics})
                    on_epoch(ep, epochs, dict(metrics))

        def _poll():
            while not stop.wait(_POLL_S):
                try:
                    _pump()
                except OSError:                      # the trainer may rotate the file mid-read
                    pass
                except Exception as e:               # a failed on_epoch must fail the run, not just the thread
                    failures.append(e)
                    stop.set()

        thread = threading.Thread(target=_poll, daemon=True)
        thread.start()
        try:
            model.train(**kw)
            _pump()                                  # rows written since the last poll
        finally:
            stop.set()
            thread.join(timeout=5)
        if failures:
            raise failures[0]

        for name in _CKPT:
            src = output_dir / name
            if src.exists():
                break
        else:
            raise RuntimeError("training produced no checkpoint")
        dst = DATA_DIR / "models" / model_id / "best.pth"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        return TrainResult(weights=dst.relative_to(DATA_DIR).as_posix(), run_dir=str(output_dir), history=history)


register(RFDetrAdapter())
