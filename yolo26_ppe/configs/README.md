# yolo26_ppe/configs — Configuration

YAML configs for training, augmentation, and MLflow.

## Files

| File | Purpose |
| ---- | ------- |
| `production_train.yaml` | Main config — epochs, lr, optimizer, loss weights |
| `production_augmentation.yaml` | Augmentation recipe (HSV, mosaic, mixup, erasing) |
| `mlflow.yaml` | MLflow tracking server config |

## production_train.yaml

Key sections:

```yaml
epochs: 150          # Training epochs
imgsz: 640           # Input image size
batch: 16            # Batch size
patience: 30         # Early stopping
freeze: 10           # Freeze backbone (small dataset)
cls_pw: 0.5          # Class weight (imbalance 10.5:1)

# Optimizer (MuSGD)
lr0: 0.01, lrf: 0.01, momentum: 0.937, weight_decay: 0.0005

# Focal Loss
fl_gamma: 1.5        # Helps with class imbalance + hard examples

# Gradient accumulation
nbs: 64              # Effective batch = 64 (batch=16 → 4x accumulation)

# 4 production models (v3 dataset, 4 classes) — defined in scripts/pipeline/02_train_models.py
models:
  small_detection:     yolo26s.pt, detect
  small_segmentation:  yolo26s-seg.pt, segment
  medium_detection:    yolo26m.pt, detect
  medium_segmentation: yolo26m-seg.pt, segment
```

## production_augmentation.yaml

```yaml
# Color (lighting robustness)
hsv_h: 0.02, hsv_s: 0.7, hsv_v: 0.5

# Geometric
degrees: 5, translate: 0.15, scale: 0.6, shear: 2.0
fliplr: 0.5, flipud: 0.0   # PPE should not be flipped upside down

# Mosaic + mixing
mosaic: 0.8, mixup: 0.1, copy_paste: 0.15, close_mosaic: 10

# Occlusion
erasing: 0.3
```

Reference: https://docs.ultralytics.com/guides/yolo26-training-recipe/

## mlflow.yaml

```yaml
tracking_uri: sqlite:///yolo26_ppe/artifacts/mlflow/backend/mlflow.db
artifact_root: yolo26_ppe/artifacts/mlflow
experiment_name: yolo26_ppe
host: 127.0.0.1, port: 5000
```

Ultralytics auto-log: lr0, batch, epochs, mAP50, mAP50-95, P, R, loss, best.pt, confusion_matrix

## Cautions

- If changing config, run tests and validation before using in production
- `cls_pw` and `fl_gamma` are tuned for class imbalance (harness is the rare class in v3)
- If GPU has low VRAM, reduce `batch` or increase `nbs` (accumulation)
- Do not change `imgsz` without testing — impacts small object detection (closed footwear, harness)
