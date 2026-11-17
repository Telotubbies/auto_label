#!/usr/bin/env bash
# DINOv3 -> SAM 3.1 IC defect detection over the Downloads test set.
# Usage: DEVICE=cuda bash run_ic_defect.sh
set -u
cd "$(dirname "$0")"

PY=./sam3_venv/bin/python
OUT="${OUT:-/mnt/c/Users/Gigabyte/Downloads/dinov3_ic_defect}"
DEVICE="${DEVICE:-cuda}"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

IMAGES=(
  "/mnt/c/Users/Gigabyte/Downloads/05vnk95w40gg1.jpg"
  "/mnt/c/Users/Gigabyte/Downloads/ijtf1mpj7de71.jpg"
  "/mnt/c/Users/Gigabyte/Downloads/DIP-ic-packaging.webp"
  "/mnt/c/Users/Gigabyte/Downloads/DIP-ICs.jpg"
  "/mnt/c/Users/Gigabyte/Downloads/realistic-computer-chip-dippackage-top-260nw-2469498987.webp"
)

"$PY" ic_defect_pipeline.py \
    --images "${IMAGES[@]}" \
    --output "$OUT" \
    --device "$DEVICE"
echo "ALL DONE -> $OUT"
