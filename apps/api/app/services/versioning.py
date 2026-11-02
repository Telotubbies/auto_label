"""Generate a frozen dataset version: rebalance splits, preprocess, augment (train only)."""
import hashlib
import json
import random
import shutil
from collections import Counter
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import DATA_DIR
from ..models import Image, LabelClass, Project, Version
from . import exporters, imaging


def version_dir(v: Version) -> Path:
    return DATA_DIR / "versions" / v.id


def cached_export(v: Version, fmt: str) -> Path:
    return exporters.cached_export(version_dir(v), fmt)


def stratified_split(items: list, ratios: dict, seed: int, groups: dict | None = None) -> dict:
    """Greedy iterative stratification. items = [(image_id, {class ids})] -> {image_id: split}.
    Images sharing a group id are placed together. Unlabeled images form their own pseudo-class."""
    rng = random.Random(seed)
    UNL = -1
    members: dict = {}
    for iid, cs in items:
        members.setdefault((groups or {}).get(iid, iid), []).append((iid, set(cs) or {UNL}))
    units = []                                   # (ids, {class: images containing it})
    for g, mem in members.items():
        cnt = Counter(c for _, cs in mem for c in cs)
        units.append(([i for i, _ in mem], cnt))
    total = Counter()
    for _, cnt in units:
        total.update(cnt)
    ssum = sum(ratios.values()) or 1
    desired = {s: {c: r / ssum * total[c] for c in total} for s, r in ratios.items()}
    out: dict = {}
    remaining = units[:]
    rng.shuffle(remaining)
    while remaining:
        left = Counter(c for _, cnt in remaining for c in cnt)
        c = min(left, key=lambda k: (left[k], k))
        for u in [u for u in remaining if c in u[1]]:
            best = max(desired, key=lambda s: (desired[s][c], sum(desired[s].values()), rng.random()))
            for i in u[0]:
                out[i] = best
            for k, n in u[1].items():
                desired[best][k] -= n
            remaining.remove(u)
    return out


def phash_groups(rows: list, max_dist: int = 6) -> dict:
    """image id -> group id; union-find over perceptual-hash Hamming distance <= max_dist."""
    import imagehash
    from PIL import Image as PImage
    ids, hashes = [], []
    for r in rows:
        try:
            with PImage.open(DATA_DIR / r.path) as im:
                hashes.append(imagehash.phash(im))
            ids.append(r.id)
        except Exception:                        # unreadable file: stays in its own group
            continue
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a in range(len(ids)):
        for b in range(a + 1, len(ids)):
            if hashes[a] - hashes[b] <= max_dist:
                ra, rb = find(ids[a]), find(ids[b])
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)
    out = {i: find(i) for i in ids}
    for r in rows:
        out.setdefault(r.id, r.id)
    return out


def generate(db: Session, v: Version, progress=lambda f: None) -> dict:
    p = db.get(Project, v.project_id)
    cfg = v.settings or {}
    classes = db.scalars(select(LabelClass).where(LabelClass.project_id == p.id).order_by(LabelClass.created)).all()
    cls_idx = {c.id: i for i, c in enumerate(classes)}
    rows = db.scalars(select(Image).where(Image.project_id == p.id, Image.status == "done",
                                          Image.deleted_at.is_(None)).order_by(Image.created)).all()
    if cfg.get("preprocessing", {}).get("filter_null"):
        rows = [r for r in rows if r.annotations]
    if not rows:
        raise ValueError("no images in the dataset yet — approve annotated images on the Annotate board first")

    rng = random.Random(cfg.get("seed", 42))
    split_cfg = cfg.get("split")
    leakage_moved = 0
    if split_cfg:                                # rebalance: {"train":70,"valid":20,"test":10}
        items_cls = [(r.id, {cls_idx[a["classId"]] for a in (r.annotations or []) if a.get("classId") in cls_idx})
                     for r in rows]
        splits = stratified_split(items_cls, split_cfg, cfg.get("seed", 42), phash_groups(rows))
    else:
        splits = {r.id: r.split for r in rows}
        members: dict = {}
        for gid_img, gid in phash_groups(rows).items():
            members.setdefault(gid, []).append(gid_img)
        for ids in members.values():
            vals = {splits[i] for i in ids}
            if len(vals) > 1:                    # near-copies must not straddle train and eval
                tgt = "train" if "train" in vals else "valid" if "valid" in vals else "test"
                for i in ids:
                    if splits[i] != tgt:
                        splits[i] = tgt
                        leakage_moved += 1

    out = version_dir(v)
    if out.exists():
        shutil.rmtree(out)
    pre, aug = cfg.get("preprocessing", {}), cfg.get("augmentation", {})
    out.mkdir(parents=True, exist_ok=True)
    (out / "recipe.json").write_text(json.dumps(
        {"resize": pre.get("resize"), "grayscale": bool(pre.get("grayscale")), "contrast": pre.get("contrast")}))
    has_aug = any(val for k, val in aug.items() if k != "outputs")
    # outputs = images produced per training example (original + outputs-1 augmented; 1 = replace with augmented)
    copies = max(1, min(int(aug.get("outputs", 3) or 1), 5))
    items, per_split, per_class = [], Counter(), Counter()

    for n, r in enumerate(rows):
        im = imaging.load(r.path)
        anns = [a for a in (r.annotations or []) if a.get("classId") in cls_idx]
        im, anns = imaging.preprocess(im, anns, pre)
        split = splits[r.id]
        variants = [(im, anns)]
        if split == "train" and has_aug:
            if copies > 1:
                variants += [imaging.augment(im, anns, aug, rng) for _ in range(copies - 1)]
            else:
                variants = [imaging.augment(im, anns, aug, rng)]
        for k, (vim, vanns) in enumerate(variants):
            stem = f"{Path(r.name).stem}_{r.id[:6]}" + (f"_aug{k}" if k else "")
            rel = f"{split}/{stem}.jpg"
            (out / split).mkdir(parents=True, exist_ok=True)
            vim.save(out / rel, "JPEG", quality=92)
            items.append({"file": rel, "split": split, "width": vim.width, "height": vim.height, "source": r.id,
                          "anns": [{"cls": cls_idx[a["classId"]], "shape": a["shape"],
                                    "source": a.get("source") or "human"} for a in vanns]})
            per_split[split] += 1
            for a in vanns:
                per_class[classes[cls_idx[a["classId"]]].name] += 1
        progress((n + 1) / len(rows))

    sources = [{"id": r.id, "sha256": r.sha256} for r in rows]
    canon = {"config": cfg, "classes": [c.name for c in classes],
             "images": sorted([r.id, r.sha256, [a for a in (r.annotations or []) if a.get("classId") in cls_idx],
                               splits[r.id]] for r in rows)}
    # class ids are replaced by index so renames show up via "classes" and ids stay out of the hash
    for row in canon["images"]:
        row[2] = [{**a, "classId": cls_idx[a["classId"]]} for a in row[2]]
    version_hash = hashlib.sha256(json.dumps(canon, sort_keys=True, default=str).encode()).hexdigest()
    manifest = {"classes": [c.name for c in classes], "skeletons": [c.skeleton for c in classes],
                "type": p.type, "items": items, "version_hash": version_hash,
                "config": cfg, "sources": sources}
    (out / "manifest.json").write_text(json.dumps(manifest))
    return {"images": len(items), "source_images": len(rows), "splits": dict(per_split),
            "classes": dict(per_class), "class_names": manifest["classes"],
            "leakage_moved": leakage_moved}
