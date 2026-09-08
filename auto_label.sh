#!/usr/bin/env bash
# =============================================================================
# Auto-Label PPE Pipeline -- Bash wrapper for the interactive CLI
# =============================================================================
# This is a thin wrapper around pipeline_cli.py which provides:
#   - Interactive dropdown menus (dataset, mode, model selection)
#   - ETA estimation
#   - Progress display and summary panels
#   - ROCm GPU environment setup (HSA_OVERRIDE_GFX_VERSION for RX 7800 XT)
#
# Usage:
#   ./auto_label.sh                          # interactive mode (dropdowns)
#   ./auto_label.sh --sam --batch blurred    # direct mode
#   ./auto_label.sh --yolo --batch blurred --model small_detection
#   ./auto_label.sh --help
#   ./auto_label.sh --version
#   ./auto_label.sh --dry-run --yolo ...     # preview without executing
# =============================================================================

set -e

# Resolve repo root from this script's location (works on any machine).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$SCRIPT_DIR}"

# Prefer the venv created by setup.py (sam3_auto_label/sam3_venv).
# Fall back to /opt/sam3_venv (legacy path) or system python.
VENV_PYTHON="${REPO_ROOT}/sam3_auto_label/sam3_venv/bin/python"
OPT_PYTHON="/opt/sam3_venv/bin/python"
if [ -x "$VENV_PYTHON" ]; then
    PYTHON="${YOLO_PYTHON:-$VENV_PYTHON}"
elif [ -x "$OPT_PYTHON" ]; then
    PYTHON="${YOLO_PYTHON:-$OPT_PYTHON}"
else
    PYTHON="${YOLO_PYTHON:-python3}"
fi

# --- ROCm GPU Environment Setup (RX 7800 XT = RDNA3 = gfx1101) ---
# WSL2 uses /dev/dxg (not /dev/kfd), so we need:
#   1. HSA_ENABLE_DXG_DETECTION=1 -- tell HIP runtime to use dxg backend
#   2. LD_LIBRARY_PATH pointing to ROCm 6.4.1 libs (with WSL-compatible libhsa-runtime64)
#   3. PyTorch's bundled libhsa-runtime64.so must be replaced with ROCm 6.4.1's version
# See: https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.2.1/docs/install/installrad/wsl/
export HSA_ENABLE_DXG_DETECTION="${HSA_ENABLE_DXG_DETECTION:-1}"

# Add ROCm to PATH and LD_LIBRARY_PATH if installed
if [ -d "/opt/rocm-6.4.1" ]; then
    export PATH="/opt/rocm-6.4.1/bin:$PATH"
    export LD_LIBRARY_PATH="/opt/rocm-6.4.1/lib:/opt/rocm-6.4.1/lib64:${LD_LIBRARY_PATH:-}"
elif [ -d "/opt/rocm" ]; then
    export PATH="/opt/rocm/bin:$PATH"
    export LD_LIBRARY_PATH="/opt/rocm/lib:/opt/rocm/lib64:${LD_LIBRARY_PATH:-}"
fi

# --- WSL2 GPU detection ---
if [ -e /dev/dxg ]; then
    # WSL2 GPU passthrough is available
    :
else
    echo "[WARN] /dev/dxg not found -- WSL2 GPU passthrough may not be configured."
    echo "   Install AMD Adrenalin driver on Windows: https://www.amd.com/en/support"
fi

exec "$PYTHON" "${REPO_ROOT}/pipeline_cli.py" "$@"
