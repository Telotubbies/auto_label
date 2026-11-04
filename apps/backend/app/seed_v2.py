"""v2 demo seed: a ready version, an evaluated PPE YOLO26n model and the gate-camera stream.

``bootstrap.init_db()`` runs this on a fresh demo DB when ``LD_SEED_DEMO=1``. Every step is
idempotent (rows are looked up by their demo names), so a restart upgrades an existing DB in
place instead of duplicating content. The model is the repo's real PPE YOLO26n checkpoint and its
headline metrics are the values recorded by that training run; the deep COCO panel is marked as
not evaluated on this dataset, because measuring it needs the demo GPU.
"""
from __future__ import annotations

import csv
import logging
import shutil
from pathlib import Path

import cv2
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import DATA_DIR, REPO_ROOT
from .db import SessionLocal
from .models import Image, Project, Stream, TrainedModel, Version, Workspace
from .services import ml, versioning

log = logging.getLogger("labeldesk.seed")

WS_SLUG = "labeldesk-demo"
PROJECT_SLUG = "ppe-detection"
VERSION_NAME = "Demo v1"
VERSION_IMAGES = 24                    # approved so the seed leaves review work for the board demo
MODEL_NAME = "PPE Detector YOLO26n"
STREAM_NAME = "Gate camera"

# The best real nano run in the repo (yolo26_ppe/reports/metrics) and the checkpoint's own class names.
MODEL_RUN = REPO_ROOT / "yolo26_ppe" / "models" / "archive" / "version_2_improved_baseline" / "nano_detection" / "training_run"
MODEL_CLASSES = ["person", "helmet", "boots", "shoes", "harness"]

ZONE = {"id": "gate", "label": "Gate area", "points": [0.08, 0.42, 0.92, 0.42, 0.92, 0.96, 0.08, 0.96]}
RULES = [
    {"kind": "line", "class": "person", "line": [0.05, 0.6, 0.95, 0.6], "direction": "both"},
    {"kind": "count", "class": "person", "op": ">=", "k": 3, "for_s": 2.0},
]
VIDEO_FPS = 10                         # the stream status panel must show >= 5 FPS
VIDEO_SIZE = (640, 360)
FRAMES_PER_IMAGE = 5


def seed_demo_v2() -> dict:
    """Ensure the demo content exists; return the row ids ({} when the demo project is absent)."""
    with SessionLocal() as db:
        project = db.scalar(select(Project).join(Workspace, Workspace.id == Project.workspace_id)
                            .where(Workspace.slug == WS_SLUG, Project.slug == PROJECT_SLUG,
                                   Project.deleted_at.is_(None)))
        if project is None:                    # a real (non-demo) install: nothing to seed
            return {}
        version = _ensure_version(db, project)
        model = _ensure_model(db, project, version)
        stream = _ensure_stream(db, project, model)
        db.commit()
        return {"version": version.id if version else None,
                "model": model.id if model else None,
                "stream": stream.id if stream else None}


def _ensure_version(db: Session, project: Project) -> Version | None:
    existing = db.scalars(select(Version).where(Version.project_id == project.id)
                          .order_by(Version.number.desc())).first()
    if existing is not None:
        return existing
    images = db.scalars(select(Image).where(Image.project_id == project.id, Image.status != "done",
                                            Image.n_annotations > 0, Image.deleted_at.is_(None))
                        .order_by(Image.created).limit(VERSION_IMAGES)).all()
    for img in images:
        img.status = "done"
    db.flush()
    version = Version(project_id=project.id, number=1, name=VERSION_NAME, settings={}, status="ready")
    db.add(version)
    db.flush()
    try:
        version.stats = versioning.generate(db, version)
    except Exception as e:                     # a pruned checkout has no seed images: seed what we can
        log.warning("seed_v2: version generation failed — %s", e)
        db.delete(version)
        db.flush()
        return None
    db.flush()
    log.info("seed_v2: version v1 with %s images", version.stats.get("images"))
    return version


def _ensure_model(db: Session, project: Project, version: Version | None) -> TrainedModel | None:
    existing = db.scalar(select(TrainedModel).where(TrainedModel.project_id == project.id,
                                                    TrainedModel.name == MODEL_NAME))
    if existing is not None:
        return existing
    src = MODEL_RUN / "weights" / "best.pt"
    if version is None or not src.is_file():
        log.warning("seed_v2: no ready version or PPE checkpoint — skipping the demo model")
        return None
    model = TrainedModel(workspace_id=project.workspace_id, project_id=project.id, version_id=version.id,
                         name=MODEL_NAME, arch="yolo26n", variant="yolo26n", task="detect",
                         family="ultralytics", license="AGPL-3.0", status="ready", classes=list(MODEL_CLASSES))
    db.add(model)
    db.flush()
    dst = DATA_DIR / "models" / model.id / "best.pt"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    model.weights = dst.relative_to(DATA_DIR).as_posix()
    history = _recorded_history()
    metrics = ml.final_metrics(history, "detect") if history else {}
    model.history = history
    model.metrics = {**metrics, "eval": _recorded_eval()}
    db.flush()
    log.info("seed_v2: model %s with %s history rows", model.id, len(history))
    return model


def _recorded_history() -> list[dict]:
    """Per-epoch validation metrics recorded by the original run (results.csv)."""
    path = MODEL_RUN / "results.csv"
    if not path.is_file():
        return []
    out = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                out.append({"epoch": int(row["epoch"]),
                            **{k: float(v) for k, v in row.items() if k.startswith("metrics/")}})
            except (KeyError, TypeError, ValueError):
                continue
    return out


def _recorded_eval() -> dict:
    """A complete report shape whose note says the numbers were not measured on this dataset.

    TotalInstances/curves are left empty on purpose: the Models page shows the provenance note
    instead of a chart that would imply a fresh COCO evaluation.
    """
    return {"split": "test", "note": "Recorded from the original PPE YOLO26n training run — not evaluated "
                                     "on this dataset. Train a model here to score it with COCO metrics.",
            "iou": "bbox",
            "coco": {k: 0.0 for k in ("AP", "AP50", "AP75", "APs", "APm", "APl",
                                      "AR1", "AR10", "AR100", "ARs", "ARm", "ARl")},
            "tide": {k: 0.0 for k in ("cls", "loc", "both", "dupe", "bkg", "missed")},
            "per_class": [], "f1_best": {"conf": 0.4, "f1": 0.0},
            "confusion": {"labels": [], "matrix": [], "images": []},
            "pr_curve": [], "worst": [], "latency_ms": 0.0, "detections": [], "split_images": 0}


def _ensure_stream(db: Session, project: Project, model: TrainedModel | None) -> Stream | None:
    existing = db.scalar(select(Stream).where(Stream.project_id == project.id, Stream.name == STREAM_NAME))
    if existing is not None:
        return existing
    if model is None:
        log.warning("seed_v2: no demo model — skipping the gate camera")
        return None
    _ensure_demo_video(db, project)
    stream = Stream(workspace_id=project.workspace_id, project_id=project.id, name=STREAM_NAME,
                    source="file:videos/demo.mp4", model_ref=f"trained:{model.id}", sample_fps=5.0,
                    zones=[ZONE], rules=RULES, status="stopped")
    db.add(stream)
    db.flush()
    log.info("seed_v2: gate camera %s", stream.id)
    return stream


def _ensure_demo_video(db: Session, project: Project) -> None:
    """A looping walk-past clip made from the seeded frames, so the demo needs no camera."""
    dest = DATA_DIR / "videos" / "demo.mp4"
    if dest.is_file():
        return
    frames, seen = [], set()
    rows = db.scalars(select(Image).where(Image.project_id == project.id, Image.deleted_at.is_(None))
                      .order_by(Image.created).limit(VERSION_IMAGES)).all()
    for row in rows:
        frame = _read_frame(DATA_DIR / row.path)
        if frame is not None and row.path not in seen:
            seen.add(row.path)
            frames.append(frame)
    if not frames:                              # project images missing (pruned checkout): try the raw folder
        for path in sorted((REPO_ROOT / "data" / "raw" / "custom_capture").glob("*.jpg"))[:VERSION_IMAGES]:
            frame = _read_frame(path)
            if frame is not None:
                frames.append(frame)
    if not frames:
        log.warning("seed_v2: no frames for videos/demo.mp4 — the gate camera will report a missing file")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(dest), cv2.VideoWriter_fourcc(*"mp4v"), VIDEO_FPS, VIDEO_SIZE)
    if not writer.isOpened():
        writer.release()
        dest.unlink(missing_ok=True)
        log.warning("seed_v2: OpenCV cannot write %s — the gate camera will report a missing file", dest)
        return
    try:
        for frame in frames:
            for _ in range(FRAMES_PER_IMAGE):    # a short dwell per frame keeps the scene readable
                writer.write(frame)
    finally:
        writer.release()
    log.info("seed_v2: wrote %s (%s frames)", dest, len(frames) * FRAMES_PER_IMAGE)


def _read_frame(path: Path):
    try:
        frame = cv2.imread(str(path))
        return None if frame is None else cv2.resize(frame, VIDEO_SIZE)
    except Exception:
        return None
