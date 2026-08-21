# Auto-Label PPE Pipeline

Automatic PPE image-labeling, training, evaluation, and production recommendation pipeline using **SAM 3.1** and **YOLO26**.

> **For developers**: read [DEVELOPMENT.md](DEVELOPMENT.md) and [AGENTS.md](AGENTS.md) first — fast-track guide to the codebase and project structure.

## What it does

1. **Auto-label** raw images with SAM 3.1 (text-prompted segmentation) → COCO/YOLO labels
2. **Train** YOLO26 (n/s × detect/seg = 4 models) using SAM-generated labels
3. **Evaluate** on test set (P, R, F1, mAP50, mAP50-95, per-class, confusion matrix)
4. **Tune** hyperparameters if results are poor
5. **Export** to ONNX for deployment
6. **Benchmark** robustness (blurred images) and ONNX inference
7. **Report** comparison of all 4 YOLO26 variants vs SAM 3.1 with production recommendations

## Pipeline overview

```
SAM 3.1 auto-label → YOLO labels → Train 4 models → Eval → Tune → Export ONNX → Benchmark → Report
```

## Project structure

```
auto_label/
├── src/                    # SAM 3.1 inference pipeline (DO NOT MODIFY)
├── sam3/                   # SAM 3.1 model code (Meta license)
├── config/ppe.yaml         # SAM 3.1 config (6 categories, thresholds)
├── input/                  # Source datasets (archive3, archive4, blurred)
├── yolo26_ppe/             # YOLO26 training + eval + report
│   ├── scripts/            # Pipeline scripts (01-23)
│   ├── models/             # Trained models (see models/MODELS.md)
│   ├── eval_results/       # Evaluation results (v4_recipe = canonical)
│   ├── report/             # LaTeX report (report.tex → report.pdf)
│   ├── data/               # YOLO datasets
│   └── configs/            # Training configs
└── eval_sam3_archive3_v2.py  # SAM 3.1 eval on archive3
```

See [AGENTS.md](AGENTS.md) for full directory structure and [yolo26_ppe/models/MODELS.md](yolo26_ppe/models/MODELS.md) for model version guide.

## Canonical experiment: v4_recipe

All report metrics come from `yolo26_ppe/eval_results/v4_recipe/`.

| Model | Type | mAP50 | mAP50-95 | Size | Params |
|-------|------|-------|----------|------|--------|
| YOLO26n | detect | 0.585 | 0.428 | 5.1 MB | 2.38M |
| YOLO26s | detect | 0.738 | 0.574 | 19.4 MB | 9.47M |
| YOLO26n | seg | 0.464 | 0.316 | 24.1 MB | 2.69M |
| YOLO26s | seg | 0.537 | 0.386 | 22.3 MB | 10.37M |

## Classes (5)

```
0: person
1: helmet
2: boots
3: shoes
4: harness
```

## Environment

- **Platform**: WSL2 Ubuntu 24.04 (GPU only, never CPU)
- **GPU**: AMD Radeon RX 7800 XT, 16 GB VRAM (ROCm)
- **Python venv**: `/opt/sam3_venv/bin/python`
- **MLflow**: local, port 5000, no auth
- **LaTeX**: XeLaTeX (Thai report)

## Quick Start (WSL2 + AMD GPU)

### SAM 3.1 auto-labeling

```bash
# Install PyTorch ROCm
pip install torch torchvision --index-url https://download.pytorch.org/whl/rocm6.2
pip install -r requirements.txt

# Run batch segmentation
export HSA_ENABLE_DXG_DETECTION=1
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1
python src/batch_segment.py --fresh --input input/ --output output/
```

### YOLO26 training pipeline

```bash
cd yolo26_ppe

# 1. Prepare data from SAM labels
python scripts/01b_prepare_data_v2.py

# 2. Train all 4 models (v4 recipe)
python scripts/13_train_recipe_all.py

# 3. Evaluate
python scripts/14_eval_and_failures.py

# 4. Export ONNX
python scripts/15_onnx_export_eval.py

# 5. Benchmark blurred robustness
python scripts/21_onnx_infer_blurred.py
python scripts/22_analyze_blurred.py

# 6. Generate report figures
python scripts/23_generate_pdf_figures.py
```

### SAM 3.1 evaluation on archive3

```bash
python eval_sam3_archive3_v2.py --sample 200
```

### Compile report

```bash
cd yolo26_ppe/report
xelatex -interaction=nonstopmode report.tex
```

## SAM 3.1 Performance (AMD RX 7800 XT, WSL2, ROCm)

| Metric | Value |
|--------|-------|
| Model inference | ~0.65s/image |
| Total (inference + export) | ~0.7s/image |
| GPU utilization | ~100% |
| 432 images | ~5 minutes |

## Configuration

Edit `config/ppe.yaml` for SAM 3.1:

```yaml
categories:
- id: 1
  name: person
  prompt: person
  threshold: 0.7
# ... 6 categories total

inference:
  confidence_threshold: 0.25
  resolution: 1008
  device: auto
  gpu_ops: true
  pipeline_export: true
```

### Default categories

| ID | Name | Prompt | Threshold |
|----|------|--------|-----------|
| 1 | person | person | 0.70 |
| 2 | helmet | helmet | 0.25 |
| 3 | boots | boots | 0.25 |
| 4 | shoes | shoes | 0.25 |
| 5 | sandals | flip-flops | 0.30 |
| 6 | harness | safety harness | 0.25 |

## GPU optimization

| Optimization | Impact |
|-------------|--------|
| OpenCV viz (replaces matplotlib) | 10-50x faster viz |
| GPU RLE encode (`robust_rle_encode`) | RLE on GPU, no CPU sync |
| GPU mask IoU NMS (`perflib.mask_iou`) | matmul-based, Tensor Core accelerated |
| Single CPU-GPU sync (1 instead of 18) | GPU stays busy across all 6 prompts |
| Pipeline export (bg thread) | CPU export overlaps GPU inference → 100% GPU util |

## Tech stack

- **Auto-labeling**: SAM 3.1 (PyTorch), text-prompted segmentation
- **Training**: YOLO26 (Ultralytics), detection + segmentation
- **Tracking**: MLflow (local, no auth)
- **Export**: ONNX Runtime (ROCm EP)
- **GPU**: AMD ROCm (RX 7800 XT, RDNA3) via WSL2
- **Report**: LaTeX (XeLaTeX, Thai, polyglossia)
- **Deploy**: Docker + Compose (ROCm / CUDA / CPU profiles)

## Datasets

| Dataset | Source | Classes | Images |
|---------|--------|---------|--------|
| archive3 | [Roboflow PPE Combined](https://universe.roboflow.com/roboflow-universe-projects/personal-protective-equipment-combined-model/dataset/4) | 14 | ~44,000 |
| archive4 | [Ultralytics Construction-PPE](https://github.com/ultralytics/assets/releases/download/v0.0.0/construction-ppe.zip) | 4 | 1,416 |
| blurred | Custom (Gaussian blur) | 5 | 48 |

## Known limitations

- **SAM 3.1 checkpoint missing keys**: `sam3.1_multiplex.pt` reports 4 missing keys in `backbone.vision_backbone.convs.3`. Known issue with public SAM 3.1 checkpoint. Model still runs.
- **ONNX ROCm provider**: `libonnxruntime_providers_rocm.so` fails to load `libhipblas.so.3`. ONNX may fall back to CPU. Report does not claim verified ROCm ONNX GPU execution.
- **SAM 3.1 zero-shot on PPE**: Low precision on archive3 (many NO-* classes cannot be detected zero-shot).
- **CPU inference**: ~30-40s per image at 1008px. GPU strongly recommended.

## License

- **SAM 3.1 code** (`sam3/`): Meta SAM License (see `sam3/LICENSE`)
- **Project code** (`src/`, `yolo26_ppe/`): Project-specific
- **Datasets** (`input/`): See respective source licenses (Roboflow CC BY 4.0, Ultralytics)
