# yolo26_ppe/configs — Configuration

YAML config สำหรับ training, augmentation, และ MLflow

## ไฟล์

| ไฟล์ | ทำอะไร |
|------|--------|
| `production_train.yaml` | config หลัก — epochs, lr, optimizer, loss weights, 4 โมเดล |
| `production_augmentation.yaml` | augmentation recipe (HSV, mosaic, mixup, erasing) |
| `mlflow.yaml` | MLflow tracking server config |

## production_train.yaml

ส่วนสำคัญ:

```yaml
epochs: 150          # รอบ training
imgsz: 640           # ขนาดภาพ input
batch: 16            # batch size
patience: 30         # early stopping
freeze: 10           # freeze backbone (dataset เล็ก)
cls_pw: 0.5          # class weight (imbalance 10.5:1)

# Optimizer (MuSGD)
lr0: 0.01, lrf: 0.01, momentum: 0.937, weight_decay: 0.0005

# Focal Loss
fl_gamma: 1.5        # ช่วยกับ class imbalance + hard examples

# Gradient accumulation
nbs: 64              # effective batch = 64 (batch=16 → 4x accumulation)

# 4 โมเดล
models:
  nano_detection:    yolo26n.pt, detect
  small_detection:   yolo26s.pt, detect
  nano_segmentation: yolo26n-seg.pt, segment
  small_segmentation: yolo26s-seg.pt, segment
```

## production_augmentation.yaml

```yaml
# Color (lighting robustness)
hsv_h: 0.02, hsv_s: 0.7, hsv_v: 0.5

# Geometric
degrees: 5, translate: 0.15, scale: 0.6, shear: 2.0
fliplr: 0.5, flipud: 0.0   # PPE ไม่ควรกลับหัว

# Mosaic + mixing
mosaic: 0.8, mixup: 0.1, copy_paste: 0.15, close_mosaic: 10

# Occlusion
erasing: 0.3
```

อ้างอิง: https://docs.ultralytics.com/guides/yolo26-training-recipe/

## mlflow.yaml

```yaml
tracking_uri: sqlite:///yolo26_ppe/artifacts/mlflow/backend/mlflow.db
artifact_root: yolo26_ppe/artifacts/mlflow
experiment_name: yolo26_ppe
host: 0.0.0.0, port: 5000
```

Ultralytics auto-log: lr0, batch, epochs, mAP50, mAP50-95, P, R, loss, best.pt, confusion_matrix

## ข้อควรระวัง

- ถ้าเปลี่ยน config ต้องรัน test และ validation ก่อนใช้ production
- `cls_pw` และ `fl_gamma` ปรับตาม class imbalance — ดู `data/dataset_analysis_reports/`
- ถ้า GPU น้อย VRAM ลด `batch` หรือเพิ่ม `nbs` (accumulation)
- อย่าเปลี่ยน `imgsz` โดยไม่ทดสอบ — กระทบ small object detection (boots/shoes)
