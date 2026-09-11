#!/usr/bin/env python3
"""Step 01: Prepare YOLO data from combined COCO dataset version 3.

- Reads combined_coco_dataset_version_3/annotations.json (480 images, 4 classes)
- Splits into train/val/test (80/10/10)
- Converts to YOLO detection format (bbox)
- Converts to YOLO segmentation format (polygon masks)
- Applies oversampling for rare classes (harness)
- Generates data.yaml files

4-class scheme (ppe_4class.yaml):
  1=person, 2=helmet, 3=closed footwear, 4=harness
"""
import json
import os
import random
import shutil
import sys
from pathlib import Path
from collections import Counter
import numpy as np

BASE = Path("/mnt/e/02_Projects/auto_label/yolo26_ppe")
COMBINED_DIR = BASE / "data" / "combined_coco_dataset_version_3"
ANN_PATH = COMBINED_DIR / "annotations.json"
IMG_DIR = COMBINED_DIR / "images"

# Output directories
DET_DIR = BASE / "data" / "yolo_detection_dataset_version_3"
SEG_DIR = BASE / "data" / "yolo_segmentation_dataset_version_3"

CLASS_NAMES = ["person", "helmet", "closed footwear", "harness"]
# COCO category IDs in v3 dataset: 1=person, 2=helmet, 3=closed footwear, 4=harness
# YOLO class IDs: 0=person, 1=helmet, 2=closed footwear, 3=harness
COCO_TO_YOLO = {1: 0, 2: 1, 3: 2, 4: 3}

SPLIT_RATIOS = {"train": 0.8, "val": 0.1, "test": 0.1}
RANDOM_SEED = 42

# Oversampling targets for rare classes (YOLO class ID → target annotation count).
# Based on v3 dataset distribution:
#   person=2267, helmet=2503, closed_footwear=3350, harness=177
#   imbalance: 3350:177 = 19:1 (footwear vs harness)
# Target brings harness closer to common classes via image duplication.
# Cap at 10x per image to avoid overfitting.
OVERSAMPLE_TARGETS = {
    3: 500,   # harness (YOLO class 3) → target 500 annotations (was 177, 19:1 imbalance)
}


def mask_to_polygons(segmentation, height, width):
    """Convert RLE or polygon segmentation to YOLO polygon format."""
    if isinstance(segmentation, list):
        # Already polygon format: [[x1,y1,x2,y2,...], ...]
        polygons = []
        for poly in segmentation:
            if len(poly) >= 6:  # At least 3 points
                coords = np.array(poly, dtype=np.float64)
                coords[0::2] /= width  # x → normalized
                coords[1::2] /= height  # y → normalized
                # Clip to [0, 1]
                coords = np.clip(coords, 0, 1)
                polygons.append(coords.tolist())
        return polygons
    elif isinstance(segmentation, dict):
        # RLE format - convert to mask then to polygons
        try:
            from pycocotools import mask as mask_utils
            rle = segmentation
            if isinstance(rle.get('counts'), str):
                rle = {'size': rle['size'], 'counts': rle['counts'].encode('utf-8')}
            m = mask_utils.decode(rle)
            contours = mask_to_contours(m)
            polygons = []
            for contour in contours:
                if len(contour) >= 6:
                    coords = np.array(contour, dtype=np.float64)
                    coords[0::2] /= width
                    coords[1::2] /= height
                    coords = np.clip(coords, 0, 1)
                    polygons.append(coords.tolist())
            return polygons
        except ImportError:
            # Fallback: use bbox as rectangle polygon
            return None
    return None


def mask_to_contours(mask):
    """Convert binary mask to list of contours."""
    try:
        import cv2
        contours, _ = cv2.findContours(
            mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        result = []
        for contour in contours:
            if len(contour) >= 3:
                pts = contour.squeeze().flatten().tolist()
                if len(pts) >= 6:
                    result.append(pts)
        return result
    except ImportError:
        return []


def bbox_to_yolo(bbox, img_w, img_h):
    """Convert COCO bbox [x,y,w,h] to YOLO format [cx,cy,w,h] normalized."""
    x, y, w, h = bbox
    cx = (x + w / 2) / img_w
    cy = (y + h / 2) / img_h
    nw = w / img_w
    nh = h / img_h
    # Clip
    cx = max(0, min(1, cx))
    cy = max(0, min(1, cy))
    nw = max(0.001, min(1, nw))
    nh = max(0.001, min(1, nh))
    return [cx, cy, nw, nh]


def main():
    print("=" * 70)
    print("Preparing YOLO v2 data (detect + segment)")
    print("=" * 70)

    # Try v3 dataset
    global ANN_PATH, IMG_DIR, COCO_TO_YOLO

    if not ANN_PATH.exists():
        print(f"ERROR: v3 annotations not found at {ANN_PATH}")
        print(f"  Run 00_combine_sam_outputs.py first to build the combined dataset.")
        sys.exit(1)

    # Load annotations
    with open(ANN_PATH) as f:
        data = json.load(f)

    images = data['images']
    annotations = data['annotations']
    print(f"Loaded: {len(images)} images, {len(annotations)} annotations")

    # Group annotations by image
    anns_by_img = {}
    for ann in annotations:
        img_id = ann['image_id']
        if img_id not in anns_by_img:
            anns_by_img[img_id] = []
        anns_by_img[img_id].append(ann)

    # Split images
    random.seed(RANDOM_SEED)
    img_ids = [img['id'] for img in images]
    random.shuffle(img_ids)

    n = len(img_ids)
    n_train = int(n * SPLIT_RATIOS['train'])
    n_val = int(n * SPLIT_RATIOS['val'])

    splits = {
        'train': img_ids[:n_train],
        'val': img_ids[n_train:n_train + n_val],
        'test': img_ids[n_train + n_val:],
    }

    print(f"Split: train={len(splits['train'])}, val={len(splits['val'])}, test={len(splits['test'])}")

    # Verify images directory exists
    if not IMG_DIR.exists():
        print(f"\nERROR: Images directory not found: {IMG_DIR}")
        print(f"  The annotations.json references {len(images)} images, but the images/ folder is missing.")
        print(f"  Expected location: {COMBINED_DIR}/images/")
        print(f"  Please place the image files (e0001.jpg, s0001.jpg, etc.) in that directory.")
        sys.exit(1)

    # Count how many referenced images actually exist
    missing_files = []
    for img in images:
        if not (IMG_DIR / img['file_name']).exists():
            missing_files.append(img['file_name'])
    if missing_files:
        print(f"\nWARNING: {len(missing_files)} of {len(images)} images are missing from {IMG_DIR}")
        print(f"  First 5 missing: {missing_files[:5]}")
        if len(missing_files) == len(images):
            print(f"\nERROR: ALL images are missing. Cannot proceed.")
            sys.exit(1)
        print(f"  Continuing with {len(images) - len(missing_files)} available images...\n")
    else:
        print(f"  All {len(images)} images found.\n")

    # Create directories
    for data_dir in [DET_DIR, SEG_DIR]:
        for split in ['train', 'val', 'test']:
            (data_dir / 'images' / split).mkdir(parents=True, exist_ok=True)
            (data_dir / 'labels' / split).mkdir(parents=True, exist_ok=True)

    # Map image id → image info
    img_map = {img['id']: img for img in images}

    # Process each split
    for split, split_img_ids in splits.items():
        print(f"\nProcessing {split} ({len(split_img_ids)} images)...")

        # Oversampling for train split
        if split == 'train':
            # Count annotations per class in train
            train_class_counts = Counter()
            for img_id in split_img_ids:
                for ann in anns_by_img.get(img_id, []):
                    yolo_cid = COCO_TO_YOLO.get(ann['category_id'])
                    if yolo_cid is not None:
                        train_class_counts[yolo_cid] += 1
            print(f"  Train class counts: {dict(train_class_counts)}")

            # Validate oversampling targets against actual class distribution
            max_count = max(train_class_counts.values()) if train_class_counts else 0
            if max_count > 0:
                for cls_id in range(len(CLASS_NAMES)):
                    count = train_class_counts.get(cls_id, 0)
                    ratio = max_count / count if count > 0 else float('inf')
                    name = CLASS_NAMES[cls_id]
                    if count == 0:
                        print(f"  ⚠ WARNING: class {name} (id={cls_id}) has 0 samples in train — cannot oversample")
                    elif ratio > 10:
                        print(f"  ⚠ WARNING: class {name} imbalance {ratio:.1f}:1 — consider increasing oversample target")
                    elif cls_id in OVERSAMPLE_TARGETS and count >= OVERSAMPLE_TARGETS[cls_id]:
                        print(f"  ℹ class {name} already has {count} (target={OVERSAMPLE_TARGETS[cls_id]}) — no oversampling needed")

            # Calculate oversampling multipliers
            oversample_imgs = []
            for target_cls, target_count in OVERSAMPLE_TARGETS.items():
                current = train_class_counts.get(target_cls, 0)
                if current == 0:
                    print(f"  ⚠ Skipping oversampling for {CLASS_NAMES[target_cls]}: 0 samples in train")
                    continue
                if current >= target_count:
                    continue  # already meets target
                # Find images that contain this class
                imgs_with_class = []
                for img_id in split_img_ids:
                    for ann in anns_by_img.get(img_id, []):
                        if COCO_TO_YOLO.get(ann['category_id']) == target_cls:
                            imgs_with_class.append(img_id)
                            break
                # Calculate how many times to duplicate
                multiplier = min(target_count // current, 10)  # Cap at 10x
                class_copies = len(imgs_with_class) * (multiplier - 1)
                for img_id in imgs_with_class:
                    for _ in range(multiplier - 1):
                        oversample_imgs.append(img_id)
                print(f"  Oversampling class {CLASS_NAMES[target_cls]}: {len(imgs_with_class)} images × {multiplier}x = +{class_copies} copies")

            split_img_ids = split_img_ids + oversample_imgs

            # Print post-oversampling imbalance
            if oversample_imgs:
                post_counts = Counter()
                for img_id in split_img_ids:
                    for ann in anns_by_img.get(img_id, []):
                        yolo_cid = COCO_TO_YOLO.get(ann['category_id'])
                        if yolo_cid is not None:
                            post_counts[yolo_cid] += 1
                post_max = max(post_counts.values()) if post_counts else 0
                post_min = min((c for c in post_counts.values() if c > 0), default=0)
                if post_max > 0 and post_min > 0:
                    print(f"  Post-oversampling imbalance: {post_max}:{post_min} = {post_max/post_min:.1f}:1")

        processed = 0
        seen_count = {}
        for img_id in split_img_ids:
            img_info = img_map[img_id]
            file_name = img_info['file_name']
            img_w = img_info.get('width', 0)
            img_h = img_info.get('height', 0)

            if img_w == 0 or img_h == 0:
                # Try to get image size
                img_path = IMG_DIR / file_name
                if img_path.exists():
                    try:
                        import cv2
                        img = cv2.imread(str(img_path))
                        img_h, img_w = img.shape[:2]
                    except Exception:
                        continue

            # Handle duplicate names from oversampling
            # Flatten file_name (remove subdirectory prefix like "2026/" or "blurred/")
            flat_name = os.path.basename(file_name)
            base_name = flat_name
            seen_count[img_id] = seen_count.get(img_id, 0) + 1
            if split == 'train' and seen_count[img_id] > 1:
                # Add suffix for oversampled copies
                idx = seen_count[img_id] - 1
                name_parts = os.path.splitext(flat_name)
                base_name = f"{name_parts[0]}_dup{idx}{name_parts[1]}"

            src_path = IMG_DIR / file_name
            if not src_path.exists():
                continue

            # Copy image to both detect and seg directories
            for data_dir in [DET_DIR, SEG_DIR]:
                dst_img = data_dir / 'images' / split / base_name
                if not dst_img.exists():
                    try:
                        os.symlink(src_path, dst_img)
                    except OSError:
                        shutil.copy2(src_path, dst_img)

            # Create detection label
            det_label_path = DET_DIR / 'labels' / split / (os.path.splitext(base_name)[0] + '.txt')
            seg_label_path = SEG_DIR / 'labels' / split / (os.path.splitext(base_name)[0] + '.txt')

            det_lines = []
            seg_lines = []

            for ann in anns_by_img.get(img_id, []):
                yolo_cid = COCO_TO_YOLO.get(ann['category_id'])
                if yolo_cid is None:
                    continue

                # Detection: class cx cy w h
                bbox = bbox_to_yolo(ann['bbox'], img_w, img_h)
                det_lines.append(f"{yolo_cid} {bbox[0]:.6f} {bbox[1]:.6f} {bbox[2]:.6f} {bbox[3]:.6f}")

                # Segmentation: class x1 y1 x2 y2 ... (polygons)
                seg = ann.get('segmentation')
                if seg:
                    polygons = mask_to_polygons(seg, img_h, img_w)
                    if polygons:
                        for poly in polygons:
                            if len(poly) >= 6:
                                coords_str = " ".join(f"{v:.6f}" for v in poly)
                                seg_lines.append(f"{yolo_cid} {coords_str}")
                    else:
                        # Fallback: use bbox as rectangle
                        x, y, w, h = ann['bbox']
                        poly = [x/img_w, y/img_h, (x+w)/img_w, y/img_h,
                                (x+w)/img_w, (y+h)/img_h, x/img_w, (y+h)/img_h]
                        coords_str = " ".join(f"{v:.6f}" for v in poly)
                        seg_lines.append(f"{yolo_cid} {coords_str}")
                else:
                    # No segmentation, use bbox as rectangle
                    x, y, w, h = ann['bbox']
                    poly = [x/img_w, y/img_h, (x+w)/img_w, y/img_h,
                            (x+w)/img_w, (y+h)/img_h, x/img_w, (y+h)/img_h]
                    coords_str = " ".join(f"{v:.6f}" for v in poly)
                    seg_lines.append(f"{yolo_cid} {coords_str}")

            # Write labels
            with open(det_label_path, 'w') as f:
                f.write('\n'.join(det_lines))
            with open(seg_label_path, 'w') as f:
                f.write('\n'.join(seg_lines))

            processed += 1

        print(f"  Processed: {processed} images")

    # Generate data.yaml files
    for data_dir, name in [(DET_DIR, "yolo_detect_v3"), (SEG_DIR, "yolo_segment_v3")]:
        yaml_path = data_dir / "data.yaml"
        task = "segment" if "segment" in name else "detect"
        yaml_content = f"""# {name} - PPE dataset v3 (4 classes: person, helmet, closed footwear, harness)
# Generated from combined_v3 (480 images + oversampling)
path: {data_dir}
train: images/train
val: images/val
test: images/test

nc: {len(CLASS_NAMES)}
names: {CLASS_NAMES}
"""
        with open(yaml_path, 'w') as f:
            f.write(yaml_content)
        print(f"\nGenerated: {yaml_path}")

    # Final summary
    print(f"\n{'=' * 70}")
    print("Summary:")
    for split in ['train', 'val', 'test']:
        det_imgs = len(os.listdir(DET_DIR / 'images' / split))
        seg_imgs = len(os.listdir(SEG_DIR / 'images' / split))
        det_labels = len(os.listdir(DET_DIR / 'labels' / split))
        seg_labels = len(os.listdir(SEG_DIR / 'labels' / split))
        print(f"  {split}: detect={det_imgs} images/{det_labels} labels, seg={seg_imgs} images/{seg_labels} labels")

    print(f"\nClasses (4): {CLASS_NAMES}")
    print(f"Note: harness oversampled in train set")
    print(f"\n{'=' * 70}")
    print("DONE")


if __name__ == "__main__":
    main()
