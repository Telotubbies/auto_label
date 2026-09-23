#!/bin/bash
set -e
cd /mnt/e/02_Projects/auto_label/yolo26_ppe
source /mnt/e/02_Projects/auto_label/sam3_auto_label/sam3_venv/bin/activate
export HSA_ENABLE_DXG_DETECTION=1
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1
export LD_PRELOAD=/opt/rocm/lib/libamdhip64.so

echo "=== [1/2] Training medium_detection stage 2 (batch=4) ==="
python scripts/pipeline/02_train_models.py --model m --task detect --stage 2 --batch 4
echo "=== medium_detection DONE ==="

echo "=== [2/2] Training medium_segmentation stage 2 (batch=2) ==="
python scripts/pipeline/02_train_models.py --model m --task segment --stage 2 --batch 2
echo "=== medium_segmentation DONE ==="

echo "=== ALL 2 REMAINING MODELS RETRAINED ==="
