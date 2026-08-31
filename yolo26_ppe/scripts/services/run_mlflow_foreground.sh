#!/bin/bash
# Start MLflow tracking server
# WARNING: No auth — for local dev only. For production, add --allowed-hosts and reverse proxy with auth.
mlflow server \
  --backend-store-uri sqlite:///yolo26_ppe/mlflow/mlflow.db \
  --default-artifact-root yolo26_ppe/mlflow/mlruns \
  --host 0.0.0.0 --port 5000
