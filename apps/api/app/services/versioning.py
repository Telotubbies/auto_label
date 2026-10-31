"""Generate a frozen dataset version: rebalance splits, preprocess, augment (train only)."""
import json
import random
import shutil
from collections import Counter
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import DATA_DIR
from ..models import Image, LabelClass, Project, Version
from . import imaging


def version_dir(v: Version) -> Path:
    return DATA_DIR / "versions" / v.id


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
    if split_cfg:                                # rebalance: {"train":70,"valid":20,"test":10}
        order = rows[:]; rng.shuffle(order)
        n = len(order); n_tr = round(n * split_cfg["train"] / 100); n_va = round(n * split_cfg["valid"] / 100)
        splits = {r.id: ("train" if i < n_tr else "valid" if i < n_tr + n_va else "test") for i, r in enumerate(order)}
    else:
        splits = {r.id: r.split for r in rows}

    out = version_dir(v)
    if out.exists():
        shutil.rmtree(out)
    pre, aug = cfg.get("preprocessing", {}), cfg.get("augmentation", {})
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
                          "anns": [{"cls": cls_idx[a["classId"]], "shape": a["shape"]} for a in vanns]})
            per_split[split] += 1
            for a in vanns:
                per_class[classes[cls_idx[a["classId"]]].name] += 1
        progress((n + 1) / len(rows))

    manifest = {"classes": [c.name for c in classes], "type": p.type, "items": items}
    (out / "manifest.json").write_text(json.dumps(manifest))
    return {"images": len(items), "source_images": len(rows), "splits": dict(per_split),
            "classes": dict(per_class), "class_names": manifest["classes"]}
