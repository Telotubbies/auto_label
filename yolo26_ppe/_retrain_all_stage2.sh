#!/bin/bash
set -e
cd /mnt/e/02_Projects/auto_label/yolo26_ppe
source /mnt/e/02_Projects/auto_label/sam3_auto_label/sam3_venv/bin/activate
export HSA_ENABLE_DXG_DETECTION=1
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1
export LD_PRELOAD=/opt/rocm/lib/libamdhip64.so

echo "=== [1/4] Training small_detection stage 2 (batch=6, AMP=True) ==="
python scripts/pipeline/02_train_models.py --model s --task detect --stage 2 --batch 6
echo "=== small_detection DONE ==="

echo "=== [2/4] Training small_segmentation stage 2 (batch=6, AMP=True) ==="
python scripts/pipeline/02_train_models.py --model s --task segment --stage 2 --batch 6
echo "=== small_segmentation DONE ==="

echo "=== [3/4] Training medium_detection stage 2 (batch=6, AMP=True) ==="
python scripts/pipeline/02_train_models.py --model m --task detect --stage 2 --batch 6
echo "=== medium_detection DONE ==="

echo "=== [4/4] Training medium_segmentation stage 2 (batch=6, AMP=True) ==="
python scripts/pipeline/02_train_models.py --model m --task segment --stage 2 --batch 6
echo "=== medium_segmentation DONE ==="

echo "=== ALL 4 MODELS RETRAINED ==="
