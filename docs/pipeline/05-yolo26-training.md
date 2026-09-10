---
title: "YOLO26 Training"
category: "Pipeline"
order: 2
status: "Verified"
---

# YOLO26 Training (Requirement 2)

> Train 4 YOLO26 models to compare the accuracy–efficiency trade-off for PPE detection
>
> **Status**: Verified — checked against `yolo26_ppe/`, `yolo26_ppe/reports/final/report.pdf`, `yolo26_ppe/configs/`

---

## Objective

Compare the performance and computational efficiency of 4 YOLO26 models:

| Model | Task | Scale |
|-------|------|-------|
| YOLO26n | Detection | Nano |
| YOLO26s | Detection | Small |
| YOLO26n-seg | Segmentation | Nano |
| YOLO26s-seg | Segmentation | Small |

> Source: `yolo26_ppe/reports/source/report.tex:634-650`

---

## Training Pipeline

```plantuml {align="center"}
@startuml
!theme plain
skinparam linetype ortho
skinparam backgroundColor #FEFEFE
skinparam ActivityBackgroundColor #E8F0FE
skinparam ActivityBorderColor #4285F4

start
:Input: Ground Truth from SAM 3.1\n(data/sam_outputs_ground_truth/);
:Convert COCO → YOLO format;
:Dataset balancing\n(oversampling sandals, harness);
:Split train/val/test\n(335/95/50);

fork
  :Train YOLO26n detect\n300 epochs;
fork again
  :Train YOLO26s detect\n300 epochs;
fork again
  :Train YOLO26n-seg\n150 + 50 epochs (2 stage);
fork again
  :Train YOLO26s-seg\n150 + 50 epochs (2 stage);
end fork

:Evaluate on test set;
:Hyperparameter tuning\n(3 trials × 4 models);
:Export ONNX;
:Generate report.pdf;
stop

@enduml
```

---

## Training Configuration

| Parameter | Value |
|-----------|-------|
| Epochs | 300 (detect), 150+50 (seg — 2 stage) |
| Batch size | 8 (detect), 4 (seg) |
| Image size | 640 px |
| Optimizer | SGD |
| Learning rate (lr0) | 0.01 |
| Final LR factor (lrf) | 0.01 (cosine decay) |
| Momentum | 0.937 |
| Weight decay | 0.0005 |
| Warmup epochs | 3 |
| Patience | 50 |
| Freeze | 10 (backbone frozen) |
| Hardware | AMD RX 7800 XT (ROCm, WSL2) |
| Random seed | 42 |

> Source: `yolo26_ppe/reports/source/report.tex:652-677`, `yolo26_ppe/configs/production_train.yaml`

---

## Dataset

### Size

| Split | Image count |
|-------|---------|
| Train | 335 |
| Validation | 95 |
| Test | 50 |
| **Total** | **480** |

> Source: `yolo26_ppe/reports/metrics/comparison_report.md:3`

### Class Distribution

| Class | Original Count | Status |
|-------|---------------|-------|
| person | 2271 | Adequate |
| helmet | 2693 | Adequate |
| boots | 802 | Adequate |
| shoes | 2407 | Adequate |
| sandals | 4 | Severely underrepresented |
| harness | 102 | Underrepresented |

### Class Balancing

- **Imbalance ratio (before)**: 2693:4 = 673:1
- **Imbalance ratio (after)**: 3003:56 = 53.6:1
- **Oversampling**: sandals +30, harness +114

> Source: `yolo26_ppe/reports/metrics/comparison_report.md:64-66`

---

## Dataset Versions

```plantuml {align="center"}
@startuml
!theme plain
skinparam linetype ortho
skinparam backgroundColor #FEFEFE

package "yolo26_ppe/data/" {
  file "yolo_detection_dataset_version_1" as v1d
  file "yolo_detection_dataset_version_2" as v2d
  file "yolo_segmentation_dataset_version_1" as v1s
  file "yolo_segmentation_dataset_version_2" as v2s
  file "combined_coco_dataset_version_2" as v2c
}

v1d --> v2d : improved split
v1s --> v2s : improved split
v2c --> v2d : convert
v2c --> v2s : convert

@enduml
```

> Source: `yolo26_ppe/data/` directory listing

---

## MLflow Integration

YOLO26 training uses **MLflow** for experiment tracking (unlike SAM 3.1 which uses SQLite):

@import "../../yolo26_ppe/configs/mlflow.yaml" {title="mlflow.yaml"}

> MLflow tracking URI and configuration are in `yolo26_ppe/configs/mlflow.yaml`

---

## Training Config

@import "../../yolo26_ppe/configs/production_train.yaml" {title="production_train.yaml"}

---

## Augmentation Config

@import "../../yolo26_ppe/configs/production_augmentation.yaml" {title="production_augmentation.yaml"}

---

## Hyperparameter Tuning

| Model | Baseline mAP50 | Best Trial mAP50 | Improved? |
|-------|---------------|-----------------|-----------|
| n_detect | 0.4623 | 0.3950 | ❌ No |
| s_detect | 0.5551 | 0.4937 | ❌ No |
| n_seg | 0.4158 | 0.3822 | ❌ No |
| s_seg | 0.5538 | 0.4753 | ❌ No |

> **Summary**: 50-epoch tuning trials could not match the 150-epoch baseline — all baseline weights were retained
>
> Source: `yolo26_ppe/reports/metrics/comparison_report.md:119-174`

### Tuned Parameters

- `lr0`, `imgsz`, `cls_pw`, `mosaic`, `mixup`, `copy_paste`, `scale`, `close_mosaic`

---

## References

- `yolo26_ppe/reports/final/report.pdf` — full report
- `yolo26_ppe/reports/source/report.tex:628-747` — RQ2 chapter
- `yolo26_ppe/reports/inputs/final_eval_results.json` — metrics
- `yolo26_ppe/reports/metrics/comparison_report.md` — comparison summary
- `yolo26_ppe/configs/production_train.yaml` — training config
- `yolo26_ppe/configs/production_augmentation.yaml` — augmentation config
- `yolo26_ppe/configs/mlflow.yaml` — MLflow config
