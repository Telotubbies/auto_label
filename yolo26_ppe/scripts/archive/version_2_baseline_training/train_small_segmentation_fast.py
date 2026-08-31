#!/usr/bin/env python3
"""Train YOLO26s segmentation v2 — FAST version.
Uses /tmp (WSL local) for dataset to avoid slow /mnt/e I/O.
batch=16, cache=True for RAM caching.
"""
import sys
from pathlib import Path

BASE = Path("/mnt/e/02_Projects/auto_label/yolo26_ppe")
DATA = "/tmp/yolo_seg_data/data.yaml"

TRAIN_ARGS = {
    "epochs": 300,
    "imgsz": 640,
    "batch": 16,
    "device": "0",
    "workers": 8,
    "patience": 50,
    "save": True,
    "save_period": 50,
    "cache": True,          # Cache images in RAM
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
    "box": 7.5,
    "cls": 0.5,
    "dfl": 1.5,
    "dropout": 0.1,
    "seed": 42,
    "deterministic": True,
    "optimizer": "SGD",
    "lr0": 0.01,
    "lrf": 0.01,
    "momentum": 0.937,
    "weight_decay": 0.0005,
    "warmup_epochs": 3,
    "warmup_momentum": 0.8,
    "warmup_bias_lr": 0.1,
}


def main():
    from ultralytics import YOLO
    import mlflow

    print("=" * 70)
    print("Training YOLO26s segmentation v2 (FAST: /tmp + cache=RAM)")
    print(f"  Data: {DATA}")
    print(f"  batch=16, cache=True, workers=8")
    print(f"  seed=42, optimizer=SGD")
    print("=" * 70)

    mlflow.set_tracking_uri(f"sqlite:///{BASE}/mlflow/mlflow.db")
    mlflow.set_experiment("yolo26_ppe_v2")

    with mlflow.start_run(run_name="yolo26s_seg_v2_train_fast") as run:
        mlflow.set_tag("task", "train")
        mlflow.set_tag("model", "yolo26s_seg_v2")
        mlflow.set_tag("model_size", "s")
        mlflow.set_tag("task_type", "segment")
        mlflow.set_tag("dataset", "yolo_segment_v2")
        mlflow.set_tag("gpu", "AMD RX 7800 XT ROCm")
        mlflow.set_tag("runtime", "WSL2")
        mlflow.set_tag("version", "fast_tmp_cache")

        for k, v in TRAIN_ARGS.items():
            mlflow.log_param(k, v)

        run_id = run.info.run_id
        print(f"  MLflow run: {run_id}")

        model = YOLO("yolo26s-seg.pt")
        results = model.train(
            data=DATA,
            project=str(BASE / "models" / "yolo26s_seg_v2"),
            name="run1",
            exist_ok=True,
            **TRAIN_ARGS,
        )

        metrics = model.val()
        box_map50 = metrics.box.map50
        seg_map50 = metrics.seg.map50 if hasattr(metrics, "seg") else 0

        mlflow.log_metric("final_box_mAP50", float(box_map50))
        mlflow.log_metric("final_mask_mAP50", float(seg_map50))

        print(f"\n  s_seg v2 training complete!")
        print(f"  Box mAP50:  {box_map50:.4f}")
        print(f"  Mask mAP50: {seg_map50:.4f}")


if __name__ == "__main__":
    main()
