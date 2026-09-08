# yolo26_ppe/artifacts — Experiment Outputs

Stores outputs from training, evaluation, ONNX export, MLflow, and robustness testing.

## Structure

```text
artifacts/
├── evaluation/                 # Evaluation results
│   ├── yolo/
│   │   └── production_v4_recipe/   # ← Official results (use this only)
│   └── sam3/
│       ├── archive3_v1/
│       └── archive3_v2/
├── logs/                       # Training/tuning/report/service logs
├── mlflow/                     # MLflow database + runs
│   ├── backend/                # Current MLflow (mlflow.db + mlruns/)
│   ├── legacy_root_runs/       # Legacy runs (root level)
│   └── legacy_yolo_runs/       # Legacy runs (yolo project)
├── onnx_models/
│   └── production/             # ONNX exports of 4 production models
├── onnx_inference_results/
│   └── blur_robustness/        # Blurred-image inference results, per model
└── ultralytics_training_runs/ # Raw Ultralytics output (val, train batch images)
    ├── detect/
    └── segment/
```

## evaluation/

| Folder | Description | Current? |
| ------ | ----------- | -------- |
| `yolo/production_v4_recipe/` | Evaluation results for 4 production models | **Yes** — official |
| `sam3/archive3_v1/` | SAM 3.1 benchmark run 1 | Reference |
| `sam3/archive3_v2/` | SAM 3.1 benchmark run 2 | Reference |

Key files in `production_v4_recipe/`:

- `all_metrics.json` — Aggregated metrics for all models (P/R/F1/mAP50/mAP50-95)
- Per-class metrics, confusion matrix

## mlflow/

- `backend/mlflow.db` — Current SQLite database
- `backend/mlruns/` — Artifacts for current runs
- `legacy_*` — Migrated from previous location, retained for reference

See config: `../configs/mlflow.yaml`

## onnx_models/production/

ONNX exports of the 4 production models, used for deployment.

## onnx_inference_results/blur_robustness/

ONNX inference results on blurred images, per model:

- `nano_detection/`, `nano_segmentation/`
- `small_detection/`, `small_segmentation/`

## ultralytics_training_runs/

Raw output from Ultralytics during training — val images, train batch previews. Not used in production but retained for inspection.

## Cautions

- This folder is large — check `.gitignore` and Git LFS before committing
- Official results for the report come from `evaluation/yolo/production_v4_recipe/` only
- Do not delete `legacy_*` if historical reference is still needed
- If re-running training, previous results may be overwritten — back up if necessary
