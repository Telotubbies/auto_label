#!/usr/bin/env python3
"""Step 01b: Prepare YOLO data from combined_v2 dataset.

- Reads combined_v2/annotations.json (913 images, 5 classes)
- Splits into train/val/test (80/10/10)
- Converts to YOLO detection format (bbox)
- Converts to YOLO segmentation format (polygon masks)
- Applies oversampling for rare classes (harness)
- Generates data.yaml files
"""
import json
import os
import random
import shutil
from pathlib import Path
from collections import Counter
import numpy as np

BASE = Path("/mnt/e/02_Projects/auto_label/yolo26_ppe")
COMBINED_DIR = BASE / "data" / "combined_v2"
ANN_PATH = COMBINED_DIR / "annotations.json"
IMG_DIR = COMBINED_DIR / "images"

# Output directories
DET_DIR = BASE / "data" / "yolo_detect_v2"
SEG_DIR = BASE / "data" / "yolo_segment_v2"

CLASS_NAMES = ["person", "helmet", "boots", "shoes", "harness"]
# COCO category IDs in our dataset: 1=person, 2=helmet, 3=boots, 4=shoes, 5=harness
# YOLO class IDs: 0=person, 1=helmet, 2=boots, 3=shoes, 4=harness
COCO_TO_YOLO = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4}

SPLIT_RATIOS = {"train": 0.8, "val": 0.1, "test": 0.1}
RANDOM_SEED = 42

# Oversampling targets for rare classes
OVERSAMPLE_TARGETS = {4: 500}  # harness (YOLO class 4) → target 500 annotations


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

            # Calculate oversampling multipliers
            oversample_imgs = []
            for target_cls, target_count in OVERSAMPLE_TARGETS.items():
                current = train_class_counts.get(target_cls, 0)
                if current < target_count and current > 0:
                    # Find images that contain this class
                    imgs_with_class = []
                    for img_id in split_img_ids:
                        for ann in anns_by_img.get(img_id, []):
                            if COCO_TO_YOLO.get(ann['category_id']) == target_cls:
                                imgs_with_class.append(img_id)
                                break
                    # Calculate how many times to duplicate
                    multiplier = min(target_count // current, 10)  # Cap at 10x
                    for img_id in imgs_with_class:
                        for _ in range(multiplier - 1):
                            oversample_imgs.append(img_id)
                    print(f"  Oversampling class {CLASS_NAMES[target_cls]}: {len(imgs_with_class)} images × {multiplier}x = +{len(oversample_imgs)} copies")

            split_img_ids = split_img_ids + oversample_imgs

        processed = 0
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
            base_name = file_name
            if split == 'train' and split_img_ids.count(img_id) > 1:
                # Add suffix for oversampled copies
                idx = split_img_ids[:split_img_ids.index(img_id)].count(img_id)
                if idx > 0:
                    name_parts = os.path.splitext(file_name)
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
    for data_dir, name in [(DET_DIR, "yolo_detect_v2"), (SEG_DIR, "yolo_segment_v2")]:
        yaml_path = data_dir / "data.yaml"
        task = "segment" if "segment" in name else "detect"
        yaml_content = f"""# {name} - PPE dataset v2 (5 classes, sandals merged into shoes)
# Generated from combined_v2 (913 images + oversampling)
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

    print(f"\nClasses (5): {CLASS_NAMES}")
    print(f"Note: sandals merged into shoes (only 12 samples total)")
    print(f"Note: harness oversampled in train set")
    print(f"\n{'=' * 70}")
    print("DONE")


if __name__ == "__main__":
    main()
