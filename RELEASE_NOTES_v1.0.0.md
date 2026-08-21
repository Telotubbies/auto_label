# Release v1.0.0 — Auto-Label PPE Pipeline

## Overview

Automatic PPE (Personal Protective Equipment) image-labeling, training, evaluation, and production recommendation pipeline using **SAM 3.1** and **YOLO26**.

## What's included

### SAM 3.1 Auto-Labeling
- Text-prompted segmentation pipeline (`src/`)
- 6 PPE categories: person, helmet, boots, shoes, sandals, harness
- GPU-accelerated: GPU RLE encode, GPU mask IoU NMS, BF16 autocast
- Pipeline export (CPU export overlaps GPU inference → ~100% GPU util)
- COCO + YOLO + 9 other export formats
- Batch CLI with checkpoint/resume
- REST API (FastAPI)

### YOLO26 Training Pipeline
- 4 models trained: YOLO26n/s × detect/segmentation
- 5 final classes: person, helmet, boots, shoes, harness
- v4_recipe = canonical experiment
- Hyperparameter tuning (Ultralytics Tune)
- Stage 2 fine-tuning for segmentation models
- MLflow tracking (local, no auth)

### Evaluation
- Test set metrics: P, R, F1, mAP50, mAP50-95
- Per-class precision, recall, mAP50
- Segmentation mask metrics (Mask P/R/F1/mAP50/mAP50-95)
- Confusion matrices
- Failure case analysis + montages
- ONNX export + ONNX evaluation
- Robustness test (blurred images)
- SAM 3.1 benchmark

### Report
- 79-page LaTeX report (XeLaTeX, Thai)
- Vector PDF figures (training curves, confusion matrices, Pareto frontier)
- Per-class comparison
- ONNX vs PyTorch comparison
- Production recommendation

## Canonical Results (v4_recipe, test set)

| Model | Type | P | R | F1 | mAP50 | mAP50-95 | Size | Params |
|-------|------|---|---|----|----|---------|------|--------|
| YOLO26n | detect | 0.663 | 0.524 | 0.585 | 0.585 | 0.428 | 5.1 MB | 2.38M |
| YOLO26s | detect | 0.822 | 0.676 | 0.742 | 0.738 | 0.574 | 19.4 MB | 9.47M |
| YOLO26n | seg | 0.682 | 0.427 | 0.525 | 0.464 | 0.316 | 24.1 MB | 2.69M |
| YOLO26s | seg | 0.740 | 0.480 | 0.582 | 0.537 | 0.386 | 22.3 MB | 10.37M |

## Model Weights

All trained model weights are included via **Git LFS**:
- 4 pretrained base weights (yolo26n/s × detect/seg)
- 4 canonical v4_recipe models (best.pt + last.pt)
- Historical v1/v2/v3 models for reference
- ONNX exports for all 4 canonical models

## Environment

- **Platform**: WSL2 Ubuntu 24.04 (GPU only)
- **GPU**: AMD Radeon RX 7800 XT, 16 GB VRAM (ROCm)
- **Python venv**: `/opt/sam3_venv/bin/python`
- **MLflow**: local, port 5000, no auth
- **LaTeX**: XeLaTeX (Thai report)

## Quick Start

```bash
# Clone (with LFS)
git clone https://github.com/Telotubbies/auto_label.git
cd auto_label
git lfs pull

# SAM 3.1 auto-labeling (WSL2 + AMD GPU)
pip install torch torchvision --index-url https://download.pytorch.org/whl/rocm6.2
pip install -r requirements.txt
python src/batch_segment.py --fresh --input input/ --output output/

# YOLO26 training pipeline
cd yolo26_ppe
python scripts/01b_prepare_data_v2.py
python scripts/13_train_recipe_all.py
python scripts/14_eval_and_failures.py
python scripts/15_onnx_export_eval.py

# Compile report
cd report
xelatex -interaction=nonstopmode report.tex
```

## Documentation

- [README.md](README.md) — Project overview
- [AGENTS.md](AGENTS.md) — Full project structure
- [DEVELOPMENT.md](DEVELOPMENT.md) — Developer guide
- [yolo26_ppe/models/MODELS.md](yolo26_ppe/models/MODELS.md) — Model version guide

## Datasets

| Dataset | Source | Classes | Images |
|---------|--------|---------|--------|
| archive3 | Roboflow PPE Combined | 14 | ~44,000 |
| archive4 | Ultralytics Construction-PPE | 4 | 1,416 |
| blurred | Custom (Gaussian blur) | 5 | 48 |

**Note**: Datasets are NOT included in this release (too large). Download separately:
- archive3: [Roboflow Universe](https://universe.roboflow.com/roboflow-universe-projects/personal-protective-equipment-combined-model/dataset/4)
- archive4: `wget https://github.com/ultralytics/assets/releases/download/v0.0.0/construction-ppe.zip`
- SAM 3.1 checkpoint: Place at `models/sam3/sam3.1_multiplex.pt` (3.3 GB, download from Meta)

## License

- SAM 3.1 code (`sam3/`): Meta SAM License
- Project code (`src/`, `yolo26_ppe/`): Project-specific
- Datasets: See respective source licenses
