#!/bin/bash
# YOLO26 PPE — Full pipeline runner
# Runs all steps sequentially: data → train → eval → tune → export → report

set -e

export HSA_ENABLE_DXG_DETECTION=1
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1

cd "$(dirname "$0")/../.."
PY=${PYTHON:-python}

echo "============================================================"
echo "YOLO26 PPE PIPELINE — START"
echo "============================================================"
echo "$(date)"

# Start MLflow server separately: bash scripts/start_mlflow.sh

# Step 1: Data preparation (already done, skip if exists)
if [ ! -f yolo26_ppe/data/yolo_detect/data.yaml ]; then
  echo ""
  echo "### Step 1: Data preparation"
  $PY yolo26_ppe/scripts/01_prepare_data.py 2>&1 | tee yolo26_ppe/logs_step1.log
fi

# Step 2: Train all 4 models
echo ""
echo "### Step 2: Training all 4 models"
$PY yolo26_ppe/scripts/03_train.py --all 2>&1 | tee yolo26_ppe/logs_train_all.log

# Step 3: Evaluate all models
echo ""
echo "### Step 3: Evaluation"
$PY yolo26_ppe/scripts/04_evaluate.py --all 2>&1 | tee yolo26_ppe/logs_eval_all.log

# Step 4: Tune loop — if any model's mAP50 < threshold, tune and re-eval
# Repeat up to MAX_TUNE_ROUNDS times
MAP_THRESHOLD=0.85
MAX_TUNE_ROUNDS=2
TUNE_ITERATIONS=5

for round in $(seq 1 $MAX_TUNE_ROUNDS); do
  echo ""
  echo "### Step 4: Tune loop — round $round/$MAX_TUNE_ROUNDS (threshold mAP50=$MAP_THRESHOLD)"

  # Check which models need tuning (mAP50 < threshold)
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
  echo "  Tuning with $TUNE_ITERATIONS iterations each..."

  for model_key in $NEEDS_TUNE; do
    # Parse model_key: n_detect, s_detect, n_seg, s_seg
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
echo "YOLO26 PPE PIPELINE — DONE"
echo "============================================================"
echo "$(date)"
echo ""
echo "Results:"
echo "  MLflow UI:    http://localhost:5000"
echo "  Report:       yolo26_ppe/reports/comparison_report.md"
echo "  Models:       yolo26_ppe/models/*/run1/weights/best.pt"
echo "  Eval JSON:    yolo26_ppe/reports/eval_all.json"

# MLflow server runs separately — see scripts/start_mlflow.sh
