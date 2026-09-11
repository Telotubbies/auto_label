#!/usr/bin/env python3
"""Create paper-style failure case montage: 10 images in a 5x2 grid, all 4 models represented."""
import cv2
import numpy as np
from pathlib import Path
import json

BASE = Path("/mnt/e/02_Projects/auto_label/yolo26_ppe/artifacts/evaluation/yolo/production_v4_recipe")
OUT = BASE / "failure_montage"
OUT.mkdir(exist_ok=True)

# Load per-model failure lists (each sorted by failure score, descending)
all_failures = {}
for model in ["medium_detection", "medium_segmentation"]:
    fj = BASE / f"{model}_failures.json"
    if fj.exists():
        all_failures[model] = json.load(open(fj))

# Selection: ensure both models represented in 10 images.
# Worst model gets more slots: m_detect=5, m_seg=5
quota = {"medium_detection": 5, "medium_segmentation": 5}

selected = []
for model, n in quota.items():
    items = all_failures.get(model, [])[:n]
    for item in items:
        # Find the saved annotated image
        stem = item.get("stem") or item.get("image", "").rsplit(".", 1)[0]
        candidates = list((BASE / "all_failure_case_images").glob(f"{model}_*{stem}*.jpg"))
        if not candidates:
            # Fallback: try just the stem
            candidates = list((BASE / "all_failure_case_images").glob(f"*{stem}*.jpg"))
        if not candidates:
            continue
        selected.append({
            "model": model,
            "image": item.get("image", stem),
            "n_gt": item.get("n_gt", "?"),
            "n_pred": item.get("n_pred", "?"),
            "n_missed": item.get("n_missed", "?"),
            "file": str(candidates[0]),
        })

print(f"Selected {len(selected)} failure cases:")
for s in selected:
    print(f"  [{s['model']}] {s['image']} | GT:{s['n_gt']} P:{s['n_pred']} M:{s['n_missed']}")

# Thumbnail size (compact, paper-style)
THUMB_W = 320
THUMB_H = 240

def resize_with_pad(img, target_w, target_h):
    h, w = img.shape[:2]
    scale = min(target_w / w, target_h / h)
    new_w, new_h = int(w * scale), int(h * scale)
    img = cv2.resize(img, (new_w, new_h))
    pad_w = target_w - new_w
    pad_h = target_h - new_h
    top = pad_h // 2
    bottom = pad_h - top
    left = pad_w // 2
    right = pad_w - left
    img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    return img

# Build thumbnails
imgs = []
for s in selected:
    img = cv2.imread(s["file"])
    if img is None:
        print(f"WARN: could not read {s['file']}")
        continue
    img = resize_with_pad(img, THUMB_W, THUMB_H)
    # Compact label
    label = f"[{s['model']}] GT:{s['n_gt']} P:{s['n_pred']} M:{s['n_missed']}"
    cv2.rectangle(img, (0, 0), (THUMB_W, 22), (255, 255, 255), -1)
    cv2.putText(img, label, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
    imgs.append(img)

# Pad to 10
while len(imgs) < 10:
    imgs.append(np.full((THUMB_H, THUMB_W, 3), 255, dtype=np.uint8))

# 5 cols x 2 rows
cols = 5
rows = 2
row1 = np.hstack(imgs[:5])
row2 = np.hstack(imgs[5:10])
grid = np.vstack([row1, row2])

# Title bar
title_bar = np.full((28, grid.shape[1], 3), 235, dtype=np.uint8)
cv2.putText(title_bar,
            "Top 10 Failure Cases (green=GT, red=Pred) - crowded scenes with small objects",
            (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
grid = np.vstack([title_bar, grid])

out_path = OUT / "montage_combined.jpg"
cv2.imwrite(str(out_path), grid, [cv2.IMWRITE_JPEG_QUALITY, 88])
print(f"\nSaved combined: {out_path} ({grid.shape[1]}x{grid.shape[0]})")

# Also save per-model montages (top 5 each) for reference
for model in ["medium_detection", "medium_segmentation"]:
    items = all_failures.get(model, [])[:5]
    m_imgs = []
    for item in items:
        stem = item.get("stem") or item.get("image", "").rsplit(".", 1)[0]
        candidates = list((BASE / "all_failure_case_images").glob(f"{model}_*{stem}*.jpg"))
        if not candidates:
            continue
        img = cv2.imread(str(candidates[0]))
        if img is None:
            continue
        img = resize_with_pad(img, THUMB_W, THUMB_H)
        label = f"{item.get('image', stem)} | GT:{item.get('n_gt','?')} M:{item.get('n_missed','?')}"
        cv2.rectangle(img, (0, 0), (THUMB_W, 22), (255, 255, 255), -1)
        cv2.putText(img, label, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
        m_imgs.append(img)
    if not m_imgs:
        continue
    while len(m_imgs) < 5:
        m_imgs.append(np.full((THUMB_H, THUMB_W, 3), 255, dtype=np.uint8))
    mgrid = np.hstack(m_imgs[:5])
    title_bar = np.full((28, mgrid.shape[1], 3), 235, dtype=np.uint8)
    cv2.putText(title_bar, f"{model} top 5 failures (green=GT, red=Pred)",
                (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
    mgrid = np.vstack([title_bar, mgrid])
    mout = OUT / f"montage_{model}.jpg"
    cv2.imwrite(str(mout), mgrid, [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(f"Saved: {mout} ({mgrid.shape[1]}x{mgrid.shape[0]})")

print("Done!")
