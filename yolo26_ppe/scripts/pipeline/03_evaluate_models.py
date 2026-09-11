#!/usr/bin/env python3
"""Evaluate all 4 v4_recipe models on test set + find 10 interesting failure cases."""
import sys, os, json, csv, shutil
sys.path.insert(0, os.path.dirname(__file__))

# Apply focal patch for consistency
try:
    import focal_patch
except Exception:
    pass

from ultralytics import YOLO
import torch
import numpy as np
from pathlib import Path
from PIL import Image
import cv2

VERSION = "v4_recipe"
BASE = Path("/mnt/e/02_Projects/auto_label/yolo26_ppe")
OUT = BASE / "artifacts" / "evaluation" / "yolo" / f"production_{VERSION}"
OUT.mkdir(parents=True, exist_ok=True)
FAIL_DIR = OUT / "all_failure_case_images"
FAIL_DIR.mkdir(exist_ok=True)

MODELS = {
    "medium_detection": {
        "weights": BASE / "yolo26_ppe/models/production/medium_detection/stage_2_final_fine_tuning/weights/best.pt",
        "data": "/tmp/yolo_detect_data/data.yaml",
        "task": "detect",
    },
    "medium_segmentation": {
        "weights": BASE / "yolo26_ppe/models/production/medium_segmentation/stage_2_final_fine_tuning/weights/best.pt",
        "data": "/tmp/yolo_seg_data/data.yaml",
        "task": "segment",
    },
    "small_detection": {
        "weights": BASE / "yolo26_ppe/models/production/small_detection/stage_2_final_fine_tuning/weights/best.pt",
        "data": "/tmp/yolo_detect_data/data.yaml",
        "task": "detect",
    },
    "small_segmentation": {
        "weights": BASE / "yolo26_ppe/models/production/small_segmentation/stage_2_final_fine_tuning/weights/best.pt",
        "data": "/tmp/yolo_seg_data/data.yaml",
        "task": "segment",
    },
}

NAMES = ["person", "helmet", "closed footwear", "harness"]

def eval_model(key, cfg):
    print(f"\n{'='*60}")
    print(f"Evaluating: {key}")
    print(f"{'='*60}")
    model = YOLO(str(cfg["weights"]))
    # Run validation on test split
    results = model.val(
        data=cfg["data"],
        split="test",
        imgsz=640,
        batch=16,
        conf=0.001,
        iou=0.6,
        device=0,
        verbose=True,
        save_json=False,
        plots=True,
        project=str(OUT / key),
        name="test_eval",
        exist_ok=True,
    )
    # Collect metrics — Ultralytics API uses lowercase property names
    # (results.box.map, .map50, .map75, .mp, .mr; same for results.seg).
    # See https://docs.ultralytics.com/modes/val and
    # https://docs.ultralytics.com/tasks/segment for the current API.
    metrics = {}
    try:
        metrics["precision"] = float(results.box.mp)  # mean precision
        metrics["recall"] = float(results.box.mr)
        metrics["mAP50"] = float(results.box.map50)
        metrics["mAP75"] = float(results.box.map75)
        metrics["mAP50-95"] = float(results.box.map)
    except Exception as e:
        print(f"box metric error: {e}")
    if cfg["task"] == "segment":
        try:
            metrics["mask_precision"] = float(results.seg.mp)
            metrics["mask_recall"] = float(results.seg.mr)
            metrics["mask_mAP50"] = float(results.seg.map50)
            metrics["mask_mAP75"] = float(results.seg.map75)
            metrics["mask_mAP50-95"] = float(results.seg.map)
        except Exception as e:
            print(f"seg metric error: {e}")
    # Per-class — box metrics for all tasks, mask metrics for segment
    try:
        names = results.names
        per_class = {}
        for i, n in names.items():
            entry = {
                "P": float(results.box.p[i]) if i < len(results.box.p) else None,
                "R": float(results.box.r[i]) if i < len(results.box.r) else None,
                "mAP50": float(results.box.ap50[i]) if i < len(results.box.ap50) else None,
                "mAP50-95": float(results.box.ap[i]) if i < len(results.box.ap) else None,
            }
            if cfg["task"] == "segment":
                entry["mask_P"] = float(results.seg.p[i]) if i < len(results.seg.p) else None
                entry["mask_R"] = float(results.seg.r[i]) if i < len(results.seg.r) else None
                entry["mask_mAP50"] = float(results.seg.ap50[i]) if i < len(results.seg.ap50) else None
                entry["mask_mAP50-95"] = float(results.seg.ap[i]) if i < len(results.seg.ap) else None
            per_class[n] = entry
        metrics["per_class"] = per_class
    except Exception as e:
        print(f"per-class error: {e}")
    # Model info
    metrics["model_size_MB"] = cfg["weights"].stat().st_size / 1024**2
    metrics["params"] = sum(p.numel() for p in model.model.parameters())
    # Inference speed
    try:
        speed = results.speed
        metrics["inference_ms"] = float(speed.get("inference", 0))
        metrics["preprocess_ms"] = float(speed.get("preprocess", 0))
        metrics["postprocess_ms"] = float(speed.get("postprocess", 0))
    except Exception:
        pass
    print(f"Results: {json.dumps(metrics, indent=2, default=str)}")
    return model, metrics

def find_failures(key, cfg, model, top_n=10):
    """Find interesting failure cases: missed (FN), small objects, low confidence."""
    print(f"\n{'='*60}")
    print(f"Finding failure cases: {key}")
    print(f"{'='*60}")
    test_dir = Path("/tmp/yolo_detect_data/images/test") if cfg["task"] == "detect" else Path("/tmp/yolo_seg_data/images/test")
    label_dir = Path("/tmp/yolo_detect_data/labels/test") if cfg["task"] == "detect" else Path("/tmp/yolo_seg_data/labels/test")
    if not test_dir.exists():
        print(f"No test dir: {test_dir}")
        return []
    images = sorted(test_dir.glob("*.jpg")) + sorted(test_dir.glob("*.png"))
    failures = []
    for img_path in images:
        label_path = label_dir / (img_path.stem + ".txt")
        if not label_path.exists():
            continue
        # Read GT
        gt_boxes = []
        with open(label_path) as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    cls = int(parts[0])
                    x, y, w, h = map(float, parts[1:5])
                    gt_boxes.append({"cls": cls, "w": w, "h": h, "x": x, "y": y})
        if not gt_boxes:
            continue
        # Smallest GT box (normalized)
        min_wh = min(b["w"] * b["h"] for b in gt_boxes)
        # Run prediction
        try:
            res = model.predict(str(img_path), imgsz=640, conf=0.25, iou=0.6, device=0, verbose=False)
            preds = res[0]
            n_pred = len(preds.boxes) if preds.boxes is not None else 0
            # Confidence
            if n_pred > 0:
                confs = preds.boxes.conf.cpu().numpy()
                max_conf = float(confs.max())
                min_conf = float(confs.min())
            else:
                max_conf = 0.0
                min_conf = 0.0
            # Missed = GT - matched (rough: if n_pred < n_gt, likely missed)
            n_missed = max(0, len(gt_boxes) - n_pred)
            # Score: prioritize small objects + missed + low confidence
            score = n_missed * 10 + (1 - max_conf) * 5 + (1 - min_wh) * 3
            failures.append({
                "image": str(img_path),
                "stem": img_path.stem,
                "n_gt": len(gt_boxes),
                "n_pred": n_pred,
                "n_missed": n_missed,
                "max_conf": max_conf,
                "min_gt_wh": min_wh,
                "score": score,
                "gt_classes": [b["cls"] for b in gt_boxes],
            })
        except Exception as e:
            print(f"Error {img_path}: {e}")
    # Sort by score descending
    failures.sort(key=lambda x: x["score"], reverse=True)
    top = failures[:top_n]
    # Save visualizations
    for i, f in enumerate(top):
        img = cv2.imread(f["image"])
        # Draw GT (green)
        label_path = label_dir / (f["stem"] + ".txt")
        H, W = img.shape[:2]
        with open(label_path) as fp:
            for line in fp:
                parts = line.strip().split()
                if len(parts) >= 5:
                    cls = int(parts[0])
                    x, y, w, h = map(float, parts[1:5])
                    x1 = int((x - w/2) * W)
                    y1 = int((y - h/2) * H)
                    x2 = int((x + w/2) * W)
                    y2 = int((y + h/2) * H)
                    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(img, f"GT:{NAMES[cls]}", (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        # Draw predictions (red)
        res = model.predict(f["image"], imgsz=640, conf=0.25, iou=0.6, device=0, verbose=False)
        if res[0].boxes is not None:
            boxes = res[0].boxes.xyxy.cpu().numpy()
            confs = res[0].boxes.conf.cpu().numpy()
            clss = res[0].boxes.cls.cpu().numpy().astype(int)
            for (x1, y1, x2, y2), c, cl in zip(boxes, confs, clss):
                cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 2)
                cv2.putText(img, f"{NAMES[cl]}:{c:.2f}", (int(x1), int(y2)+15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        out_path = FAIL_DIR / f"{key}_{i:02d}_{f['stem']}.jpg"
        cv2.imwrite(str(out_path), img)
        f["saved_to"] = str(out_path)
    return top

def main():
    all_metrics = {}
    all_failures = {}
    for key, cfg in MODELS.items():
        if not cfg["weights"].exists():
            print(f"SKIP {key}: weights not found")
            continue
        model, metrics = eval_model(key, cfg)
        all_metrics[key] = metrics
        failures = find_failures(key, cfg, model, top_n=10)
        all_failures[key] = failures
        # Save per-model
        with open(OUT / f"{key}_metrics.json", "w") as f:
            json.dump(metrics, f, indent=2, default=str)
        with open(OUT / f"{key}_failures.json", "w") as f:
            json.dump(failures, f, indent=2, default=str)
    # Summary
    with open(OUT / "all_metrics.json", "w") as f:
        json.dump(all_metrics, f, indent=2, default=str)
    with open(OUT / "all_failures.json", "w") as f:
        json.dump(all_failures, f, indent=2, default=str)
    # Print summary table
    print(f"\n{'='*80}")
    print("SUMMARY: v4_recipe test set evaluation")
    print(f"{'='*90}")
    print(f"{'Model':<18} {'mAP50':>7} {'mAP75':>7} {'mAP50-95':>9} {'P':>7} {'R':>7} {'Size(MB)':>9} {'Params':>11} {'Inf(ms)':>8}")
    for key, m in all_metrics.items():
        print(f"{key:<18} {m.get('mAP50',0):>7.3f} {m.get('mAP75',0):>7.3f} {m.get('mAP50-95',0):>9.3f} {m.get('precision',0):>7.3f} {m.get('recall',0):>7.3f} {m.get('model_size_MB',0):>9.1f} {m.get('params',0):>11,} {m.get('inference_ms',0):>8.1f}")
    # Mask summary for segmentation models
    seg_models = {k: m for k, m in all_metrics.items() if "mask_mAP50" in m}
    if seg_models:
        print(f"\n--- Mask (M) metrics for segmentation models ---")
        print(f"{'Model':<18} {'mAP50':>7} {'mAP75':>7} {'mAP50-95':>9} {'P':>7} {'R':>7}")
        for key, m in seg_models.items():
            print(f"{key:<18} {m.get('mask_mAP50',0):>7.3f} {m.get('mask_mAP75',0):>7.3f} {m.get('mask_mAP50-95',0):>9.3f} {m.get('mask_precision',0):>7.3f} {m.get('mask_recall',0):>7.3f}")
    print(f"\nFailure cases saved to: {FAIL_DIR}")
    print(f"Metrics saved to: {OUT}")

if __name__ == "__main__":
    main()
