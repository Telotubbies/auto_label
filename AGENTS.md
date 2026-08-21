# Auto-Label PPE Pipeline — Project Structure

## Overview

Automatic PPE image-labeling, training, evaluation, and production recommendation pipeline using SAM 3.1 and YOLO26.

## Environment

- **Platform**: WSL2 Ubuntu 24.04 (GPU only, never CPU)
- **GPU**: AMD Radeon RX 7800 XT, 16 GB VRAM (ROCm)
- **Python venv**: `/opt/sam3_venv/bin/python`
- **MLflow**: local, port 5000, no auth
- **LaTeX**: XeLaTeX at `C:\texlive\2026\bin\windows\xelatex.exe`

## Directory Structure

```
E:\02_Projects\auto_label\
├── AGENTS.md                          # This file
├── README.md                          # Project overview
├── DEVELOPMENT.md                     # Dev setup guide
├── requirements.txt                   # Python dependencies
├── setup.py                           # Package setup
├── Dockerfile                         # Docker config
├── docker-compose.yml                 # Docker compose
├── .gitignore
├── .dockerignore
├── .coverage                          # Coverage data (kept)
├── eval_sam3_archive3_v2.py           # SAM 3.1 eval on archive3 (uses src/ pipeline)
│
├── config/                            # SAM 3.1 config
│   └── ppe.yaml                       # Main config: 6 categories, thresholds, resolution
│
├── src/                               # SAM 3.1 source code (DO NOT MODIFY)
│   ├── batch_segment.py               # Batch segmentation (optimized pipeline)
│   ├── config.py                      # Config loader
│   ├── exporters.py                   # Export formats (COCO, YOLO, VOC, etc.)
│   ├── inference.py                   # Core inference (build_model, segment_image)
│   ├── service.py                     # API service
│   └── tracker.py                     # MLflow experiment tracker
│
├── sam3/                              # SAM 3.1 model code
│   └── sam3/                          # Python package
│
├── sam3_venv/                         # Python venv (Windows side, not used)
│
├── models/
│   └── sam3/
│       └── sam3.1_multiplex.pt        # SAM 3.1 checkpoint (3.5 GB)
│
├── input/                             # Source datasets
│   ├── archive3_extract/              # Roboflow PPE Combined (14 classes, ~44k images)
│   ├── archive4_extract/              # Ultralytics Construction-PPE (4 classes, 1416 images)
│   ├── blurred/                       # Blurred images for robustness test (48 images)
│   ├── 2026-08-14_14-34-14/           # Custom input
│   └── fipflop/                       # Custom input
│
├── dataset_combined/                  # Combined dataset for training
│
├── output_2026/                       # SAM 3.1 output (COCO + viz + experiments.db)
├── output_blurred/                    # SAM 3.1 blurred output
├── runs/                              # Ultralytics auto-output (old val runs)
├── mlruns/                            # MLflow tracking (root-level experiments)
│
└── yolo26_ppe/                        # YOLO26 PPE project
    ├── README.md
    ├── requirements.txt
    │
    ├── configs/                       # Training configs
    │   ├── augmentation.yaml
    │   ├── mlflow.yaml
    │   └── train.yaml
    │
    ├── data/                          # YOLO datasets
    │   ├── yolo_detect/               # v1 detection dataset
    │   ├── yolo_detect_v2/            # v2 detection dataset
    │   ├── yolo_segment/              # v1 segmentation dataset
    │   └── yolo_segment_v2/           # v2 segmentation dataset
    │
    ├── docs/                          # Documentation
    │   ├── accuracy_techniques.md
    │   ├── CODE_REVIEW.md
    │   └── OPTIMIZER_EXPERIMENT_PLAN.md
    │
    ├── scripts/                       # Pipeline scripts (35 files)
    │   ├── 01_prepare_data.py         # Data preparation
    │   ├── 01b_prepare_data_v2.py     # v2 data prep
    │   ├── 02b_train_all_v2.py        # Train all v2
    │   ├── 03_train.py                # Training
    │   ├── 03_train_s_seg_v2.py       # s_seg v2 training
    │   ├── 03b_train_s_seg_fast.py    # Fast s_seg training
    │   ├── 04_evaluate.py             # Evaluation
    │   ├── 04_train_optimizer_experiment.py
    │   ├── 04b_run_v3_adamw_all.py
    │   ├── 05_eval_optimizer_experiment.py
    │   ├── 05_tune.py                 # Hyperparameter tuning
    │   ├── 06_compare.py              # Model comparison
    │   ├── 06_compare_optimizers.py
    │   ├── 07_export.py               # Model export
    │   ├── 07_final_eval.py           # Final evaluation
    │   ├── 08_export_onnx_all.py      # ONNX export
    │   ├── 08_merge_new_data.py       # Merge new data
    │   ├── 09_benchmark_sam3.py       # SAM 3.1 benchmark
    │   ├── 10_generate_final_visualizations.py
    │   ├── 11_error_analysis.py       # Error analysis
    │   ├── 12_finetune_stage2.py      # Stage 2 fine-tune
    │   ├── 13_train_recipe_all.py     # v4 recipe training
    │   ├── 14_eval_and_failures.py    # Eval + failure cases
    │   ├── 15_onnx_export_eval.py     # ONNX export + eval
    │   ├── 16_failure_montage.py      # Failure montages
    │   ├── 21_onnx_infer_blurred.py   # ONNX inference on blurred
    │   ├── 22_analyze_blurred.py      # Blurred analysis
    │   ├── 23_generate_pdf_figures.py # PDF figure generation
    │   ├── export_onnx.py             # ONNX export helper
    │   ├── filter_annotations.py      # Annotation filtering
    │   ├── generate_visualizations.py # Visualization generation
    │   ├── mlflow_env.sh              # MLflow env setup
    │   ├── run_all.sh                 # Run all pipeline
    │   ├── run_tune_eval_report.sh    # Tune + eval + report
    │   ├── start_mlflow.sh            # Start MLflow server
    │   └── start_mlflow_service.sh    # Start MLflow service
    │
    ├── models/                        # Trained models (see models/MODELS.md)
    │   ├── pretrained/                # Base weights (yolo26n/s .pt)
    │   ├── MODELS.md                  # Version guide
    │   ├── yolo26n_detect_v1/         # v1 baseline (old)
    │   ├── yolo26n_detect_v2/         # v2 (old)
    │   ├── yolo26n_detect_v3_adamw/   # v3 AdamW (old)
    │   ├── yolo26n_detect_v4_recipe/  # v4 (CANONICAL)
    │   ├── yolo26s_detect_v1/         # v1 baseline (old)
    │   ├── yolo26s_detect_v2/         # v2 (old)
    │   ├── yolo26s_detect_v4_recipe/  # v4 (CANONICAL)
    │   ├── yolo26n_seg_v1/            # v1 baseline (old)
    │   ├── yolo26n_seg_v2/            # v2 (old)
    │   ├── yolo26n_seg_v4_recipe/     # v4 (CANONICAL)
    │   ├── yolo26s_seg_v1/            # v1 baseline (old)
    │   ├── yolo26s_seg_v2/            # v2 (old)
    │   └── yolo26s_seg_v4_recipe/     # v4 (CANONICAL)
    │
    ├── eval_results/                  # Evaluation results
    │   ├── sam3_archive3_v2/          # SAM 3.1 eval on archive3
    │   └── v4_recipe/                 # v4 canonical results
    │       ├── all_metrics.json       # All 4 models metrics
    │       ├── all_failures.json      # Failure cases
    │       ├── n_detect_metrics.json
    │       ├── s_detect_metrics.json
    │       ├── n_seg_metrics.json
    │       ├── s_seg_metrics.json
    │       ├── failure_cases/         # Failure case images
    │       ├── top10/                 # Top 10 failures
    │       ├── n_detect/              # Per-model eval plots
    │       ├── s_detect/
    │       ├── n_seg/
    │       ├── s_seg/
    │       └── onnx/                  # ONNX comparison
    │           ├── all_comparison.json
    │           ├── n_detect_comparison.json
    │           ├── s_detect_comparison.json
    │           ├── n_seg_comparison.json
    │           └── s_seg_comparison.json
    │
    ├── onnx_exports/                  # ONNX exported models
    │   └── v4_recipe/
    │
    ├── onnx_inference/                # ONNX inference outputs
    │   └── blurred/                   # Blurred inference (n_detect, s_detect, n_seg, s_seg)
    │
    ├── report/                        # LaTeX report
    │   ├── report.tex                 # Main report (XeLaTeX)
    │   ├── report.pdf                 # Compiled PDF
    │   ├── PLAN.md                    # Report plan
    │   ├── final_eval_results.json
    │   ├── onnx_export_results.json
    │   ├── sam3_benchmark_results.json
    │   ├── figures/                   # Vector PDF figures + PNG photos
    │   │   ├── blurred/               # Blurred montages + stats
    │   │   ├── training_curves_*.pdf  # 4 models
    │   │   ├── confusion_matrix_*.pdf # 4 models
    │   │   ├── pareto_frontier.pdf
    │   │   ├── perclass_map50.pdf
    │   │   ├── size_vs_accuracy.pdf
    │   │   ├── overall_metrics.pdf
    │   │   ├── latency_pt_vs_onnx.pdf
    │   │   ├── blurred_class_dist.pdf
    │   │   └── blurred_latency.pdf
    │   └── fonts/                     # Thai fonts
    │
    ├── reports/                       # JSON/CSV reports
    │   ├── comparison_report.md
    │   ├── eval_all.json
    │   ├── model_comparison.csv
    │   ├── model_comparison.json
    │   ├── train_v2_summary.json
    │   └── tune_*.json
    │
    ├── logs/                          # All log files
    │   ├── logs_*.log                 # Training/eval/tune logs
    │   ├── mlflow_server.log
    │   ├── compile*.log               # LaTeX compile logs
    │   ├── run_2026.log
    │   └── run_blurred.log
    │
    ├── mlflow/                        # MLflow config
    ├── mlruns/                        # MLflow tracking (yolo26_ppe experiments)
    ├── runs/                          # Ultralytics auto-output (old)
    └── tests/                         # Tests
        ├── conftest.py
        ├── test_dataset_artifacts.py
        └── test_split_integrity.py
```

## Canonical Experiment: v4_recipe

The **v4_recipe** is the canonical experiment. All report metrics must come from:
- `yolo26_ppe/eval_results/v4_recipe/all_metrics.json`
- `yolo26_ppe/eval_results/v4_recipe/onnx/all_comparison.json`

Older runs (v1, v2, v3) are kept for reference but should NOT be used in the report.

## Class Order (5 classes)

```
0: person
1: helmet
2: boots
3: shoes
4: harness
```

## Key Commands

### Run SAM 3.1 eval on archive3
```bash
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/e/02_Projects/auto_label && /opt/sam3_venv/bin/python -u eval_sam3_archive3_v2.py --sample 200"
```

### Compile report
```bash
cd E:\02_Projects\auto_label\yolo26_ppe\report
C:\texlive\2026\bin\windows\xelatex.exe -interaction=nonstopmode report.tex
```

### Start MLflow
```bash
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/e/02_Projects/auto_label/yolo26_ppe && bash scripts/start_mlflow.sh"
```
