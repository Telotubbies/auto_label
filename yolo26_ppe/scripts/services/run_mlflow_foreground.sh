#!/bin/bash
# Start MLflow tracking server
# WARNING: No auth — for local dev only. For production, add --allowed-hosts and reverse proxy with auth.
mlflow server \
  --backend-store-uri sqlite:///yolo26_ppe/artifacts/mlflow/backend/mlflow.db \
  --default-artifact-root yolo26_ppe/artifacts/mlflow \
  --host 127.0.0.1 --port 5000
