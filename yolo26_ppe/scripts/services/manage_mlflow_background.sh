#!/usr/bin/env bash
# Start MLflow tracking server as background service on port 5000
# Production config: SQLite WAL backend + file artifact store + gunicorn
#
# Usage:
#   ./start_mlflow_service.sh start   # start in background
#   ./start_mlflow_service.sh stop    # stop
#   ./start_mlflow_service.sh status  # check
#   ./start_mlflow_service.sh restart # restart

set -e

TRACKING_URI="sqlite:////mnt/e/02_Projects/auto_label/yolo26_ppe/artifacts/mlflow/backend/mlflow.db"
ARTIFACT_ROOT="/mnt/e/02_Projects/auto_label/yolo26_ppe/artifacts/mlflow/artifacts"
PORT=5000
HOST="127.0.0.1"
PID_FILE="/tmp/mlflow_server.pid"
LOG_FILE="/mnt/e/02_Projects/auto_label/yolo26_ppe/artifacts/logs/mlflow_server.log"
PYTHON="/opt/sam3_venv/bin/python3"

mkdir -p "$(dirname "$LOG_FILE")"
mkdir -p "$ARTIFACT_ROOT"

start() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat $PID_FILE)" 2>/dev/null; then
        echo "MLflow already running (PID $(cat $PID_FILE))"
        exit 0
    fi
    echo "Starting MLflow server on ${HOST}:${PORT}..."
    nohup "$PYTHON" -m mlflow server \
        --backend-store-uri "$TRACKING_URI" \
        --default-artifact-root "$ARTIFACT_ROOT" \
        --host "$HOST" \
        --port "$PORT" \
        --workers 2 \
        > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    sleep 3
    if kill -0 "$(cat $PID_FILE)" 2>/dev/null; then
        echo "  [OK] MLflow running: PID $(cat $PID_FILE)"
        echo "  [OK] UI: http://localhost:${PORT}"
        echo "  [OK] Log: $LOG_FILE"
    else
        echo "  [FAIL] MLflow failed to start. Check $LOG_FILE"
        tail -20 "$LOG_FILE"
        exit 1
    fi
}

stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo "MLflow not running (no PID file)"
        exit 0
    fi
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Stopping MLflow (PID $PID)..."
        kill "$PID"
        sleep 2
        if kill -0 "$PID" 2>/dev/null; then
            echo "  Force killing..."
            kill -9 "$PID"
        fi
        echo "  [OK] Stopped"
    else
        echo "  Process not running, cleaning PID file"
    fi
    rm -f "$PID_FILE"
}

status() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat $PID_FILE)" 2>/dev/null; then
        echo "MLflow running: PID $(cat $PID_FILE) on port $PORT"
        echo "  UI: http://localhost:${PORT}"
        echo "  Log: $LOG_FILE"
    else
        echo "MLflow not running"
        exit 1
    fi
}

case "${1:-status}" in
    start)   start ;;
    stop)    stop ;;
    restart) stop; start ;;
    status)  status ;;
    *) echo "Usage: $0 {start|stop|restart|status}"; exit 1 ;;
esac
