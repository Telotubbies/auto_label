# YOLO26 PPE Training Pipeline

Train YOLO26 (n + s) for PPE detection and segmentation, compare with SAM 3.1.

## Models

| Model | Task | Weights | Params |
|-------|------|---------|--------|
| yolo26n_detect | Detection (bbox) | yolo26n.pt | 2.6M |
| yolo26s_detect | Detection (bbox) | yolo26s.pt | 10.0M |
| yolo26n_seg | Instance Segmentation | yolo26n-seg.pt | 3.1M |
| yolo26s_seg | Instance Segmentation | yolo26s-seg.pt | 11.5M |

## Pipeline

```
01_prepare_data.py   COCO → YOLO + balance + split 70/20/10
03_train.py          Train 1 or all 4 models (MLflow tracked)
04_evaluate.py       Eval on test set + confusion matrix
05_tune.py           Hyperparameter tuning (if results poor)
07_export.py         Export ONNX + TorchScript for production
06_compare.py        Compare 4 YOLO + SAM 3.1 → report
run_all.sh           Run entire pipeline
```

## Quick Start

```bash
# WSL2 + AMD GPU
export HSA_ENABLE_DXG_DETECTION=1
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1
cd /mnt/e/02_Projects/auto_label

# Option 1: Run everything
bash yolo26_ppe/scripts/run_all.sh

# Option 2: Step by step
# Start MLflow server (terminal 1)
bash yolo26_ppe/scripts/start_mlflow.sh

# Train (terminal 2)
/opt/sam3_venv/bin/python yolo26_ppe/scripts/03_train.py --all

# Evaluate
/opt/sam3_venv/bin/python yolo26_ppe/scripts/04_evaluate.py --all

# Compare + report
/opt/sam3_venv/bin/python yolo26_ppe/scripts/06_compare.py
```

## Data

- **Source**: `dataset_combined/` (480 images, 8,279 annotations, COCO RLE)
- **Split**: 335 train / 95 val / 50 test (stratified by source)
- **Balance**: Oversampling sandals (6→200) and harness (86→200)
- **Imbalance**: 673:1 → 10.5:1 after balance

## Augmentation (medium-heavy)

| Augment | Value | Purpose |
|---------|-------|---------|
| hsv_h/s/v | 0.02/0.7/0.5 | Lighting robustness |
| degrees | 5.0 | Camera tilt |
| scale | 0.6 | Object size variation |
| mosaic | 0.8 | 4-image mix (regularization) |
| copy_paste | 0.15 | Helps rare classes |
| erasing | 0.3 | Occlusion robustness |
| close_mosaic | 10 | Stabilize last 10 epochs |

## MLflow

- **UI**: http://localhost:5000
- **Backend**: SQLite (`yolo26_ppe/mlflow/mlflow.db`)
- **Artifacts**: `yolo26_ppe/mlflow/mlruns/`
- **Auto-logged**: params, metrics (per epoch), artifacts (best.pt, plots)

## Output

```
yolo26_ppe/
├── data/
│   ├── yolo_detect/        YOLO bbox format
│   ├── yolo_segment/       YOLO polygon format
│   └── analysis/           Class distribution + imbalance
├── models/
│   ├── yolo26n_detect/     best.pt + eval + export
│   ├── yolo26s_detect/
│   ├── yolo26n_seg/
│   └── yolo26s_seg/
├── mlflow/                 Tracking server data
├── reports/
│   ├── eval_all.json       All eval results
│   └── comparison_report.md  YOLO vs SAM 3.1
├── scripts/                All pipeline scripts
└── configs/                train.yaml + augmentation.yaml + mlflow.yaml
```
