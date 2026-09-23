# YOLO26 vs SAM 3.1 — PPE Detection Comparison Report
Generated: 2026-09-11
Dataset: combined_coco_dataset_version_3 — 662 images (566 train / 48 val / 48 test)
Classes (4): person, helmet, closed footwear, harness
GPU: AMD RX 7800 XT (ROCm, WSL2)
Recipe: v4_recipe — two-stage (Stage 1 SGD 150 epochs → Stage 2 AdamW 50 epochs), seed 42, imgsz 640

> Note: This report covers the current v3 4-class cohort (small + medium).
> The older v2 5-class results (nano + small) are archived in
> `models/archive/version_2_5class/` and are NOT directly comparable
> (different dataset and class schema).

## 1. Overall Performance Summary (test set, 48 images)
| Model | Task | mAP50 | mAP50-95 | Precision | Recall | Inference (ms) | Size (MB) | Params (M) |
|-------|------|-------|----------|-----------|--------|----------------|-----------|------------|
| small_detection | detect | 0.670 | 0.479 | 0.792 | 0.619 | 22.2 | 19.4 | 9.95 |
| medium_detection | detect | 0.693 | 0.507 | 0.795 | 0.657 | 24.1 | 42.0 | 21.78 |
| small_segmentation | segment (box) | 0.566 | 0.389 | 0.762 | 0.510 | 8.6 | 22.3 | 11.44 |
| medium_segmentation | segment (box) | 0.599 | 0.431 | 0.800 | 0.549 | 13.7 | 52.0 | 26.98 |
| small_segmentation | segment (mask) | 0.509 | 0.288 | 0.712 | 0.482 | — | — | — |
| medium_segmentation | segment (mask) | 0.512 | 0.290 | 0.718 | 0.493 | — | — | — |
| sam3.1 | segment (zero-shot) | N/A | N/A | N/A | N/A | ~2755 | 3340.5 | N/A |

## 2. Per-Class mAP50 (box)
| Model | person | helmet | closed footwear | harness |
|-------|--------|--------|-----------------|---------|
| small_detection | 0.947 | 0.754 | 0.564 | 0.416 |
| medium_detection | 0.935 | 0.798 | 0.615 | 0.424 |
| small_segmentation | 0.711 | 0.709 | 0.538 | 0.306 |
| medium_segmentation | 0.734 | 0.739 | 0.625 | 0.298 |

## 3. Medium vs Small (same v3 dataset, same recipe)
| Model | mAP50 | mAP50-95 | Params (M) | Inference (ms) |
|-------|-------|----------|------------|----------------|
| small_detection | 0.670 | 0.479 | 9.95 | 22.2 |
| medium_detection | 0.693 | 0.507 | 21.78 | 24.1 |
| small_segmentation (box) | 0.566 | 0.389 | 11.44 | 8.6 |
| medium_segmentation (box) | 0.599 | 0.431 | 26.98 | 13.7 |

- Medium detection outperforms small detection by +2.3 mAP50 points at ~2.2x parameters.
- Small segmentation is competitive with medium segmentation at less than half the parameters.
- ONNX exports match PyTorch metrics (delta mAP50 < 0.02) — export fidelity confirmed.

## 4. Trade-off Analysis
| Model | Best For | Note |
|-------|----------|------|
| small_detection | Balanced accuracy/size | Nearly matches medium at half the size |
| medium_detection | Highest box accuracy | Best mAP50 of the cohort |
| small_segmentation | Fast masks | Fastest model in the cohort |
| medium_segmentation | Best mask quality | Largest model (52 MB) |
| sam3.1 | Zero-shot labeling | No training; ~100x slower; used upstream for auto-labeling |

## 5. Production Recommendations
### Scenario 1: Highest detection accuracy
- **Recommended**: medium_detection (mAP50 0.693)
- **Trade-off**: 42 MB, 24.1 ms inference

### Scenario 2: Lightweight deployment
- **Recommended**: small_detection (mAP50 0.670, 19.4 MB)
- **Trade-off**: -2.3 mAP50 points vs medium

### Scenario 3: Instance segmentation
- **Recommended**: medium_segmentation for quality, small_segmentation for speed
- **Note**: mask mAP50 ~0.51 — usable but weaker than detection

### Scenario 4: Hybrid auto-labeling loop
- **Primary**: SAM 3.1 generates labels → human verify → train YOLO
- **Inference**: YOLO26 production models for deployment

## 6. Known Limitations
- **harness** is the weakest class across all models (mAP50 0.30-0.46) due to class imbalance (177 annotations, 19:1 vs closed footwear).
- **closed footwear** and harness are small objects — reduced confidence at 640 px.
- Dataset is 662 images; mAP50 target of 0.85 was not met (data-limited, not recipe-limited).
- medium_segmentation stage 1 early-stopped at epoch 117 (best epoch 96) — normal early-stopping behavior.

## 7. Sources
- Metrics: `yolo26_ppe/artifacts/evaluation/yolo/production_v4_recipe/all_metrics.json`
- ONNX comparison: `artifacts/evaluation/yolo/production_v4_recipe/onnx/`
- Failure analysis: `artifacts/evaluation/yolo/production_v4_recipe/*_failures.json`
- Full report: `reports/final/report.pdf`
