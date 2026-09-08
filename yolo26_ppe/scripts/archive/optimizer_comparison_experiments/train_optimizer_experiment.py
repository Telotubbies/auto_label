#!/usr/bin/env python3
"""Train YOLO26 with configurable optimizer — v3/v4/v5 experiment.

Usage:
    python 04_train_optimizer_experiment.py \
        --model n_detect --optimizer AdamW --version v3
    python 04_train_optimizer_experiment.py \
        --model s_seg --optimizer Adam --version v4
    python 04_train_optimizer_experiment.py \
        --model n_detect --optimizer auto --version v5

This script is parameterized so we can run any of the 4 model variants
with any optimizer without duplicating code.
"""
import argparse
import sys
from pathlib import Path

from ultralytics import YOLO
import mlflow

# ===== Config =====
BASE = Path("/mnt/e/02_Projects/auto_label/yolo26_ppe")

MODEL_CONFIG = {
    "n_detect": {
        "weights": "yolo26n.pt",
        "data": BASE / "data/yolo_detect_v2/data.yaml",
        "task": "detect",
        "batch": 16,
    },
    "s_detect": {
        "weights": "yolo26s.pt",
        "data": BASE / "data/yolo_detect_v2/data.yaml",
        "task": "detect",
        "batch": 16,
    },
    "n_seg": {
        "weights": "yolo26n-seg.pt",
        "data": "/tmp/yolo_seg_data/data.yaml",
        "task": "segment",
        "batch": 16,
    },
    "s_seg": {
        "weights": "yolo26s-seg.pt",
        "data": "/tmp/yolo_seg_data/data.yaml",
        "task": "segment",
        "batch": 16,
    },
}

OPTIMIZER_CONFIG = {
    "SGD": {
        "optimizer": "SGD",
        "lr0": 0.01,
        "lrf": 0.01,
        "momentum": 0.937,
        "weight_decay": 0.0005,
        "warmup_bias_lr": 0.1,
    },
    "AdamW": {
        "optimizer": "AdamW",
        "lr0": 0.001,          # Must be 10x lower, otherwise NaN
        "lrf": 0.01,
        "momentum": 0.937,     # beta1
        "weight_decay": 0.0005,
        "warmup_bias_lr": 0.0, # Must be 0 for Adam family
    },
    "Adam": {
        "optimizer": "Adam",
        "lr0": 0.001,
        "lrf": 0.01,
        "momentum": 0.937,
        "weight_decay": 0.0005,
        "warmup_bias_lr": 0.0,
    },
    "auto": {
        "optimizer": "auto",
        # auto ignores lr0 and momentum, but kept here for reference
        "lr0": 0.01,
        "lrf": 0.01,
        "momentum": 0.937,
        "weight_decay": 0.0005,
        "warmup_bias_lr": 0.1,
    },
}

# Common training params (same for all optimizers)
COMMON_PARAMS = {
    "epochs": 300,
    "imgsz": 640,
    "device": "0",
    "workers": 8,
    "patience": 30,        # Early stop if no improvement for 30 epochs
    "cache": True,         # Cache in RAM for speed
    "seed": 42,
    "deterministic": True,
    "warmup_epochs": 3,
    "warmup_momentum": 0.8,
    # Augmentation (moderate, same as v2)
    "hsv_h": 0.02,
    "hsv_s": 0.7,
    "hsv_v": 0.5,
    "degrees": 5.0,
    "translate": 0.15,
    "scale": 0.5,
    "shear": 2.0,
    "perspective": 0.0,
    "flipud": 0.1,
    "fliplr": 0.5,
    "mosaic": 0.5,
    "mixup": 0.1,
    "copy_paste": 0.1,
    "close_mosaic": 20,
    "dropout": 0.1,
}


def main():
    parser = argparse.ArgumentParser(description="Train YOLO26 optimizer experiment")
    parser.add_argument("--model", required=True,
                        choices=["n_detect", "s_detect", "n_seg", "s_seg"],
                        help="Model variant")
    parser.add_argument("--optimizer", required=True,
                        choices=["SGD", "AdamW", "Adam", "auto"],
                        help="Optimizer name")
    parser.add_argument("--version", required=True,
                        help="Version tag: v2, v3, v4, v5")
    parser.add_argument("--batch", type=int, default=None,
                        help="Override batch size (default: from model config)")
    args = parser.parse_args()

    model_cfg = MODEL_CONFIG[args.model]
    opt_cfg = OPTIMIZER_CONFIG[args.optimizer]

    # Override batch if specified
    batch = args.batch if args.batch else model_cfg["batch"]

    # Folder naming: yolo26{variant}_{version}_{optimizer_lower}
    opt_lower = args.optimizer.lower()
    folder_name = f"yolo26{args.model.replace('_', '_')}_v{args.version.lstrip('v')}"
    if args.optimizer != "SGD":
        # SGD is the baseline (v2), others add optimizer suffix
        folder_name = f"yolo26{args.model}_{opt_lower}"
    # Actually use clear naming:
    folder_name = f"yolo26{args.model}_{args.version}_{opt_lower}"

    output_dir = BASE / "models" / folder_name / "run1"

    print("=" * 60)
    print(f"  Training YOLO26 {args.model} {args.version} ({args.optimizer})")
    print("=" * 60)
    print(f"  Weights: {model_cfg['weights']}")
    print(f"  Data:    {model_cfg['data']}")
    print(f"  Task:    {model_cfg['task']}")
    print(f"  Batch:   {batch}")
    print(f"  Output:  {output_dir}")
    print(f"  Seed:    42")
    print(f"  Optimizer config: {opt_cfg}")
    print()

    # Load model
    model = YOLO(model_cfg["weights"])

    # Build train args
    train_args = {
        "data": str(model_cfg["data"]),
        "project": str(BASE / "models" / folder_name),
        "name": "run1",
        "exist_ok": True,
        "batch": batch,
        **COMMON_PARAMS,
        **opt_cfg,
    }

    # MLflow logging
    mlflow.set_tracking_uri(f"sqlite:///{BASE}/mlflow/mlflow.db")
    mlflow.set_experiment("yolo26_ppe_optimizer_experiment")

    with mlflow.start_run(run_name=f"{args.model}_{args.version}_{opt_lower}") as run:
        run_id = run.info.run_id
        print(f"  MLflow run ID: {run_id}")

        # Log tags
        mlflow.set_tags({
            "optimizer": args.optimizer,
            "version": args.version,
            "model_variant": args.model,
            "dataset": "ppe_v2",
            "seed": "42",
            "task": model_cfg["task"],
            "experiment_type": "optimizer_comparison",
        })

        # Log params
        mlflow.log_params({
            "weights": model_cfg["weights"],
            "batch": batch,
            "epochs": COMMON_PARAMS["epochs"],
            "imgsz": COMMON_PARAMS["imgsz"],
            "lr0": opt_cfg["lr0"],
            "lrf": opt_cfg["lrf"],
            "momentum": opt_cfg["momentum"],
            "weight_decay": opt_cfg["weight_decay"],
            "warmup_bias_lr": opt_cfg["warmup_bias_lr"],
        })

        # Train
        results = model.train(**train_args)

        # Log final metrics
        if hasattr(results, "results_dict"):
            metrics = results.results_dict
            for k, v in metrics.items():
                mlflow.log_metric(f"final_{k}", v)

        print(f"\n  Training complete!")
        print(f"  Best weights: {output_dir}/weights/best.pt")
        print(f"  MLflow run:   {run_id}")

    return run_id


if __name__ == "__main__":
    main()
