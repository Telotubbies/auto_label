"""Good-only anomaly detection core: patch memory bank, nearest-neighbour score map, regions.

Training sees only normal (good) images. Each image becomes a grid of patch descriptors;
the bank keeps a bounded sample of standardised normal patches. Inference scores every patch
by its distance to the closest normal patch and normalises by the bank's own leave-one-image-out
distance, so scores are comparable across stations. Heatmaps and connected regions are returned
in image-normalised coordinates; the caller supplies the station threshold.

Descriptors are the cheap colour/layout features already used when CLIP is unavailable
(mean/std RGB, grey level, gradient), labelled `colour/layout` in the API and UI. No network,
GPU or model download is needed, which keeps the seam deterministic and testable.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image as PImage

GRID = 16
FEATURE_DIM = 8
MIN_NORMAL_IMAGES = 5
MAX_BANK_PATCHES = 4096
MAX_CALIBRATION_IMAGES = 24
MAX_REGIONS = 12
_CHUNK = 128
BACKEND = "colour/layout"
VLM_QUESTION = "Does this image show a defect, damage or other anomaly? Answer yes or no."
_LUMA = np.array([0.299, 0.587, 0.114], dtype=np.float32)
log = logging.getLogger(__name__)


class TrainingError(ValueError):
    """Our own validation failure: its message is safe to show to the user."""


@dataclass(frozen=True)
class Model:
    bank: np.ndarray
    mean: np.ndarray
    std: np.ndarray
    scale: float
    grid: int
    n_images: int
    metrics: dict


def patch_features(im: PImage.Image, grid: int = GRID) -> np.ndarray:
    """(grid*grid, FEATURE_DIM) local descriptors; deterministic for the same image."""
    side = grid * 4
    small = im.convert("RGB").resize((side, side), PImage.Resampling.BILINEAR)
    arr = np.asarray(small, dtype=np.float32) / 255.0
    gray = arr @ _LUMA
    gy, gx = np.gradient(gray)
    grad = np.hypot(gx, gy)
    blocks = arr.reshape(grid, 4, grid, 4, 3)
    means = blocks.mean(axis=(1, 3))
    stds = blocks.std(axis=(1, 3))
    gray_mean = gray.reshape(grid, 4, grid, 4).mean(axis=(1, 3))
    grad_mean = grad.reshape(grid, 4, grid, 4).mean(axis=(1, 3))
    return np.concatenate(
        [means.reshape(-1, 3), stds.reshape(-1, 3), gray_mean.reshape(-1, 1), grad_mean.reshape(-1, 1)], axis=1
    ).astype(np.float32)


def _cap(rows: np.ndarray, limit: int) -> np.ndarray:
    """Deterministic stride sample; keeps the bank bounded without random state."""
    if len(rows) <= limit:
        return rows
    step = int(np.ceil(len(rows) / limit))
    return rows[::step][:limit]


def _min_distances(bank: np.ndarray, patches: np.ndarray) -> np.ndarray:
    out = np.empty(len(patches), dtype=np.float32)
    for start in range(0, len(patches), _CHUNK):
        block = patches[start : start + _CHUNK]
        diff = block[:, None, :] - bank[None, :, :]
        out[start : start + _CHUNK] = np.sqrt(np.einsum("ijk,ijk->ij", diff, diff)).min(axis=1)
    return out


def train(images: list[PImage.Image], grid: int = GRID) -> Model:
    """Fit a normal-patch bank; raises ValueError when there are too few good images."""
    if len(images) < MIN_NORMAL_IMAGES:
        raise TrainingError(f"need at least {MIN_NORMAL_IMAGES} normal images to train a station")
    per_image = [patch_features(im, grid) for im in images]
    all_patches = np.concatenate(per_image)
    mean = all_patches.mean(axis=0)
    std = all_patches.std(axis=0)
    std = np.where(std < 1e-4, 1.0, std).astype(np.float32)
    standardised = [((p - mean) / std).astype(np.float32) for p in per_image]
    bank = _cap(np.concatenate(standardised), MAX_BANK_PATCHES)

    # Calibrate on leave-one-image-out neighbours so a training image never scores against itself.
    picked = _cap(np.arange(len(standardised)), MAX_CALIBRATION_IMAGES)
    raw_scores: list[float] = []
    for i in picked:
        others = np.concatenate([p for j, p in enumerate(standardised) if j != i])
        distances = _min_distances(_cap(others, MAX_BANK_PATCHES), standardised[int(i)])
        raw_scores.append(float(distances.max()))
    scale = max(float(np.percentile(raw_scores, 99)), 1e-6)
    metrics = {
        "normal_images": len(images),
        "patches": len(bank),
        "grid": int(grid),
        "backend": BACKEND,
        "train_p50": round(float(np.percentile(raw_scores, 50)), 4),
        "train_p99": round(scale, 4),
        "suggested_threshold": 1.0,
    }
    return Model(
        bank=bank,
        mean=mean.astype(np.float32),
        std=std,
        scale=scale,
        grid=int(grid),
        n_images=len(images),
        metrics=metrics,
    )


def _regions(cells: np.ndarray, threshold: float, grid: int) -> list[dict]:
    mask = cells >= threshold
    seen: set[tuple[int, int]] = set()
    out: list[dict] = []
    for row, col in zip(*np.nonzero(mask)):
        if (int(row), int(col)) in seen:
            continue
        stack = [(int(row), int(col))]
        seen.add((int(row), int(col)))
        rows, cols = [], []
        while stack:
            r, c = stack.pop()
            rows.append(r)
            cols.append(c)
            for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                if 0 <= nr < grid and 0 <= nc < grid and mask[nr, nc] and (nr, nc) not in seen:
                    seen.add((nr, nc))
                    stack.append((nr, nc))
        top, bottom = min(rows), max(rows)
        left, right = min(cols), max(cols)
        out.append(
            {
                "x": round(left / grid, 4),
                "y": round(top / grid, 4),
                "w": round((right - left + 1) / grid, 4),
                "h": round((bottom - top + 1) / grid, 4),
                "score": round(float(cells[rows, cols].max()), 4),
                "cells": len(rows),
            }
        )
    out.sort(key=lambda r: r["score"], reverse=True)
    return out[:MAX_REGIONS]


def score(model: Model, im: PImage.Image, threshold: float) -> dict:
    """Score one image against the normal bank and return heatmap + thresholded regions."""
    features = ((patch_features(im, model.grid) - model.mean) / model.std).astype(np.float32)
    distances = _min_distances(model.bank, features) / model.scale
    cells = distances.reshape(model.grid, model.grid)
    value = round(float(cells.max()), 4)
    limit = round(float(threshold), 4)
    return {
        "score": value,
        "threshold": limit,
        "is_anomaly": value >= limit,
        "heatmap": {"grid": model.grid, "values": [[round(float(v), 4) for v in row] for row in cells]},
        "regions": _regions(cells, limit, model.grid),
        "backend": BACKEND,
    }


def vlm_compare(im: PImage.Image, detected: bool) -> dict:
    """Optional zero-shot comparator: ask the VLM whether the image is anomalous.

    A missing/failed vLLM never fails the detector's result; callers get `available: false`.
    """
    from ..adapters import ADAPTERS

    ask = getattr(ADAPTERS.get("vlm"), "ask_yes_no", None)
    if ask is None:
        return {"available": False, "reason": "VLM adapter is not installed"}
    try:
        anomaly = bool(ask(im, VLM_QUESTION))
    except Exception:  # the comparator is optional; the detector result stands
        log.info("VLM zero-shot comparison failed", exc_info=True)
        return {"available": False, "reason": "VLM unavailable"}
    return {"available": True, "anomaly": anomaly, "agrees": anomaly == detected}


def save(path: Path, model: Model) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        bank=model.bank,
        mean=model.mean,
        std=model.std,
        scale=np.float32(model.scale),
        grid=np.int32(model.grid),
        n_images=np.int32(model.n_images),
        metrics=np.array(json.dumps(model.metrics)),
    )


def load(path: Path) -> Model:
    with np.load(Path(path), allow_pickle=False) as data:
        return Model(
            bank=data["bank"].astype(np.float32),
            mean=data["mean"].astype(np.float32),
            std=data["std"].astype(np.float32),
            scale=float(data["scale"]),
            grid=int(data["grid"]),
            n_images=int(data["n_images"]),
            metrics=json.loads(str(data["metrics"])),
        )
