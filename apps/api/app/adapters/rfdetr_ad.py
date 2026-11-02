"""RF-DETR (Apache-2.0) detection family: cached inference + fine-tuning.

rfdetr 1.11 exposes no per-epoch callback, so training runs in a child process: the parent polls
the PyTorch-Lightning CSV that rfdetr writes to <output_dir>/metrics.csv, gives the worker's
watchdog a heartbeat, and terminates the child at the next poll when a cancel arrives or
max_minutes runs out.
"""
import csv
import importlib.util
import json
import math
import multiprocessing
import os
import shutil
import time
from pathlib import Path

from ..config import DATA_DIR, TRAIN_DEVICE
from ..services import exporters
from .base import Availability, Cancelled, TrainResult, register

VARIANTS = {"nano": "RFDETRNano", "small": "RFDETRSmall", "medium": "RFDETRMedium", "large": "RFDETRLarge"}

# Inference lease per variant at 640 px; the 4.5 GB budget must fit a detector beside SAM 3.1.
VRAM_MB = {"nano": 1200, "small": 1500, "medium": 2000, "large": 2600}
VRAM_MB_DEFAULT = 2600
_POLL_S = 1.0                   # parent poll interval while the training child runs
_CKPT = ("checkpoint_best_total.pth", "checkpoint_best_ema.pth",
         "checkpoint_best_regular.pth", "checkpoint.pth")
# Lightning CSV column -> common metric key (spec P4)
_METRICS = {"train/loss": "train/loss", "val/mAP_50": "val/map50", "val/mAP_50_95": "val/map5095",
            "val/precision": "val/precision", "val/recall": "val/recall"}
_now = time.monotonic          # test seam for the max_minutes deadline


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


def _run_child(variant: str, init: dict, kw: dict) -> None:
    """Child-process entry point: the fit itself, picklable for the spawn start method."""
    _model_class(variant)(**init).train(**kw)


def _spawn(variant: str, init: dict, kw: dict):
    """Start the training child. rfdetr has no in-process cancel hook, so it must be killable."""
    ctx = multiprocessing.get_context("spawn")
    proc = ctx.Process(target=_run_child, args=(variant, init, kw))   # non-daemon: rfdetr spawns its DataLoader workers
    proc.start()
    return proc


def _stop_child(proc) -> None:
    proc.terminate()
    proc.join(timeout=10)
    if proc.is_alive():
        proc.kill()
        proc.join(timeout=5)


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

    return scheduler.lease(f"rfdetr|{weights or variant}", VRAM_MB.get(variant, VRAM_MB_DEFAULT), _make, _drop)


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
                # DATA_DIR and the export can sit on different drives on Windows (E: data, C: pytest
                # tmp); relpath raises ValueError across drives, so fall back to the absolute path.
                target = root / split / img["file_name"]
                try:
                    img["file_name"] = os.path.relpath(target, dst)
                except ValueError:
                    img["file_name"] = str(target)
            (dst / "_annotations.coco.json").write_text(json.dumps(data))
    if not (work / "valid" / "_annotations.coco.json").exists():
        shutil.copytree(work / "train", work / "valid")
    return work


def _progress_signature(paths) -> tuple:
    """(name, mtime, size) of the files a training child writes: a change means real progress."""
    sig = []
    for path in paths:
        try:
            st = path.stat()
        except OSError:                         # not written yet
            continue
        sig.append((path.name, st.st_mtime_ns, st.st_size))
    return tuple(sig)


def _device(value: str) -> str:
    """Ultralytics-style '0' -> 'cuda:0'; rfdetr (torch.device) rejects a bare index."""
    value = str(value).strip()
    return f"cuda:{value}" if value.isdigit() else value


def _class_names(coco: Path) -> list[str]:
    """Category names ordered by category id, read from the COCO export the run trained on."""
    data = json.loads(coco.read_text())
    cats = sorted(data.get("categories") or [], key=lambda c: int(c["id"]))
    return [str(c.get("name", c["id"])) for c in cats]


def _sibling_classes(weights: Path) -> list[str] | None:
    """The class names written beside a trained checkpoint; None when the file is missing or malformed."""
    try:
        names = json.loads((weights.parent / "classes.json").read_text())
    except (OSError, ValueError):
        return None
    return [str(n) for n in names] if isinstance(names, list) else None


def _preds(det, names: list[str] | None = None) -> list[dict]:
    """supervision.Detections -> shared prediction schema (centre boxes in pixels).

    Trained checkpoints carry ids only, so `names` (classes.json beside the weights) names them."""
    data_names = list(getattr(det, "data", {}).get("class_name") or [])
    out = []
    for i in range(len(det.xyxy)):
        x1, y1, x2, y2 = (float(v) for v in det.xyxy[i])
        ci = int(det.class_id[i])
        if i < len(data_names):
            name = str(data_names[i])
        elif names and 0 <= ci < len(names):
            name = names[ci]
        else:
            name = str(ci)
        out.append({"class": name, "class_id": ci,
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
        names = _sibling_classes(Path(path)) if path else None
        m = _load(variant, path)
        t0 = time.time()
        preds = _preds(m.predict(im, threshold=conf), names)
        if classes:
            preds = [p for p in preds if p["class"] in classes]
        return {"model": f"{self.family}:{variant}", "image": {"width": im.width, "height": im.height},
                "time": round(time.time() - t0, 4), "predictions": preds}

    def train(self, variant, dataset_dir, task, opts, on_epoch, should_stop) -> TrainResult:
        """Fine-tune on a version's cached COCO export. opts: model_id, epochs, batch, lr, patience, device,
        resume_from, max_minutes, heartbeat, stalled.

        The fit runs in a child process: cancel and max_minutes terminate it at the next poll.
        `stalled` and `heartbeat` are the worker's watchdog probes and are required by run_train."""
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

        kw = dict(dataset_dir=str(root), epochs=epochs, batch_size=int(opts["batch"]),
                  lr=float(opts.get("lr", 1e-4)), output_dir=str(output_dir),
                  early_stopping=True, early_stopping_patience=int(opts.get("patience", 50)),
                  tensorboard=False, run_test=False)     # the fit-end test pass must not need test/
        device = opts.get("device") or TRAIN_DEVICE
        if device:
            kw["device"] = _device(device)

        history: list[dict] = []
        seen = [0]                                   # CSV rows already reported
        by_epoch: dict[int, dict] = {}               # Lightning may split one epoch over several rows
        csv_path = output_dir / "metrics.csv"

        def _pump():
            if not csv_path.exists():
                return
            with open(csv_path, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            for row in rows[seen[0]:]:               # Lightning logs 0-based epochs; the UI counts from 1
                try:
                    ep = int(float(row.get("epoch") or "")) + 1
                except (TypeError, ValueError):
                    seen[0] += 1
                    continue                         # a step row (no epoch); a partial line is retried
                seen[0] += 1
                metrics = by_epoch.setdefault(ep, {})
                found = False
                for col, key in _METRICS.items():
                    value = _num(row.get(col))
                    if value is not None:            # only the keys the CSV actually carries
                        metrics[key] = value
                        found = True
                if not found:
                    continue
                if history and history[-1]["epoch"] == ep:
                    history[-1] = {"epoch": ep, **metrics}
                else:
                    history.append({"epoch": ep, **metrics})
                on_epoch(ep, epochs, dict(metrics))

        def _safe_pump():
            try:
                _pump()
            except OSError:                          # the trainer may rotate the file mid-read
                pass

        max_minutes = opts.get("max_minutes")
        deadline = _now() + float(max_minutes) * 60 if max_minutes else None
        watched = (csv_path, *(output_dir / name for name in _CKPT))
        last_sig = _progress_signature(watched)
        heartbeat = opts.get("heartbeat")
        stopped_by = None
        proc = _spawn(variant, init, kw)
        try:
            while True:
                _safe_pump()
                sig = _progress_signature(watched)
                if sig != last_sig:                  # the child wrote metrics or a checkpoint
                    last_sig = sig
                    if heartbeat:
                        heartbeat()                  # real progress only: a hung child must still stall
                if should_stop():
                    stopped_by = "cancelled"
                elif deadline is not None and _now() >= deadline:
                    stopped_by = "max_minutes"
                if stopped_by:
                    _stop_child(proc)
                    break
                if not proc.is_alive():
                    break
                time.sleep(_POLL_S)
            _safe_pump()                             # rows written since the last poll
        finally:
            if proc.is_alive():
                _stop_child(proc)

        if stopped_by is None and proc.exitcode not in (0, None):
            raise RuntimeError(f"rfdetr training failed (exit code {proc.exitcode})")
        if stopped_by and not any((output_dir / name).exists() for name in _CKPT):
            if opts.get("stalled") and opts["stalled"]():
                raise RuntimeError("no training progress before the first checkpoint")
            if stopped_by == "max_minutes":
                raise RuntimeError("max_minutes reached before the first checkpoint")
            raise Cancelled("cancelled before the first checkpoint")

        for name in _CKPT:
            src = output_dir / name
            if src.exists():
                break
        else:
            raise RuntimeError("training produced no checkpoint")
        dst = DATA_DIR / "models" / model_id / "best.pth"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        (dst.parent / "classes.json").write_text(json.dumps(_class_names(root / "train" / "_annotations.coco.json")))
        return TrainResult(weights=dst.relative_to(DATA_DIR).as_posix(), run_dir=str(output_dir), history=history)


register(RFDetrAdapter())
