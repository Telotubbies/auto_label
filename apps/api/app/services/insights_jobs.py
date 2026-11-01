"""Expensive Insights scans: image pixel stats and pHash leakage pairs.

Each function is the body of one worker job and stores its payload on the job row; the GET
endpoints only read that row, so no request decodes pixels. The embedding map lives in
`insights_embedding` (CLIP/UMAP dependencies stay isolated there) and is re-exported for the worker.
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
from ..models import Image, Project
from . import imaging, insights, versioning
from .insights_embedding import scan_embedding  # noqa: F401  re-exported for worker.HANDLERS

THUMB = 256
RESOLUTION_MAX = 2000
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
