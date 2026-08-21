#!/usr/bin/env python3
"""Evaluate a trained model on the test set and log to MLflow.

Usage:
    python 05_eval_optimizer_experiment.py \
        --model n_detect --version v3 --optimizer AdamW
    python 05_eval_optimizer_experiment.py \
        --model s_seg --version v4 --optimizer Adam
"""
import argparse
import json
from pathlib import Path

from ultralytics import YOLO
import mlflow

BASE = Path("/mnt/e/02_Projects/auto_label/yolo26_ppe")

MODEL_CONFIG = {
    "n_detect": {"data": BASE / "data/yolo_detect_v2/data.yaml", "task": "detect"},
    "s_detect": {"data": BASE / "data/yolo_detect_v2/data.yaml", "task": "detect"},
    "n_seg":    {"data": BASE / "data/yolo_segment_v2/data.yaml", "task": "segment"},
    "s_seg":    {"data": BASE / "data/yolo_segment_v2/data.yaml", "task": "segment"},
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True,
                        choices=["n_detect", "s_detect", "n_seg", "s_seg"])
    parser.add_argument("--version", required=True, help="v2, v3, v4, v5")
    parser.add_argument("--optimizer", required=True,
                        choices=["SGD", "AdamW", "Adam", "auto"])
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.001)
    parser.add_argument("--iou", type=float, default=0.6)
    args = parser.parse_args()

    opt_lower = args.optimizer.lower()
    folder_name = f"yolo26{args.model}_{args.version}_{opt_lower}"
    weights_path = BASE / "models" / folder_name / "run1" / "weights" / "best.pt"

    if not weights_path.exists():
        print(f"ERROR: weights not found: {weights_path}")
        return

    cfg = MODEL_CONFIG[args.model]

    print("=" * 60)
    print(f"  Evaluating {args.model} {args.version} ({args.optimizer})")
    print(f"  Weights: {weights_path}")
    print(f"  Data:    {cfg['data']}")
    print(f"  imgsz:   {args.imgsz}")
    print("=" * 60)

    model = YOLO(str(weights_path))

    # Evaluate on test split
    results = model.val(
        data=str(cfg["data"]),
        split="test",
        imgsz=args.imgsz,
        conf=args.conf,
        iou=args.iou,
        device="0",
        project=str(BASE / "models" / folder_name),
        name="eval_test",
        exist_ok=True,
    )

    # Extract metrics
    metrics = {}
    if hasattr(results, "results_dict"):
        metrics = results.results_dict
    elif hasattr(results, "box"):
        # Segmentation has box + mask
        metrics["box_mAP50"] = results.box.map50
        metrics["box_mAP50_95"] = results.box.map
        metrics["box_precision"] = results.box.mp
        metrics["box_recall"] = results.box.mr
        if hasattr(results, "mask"):
            metrics["mask_mAP50"] = results.mask.map50
            metrics["mask_mAP50_95"] = results.mask.map
            metrics["mask_precision"] = results.mask.mp
            metrics["mask_recall"] = results.mask.mr

    print("\n  Results:")
    for k, v in metrics.items():
        print(f"    {k}: {v:.4f}")

    # Log to MLflow
    mlflow.set_tracking_uri(f"sqlite:///{BASE}/mlflow/mlflow.db")
    mlflow.set_experiment("yolo26_ppe_optimizer_experiment")

    with mlflow.start_run(run_name=f"eval_{args.model}_{args.version}_{opt_lower}") as run:
        run_id = run.info.run_id
        mlflow.set_tags({
            "optimizer": args.optimizer,
            "version": args.version,
            "model_variant": args.model,
            "dataset": "ppe_v2",
            "task": cfg["task"],
            "eval_type": "test_set",
            "experiment_type": "optimizer_comparison",
        })
        mlflow.log_params({
            "imgsz": args.imgsz,
            "conf": args.conf,
            "iou": args.iou,
            "weights_path": str(weights_path),
        })
        for k, v in metrics.items():
            mlflow.log_metric(k, float(v))

        # Save metrics JSON
        metrics_file = BASE / "models" / folder_name / "eval_test" / "metrics.json"
        metrics_file.parent.mkdir(parents=True, exist_ok=True)
        with open(metrics_file, "w") as f:
            json.dump(metrics, f, indent=2)

        print(f"\n  MLflow run ID: {run_id}")
        print(f"  Metrics saved: {metrics_file}")

    return run_id


if __name__ == "__main__":
    main()
