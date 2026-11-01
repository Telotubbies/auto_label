"""Expensive Insights scans: image pixel stats, pHash leakage pairs and the embedding map.

Each function is the body of one worker job and stores its payload on the job row; the GET
endpoints only read that row, so no request decodes pixels or runs a projection.
"""

import math
from collections import Counter, defaultdict

import cv2
import imagehash
import numpy as np
from PIL import Image as PImage
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import DATA_DIR
from ..models import Image, LabelClass, Project
from . import imaging, insights, versioning

IMGSZ = 640
THUMB = 256
RESOLUTION_MAX = 2000
EMBED_MAX = 3000
GALLERY_MAX = 200
BLUR_BUCKETS = ("0–10", "10–30", "30–100", "100–300", "300–1000", "≥1000")


def _live(db: Session, project: Project) -> list[Image]:
    return db.scalars(
        select(Image)
        .where(Image.project_id == project.id, Image.deleted_at.is_(None))
        .order_by(Image.created, Image.id)
    ).all()


def _sample(items: list, limit: int) -> list:
    if len(items) <= limit:
        return items
    return items[:: math.ceil(len(items) / limit)][:limit]


def _blur_bucket(variance: float) -> str:
    for bucket, edge in zip(BLUR_BUCKETS, (10, 30, 100, 300, 1000)):
        if variance < edge:
            return bucket
    return BLUR_BUCKETS[-1]


def scan_images(db: Session, project: Project) -> dict:
    """Brightness/blur distributions and the resolution scatter for every readable thumbnail."""
    signature = list(insights.signature(db, project))
    brightness: Counter = Counter()
    blur: Counter = Counter()
    resolution: list[dict] = []
    scanned = 0
    for row in _live(db, project):
        try:
            image = imaging.load(row.thumb or row.path)
            gray = image.convert("L")
            gray.thumbnail((THUMB, THUMB))
            pixels = np.asarray(gray, dtype=np.uint8)
            mean = float(pixels.mean())
            variance = float(cv2.Laplacian(pixels, cv2.CV_64F).var())
        except Exception:  # unreadable row: contributes nothing, never fails the scan
            continue
        scanned += 1
        brightness[min(15, max(0, int(mean // 16)))] += 1
        blur[_blur_bucket(variance)] += 1
        resolution.append({"w": int(row.width or image.width), "h": int(row.height or image.height)})
    return {
        "signature": signature,
        "resolution": _sample(resolution, RESOLUTION_MAX),
        "brightness": [{"bin": i, "count": brightness.get(i, 0)} for i in range(16)],
        "blur": [{"bin": b, "count": blur.get(b, 0)} for b in BLUR_BUCKETS],
        "scanned": scanned,
    }


def _phash(row: Image):
    with PImage.open(DATA_DIR / (row.thumb or row.path)) as image:
        return imagehash.phash(image)


def _ref(row: Image) -> dict:
    return {
        "image_id": row.id,
        "name": row.name,
        "split": row.split,
        "thumb": row.thumb or None,
        "width": int(row.width or 0),
        "height": int(row.height or 0),
    }


def scan_leakage(db: Session, project: Project) -> dict:
    """Cross-split near-duplicate pairs from versioning's pHash union-find."""
    signature = list(insights.signature(db, project))
    rows = _live(db, project)
    by_id = {r.id: r for r in rows}
    members: dict = defaultdict(list)
    group_of = versioning.phash_groups(rows)
    for row in rows:
        members[group_of.get(row.id, row.id)].append(row)

    pairs: list[tuple[int, str, str]] = []
    split_counts: Counter = Counter()
    total = 0
    for group in members.values():
        if len(group) < 2:  # only multi-member groups need an exact distance
            continue
        hashes = {}
        for row in group:
            try:
                hashes[row.id] = _phash(row)
            except Exception:
                continue
        ids = [row.id for row in group if row.id in hashes]
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                if by_id[a].split == by_id[b].split:
                    continue
                total += 1
                split_counts[tuple(sorted((by_id[a].split, by_id[b].split)))] += 1
                pairs.append((int(hashes[a] - hashes[b]), a, b))
    pairs.sort()
    order = {split: i for i, split in enumerate(("train", "valid", "test"))}
    split_pairs = [
        {"a": a, "b": b, "count": n}
        for (a, b), n in sorted(
            split_counts.items(),
            key=lambda kv: (order.get(kv[0][0], 9), order.get(kv[0][1], 9)),
        )
    ]
    return {
        "signature": signature,
        "pairs": [
            {"a": _ref(by_id[a]), "b": _ref(by_id[b]), "distance": distance} for distance, a, b in pairs[:GALLERY_MAX]
        ],
        "split_pairs": split_pairs,
        "total_pairs": total,
    }


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
    """Cheap deterministic image features projected to 2-D for the embedding scatter."""
    signature = list(insights.signature(db, project))
    classes = {c.id: c.name for c in db.scalars(select(LabelClass).where(LabelClass.project_id == project.id))}
    rows = _live(db, project)[:EMBED_MAX]
    kept: list[Image] = []
    features: list[np.ndarray] = []
    for row in rows:
        try:
            features.append(_features(row))
        except Exception:  # unreadable row: omitted rather than given a fake position
            continue
        kept.append(row)
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
    return {"signature": signature, "points": points, "projection": projection}
