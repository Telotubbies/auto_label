#!/bin/bash
# YOLO26 PPE — Tune + Eval + Export + Report
# Run this after training is complete and models exist.

set -e

export HSA_ENABLE_DXG_DETECTION=1
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1

cd "$(dirname "$0")/../.."
PY=${PYTHON:-python}

echo "============================================================"
echo "YOLO26 PPE — TUNE + EVAL + EXPORT + REPORT"
echo "============================================================"
echo "$(date)"

# Verify all 4 best.pt exist
echo ""
echo "### Verifying trained models..."
ALL_FOUND=true
for model_dir in yolo26n_detect yolo26s_detect yolo26n_seg yolo26s_seg; do
  if [ ! -f "yolo26_ppe/models/$model_dir/run1/weights/best.pt" ]; then
    echo "  MISSING: yolo26_ppe/models/$model_dir/run1/weights/best.pt"
    ALL_FOUND=false
  else
    echo "  OK: $model_dir"
  fi
done

if [ "$ALL_FOUND" = "false" ]; then
  echo "ERROR: Not all models found. Train first."
  exit 1
fi

# Step 3: Evaluate all models (baseline)
echo ""
echo "### Step 3: Evaluation (baseline)"
$PY yolo26_ppe/scripts/04_evaluate.py --all 2>&1 | tee yolo26_ppe/logs_eval_all.log

# Step 4: Tune loop
MAP_THRESHOLD=0.85
MAX_TUNE_ROUNDS=2
TUNE_ITERATIONS=3

for round in $(seq 1 $MAX_TUNE_ROUNDS); do
  echo ""
  echo "### Step 4: Tune loop — round $round/$MAX_TUNE_ROUNDS (threshold mAP50=$MAP_THRESHOLD)"

  NEEDS_TUNE=$($PY -c "
import json, os, sys
eval_path = 'yolo26_ppe/reports/eval_all.json'
if not os.path.exists(eval_path):
    sys.exit(0)
with open(eval_path) as f:
    results = json.load(f)
threshold = $MAP_THRESHOLD
for key, m in results.items():
    map50 = m.get('mAP50', 0) or 0
    if map50 < threshold:
        print(key)
" 2>/dev/null)

  if [ -z "$NEEDS_TUNE" ]; then
    echo "  All models above threshold ($MAP_THRESHOLD). Skipping tune."
    break
  fi

  echo "  Models below threshold: $NEEDS_TUNE"
  echo "  Tuning with $TUNE_ITERATIONS trials each..."

  for model_key in $NEEDS_TUNE; do
    model_size=$(echo "$model_key" | cut -c1)
    task=$(echo "$model_key" | sed 's/^[ns]_//' | sed 's/seg/segment/')
    echo ""
    echo "  Tuning: $model_key (size=$model_size, task=$task)"
    $PY yolo26_ppe/scripts/05_tune.py --model "$model_size" --task "$task" --iterations $TUNE_ITERATIONS 2>&1 | tee "yolo26_ppe/logs_tune_${model_key}_round${round}.log"
  done

  # Re-evaluate after tuning
  echo ""
  echo "  Re-evaluating after tune round $round..."
  $PY yolo26_ppe/scripts/04_evaluate.py --all 2>&1 | tee "yolo26_ppe/logs_eval_round${round}.log"

  if [ "$round" -eq "$MAX_TUNE_ROUNDS" ]; then
    echo "  Reached max tune rounds ($MAX_TUNE_ROUNDS). Proceeding with current best."
  fi
done

# Step 5: Export for production
echo ""
echo "### Step 5: Export"
$PY yolo26_ppe/scripts/07_export.py --all 2>&1 | tee yolo26_ppe/logs_export.log

# Step 6: Comparison report
echo ""
echo "### Step 6: Comparison report"
$PY yolo26_ppe/scripts/06_compare.py 2>&1 | tee yolo26_ppe/logs_report.log

echo ""
echo "============================================================"
echo "YOLO26 PPE — DONE"
echo "============================================================"
echo "$(date)"
echo ""
echo "Results:"
echo "  MLflow UI:    http://localhost:5000"
echo "  Report:       yolo26_ppe/reports/comparison_report.md"
echo "  Models:       yolo26_ppe/models/*/run1/weights/best.pt"
echo "  Eval JSON:    yolo26_ppe/reports/eval_all.json"
