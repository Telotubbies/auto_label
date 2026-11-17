#!/usr/bin/env bash
# Test SAM 3.1 text prompts "ic" / "ic package" on IC packaging images.
# Outputs per-image, per-prompt: viz.png, objects/*.png cutouts, detections.json
export HSA_ENABLE_DXG_DETECTION=1
export LD_LIBRARY_PATH=/opt/rocm-6.4.1/lib:/opt/rocm-6.4.1/lib64
cd /mnt/e/02_Projects/auto_label/sam3_auto_label || exit 1
PY=./sam3_venv/bin/python
OUT=/mnt/c/Users/Gigabyte/Downloads/sam3_ic_test
DEVICE="${DEVICE:-cpu}"

for img in \
  "/mnt/c/Users/Gigabyte/Downloads/DIP-ic-packaging.webp" \
  "/mnt/c/Users/Gigabyte/Downloads/realistic-computer-chip-dippackage-top-260nw-2469498987.webp" \
  "/mnt/c/Users/Gigabyte/Downloads/DIP-ICs.jpg"
do
  stem=$(basename "$img" .webp)
  echo "=== $stem (device=$DEVICE) ==="
  "$PY" test_ic_prompts.py --image "$img" --prompts "ic" "ic package" \
      --output "$OUT/$stem" --device "$DEVICE"
done
