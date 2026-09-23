# YOLO26 PPE

Training, evaluation, ONNX export, robustness testing, and reporting for four PPE classes (v3 dataset):

`person`, `helmet`, `closed footwear`, `harness`

## Start here

| Need | Location |
|---|---|
| Production models | `models/production/` |
| Model selection guide | `models/README.md` |
| Production training config | `configs/production_train.yaml` |
| Current pipeline | `scripts/pipeline/` |
| Test-set metrics | `artifacts/evaluation/yolo/production_v4_recipe/all_metrics.json` |
| Production ONNX models | `artifacts/onnx_models/production/` |
| Final PDF report | `reports/final/report.pdf` |
| Historical experiments | `models/archive/` and `scripts/archive/` |

## Production models

Use only models under `models/production` for deployment, evaluation, export, or reporting.

| Directory | Meaning | Production weight |
|---|---|---|
| `small_detection` | Balanced bounding-box detector (mAP50 0.670) | `models/production/small_detection/stage_2_final_fine_tuning/weights/best.pt` |
| `medium_detection` | Highest-accuracy bounding-box detector (mAP50 0.693) | `models/production/medium_detection/stage_2_final_fine_tuning/weights/best.pt` |
| `small_segmentation` | Faster instance-segmentation model | `models/production/small_segmentation/stage_2_final_fine_tuning/weights/best.pt` |
| `medium_segmentation` | Highest-accuracy instance-segmentation model | `models/production/medium_segmentation/stage_2_final_fine_tuning/weights/best.pt` |

Each model has two training stages:

- `stage_1_initial_training`: initial 150-epoch training from pretrained weights
- `stage_2_final_fine_tuning`: final 50-epoch fine-tuning from stage 1; use its `best.pt`

The `production` models are the former **v4_recipe** experiment. Versions 1–3 are historical experiments retained only for reproducibility.

## Current pipeline

Run scripts in numeric order:

```text
scripts/pipeline/
├── 01_prepare_dataset.py
├── 02_train_models.py
├── 03_evaluate_models.py
├── 04_export_and_evaluate_onnx.py
├── 05_generate_failure_montage.py
├── 06_run_blur_robustness.py
├── 07_analyze_blur_robustness.py
└── 08_generate_report_figures.py
```

Other groups:

- `scripts/tools/`: standalone utilities
- `scripts/services/`: MLflow foreground/background management
- `scripts/archive/`: historical pipelines; do not use for the production workflow

## Directory map

```text
yolo26_ppe/
├── configs/                         # Production and MLflow configuration
├── data/                            # Prepared training datasets
├── models/
│   ├── production/                  # Models currently used
│   ├── pretrained/                  # Upstream starting weights
│   └── archive/                     # Historical model versions
├── artifacts/
│   ├── evaluation/                  # SAM and YOLO evaluation results
│   ├── logs/                        # Training, tuning, report, and service logs
│   ├── mlflow/                      # MLflow database and historical runs
│   ├── onnx_models/                 # Exported ONNX models
│   ├── onnx_inference_results/      # Predictions produced by ONNX models
│   └── ultralytics_training_runs/   # Raw Ultralytics outputs
├── reports/
│   ├── final/                       # Final PDF
│   ├── source/                      # LaTeX source, figures, and fonts
│   ├── inputs/                      # JSON inputs used by the report
│   ├── metrics/                     # JSON/CSV/Markdown summaries
│   └── build/                       # XeLaTeX generated files and logs
├── scripts/
│   ├── pipeline/                    # Current production pipeline
│   ├── tools/                       # Standalone utilities
│   ├── services/                    # MLflow management
│   └── archive/                     # Historical scripts
├── docs/                            # Engineering notes and model documentation
├── tests/
└── .cache/                          # Test cache and coverage data
```

## Dataset names

| Directory | Meaning |
|---|---|
| `combined_coco_dataset_version_3` | Merged four-class COCO source dataset (current) |
| `yolo_detection_dataset_version_3` | Current four-class detection dataset |
| `yolo_segmentation_dataset_version_3` | Current four-class segmentation dataset |
| `dataset_analysis_reports` | Dataset distribution and integrity analysis |

## Historical model versions

| Directory | Meaning | Use in production? |
|---|---|---|
| `models/archive/version_1_initial_baseline` | First baseline and tuning trials | No |
| `models/archive/version_2_improved_baseline` | Improved data preparation and longer training | No |
| `models/archive/version_2_5class` | Former production cohort (v2 five-class, nano/small) | No — different class schema |
| `models/archive/version_3_adamw_experiment` | Incomplete AdamW comparison | No |

Report metrics must come from `artifacts/evaluation/yolo/production_v4_recipe/`.
