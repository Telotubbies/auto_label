"""Embedding-map job: CLIP ViT-B/32 when available, cheap CV features otherwise.

Features are cached per image sha256 on disk; the 2-D projection uses UMAP when installed and a
deterministic numpy PCA otherwise. The worker takes the GPU lease only when CLIP will run on CUDA
and always calls `release_clip()` after the scan so the card is never held outside the ledger.
"""

import math
import threading
from collections import Counter

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import DATA_DIR
from ..models import Image, LabelClass, Project
from . import imaging, insights

EMBED_MAX = 3000
EMBED_BATCH = 16
CLIP_MODEL_ID = "openai/clip-vit-base-patch32"
FEATURE_DIR = DATA_DIR / "insights" / "features"
SPLIT_ORDER = ("train", "valid", "test")
# None = untried, False = unavailable, else (torch, model, processor, device). Never outlives a scan.
_CLIP: tuple | bool | None = None
_CLIP_LOCK = threading.Lock()
def _stride(items: list, count: int) -> list:
    if count <= 0:
        return []
    if count >= len(items):
        return list(items)
    return items[:: math.ceil(len(items) / count)][:count]


def _sample_images(rows: list, limit: int) -> list:
    """Deterministic stratified sample: proportional per split, at least one per non-empty split.

    The embedding map must stay bounded without silently dropping a split, so every non-empty
    group gets a quota and the remainder is filled from the ordered full list. Output keeps the
    caller's order (created, id) as far as the picked set allows.
    """
    if limit <= 0:
        return []
    if len(rows) <= limit:
        return list(rows)

    groups: dict[str, list] = {}
    for row in rows:
        key = row.split if row.split in SPLIT_ORDER else (row.split or "")
        groups.setdefault(key, []).append(row)
    keys = [s for s in SPLIT_ORDER if s in groups]
    keys += [s for s in groups if s not in SPLIT_ORDER]     # dict order = first appearance
    if len(keys) > limit:                                    # pathological: more splits than slots
        return _stride(rows, limit)

    total = sum(len(groups[k]) for k in keys)
    quota = {k: max(1, (limit * len(groups[k])) // total) for k in keys}
    while sum(quota.values()) > limit:
        roomy = [k for k in keys if quota[k] > 1]
        if not roomy:
            break
        quota[max(roomy, key=lambda k: (quota[k], len(groups[k])))] -= 1
    while sum(quota.values()) < limit:
        added = False
        for k in keys:
            if quota[k] < len(groups[k]) and sum(quota.values()) < limit:
                quota[k] += 1
                added = True
        if not added:
            break

    picked: list = []
    chosen: set[int] = set()
    for k in keys:
        for row in _stride(groups[k], quota[k]):
            if id(row) not in chosen:
                picked.append(row)
                chosen.add(id(row))
    if len(picked) < limit:                                  # stride rounding left a few slots
        for row in rows:
            if len(picked) >= limit:
                break
            if id(row) not in chosen:
                picked.append(row)
                chosen.add(id(row))
    position = {id(row): i for i, row in enumerate(rows)}
    picked.sort(key=lambda row: position[id(row)])
    return picked[:limit]

def _features(row: Image) -> np.ndarray:
    image = imaging.load(row.thumb or row.path)
    image.thumbnail((64, 64))
    gray = np.asarray(image.convert("L").resize((8, 8)), dtype=np.float64).ravel() / 255.0
    hsv = np.asarray(image.convert("HSV").resize((16, 16)), dtype=np.uint8)
    hist: list[float] = []
    for channel in range(3):
        counts, _ = np.histogram(hsv[:, :, channel], bins=4, range=(0, 256))
        total = float(counts.sum()) or 1.0
        hist.extend((counts / total).tolist())
    return np.concatenate([gray, np.asarray(hist, dtype=np.float64)])


def _clip_backend():
    """(torch, model, processor, device) when CLIP ViT-B/32 loads; None keeps the cheap CV path."""
    global _CLIP
    if _CLIP is not None:
        return _CLIP or None
    with _CLIP_LOCK:
        if _CLIP is not None:
            return _CLIP or None
        try:
            import torch
            from transformers import CLIPModel, CLIPProcessor

            device = "cuda" if torch.cuda.is_available() else "cpu"
            model = CLIPModel.from_pretrained(CLIP_MODEL_ID)
            processor = CLIPProcessor.from_pretrained(CLIP_MODEL_ID)
            model.eval()
            model.to(device)
        except Exception:            # not installed / offline / no weights: never fail the job
            _CLIP = False
            return None
        _CLIP = (torch, model, processor, device)
        return _CLIP


def clip_available() -> bool:
    """True when the next scan will load CLIP *and* place it on CUDA (cheap: no model load).

    The worker uses this before taking the GPU: a missing `transformers` (the default install) or a
    CPU-only box means the scan computes cheap CV features and must not pause streams or sleep vLLM.
    """
    if isinstance(_CLIP, tuple):
        return _CLIP[3] == "cuda"
    if _CLIP is False:
        return False
    try:
        import torch
        from transformers import CLIPModel, CLIPProcessor  # noqa: F401  importable is enough to decide
    except Exception:
        return False
    return bool(torch.cuda.is_available())


def release_clip() -> None:
    """Drop the loaded CLIP model so it stops holding VRAM/RAM outside the scheduler's ledger.

    A cached "unavailable" verdict (False) is kept: retrying an offline download on every scan would
    only slow the job down. Called from the worker's `finally` after the scan, exceptions included.
    """
    global _CLIP
    if not isinstance(_CLIP, tuple):
        return
    _CLIP = None
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:            # torch missing: nothing was placed on a card
        return


def _feature_path(backend: str, sha: str):
    return FEATURE_DIR / backend / sha[:2] / f"{sha}.npy"


def _load_feature(backend: str, sha: str):
    if not sha:
        return None
    try:
        return np.load(_feature_path(backend, sha))
    except Exception:            # missing/corrupt cache entry: recompute this row
        return None


def _store_feature(backend: str, sha: str, vector: np.ndarray) -> None:
    if not sha:
        return
    path = _feature_path(backend, sha)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(path, vector)
    except Exception:            # an unwritable cache must not lose the scan
        return


def _clip_vectors(state: tuple, rows: list) -> list[tuple[Image, np.ndarray]]:
    torch, model, processor, device = state
    images = []
    valid = []
    for row in rows:
        try:
            im = imaging.load(row.thumb or row.path).convert("RGB")
        except Exception:        # unreadable row: omitted rather than given a fake position
            continue
        images.append(im)
        valid.append(row)
    if not valid:
        return []
    inputs = processor(images=images, return_tensors="pt")
    inputs = {name: value.to(device) for name, value in inputs.items()}
    with torch.no_grad():
        out = model.get_image_features(**inputs)
    feats = out.detach().cpu().numpy().astype(np.float32)
    norms = np.linalg.norm(feats, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    feats = feats / norms
    return [(row, feats[i]) for i, row in enumerate(valid)]


def _clip_features(state: tuple, rows: list) -> list[tuple[Image, np.ndarray]]:
    """Batch thumbnails (~16) through CLIP; a bad image falls back to a one-row batch."""
    out: list[tuple[Image, np.ndarray]] = []
    for start in range(0, len(rows), EMBED_BATCH):
        batch = rows[start:start + EMBED_BATCH]
        try:
            out.extend(_clip_vectors(state, batch))
        except Exception:
            for row in batch:
                try:
                    out.extend(_clip_vectors(state, [row]))
                except Exception:
                    continue
    return out


def _cv_features(rows: list) -> list[tuple[Image, np.ndarray]]:
    out: list[tuple[Image, np.ndarray]] = []
    for row in rows:
        try:
            out.append((row, _features(row)))
        except Exception:        # unreadable row: omitted rather than given a fake position
            continue
    return out


def _embedding_features(rows: list, backend: str, state: tuple | None) -> tuple[list[Image], list[np.ndarray]]:
    """Resolve features batch-wise, reading the per-sha cache first and writing it after computing."""
    kept: list[Image] = []
    vectors: list[np.ndarray] = []
    for start in range(0, len(rows), EMBED_BATCH):
        batch = rows[start:start + EMBED_BATCH]
        resolved: dict[int, np.ndarray] = {}
        pending: list[Image] = []
        for row in batch:
            cached = _load_feature(backend, row.sha256)
            if cached is None:
                pending.append(row)
            else:
                resolved[id(row)] = cached
        if pending:
            computed = _clip_features(state, pending) if backend == "clip" else _cv_features(pending)
            for row, vector in computed:
                _store_feature(backend, row.sha256, vector)
                resolved[id(row)] = vector
        for row in batch:
            vector = resolved.get(id(row))
            if vector is not None:
                kept.append(row)
                vectors.append(vector)
    return kept, vectors


def _projection(features: list[np.ndarray]) -> tuple[list[tuple[float, float]], str]:
    n = len(features)
    if n == 0:
        return [], "pca"
    if n == 1:
        return [(0.0, 0.0)], "pca"
    matrix = np.asarray(features, dtype=np.float64)
    std = matrix.std(axis=0)
    std[std == 0] = 1.0
    standardised = (matrix - matrix.mean(axis=0)) / std
    try:
        import umap

        reducer = umap.UMAP(n_neighbors=max(2, min(15, n - 1)), min_dist=0.1, random_state=42)
        coords = reducer.fit_transform(standardised)
        projection = "umap"
    except Exception:  # not installed, or too few points for the reducer
        _, _, components = np.linalg.svd(standardised, full_matrices=False)
        components = components[:2]
        for row in range(len(components)):  # deterministic sign: largest loading points positive
            if components[row][int(np.argmax(np.abs(components[row])))] < 0:
                components[row] = -components[row]
        coords = standardised @ components.T
        if coords.shape[1] < 2:
            coords = np.column_stack([coords, np.zeros(len(coords))])
        projection = "pca"
    coords = np.nan_to_num(np.asarray(coords, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    return [(round(float(x), 6), round(float(y), 6)) for x, y in coords], projection


def scan_embedding(db: Session, project: Project) -> dict:
    """CLIP (or cheap CV fallback) image features projected to 2-D for the embedding scatter."""
    signature = list(insights.signature(db, project))
    classes = {c.id: c.name for c in db.scalars(select(LabelClass).where(LabelClass.project_id == project.id))}
    all_rows = insights.live_images(db, project)
    total = len(all_rows)
    rows = _sample_images(all_rows, EMBED_MAX)
    state = _clip_backend()
    backend = "clip" if state else "cv"
    kept, features = _embedding_features(rows, backend, state)
    coords, projection = _projection(features)
    points = []
    for row, (x, y) in zip(kept, coords, strict=True):
        anns = [a for a in (row.annotations or []) if isinstance(a, dict)]
        counts = Counter(
            classes[a["classId"]] for a in anns if isinstance(a.get("classId"), str) and a["classId"] in classes
        )
        most_common = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        ai = any(isinstance(a.get("source"), str) and a["source"].strip() and a["source"] != "human" for a in anns)
        points.append(
            {
                "image_id": row.id,
                "name": row.name,
                "x": x,
                "y": y,
                "split": row.split,
                "class": most_common[0][0] if most_common else None,
                "source": "ai" if ai else "human",
                "error": row.review == "rejected",
                "thumb": row.thumb or None,
            }
        )
    return {
        "signature": signature,
        "points": points,
        "projection": projection,
        "features": backend,
        "total": total,
        "used": len(points),
        "sampled": total > len(points),
    }
