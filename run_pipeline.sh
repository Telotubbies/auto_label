#!/usr/bin/env bash
# =============================================================================
# Auto-Label PPE Pipeline — Bash wrapper for the interactive CLI
# =============================================================================
# This is a thin wrapper around pipeline_cli.py which provides:
#   - Interactive dropdown menus (dataset, mode, model selection)
#   - ETA estimation
#   - Progress display and summary panels
#
# Usage:
#   ./run_pipeline.sh                          # interactive mode (dropdowns)
#   ./run_pipeline.sh --sam --batch blurred    # direct mode
#   ./run_pipeline.sh --yolo --batch blurred --model small_detection
#   ./run_pipeline.sh --help
# =============================================================================
set -e

REPO_ROOT="/mnt/e/02_Projects/auto_label"
PYTHON="${YOLO_PYTHON:-/opt/sam3_venv/bin/python}"

exec "$PYTHON" "${REPO_ROOT}/pipeline_cli.py" "$@"
