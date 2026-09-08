# yolo26_ppe/scripts — Pipeline and Utilities

Scripts for training, evaluating, exporting, and reporting YOLO26 PPE.

## Structure

```text
scripts/
├── pipeline/      # Current pipeline — run in numeric order
├── tools/         # Standalone utilities (not in pipeline order)
├── services/      # MLflow management (foreground/background)
└── archive/       # Legacy pipelines and experiments — do not use for production
```

## pipeline/ — Current Pipeline

Run in numeric order by filename:

| Step | File | Purpose |
| ---- | ---- | ------- |
| 01 | `01_prepare_dataset.py` | Convert COCO → YOLO format, split train/val/test, oversampling |
| 02 | `02_train_models.py` | Train 4 models (nano/small × detect/segment) |
| 03 | `03_evaluate_models.py` | Measure P/R/F1/mAP50/mAP50-95, confusion matrix |
| 04 | `04_export_and_evaluate_onnx.py` | Export ONNX + evaluate against PyTorch |
| 05 | `05_generate_failure_montage.py` | Generate montage of failure cases |
| 06 | `06_run_blur_robustness.py` | Test robustness to blurred images |
| 07 | `07_analyze_blur_robustness.py` | Analyze blur robustness results |
| 08 | `08_generate_report_figures.py` | Generate PDF/PNG charts for the report |
| 09 | `09_predict_raw_images.py` | Inference with production models on raw images |

Or run via the main CLI: `../../auto_label.sh --yolo --model <model_name>`

## tools/ — Standalone Utilities

| File | Purpose |
| ---- | ------- |
| `export_legacy_models.py` | Export legacy models in archive to ONNX |
| `filter_annotations.py` | Filter annotations by criteria |
| `generate_visualizations.py` | Generate visualizations outside the pipeline |

## services/ — MLflow

| File | Purpose |
| ---- | ------- |
| `manage_mlflow_background.sh` | Start/stop MLflow in the background |
| `run_mlflow_foreground.sh` | Run MLflow in the foreground |
| `mlflow_env.sh` | Set up environment for MLflow |

MLflow config is at `../configs/mlflow.yaml`

## archive/ — Experiment History

**Do not use for production** — retained for reproducibility only.

| Folder | Description |
| ------ | ----------- |
| `version_1_baseline_pipeline/` | First pipeline (01-08 + shell scripts) |
| `version_2_baseline_training/` | v2 training |
| `dataset_migration/` | Dataset migration scripts |
| `historical_analysis/` | SAM3 benchmark, error analysis, visualization |
| `legacy_stage_2_fine_tuning/` | Legacy stage 2 fine-tuning |
| `optimizer_comparison_experiments/` | Optimizer comparison experiments (AdamW) |

## Cautions

- Files in `pipeline/` start with numbers — to load as a module, use `importlib.util` (names starting with digits cannot be imported directly)
- If adding a new pipeline step, use the next number (e.g., `10_...`)
- Do not delete files in `archive/` without team confirmation
- Official evaluation results come from `production_v4_recipe` only
