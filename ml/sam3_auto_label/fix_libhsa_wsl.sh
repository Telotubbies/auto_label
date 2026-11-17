#!/usr/bin/env bash
# One-time fix: point torch/triton's bundled libhsa-runtime64.so at the
# WSL-compatible ROCm 6.4.1 runtime (originals kept as .bak).
set -e
VENV=/mnt/e/02_Projects/auto_label/sam3_auto_label/sam3_venv/lib/python3.12/site-packages
SRC=/opt/rocm-6.4.1/lib/libhsa-runtime64.so.1.15.60401
for d in "$VENV/torch/lib" "$VENV/triton/backends/amd/lib"; do
  f="$d/libhsa-runtime64.so"
  if [ -L "$f" ]; then
    echo "already symlink: $f"
  elif [ -f "$f" ]; then
    mv "$f" "$f.bak"
    echo "backed up: $f.bak"
  fi
  ln -sf "$SRC" "$f"
done
ls -la "$VENV/torch/lib/"libhsa* "$VENV/triton/backends/amd/lib/"libhsa*
