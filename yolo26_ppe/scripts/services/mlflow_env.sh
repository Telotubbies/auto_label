#!/usr/bin/env bash
# MLflow production environment variables for yolo26_ppe pipeline.
# Source this before running any training/eval/tune script:
#   source /mnt/e/02_Projects/auto_label/yolo26_ppe/scripts/services/mlflow_env.sh
#
# Or add to ~/.bashrc for persistence:
#   echo 'source /mnt/e/02_Projects/auto_label/yolo26_ppe/scripts/services/mlflow_env.sh' >> ~/.bashrc

# Tracking server (local production)
export MLFLOW_TRACKING_URI="http://localhost:5000"
export MLFLOW_EXPERIMENT_NAME="yolo26_ppe_v2"
export MLFLOW_REGISTRY_URI="http://localhost:5000"

# Artifact location
export MLFLOW_ARTIFACT_ROOT="/mnt/e/02_Projects/auto_label/yolo26_ppe/artifacts/mlflow/artifacts"

# Autologging (disabled — we log manually for full control)
export MLFLOW_AUTOLOGGING="false"

# Reproducibility
export MLFLOW_SEED="42"

# GPU/ROCm (must stay GPU-only)
export HSA_ENABLE_DXG_DETECTION="1"
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL="1"
export HIP_VISIBLE_DEVICES="0"
export CUDA_VISIBLE_DEVICES="0"

# Python path
export PYTHONPATH="/mnt/e/02_Projects/auto_label/yolo26_ppe:${PYTHONPATH:-}"

echo "[mlflow_env] MLflow tracking: $MLFLOW_TRACKING_URI"
echo "[mlflow_env] Experiment: $MLFLOW_EXPERIMENT_NAME"
echo "[mlflow_env] Registry: $MLFLOW_REGISTRY_URI"
