#!/usr/bin/env python3
"""Step 02b: Train all 4 YOLO26 models with v2 dataset (913 images, 5 classes).

Improved config:
- 300 epochs (vs 150 before)
- imgsz=960 (balance between accuracy and GPU memory)
- batch=16 with auto fallback
- Focal loss for class imbalance
- Better augmentation for noise/lighting tolerance
- MLflow tracking
- GPU only (ROCm)
"""
import os
import sys
import time
from pathlib import Path

# GPU/ROCm environment
os.environ.setdefault("HSA_ENABLE_DXG_DETECTION", "1")
os.environ.setdefault("TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL", "1")
os.environ.setdefault("MLFLOW_TRACKING_URI", "sqlite:////mnt/e/02_Projects/auto_label/yolo26_ppe/mlflow/mlflow.db")
os.environ.setdefault("MLFLOW_EXPERIMENT_NAME", "yolo26_ppe_v2")

BASE = Path("/mnt/e/02_Projects/auto_label/yolo26_ppe")

MODELS = {
    "n_detect": {
        "model": "yolo26n.pt",
        "task": "detect",
        "data": str(BASE / "data" / "yolo_detect_v2" / "data.yaml"),
        "project": str(BASE / "models" / "yolo26n_detect_v2"),
    },
    "s_detect": {
        "model": "yolo26s.pt",
        "task": "detect",
        "data": str(BASE / "data" / "yolo_detect_v2" / "data.yaml"),
        "project": str(BASE / "models" / "yolo26s_detect_v2"),
    },
    "n_seg": {
        "model": "yolo26n-seg.pt",
        "task": "segment",
        "data": str(BASE / "data" / "yolo_segment_v2" / "data.yaml"),
        "project": str(BASE / "models" / "yolo26n_seg_v2"),
    },
    "s_seg": {
        "model": "yolo26s-seg.pt",
        "task": "segment",
        "data": str(BASE / "data" / "yolo_segment_v2" / "data.yaml"),
        "project": str(BASE / "models" / "yolo26s_seg_v2"),
    },
}

# Improved training config
TRAIN_ARGS = {
    "epochs": 300,
    "imgsz": 640,  # Safe for 16GB VRAM
    "batch": 8,   # Conservative for high-annotation dataset
    "device": "0",
    "workers": 8,
    "patience": 50,  # Early stopping patience
    "save": True,
    "save_period": 50,
    "cache": False,  # Don't cache on mounted drive
    # Moderate augmentation for noise/lighting tolerance
    "hsv_h": 0.02,  # Hue augmentation
    "hsv_s": 0.7,   # Saturation augmentation
    "hsv_v": 0.5,   # Value (brightness) augmentation
    "degrees": 5.0,  # Rotation
    "translate": 0.15,  # Translation
    "scale": 0.5,   # Scale variation
    "shear": 2.0,   # Shear augmentation
    "perspective": 0.0,
    "flipud": 0.1,  # Vertical flip (10%)
    "fliplr": 0.5,  # Horizontal flip (50%)
    "mosaic": 0.5,  # Reduced from 1.0 to avoid OOM with high-annotation images
    "mixup": 0.1,   # MixUp augmentation
    "copy_paste": 0.1,  # Copy-paste for rare classes
    "close_mosaic": 20,  # Close mosaic last 20 epochs
    # Loss settings
    "box": 7.5,
    "cls": 0.5,
    "dfl": 1.5,
    # Regularization
    "dropout": 0.1,  # Dropout for regularization
    # Reproducibility
    "seed": 42,           # Fixed seed for reproducibility
    "deterministic": True,  # Deterministic mode (may warn on ROCm)
    # Optimizer — explicit SGD (Ultralytics default for YOLO, was "auto")
    "optimizer": "SGD",
    "lr0": 0.01,          # Initial learning rate
    "lrf": 0.01,          # Final LR factor (cosine schedule: lr0 -> lr0*lrf)
    "momentum": 0.937,    # SGD momentum
    "weight_decay": 0.0005,
    "warmup_epochs": 3,
    "warmup_momentum": 0.8,
    "warmup_bias_lr": 0.1,
}


def train_model(key, config):
    """Train a single model."""
    print(f"\n{'=' * 70}")
    print(f"Training: {key}")
    print(f"  Model: {config['model']}")
    print(f"  Task: {config['task']}")
    print(f"  Data: {config['data']}")
    print(f"  Project: {config['project']}")
    print(f"{'=' * 70}")

    from ultralytics import YOLO

    # Load model
    model = YOLO(config["model"])

    # Train
    name = "run1"
    results = model.train(
        data=config["data"],
        project=config["project"],
        name=name,
        **TRAIN_ARGS,
    )

    # Get final metrics
    metrics = model.val()
    map50 = metrics.box.map50 if hasattr(metrics, 'box') else metrics.seg.map50

    print(f"\n  {key} training complete!")
    print(f"  mAP50: {map50:.4f}")

    return {"key": key, "mAP50": float(map50), "results": results}


def main():
    print("=" * 70)
    print("STEP 2b: Train all 4 YOLO26 models — v2 dataset (913 images, 5 classes)")
    print(f"Config: epochs={TRAIN_ARGS['epochs']}, imgsz={TRAIN_ARGS['imgsz']}, batch={TRAIN_ARGS['batch']}")
    print(f"GPU: AMD RX 7800 XT (ROCm, WSL2)")
    print("=" * 70)

    # Parse args
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs='+', default=["n_detect", "s_detect", "n_seg", "s_seg"],
                        choices=list(MODELS.keys()))
    args = parser.parse_args()

    results = {}
    for key in args.models:
        if key not in MODELS:
            print(f"Unknown model: {key}")
            continue
        try:
            result = train_model(key, MODELS[key])
            results[key] = result
        except Exception as e:
            print(f"\n  ERROR training {key}: {e}")
            import traceback
            traceback.print_exc()
            results[key] = {"key": key, "error": str(e)}

    # Summary
    print(f"\n{'=' * 70}")
    print("TRAINING SUMMARY")
    print(f"{'=' * 70}")
    for key, result in results.items():
        if "mAP50" in result:
            print(f"  {key}: mAP50={result['mAP50']:.4f}")
        elif "error" in result:
            print(f"  {key}: ERROR - {result['error']}")

    # Save summary
    summary_path = BASE / "reports" / "train_v2_summary.json"
    import json
    with open(summary_path, 'w') as f:
        json.dump({k: {kk: vv for kk, vv in v.items() if kk != 'results'}
                    for k, v in results.items()}, f, indent=2)
    print(f"\nSummary saved: {summary_path}")


if __name__ == "__main__":
    main()
