"""HuggingFace detection family: D-FINE and RT-DETRv2 (Apache-2.0)."""
import importlib.util
import json
import logging
import time
from pathlib import Path

from PIL import Image as PImage

from ..config import DATA_DIR, TRAIN_DEVICE
from ..services import exporters
from .base import Availability, TrainResult, register

PREFIXES = ("ustc-community/dfine-", "PekingU/rtdetr_v2_")
VRAM_MB = 1600                                    # D-FINE / RT-DETRv2 inference, upper end of spec 3.6
CONF = 0.5                                        # validation threshold used for the reported P/R

log = logging.getLogger("labeldesk.hf")


def _check_variant(variant: str) -> None:
    if not variant.startswith(PREFIXES):
        raise ValueError(f"unsupported hf detector '{variant}'")


def _names(model) -> dict[int, str]:
    """id2label with int keys (checkpoints store them as ints or strings)."""
    return {int(k): str(v) for k, v in (getattr(model.config, "id2label", None) or {}).items()}


def _device(model):
    import torch
    return getattr(model, "device", None) or torch.device("cpu")


# --- inference ------------------------------------------------------------------

def _source(variant: str, weights: str | None) -> str:
    """The Hub id or local model dir _load() reads; also the scheduler key's identity."""
    return str(DATA_DIR / weights) if weights else variant


def lease_key(variant: str, weights: str | None) -> str:
    return f"hf|{_source(variant, weights)}"


def _load(variant: str, weights: str | None):
    """(processor, model) for a variant id or a DATA_DIR-relative trained model dir.

    Leases through the GPU scheduler so its VRAM ledger can evict the LRU model."""
    from ..gpu import scheduler

    source = _source(variant, weights)

    def _make():
        import torch
        from transformers import AutoImageProcessor, AutoModelForObjectDetection
        processor = AutoImageProcessor.from_pretrained(source)
        model = AutoModelForObjectDetection.from_pretrained(source)
        model.to("cuda" if torch.cuda.is_available() else "cpu").eval()
        return processor, model

    def _drop(_obj):
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:                         # CPU-only installs have nothing to free
            pass

    return scheduler.lease(f"hf|{source}", VRAM_MB, _make, _drop)


# --- training data ----------------------------------------------------------------

class CocoDetection:
    """COCO split as (PIL image, DETR target): boxes normalized cxcywh + 0-based class labels."""

    def __init__(self, root: Path):
        self.root = Path(root)
        data = json.loads((self.root / "_annotations.coco.json").read_text())
        self.images = data["images"]
        self.categories = sorted(data.get("categories", []), key=lambda c: c["id"])
        self._index = {c["id"]: i for i, c in enumerate(self.categories)}
        self._anns: dict[int, list] = {}
        for ann in data.get("annotations", []):
            self._anns.setdefault(ann["image_id"], []).append(ann)

    @property
    def classes(self) -> list[str]:
        return [c["name"] for c in self.categories]

    def __len__(self) -> int:
        return len(self.images)

    def __getitem__(self, i: int):
        import torch
        info = self.images[i]
        im = PImage.open(self.root / info["file_name"]).convert("RGB")
        W, H = im.size
        boxes, labels = [], []
        for ann in self._anns.get(info["id"], []):
            x, y, w, h = ann["bbox"]
            boxes.append([(x + w / 2) / W, (y + h / 2) / H, w / W, h / H])
            labels.append(self._index[ann["category_id"]])
        target = {"image_id": info["id"], "class_labels": torch.tensor(labels, dtype=torch.long),
                  "boxes": torch.tensor(boxes, dtype=torch.float32).reshape(-1, 4)}
        return im, target


def _collate(processor):
    """Standard HF DETR batch: processor pixel_values + one label dict per image."""
    def collate(batch):
        inputs = processor(images=[im for im, _ in batch], return_tensors="pt")
        labels = [{"class_labels": t["class_labels"], "boxes": t["boxes"]} for _, t in batch]
        return {**inputs, "labels": labels}
    return collate


def _validate(model, processor, root: Path) -> dict:
    """COCO AP/AP50 + greedy precision/recall at confidence 0.5 on a COCO split."""
    import torch
    from ..services.evaluate import coco_epoch_metrics

    path = Path(root) / "_annotations.coco.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if not data.get("images"):
        return {}
    cat_ids = {c["name"]: c["id"] for c in data.get("categories", [])}
    names, device = _names(model), _device(model)
    detections = []
    model.eval()
    try:
        with torch.no_grad():
            for info in data["images"]:
                im = PImage.open(Path(root) / info["file_name"]).convert("RGB")
                inputs = processor(images=im, return_tensors="pt")
                inputs = {k: v.to(device) if hasattr(v, "to") else v for k, v in inputs.items()}
                outputs = model(**inputs)
                result = processor.post_process_object_detection(
                    outputs, threshold=CONF,
                    target_sizes=torch.tensor([(im.height, im.width)], device=device))[0]
                for score, label, box in zip(result["scores"].tolist(), result["labels"].tolist(),
                                             result["boxes"].tolist()):
                    name = names.get(int(label), str(label))
                    if name not in cat_ids:                 # a class the checkpoint no longer knows
                        continue
                    x1, y1, x2, y2 = box
                    detections.append({"image_id": info["id"], "category_id": cat_ids[name],
                                       "bbox": [x1, y1, x2 - x1, y2 - y1], "score": float(score)})
    finally:
        model.train()                            # the Trainer keeps training after this callback

    metrics = coco_epoch_metrics(path, detections, conf=CONF)
    if not metrics:
        return {}
    return {"val/map50": metrics["map50"], "val/map5095": metrics["map5095"],
            "val/precision": metrics["precision"], "val/recall": metrics["recall"]}


class _EpochReport:
    """Epoch metrics -> common keys (spec P4).

    The Trainer logs an epoch's loss *after* on_epoch_end, so the loss is captured in on_log and
    the epoch is reported there; on_epoch_end computes validation and honours stop requests.
    Transformers requires a real TrainerCallback (it calls every event hook), so _build composes
    this with transformers.TrainerCallback."""

    def __init__(self, on_epoch, should_stop, history: list[dict], total: int,
                 model, processor, valid_root: Path, max_minutes: float | None = None):
        self.on_epoch, self.should_stop, self.history, self.total = on_epoch, should_stop, history, total
        self.model, self.processor, self.valid_root = model, processor, valid_root
        self.epoch = 0
        self.pending: dict = {}
        self.ready = False
        self.deadline = time.monotonic() + float(max_minutes) * 60 if max_minutes else None

    def on_epoch_end(self, args, state, control, model=None, processing_class=None, **kw):
        self.epoch = int(round(getattr(state, "epoch", 0) or 0)) or self.epoch + 1
        metrics = {}
        try:
            metrics.update(_validate(model or self.model, processing_class or self.processor,
                                     self.valid_root))
        except Exception:                            # a broken validation must not kill training
            log.exception("HF validation failed at epoch %s; reporting available metrics", self.epoch)
        self.pending, self.ready = metrics, True
        if self.should_stop() or (self.deadline is not None and time.monotonic() > self.deadline):
            control.should_training_stop = True

    def on_log(self, args, state, control, logs=None, **kw):
        """The epoch loss arrives after on_epoch_end; report the merged epoch exactly once."""
        if not self.ready or not isinstance(logs, dict) or not isinstance(logs.get("loss"), (int, float)):
            return
        metrics = {"train/loss": float(logs["loss"]), **self.pending}
        self.pending, self.ready = {}, False
        self.history.append({"epoch": self.epoch, **metrics})
        self.on_epoch(self.epoch, self.total, metrics)


def _report_class():
    """Epoch reporter + transformers' no-op callback base: Trainer calls every event hook."""
    from transformers import TrainerCallback

    class _Report(_EpochReport, TrainerCallback):
        pass
    return _Report


def _build(*, source: str, classes: list[str], train_ds, valid_ds, valid_root: Path, opts: dict,
           model_id: str, on_epoch, should_stop, history: list[dict]):
    """Processor, model and Trainer; the only place that imports transformers/torch at train time."""
    if importlib.util.find_spec("transformers") is None:
        raise RuntimeError("transformers not installed")
    if importlib.util.find_spec("torch") is None:
        raise RuntimeError("torch not installed")
    from transformers import AutoImageProcessor, AutoModelForObjectDetection, Trainer, TrainingArguments

    processor = AutoImageProcessor.from_pretrained(source)
    model = AutoModelForObjectDetection.from_pretrained(source, num_labels=len(classes),
                                                        ignore_mismatched_sizes=True)
    args = TrainingArguments(
        output_dir=str(DATA_DIR / "runs" / model_id),
        per_device_train_batch_size=int(opts.get("batch", 8)),
        per_device_eval_batch_size=int(opts.get("batch", 8)),
        num_train_epochs=float(opts.get("epochs", 30)),
        learning_rate=float(opts.get("lr") or 1e-4),
        remove_unused_columns=False,
        eval_strategy="no",                     # _EpochReport validates with pycocotools; Trainer's loss-only pass would duplicate it
        save_strategy="no",
        logging_strategy="epoch",
        report_to=[],
        use_cpu=TRAIN_DEVICE == "cpu",
        seed=42,
        dataloader_num_workers=0,
    )

    report = _report_class()(on_epoch, should_stop, history, int(opts.get("epochs", 30)),
                             model, processor, valid_root, max_minutes=opts.get("max_minutes"))
    trainer = Trainer(model=model, args=args, train_dataset=train_ds, eval_dataset=valid_ds,
                      data_collator=_collate(processor), callbacks=[report])
    return processor, model, trainer


class HfAdapter:
    family = "hf"

    def probe(self) -> Availability:
        if importlib.util.find_spec("transformers") is None:
            return Availability(False, "transformers not installed")
        if importlib.util.find_spec("torch") is None:
            return Availability(False, "torch not installed")
        return Availability(True)      # zoo weights download on first use

    def capabilities(self, variant: str) -> set[str]:
        return {"detect"}

    def runtime_key(self, variant: str, weights: str | None) -> str:
        return lease_key(variant, weights)

    def predict(self, variant, im, *, classes=None, prompt=None, weights=None, conf=0.4, iou=0.5) -> dict:
        """weights is a DATA_DIR-relative trained model dir; None loads the Hub variant.

        HF detectors already return final boxes, so iou stays unused here."""
        import torch

        _check_variant(variant)
        t0 = time.time()
        processor, model = _load(variant, weights)
        device = _device(model)
        inputs = processor(images=im, return_tensors="pt")
        inputs = {k: v.to(device) if hasattr(v, "to") else v for k, v in inputs.items()}
        with torch.no_grad():
            outputs = model(**inputs)
        result = processor.post_process_object_detection(
            outputs, threshold=conf, target_sizes=torch.tensor([(im.height, im.width)], device=device))[0]
        names = _names(model)
        preds = []
        for score, label, box in zip(result["scores"].tolist(), result["labels"].tolist(),
                                     result["boxes"].tolist()):
            ci = int(label)
            name = names.get(ci, str(ci))
            if classes and name not in classes:
                continue
            x1, y1, x2, y2 = box
            preds.append({"x": round((x1 + x2) / 2, 1), "y": round((y1 + y2) / 2, 1),
                          "width": round(x2 - x1, 1), "height": round(y2 - y1, 1),
                          "confidence": round(float(score), 4), "class_id": ci, "class": name})
        return {"predictions": preds, "time": round(time.time() - t0, 4),
                "image": {"width": im.width, "height": im.height}, "model": f"{self.family}:{variant}"}

    def train(self, variant, dataset_dir, task, opts, on_epoch, should_stop) -> TrainResult:
        """Fine-tune a Hub detector or a previous run on the version's cached COCO export."""
        _check_variant(variant)
        model_id = opts["model_id"]
        root = exporters.cached_export(Path(dataset_dir), "coco")
        train_ds = CocoDetection(root / "train")
        valid_root = root / "valid"
        valid_ds = CocoDetection(valid_root) if (valid_root / "_annotations.coco.json").exists() else None
        source = variant
        if opts.get("resume_from"):          # a trained-model id ("<id>") or its weights dir ("models/<id>")
            for candidate in (DATA_DIR / opts["resume_from"], DATA_DIR / "models" / opts["resume_from"]):
                if candidate.is_dir():
                    source = str(candidate)
                    break
        history: list[dict] = []
        processor, model, trainer = _build(
            source=source, classes=train_ds.classes, train_ds=train_ds, valid_ds=valid_ds,
            valid_root=valid_root, opts=opts, model_id=model_id, on_epoch=on_epoch,
            should_stop=should_stop, history=history)
        # from_pretrained(num_labels=...) resets id2label to LABEL_0..; predictions and eval need the dataset names
        model.config.id2label = dict(enumerate(train_ds.classes))
        model.config.label2id = {name: i for i, name in enumerate(train_ds.classes)}
        trainer.train()
        out = DATA_DIR / "models" / model_id
        model.save_pretrained(str(out))
        processor.save_pretrained(str(out))
        return TrainResult(weights=out.relative_to(DATA_DIR).as_posix(),
                           run_dir=str(DATA_DIR / "runs" / model_id), history=history)


register(HfAdapter())
