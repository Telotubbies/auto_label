#!/usr/bin/env python3
"""Run v3 AdamW on all 4 models sequentially."""
import subprocess
import sys
import time
from pathlib import Path

BASE = Path("/mnt/e/02_Projects/auto_label/yolo26_ppe")
SCRIPT = BASE / "scripts/04_train_optimizer_experiment.py"

MODELS = ["n_detect", "s_detect", "n_seg", "s_seg"]

for model in MODELS:
    print("\n" + "=" * 70)
    print(f"  START: {model} v3 AdamW")
    print("=" * 70)

    t0 = time.time()
    result = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--model", model,
         "--optimizer", "AdamW",
         "--version", "v3"],
        cwd=str(BASE),
    )
    elapsed = time.time() - t0

    status = "OK" if result.returncode == 0 else f"FAIL (rc={result.returncode})"
    print(f"\n  {model} v3 AdamW: {status}  ({elapsed/60:.1f} min)")

    if result.returncode != 0:
        print(f"  ERROR on {model}, continuing to next...")

print("\n" + "=" * 70)
print("  ALL 4 v3 AdamW TRAINING COMPLETE")
print("=" * 70)
