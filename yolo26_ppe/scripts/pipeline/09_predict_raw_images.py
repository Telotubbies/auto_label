#!/usr/bin/env python3
"""Run production YOLO26 PPE models on raw images for VLM comparison research.

Usage:
  # Predict on all images in data/raw/<batch> using all 4 production models
  python 09_predict_raw_images.py --batch custom_capture_2026-08-14

  # Predict on a specific directory
  python 09_predict_raw_images.py --input /mnt/e/02_Projects/auto_label/data/raw/blurred

  # Use only one model
  python 09_predict_raw_images.py --batch custom_capture_2026-08-14 --model small_detection

  # Custom output directory
  python 09_predict_raw_images.py --batch custom_capture_2026-08-14 --output /tmp/my_predictions

Output:
  yolo26_ppe/data/predictions/<batch>/<model>/*.jpg   (annotated images)
  yolo26_ppe/data/predictions/<batch>/summary.json    (per-image results)
"""
import argparse
import json
import os
import time
from pathlib import Path

# ROCm env (must be before torch import)
os.environ.setdefault("HSA_ENABLE_DXG_DETECTION", "1")
os.environ.setdefault("TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL", "1")

from ultralytics import YOLO

BASE = Path("/mnt/e/02_Projects/auto_label")
PRODUCTION_DIR = BASE / "yolo26_ppe" / "yolo26_ppe" / "models" / "production"
PREDICTIONS_DIR = BASE / "yolo26_ppe" / "data" / "predictions"
RAW_DIR = BASE / "data" / "raw"

# Production models — final weights from stage_2_final_fine_tuning
MODELS = {
    "medium_detection": {
        "weights": PRODUCTION_DIR / "medium_detection" / "stage_2_final_fine_tuning" / "weights" / "best.pt",
        "task": "detect",
    },
    "medium_segmentation": {
        "weights": PRODUCTION_DIR / "medium_segmentation" / "stage_2_final_fine_tuning" / "weights" / "best.pt",
        "task": "segment",
    },
}

CLASSES = ["person", "helmet", "closed footwear", "harness"]


def parse_args():
    p = argparse.ArgumentParser(description="Run production YOLO26 PPE models on raw images")
    p.add_argument("--batch", help="batch name under data/raw/ (e.g. blurred, custom_capture_2026-08-14)")
    p.add_argument("--input", help="explicit input directory (overrides --batch)")
    p.add_argument("--output", help="explicit output directory (overrides default predictions/<batch>)")
    p.add_argument("--model", choices=list(MODELS.keys()), help="run only one model (default: all 4)")
    p.add_argument("--conf", type=float, default=0.25, help="confidence threshold (default 0.25)")
    p.add_argument("--iou", type=float, default=0.45, help="IoU threshold for NMS (default 0.45)")
    p.add_argument("--imgsz", type=int, default=640, help="inference image size (default 640)")
    p.add_argument("--device", default="0", help="device (default 0 for GPU, or 'cpu')")
    return p.parse_args()


def resolve_paths(args):
    """Resolve input and output directories."""
    if args.input:
        input_dir = Path(args.input)
    elif args.batch:
        input_dir = RAW_DIR / args.batch
    else:
        raise SystemExit("ERROR: must specify --batch or --input")

    if not input_dir.exists():
        raise SystemExit(f"ERROR: input directory not found: {input_dir}")

    if args.output:
        output_dir = Path(args.output)
    elif args.batch:
        output_dir = PREDICTIONS_DIR / args.batch
    else:
        # Use input dir name as batch
        output_dir = PREDICTIONS_DIR / input_dir.name

    output_dir.mkdir(parents=True, exist_ok=True)
    return input_dir, output_dir


def collect_images(input_dir):
    """Collect all image files from input directory (non-recursive)."""
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif"}
    images = sorted([p for p in input_dir.iterdir()
                     if p.is_file() and p.suffix.lower() in exts])
    return images


def run_model(model_name, model_cfg, images, output_dir, args):
    """Run one model on all images, save annotated outputs."""
    weights = model_cfg["weights"]
    if not weights.exists():
        print(f"  SKIP {model_name}: weights not found at {weights}")
        return None

    print(f"\n{'=' * 60}")
    print(f"Predicting: {model_name}")
    print(f"  Weights: {weights}")
    print(f"  Task:    {model_cfg['task']}")
    print(f"  Images:  {len(images)}")
    print(f"{'=' * 60}")

    model = YOLO(str(weights))
    model_out = output_dir / model_name
    model_out.mkdir(parents=True, exist_ok=True)

    results = []
    total_time = 0.0
    for img_path in images:
        t0 = time.time()
        res = model.predict(
            str(img_path),
            imgsz=args.imgsz,
            conf=args.conf,
            iou=args.iou,
            device=args.device,
            save=False,
            verbose=False,
        )
        dt = time.time() - t0
        total_time += dt
        preds = res[0]

        # Save annotated image
        annotated = preds.plot()  # numpy BGR array with bboxes/masks drawn
        import cv2
        out_path = model_out / (img_path.stem + ".jpg")
        cv2.imwrite(str(out_path), annotated, [cv2.IMWRITE_JPEG_QUALITY, 92])

        # Collect detection info
        cls_counts = {}
        n_det = 0
        if preds.boxes is not None:
            clss = preds.boxes.cls.cpu().numpy().astype(int)
            confs = preds.boxes.conf.cpu().numpy()
            n_det = len(clss)
            for c, cf in zip(clss, confs):
                name = CLASSES[c] if c < len(CLASSES) else str(c)
                cls_counts[name] = cls_counts.get(name, 0) + 1

        results.append({
            "image": img_path.name,
            "n_det": n_det,
            "latency_ms": round(dt * 1000, 1),
            "classes": cls_counts,
        })

    avg = total_time / max(len(images), 1) * 1000
    summary = {
        "model": model_name,
        "task": model_cfg["task"],
        "n_images": len(images),
        "total_time_s": round(total_time, 2),
        "avg_latency_ms": round(avg, 1),
        "conf_threshold": args.conf,
        "iou_threshold": args.iou,
        "imgsz": args.imgsz,
        "class_order": CLASSES,
        "results": results,
    }
    with open(model_out / "_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"  Done: {len(images)} images, avg {avg:.1f} ms/img")
    print(f"  Output: {model_out}")
    return summary


def main():
    args = parse_args()
    input_dir, output_dir = resolve_paths(args)
    images = collect_images(input_dir)

    if not images:
        raise SystemExit(f"ERROR: no images found in {input_dir}")

    print(f"Input:  {input_dir}")
    print(f"Output: {output_dir}")
    print(f"Images: {len(images)}")
    print(f"Conf:   {args.conf}, IoU: {args.iou}, Imgsz: {args.imgsz}, Device: {args.device}")

    models_to_run = [args.model] if args.model else list(MODELS.keys())
    all_summaries = {}
    for model_name in models_to_run:
        s = run_model(model_name, MODELS[model_name], images, output_dir, args)
        if s is not None:
            all_summaries[model_name] = s

    # Combined summary
    with open(output_dir / "all_summary.json", "w") as f:
        json.dump(all_summaries, f, indent=2)

    # Print comparison table
    print(f"\n{'=' * 70}")
    print(f"SUMMARY — predictions saved to: {output_dir}")
    print(f"{'=' * 70}")
    print(f"{'Model':<22} {'Task':<10} {'Images':>7} {'Avg ms':>8} {'Total det':>10}")
    print("-" * 70)
    for name, s in all_summaries.items():
        total_det = sum(r["n_det"] for r in s["results"])
        print(f"{name:<22} {s['task']:<10} {s['n_images']:>7} {s['avg_latency_ms']:>8.1f} {total_det:>10}")
    print(f"\nAnnotated images: {output_dir}/<model>/<image>.jpg")
    print(f"Per-model summary: {output_dir}/<model>/_summary.json")
    print(f"Combined summary:  {output_dir}/all_summary.json")


if __name__ == "__main__":
    main()
