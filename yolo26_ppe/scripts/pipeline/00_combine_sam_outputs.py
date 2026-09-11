#!/usr/bin/env python3
"""Step 00: Combine SAM 3.1 COCO outputs from multiple batches into one dataset.

Reads per-image COCO JSONs from each batch's coco/ directory, merges them
into a single COCO annotations.json with renumbered image/annotation IDs,
and symlinks/copies images into a combined images/ folder.

Output: yolo26_ppe/data/combined_coco_dataset_version_3/
  - annotations.json  (combined COCO with 4 classes)
  - images/           (symlinks to source images)

4-class scheme (ppe_4class.yaml):
  id=1 person
  id=2 helmet
  id=3 closed footwear
  id=4 harness
"""
import json
import os
import sys
from pathlib import Path

BASE = Path("/mnt/e/02_Projects/auto_label")
SAM_OUTPUTS = BASE / "data" / "sam_outputs_ground_truth"
OUTPUT_DIR = BASE / "yolo26_ppe" / "data" / "combined_coco_dataset_version_3"

# Batches to combine
BATCHES = ["blurred", "custom_capture"]

# Source image directories (raw images)
RAW_DIR = BASE / "data" / "raw"

# 4-class categories
CATEGORIES = [
    {"id": 1, "name": "person", "supercategory": "ppe"},
    {"id": 2, "name": "helmet", "supercategory": "ppe"},
    {"id": 3, "name": "closed footwear", "supercategory": "ppe"},
    {"id": 4, "name": "harness", "supercategory": "ppe"},
]


def main():
    print("=" * 70)
    print("Combining SAM 3.1 COCO outputs -> combined_coco_dataset_version_3")
    print("=" * 70)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    img_out = OUTPUT_DIR / "images"
    img_out.mkdir(exist_ok=True)

    combined_images = []
    combined_annotations = []
    img_id = 1
    ann_id = 1
    total_per_batch = {}

    for batch in BATCHES:
        batch_coco = SAM_OUTPUTS / batch / "coco"
        batch_raw = RAW_DIR / batch

        if not batch_coco.exists():
            print(f"  WARNING: {batch_coco} does not exist, skipping")
            continue

        # Find all per-image COCO JSONs
        json_files = sorted(batch_coco.glob("*.json"))
        # Exclude combined files if any
        json_files = [f for f in json_files if f.name != "annotations.json"]
        print(f"\n  {batch}: {len(json_files)} per-image COCO files")

        batch_count = 0
        for jf in json_files:
            with open(jf) as f:
                coco = json.load(f)

            # Each per-image COCO has one image and its annotations
            images = coco.get("images", [])
            annotations = coco.get("annotations", [])

            if not images:
                continue

            src_img = images[0]
            file_name = src_img["file_name"]
            w = src_img.get("width", 0)
            h = src_img.get("height", 0)

            # Find source image file
            src_path = batch_raw / file_name
            if not src_path.exists():
                # Try in the batch directory itself
                src_path = SAM_OUTPUTS / batch / "images" / file_name
            if not src_path.exists():
                print(f"    WARNING: image not found: {file_name}")
                continue

            # Create symlink in output (avoid copying large files)
            dst_path = img_out / file_name
            if not dst_path.exists():
                try:
                    os.symlink(src_path, dst_path)
                except (OSError, FileExistsError):
                    # Fallback: copy
                    import shutil
                    shutil.copy2(src_path, dst_path)

            # Renumber image ID
            new_img = {
                "id": img_id,
                "file_name": file_name,
                "width": w,
                "height": h,
            }
            combined_images.append(new_img)

            # Renumber annotations
            for ann in annotations:
                ann["id"] = ann_id
                ann["image_id"] = img_id
                combined_annotations.append(ann)
                ann_id += 1

            img_id += 1
            batch_count += 1

        total_per_batch[batch] = batch_count
        print(f"    added: {batch_count} images")

    # Write combined annotations.json
    combined = {
        "info": {
            "description": "PPE 4-class combined dataset from SAM 3.1 auto-labeling",
            "version": "3.0",
            "year": 2026,
        },
        "categories": CATEGORIES,
        "images": combined_images,
        "annotations": combined_annotations,
    }

    ann_path = OUTPUT_DIR / "annotations.json"
    with open(ann_path, "w") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 70}")
    print(f"Combined dataset: {OUTPUT_DIR}")
    print(f"  images:      {len(combined_images)}")
    print(f"  annotations: {len(combined_annotations)}")
    print(f"  classes:     {len(CATEGORIES)}")
    for b, c in total_per_batch.items():
        print(f"    {b}: {c} images")
    print(f"  output:      {ann_path}")
    print(f"{'=' * 70}")

    # Print class distribution
    from collections import Counter
    cat_counts = Counter()
    for ann in combined_annotations:
        cat_counts[ann["category_id"]] += 1
    print("\nClass distribution:")
    for cat in CATEGORIES:
        print(f"  {cat['id']} {cat['name']:20s}: {cat_counts.get(cat['id'], 0)}")


if __name__ == "__main__":
    main()
