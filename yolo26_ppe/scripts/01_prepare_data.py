"""Step 1: Convert COCO → YOLO format + balance + analysis.

- COCO RLE → YOLO detect (bbox) + YOLO segment (polygon)
- Stratified split 70/20/10 by source
- Oversampling rare classes (sandals, harness) in train only
- Class distribution analysis report
- Writes data.yaml for both tasks
"""
import json
import os
import shutil
import random
from collections import Counter, defaultdict

import numpy as np
import cv2
from pycocotools import mask as mask_util

try:
    import yaml
except ImportError:
    yaml = None

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COCO_JSON = os.path.join(BASE, "dataset_combined", "annotations.json")
IMG_BASE = os.path.join(BASE, "dataset_combined", "images")

OUT_DETECT = os.path.join(BASE, "yolo26_ppe", "data", "yolo_detect")
OUT_SEGMENT = os.path.join(BASE, "yolo26_ppe", "data", "yolo_segment")
ANALYSIS_DIR = os.path.join(BASE, "yolo26_ppe", "data", "analysis")

COCO_TO_YOLO = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}
_CLASS_NAMES_FALLBACK = ["person", "helmet", "boots", "shoes", "sandals", "harness"]


def _load_class_names():
    """Read CLASS_NAMES from configs/train.yaml if available, else fallback."""
    config_path = os.path.join(BASE, "yolo26_ppe", "configs", "train.yaml")
    if yaml is not None and os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            names = cfg.get("class_names") if isinstance(cfg, dict) else None
            if names and isinstance(names, list) and len(names) == len(_CLASS_NAMES_FALLBACK):
                return names
        except Exception:
            pass
    return list(_CLASS_NAMES_FALLBACK)


CLASS_NAMES = _load_class_names()

SPLIT_RATIO = {"train": 0.7, "val": 0.2, "test": 0.1}
RANDOM_SEED = 42

# Oversampling targets (rare classes only).
# NOTE: copy_paste augmentation + class weights (cls_pw in train.yaml) are the
# PRIMARY strategy for handling class imbalance. Oversampling here is a
# SECONDARY support measure and is capped at MAX_OVERSAMPLE_FACTOR per image
# to avoid the model memorizing duplicated images (e.g. sandals at 83x).
MAX_OVERSAMPLE_FACTOR = 10
OVERSAMPLE_TARGETS = {
    "sandals": 200,   # 6 → 200 (capped at 10x per image)
    "harness": 200,   # 86 → 200 (capped at 10x per image)
    "boots": 400,     # 795 → keep (already reasonable)
}


def rle_to_polygon(rle, img_w, img_h):
    """Convert COCO RLE to normalized polygon coordinates."""
    if rle is None:
        return None
    try:
        mask = mask_util.decode(rle)
    except Exception:
        return None
    if mask.sum() == 0:
        return None
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) < 10:
        return None
    epsilon = 0.005 * cv2.arcLength(largest, True)
    approx = cv2.approxPolyDP(largest, epsilon, True)
    if len(approx) < 3:
        return None
    pts = approx.reshape(-1, 2).astype(np.float32)
    pts[:, 0] /= img_w
    pts[:, 1] /= img_h
    return pts.flatten().tolist()


def bbox_to_yolo(bbox, img_w, img_h):
    x, y, w, h = bbox
    cx = (x + w / 2) / img_w
    cy = (y + h / 2) / img_h
    return [cx, cy, w / img_w, h / img_h]


def bbox_to_polygon(bbox, img_w, img_h):
    """Fallback: bbox → 4-point polygon."""
    x, y, w, h = bbox
    return [x/img_w, y/img_h, (x+w)/img_w, y/img_h,
            (x+w)/img_w, (y+h)/img_h, x/img_w, (y+h)/img_h]


def split_imgs(imgs):
    """Shuffle (in place) and split into train/val/test by SPLIT_RATIO.

    MUST be called exactly ONCE per source list. Calling it repeatedly
    reuses the advancing RNG state and in-place shuffling, which can place
    the same image in multiple splits (data leakage — see CODE_REVIEW C1).
    """
    random.shuffle(imgs)
    n = len(imgs)
    n_train = int(n * SPLIT_RATIO["train"])
    n_val = int(n * SPLIT_RATIO["val"])
    return {
        "train": imgs[:n_train],
        "val": imgs[n_train:n_train + n_val],
        "test": imgs[n_train + n_val:],
    }


def main():
    print("=" * 70)
    print("STEP 1: COCO → YOLO + Balance + Analysis")
    print("=" * 70)

    # Load COCO
    with open(COCO_JSON, "r", encoding="utf-8") as f:
        coco = json.load(f)
    images = {img["id"]: img for img in coco["images"]}
    annotations = coco["annotations"]

    print(f"\n  Source: {len(images)} images, {len(annotations)} annotations")

    # Group annotations by image
    anns_by_image = defaultdict(list)
    for ann in annotations:
        anns_by_image[ann["image_id"]].append(ann)

    # --- Class distribution BEFORE balance ---
    class_counts = Counter()
    for ann in annotations:
        cat_id = ann["category_id"]
        if cat_id in COCO_TO_YOLO:
            class_counts[CLASS_NAMES[COCO_TO_YOLO[cat_id]]] += 1

    print(f"\n  Class distribution (BEFORE balance):")
    for cls in CLASS_NAMES:
        print(f"    {cls:15s}: {class_counts[cls]:5d}")

    max_count = max(class_counts.values())
    min_count = min(class_counts.values())
    print(f"\n  Imbalance ratio: {max_count}:{min_count} = {max_count/max(1,min_count):.0f}:1")

    # --- Stratified split ---
    images_2026 = [img for img in coco["images"] if img.get("source") == "2026"]
    images_blurred = [img for img in coco["images"] if img.get("source") == "blurred"]

    random.seed(RANDOM_SEED)

    # Call split_imgs ONCE per source to avoid data leakage.
    # Calling it repeatedly reuses the same in-place shuffled list and the
    # same RNG state, which can place the same image in multiple splits.
    split_2026 = split_imgs(images_2026)
    split_blurred = split_imgs(images_blurred)
    splits = {}
    for s in ["train", "val", "test"]:
        splits[s] = split_2026[s] + split_blurred[s]

    print(f"\n  Split:")
    for s in ["train", "val", "test"]:
        print(f"    {s:5s}: {len(splits[s])} images")

    # --- Identify images with rare classes for oversampling ---
    train_imgs_with_rare = defaultdict(list)  # class_name -> list of (img_info, anns)
    for img_info in splits["train"]:
        img_id = img_info["id"]
        for ann in anns_by_image.get(img_id, []):
            cat_id = ann["category_id"]
            if cat_id not in COCO_TO_YOLO:
                continue
            cls_name = CLASS_NAMES[COCO_TO_YOLO[cat_id]]
            if cls_name in OVERSAMPLE_TARGETS:
                train_imgs_with_rare[cls_name].append(img_info)

    print(f"\n  Oversampling plan (max {MAX_OVERSAMPLE_FACTOR}x per image):")
    for cls, target in OVERSAMPLE_TARGETS.items():
        current = class_counts[cls]
        n_imgs = len(train_imgs_with_rare.get(cls, []))
        if current < target and n_imgs > 0:
            # Cap oversample factor so no single image is copied more than
            # MAX_OVERSAMPLE_FACTOR times (prevents memorization).
            oversample_factor = min(MAX_OVERSAMPLE_FACTOR, max(1, target // max(1, current)))
            print(f"    {cls:15s}: {current} anns → target {target}, {n_imgs} unique train images, oversample {oversample_factor}x")
        else:
            print(f"    {cls:15s}: {current} (no oversample needed)")

    # --- Process and write labels ---
    stats = {"detect": Counter(), "segment": Counter()}
    oversample_log = Counter()
    skipped_missing = 0  # count images skipped because source file missing

    for split_name, split_list in splits.items():
        # For train: add oversampled copies of rare-class images
        process_list = list(split_list)

        if split_name == "train":
            for cls, target in OVERSAMPLE_TARGETS.items():
                current = sum(1 for img in split_list
                              for ann in anns_by_image.get(img["id"], [])
                              if COCO_TO_YOLO.get(ann["category_id"]) == CLASS_NAMES.index(cls))
                rare_imgs = train_imgs_with_rare.get(cls, [])
                if current < target and rare_imgs:
                    needed = target - current
                    copies_needed = max(1, needed // max(1, len(rare_imgs)))
                    # Cap so no image is copied more than MAX_OVERSAMPLE_FACTOR times.
                    copies_needed = min(copies_needed, MAX_OVERSAMPLE_FACTOR)
                    for _ in range(copies_needed):
                        for img_info in rare_imgs:
                            process_list.append(img_info)
                            oversample_log[cls] += 1

        print(f"\n  Processing {split_name}: {len(process_list)} images (incl. oversamples)")

        seen_filenames = set()
        for idx, img_info in enumerate(process_list):
            img_id = img_info["id"]
            file_name = img_info["file_name"]
            img_w = img_info["width"]
            img_h = img_info["height"]

            src_img = os.path.join(IMG_BASE, file_name)
            if not os.path.exists(src_img):
                skipped_missing += 1
                continue

            basename = os.path.basename(file_name)
            name = os.path.splitext(basename)[0]

            # Handle duplicate filenames from oversampling
            if basename in seen_filenames:
                name = f"{name}_os{idx}"
                basename = f"{name}.jpg"
            seen_filenames.add(basename)

            # Copy image
            for out_dir in [OUT_DETECT, OUT_SEGMENT]:
                dst_img = os.path.join(out_dir, "images", split_name, basename)
                if not os.path.exists(dst_img):
                    shutil.copy2(src_img, dst_img)

            # Build label lines
            img_anns = anns_by_image.get(img_id, [])
            detect_lines = []
            segment_lines = []

            for ann in img_anns:
                cat_id = ann["category_id"]
                if cat_id not in COCO_TO_YOLO:
                    continue
                yolo_cls = COCO_TO_YOLO[cat_id]

                bbox = ann.get("bbox")
                if bbox and len(bbox) == 4:
                    yb = bbox_to_yolo(bbox, img_w, img_h)
                    detect_lines.append(f"{yolo_cls} {yb[0]:.6f} {yb[1]:.6f} {yb[2]:.6f} {yb[3]:.6f}")
                    stats["detect"][CLASS_NAMES[yolo_cls]] += 1

                seg = ann.get("segmentation")
                if seg and isinstance(seg, dict):
                    poly = rle_to_polygon(seg, img_w, img_h)
                    if poly and len(poly) >= 6:
                        poly_str = " ".join(f"{v:.6f}" for v in poly)
                        segment_lines.append(f"{yolo_cls} {poly_str}")
                    elif bbox:
                        poly = bbox_to_polygon(bbox, img_w, img_h)
                        poly_str = " ".join(f"{v:.6f}" for v in poly)
                        segment_lines.append(f"{yolo_cls} {poly_str}")
                    stats["segment"][CLASS_NAMES[yolo_cls]] += 1
                elif bbox:
                    poly = bbox_to_polygon(bbox, img_w, img_h)
                    poly_str = " ".join(f"{v:.6f}" for v in poly)
                    segment_lines.append(f"{yolo_cls} {poly_str}")
                    stats["segment"][CLASS_NAMES[yolo_cls]] += 1

            for out_dir, lines in [(OUT_DETECT, detect_lines), (OUT_SEGMENT, segment_lines)]:
                label_path = os.path.join(out_dir, "labels", split_name, f"{name}.txt")
                with open(label_path, "w") as f:
                    f.write("\n".join(lines))
                    if lines:
                        f.write("\n")

    # Warn about silently skipped images (missing source files)
    if skipped_missing > 0:
        print(f"\n  WARNING: {skipped_missing} image(s) skipped because source file was not found in {IMG_BASE}")

    # --- Analysis report ---
    print(f"\n{'=' * 70}")
    print(f"CLASS DISTRIBUTION AFTER BALANCE")
    print(f"{'=' * 70}")

    print(f"\n  {'Class':15s} {'Before':>8s} {'After':>8s} {'Change':>8s}")
    print(f"  {'-'*15} {'-'*8} {'-'*8} {'-'*8}")
    for cls in CLASS_NAMES:
        before = class_counts[cls]
        after = stats["detect"][cls]
        change = after - before
        print(f"  {cls:15s} {before:8d} {after:8d} {change:+8d}")

    new_max = max(stats["detect"].values())
    new_min = min(v for v in stats["detect"].values() if v > 0)
    print(f"\n  New imbalance ratio: {new_max}:{new_min} = {new_max/new_min:.1f}:1")

    print(f"\n  Oversampling log:")
    for cls, count in oversample_log.items():
        n_unique = len(train_imgs_with_rare.get(cls, []))
        print(f"    {cls:15s}: +{count} image copies (from {n_unique} unique images)")

    # Save analysis JSON
    analysis = {
        "total_images": len(images),
        "splits": {k: len(v) for k, v in splits.items()},
        "before_balance": dict(class_counts),
        "after_balance_detect": dict(stats["detect"]),
        "after_balance_segment": dict(stats["segment"]),
        "class_names": CLASS_NAMES,
        "imbalance_before": f"{max_count}:{min_count} = {max_count/max(1,min_count):.0f}:1",
        "imbalance_after": f"{new_max}:{new_min} = {new_max/new_min:.1f}:1",
        "oversample_targets": OVERSAMPLE_TARGETS,
        "oversample_log": dict(oversample_log),
        "oversample_unique_images": {cls: len(train_imgs_with_rare.get(cls, [])) for cls in OVERSAMPLE_TARGETS},
        "skipped_missing_images": skipped_missing,
    }
    with open(os.path.join(ANALYSIS_DIR, "data_analysis.json"), "w") as f:
        json.dump(analysis, f, indent=2)

    # Write data.yaml
    # Use absolute path so Ultralytics resolves images correctly regardless of cwd.
    for task, out_dir in [("detect", OUT_DETECT), ("segment", OUT_SEGMENT)]:
        yaml_content = f"""# YOLO26 PPE {task} dataset
path: {out_dir}
train: images/train
val: images/val
test: images/test

nc: {len(CLASS_NAMES)}
names: {CLASS_NAMES}
"""
        with open(os.path.join(out_dir, "data.yaml"), "w") as f:
            f.write(yaml_content)

    print(f"\n  Analysis saved: {ANALYSIS_DIR}/data_analysis.json")
    print(f"  data.yaml written for detect + segment")
    print(f"\n{'=' * 70}")
    print(f"DONE")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
