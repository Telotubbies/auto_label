#!/usr/bin/env python3
"""Step 1.5: Merge 432 new SAM 3.1 labeled images into the combined dataset.

- Reads existing dataset_combined/annotations.json (480 images)
- Reads 433 SAM 3.1 COCO output files from output_2026/coco/ (432 new images)
- Merges them into a single COCO annotations file
- Merges sandals (class 5) into shoes (class 4) due to insufficient samples
- Copies/links all images to a flat directory with unique names
- Outputs to yolo26_ppe/data/combined_v2/
"""
import json
import os
import shutil
from pathlib import Path
from collections import Counter

BASE = Path("/mnt/e/02_Projects/auto_label")
EXISTING_ANN = BASE / "dataset_combined" / "annotations.json"
EXISTING_IMG_DIR = BASE / "dataset_combined" / "images"
SAM_COCO_DIR = BASE / "output_2026" / "coco"
SAM_IMG_DIR = BASE / "input" / "2026-08-14_14-34-14"
OUTPUT_DIR = BASE / "yolo26_ppe" / "data" / "combined_v2"
OUTPUT_ANN = OUTPUT_DIR / "annotations.json"
OUTPUT_IMG_DIR = OUTPUT_DIR / "images"

# Class mapping: merge sandals(5) → shoes(4)
CLASS_MERGE = {5: 4}

# Final classes (after merge) - renumber to 1-5
OLD_TO_NEW_CID = {1: 1, 2: 2, 3: 3, 4: 4, 6: 5}  # harness 6→5
FINAL_CATEGORIES = [
    {"id": 1, "name": "person", "supercategory": "ppe", "prompt": "person"},
    {"id": 2, "name": "helmet", "supercategory": "ppe", "prompt": "helmet"},
    {"id": 3, "name": "boots", "supercategory": "ppe", "prompt": "boots"},
    {"id": 4, "name": "shoes", "supercategory": "ppe", "prompt": "shoes"},
    {"id": 5, "name": "harness", "supercategory": "ppe", "prompt": "safety harness"},
]


def remap_cid(old_cid):
    """Remap class ID: merge sandals→shoes, then renumber."""
    merged = CLASS_MERGE.get(old_cid, old_cid)
    return OLD_TO_NEW_CID.get(merged, merged)


def main():
    print("=" * 70)
    print("Merging 432 new SAM 3.1 images into combined dataset v2")
    print("=" * 70)

    # Load existing annotations
    print("\nLoading existing dataset...")
    with open(EXISTING_ANN) as f:
        existing = json.load(f)
    print(f"  Existing: {len(existing['images'])} images, {len(existing['annotations'])} annotations")

    # Load SAM 3.1 output files
    print("\nLoading SAM 3.1 output files...")
    coco_files = sorted([f for f in os.listdir(SAM_COCO_DIR) if f.endswith('.json')])
    print(f"  Found {len(coco_files)} SAM 3.1 COCO files")

    # Build merged dataset
    merged_images = []
    merged_annotations = []
    img_id_counter = 1
    ann_id_counter = 1

    # Create output image directory
    OUTPUT_IMG_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Add existing images (prefix with "e" to avoid name conflicts)
    print("\nProcessing existing images...")
    existing_img_map = {}
    existing_copied = 0
    for img in existing['images']:
        old_fn = img['file_name']  # e.g., "2026/0001.jpg"
        # Create unique flat name
        base_name = os.path.basename(old_fn)
        new_fn = f"e{base_name}"  # prefix with 'e' for existing

        # Copy/symlink image
        src = EXISTING_IMG_DIR / old_fn
        dst = OUTPUT_IMG_DIR / new_fn
        if src.exists() and not dst.exists():
            try:
                os.symlink(src, dst)
            except OSError:
                shutil.copy2(src, dst)
            existing_copied += 1

        new_img = {
            "id": img_id_counter,
            "file_name": new_fn,
            "width": img.get('width', 0),
            "height": img.get('height', 0),
            "source": "existing"
        }
        existing_img_map[img['id']] = img_id_counter
        merged_images.append(new_img)
        img_id_counter += 1

    # Remap existing annotations
    for ann in existing['annotations']:
        new_cid = remap_cid(ann['category_id'])
        new_ann = {
            "id": ann_id_counter,
            "image_id": existing_img_map[ann['image_id']],
            "category_id": new_cid,
            "bbox": ann['bbox'],
            "area": ann.get('area', 0),
            "iscrowd": ann.get('iscrowd', 0),
            "segmentation": ann.get('segmentation', []),
        }
        merged_annotations.append(new_ann)
        ann_id_counter += 1

    print(f"  Added {len(merged_images)} existing images ({existing_copied} copied), {len(merged_annotations)} annotations")

    # 2. Add SAM 3.1 new images (prefix with "s" to avoid name conflicts)
    print("\nProcessing SAM 3.1 new images...")
    sam_img_count = 0
    sam_ann_count = 0
    sam_copied = 0

    for fn in coco_files:
        with open(os.path.join(SAM_COCO_DIR, fn)) as f:
            data = json.load(f)

        if not data.get('images'):
            continue

        img_info = data['images'][0]
        old_fn = img_info['file_name']
        base_name = os.path.basename(old_fn)
        new_fn = f"s{base_name}"  # prefix with 's' for SAM

        # Copy/symlink image
        src = SAM_IMG_DIR / old_fn
        dst = OUTPUT_IMG_DIR / new_fn
        if src.exists() and not dst.exists():
            try:
                os.symlink(src, dst)
            except OSError:
                shutil.copy2(src, dst)
            sam_copied += 1

        new_img = {
            "id": img_id_counter,
            "file_name": new_fn,
            "width": img_info.get('width', 0),
            "height": img_info.get('height', 0),
            "source": "sam3.1"
        }
        merged_images.append(new_img)
        sam_img_id = img_id_counter
        img_id_counter += 1
        sam_img_count += 1

        # Add annotations
        for ann in data.get('annotations', []):
            new_cid = remap_cid(ann['category_id'])
            new_ann = {
                "id": ann_id_counter,
                "image_id": sam_img_id,
                "category_id": new_cid,
                "bbox": ann['bbox'],
                "area": ann.get('area', 0),
                "iscrowd": ann.get('iscrowd', 0),
                "segmentation": ann.get('segmentation', []),
                "score": ann.get('score', 1.0),
            }
            merged_annotations.append(new_ann)
            ann_id_counter += 1
            sam_ann_count += 1

    print(f"  Added {sam_img_count} new SAM 3.1 images ({sam_copied} copied), {sam_ann_count} annotations")

    # Summary
    print(f"\n{'=' * 70}")
    print(f"Merged dataset v2: {len(merged_images)} images, {len(merged_annotations)} annotations")

    # Count per class
    cat_names = {c['id']: c['name'] for c in FINAL_CATEGORIES}
    class_counts = Counter()
    for ann in merged_annotations:
        class_counts[ann['category_id']] += 1
    print(f"\nAnnotation counts per class (5 classes, sandals merged into shoes):")
    for cid in sorted(class_counts.keys()):
        name = cat_names.get(cid, f'unknown_{cid}')
        print(f"  {name} (id={cid}): {class_counts[cid]}")

    # Check images in output dir
    img_files = os.listdir(OUTPUT_IMG_DIR)
    print(f"\nImages in output dir: {len(img_files)}")

    # Save merged annotations
    merged = {
        "info": {"description": "PPE dataset v2: 480 existing + 432 SAM 3.1 new, sandals merged into shoes, 5 classes"},
        "licenses": existing.get('licenses', []),
        "images": merged_images,
        "annotations": merged_annotations,
        "categories": FINAL_CATEGORIES,
    }
    with open(OUTPUT_ANN, 'w') as f:
        json.dump(merged, f, indent=2)
    print(f"\nSaved: {OUTPUT_ANN}")

    print(f"\n{'=' * 70}")
    print("DONE - Merged dataset v2 ready")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
