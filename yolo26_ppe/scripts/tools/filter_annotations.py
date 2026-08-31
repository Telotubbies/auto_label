#!/usr/bin/env python3
"""Filter combined_v2 dataset to cap annotations per image.

Some SAM 3.1 outputs have 50+ annotations per image, causing GPU OOM
during mosaic augmentation. This script caps at max_anns_per_image by
keeping only the highest-confidence annotations.
"""
import json
import os
from pathlib import Path
from collections import Counter

BASE = Path("/mnt/e/02_Projects/auto_label/yolo26_ppe")
ANN_PATH = BASE / "data" / "combined_v2" / "annotations.json"
MAX_ANNS = 30  # Cap annotations per image

def main():
    print(f"Loading {ANN_PATH}...")
    with open(ANN_PATH) as f:
        data = json.load(f)

    # Group annotations by image
    anns_by_img = {}
    for ann in data['annotations']:
        img_id = ann['image_id']
        if img_id not in anns_by_img:
            anns_by_img[img_id] = []
        anns_by_img[img_id].append(ann)

    # Show distribution before
    counts = [len(anns) for anns in anns_by_img.values()]
    print(f"\nBefore filtering:")
    print(f"  Images: {len(data['images'])}")
    print(f"  Total annotations: {len(data['annotations'])}")
    print(f"  Avg anns/image: {sum(counts)/len(counts):.1f}")
    print(f"  Max anns/image: {max(counts)}")
    print(f"  Images with >{MAX_ANNS} anns: {sum(1 for c in counts if c > MAX_ANNS)}")

    # Filter: for images with too many annotations, keep top MAX_ANNS by score
    filtered_annotations = []
    removed = 0
    for img_id, anns in anns_by_img.items():
        if len(anns) > MAX_ANNS:
            # Sort by score (descending), keep top MAX_ANNS
            anns_sorted = sorted(anns, key=lambda a: a.get('score', 1.0), reverse=True)
            kept = anns_sorted[:MAX_ANNS]
            removed += len(anns) - len(kept)
            filtered_annotations.extend(kept)
        else:
            filtered_annotations.extend(anns)

    # Show distribution after
    anns_by_img2 = {}
    for ann in filtered_annotations:
        img_id = ann['image_id']
        if img_id not in anns_by_img2:
            anns_by_img2[img_id] = []
        anns_by_img2[img_id].append(ann)
    counts2 = [len(anns) for anns in anns_by_img2.values()]

    print(f"\nAfter filtering (cap={MAX_ANNS}):")
    print(f"  Total annotations: {len(filtered_annotations)}")
    print(f"  Removed: {removed}")
    print(f"  Avg anns/image: {sum(counts2)/len(counts2):.1f}")
    print(f"  Max anns/image: {max(counts2)}")

    # Class distribution after filtering
    cat_names = {c['id']: c['name'] for c in data['categories']}
    class_counts = Counter()
    for ann in filtered_annotations:
        class_counts[ann['category_id']] += 1
    print(f"\nClass distribution after filtering:")
    for cid in sorted(class_counts.keys()):
        print(f"  {cat_names.get(cid, cid)}: {class_counts[cid]}")

    # Save filtered annotations
    data['annotations'] = filtered_annotations
    with open(ANN_PATH, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"\nSaved filtered annotations to {ANN_PATH}")

if __name__ == "__main__":
    main()
