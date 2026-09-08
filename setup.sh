#!/usr/bin/env bash
# =============================================================================
# Auto-Label PPE Pipeline — One-shot setup + launch
# =============================================================================
# This script:
#   1. Locates a Python interpreter to run the SAM environment setup
#      (prefers 3.10-3.12; falls back to 3.13 with upgraded deps).
#   2. Runs sam3_auto_label/setup.py, which creates the venv, installs
#      hardware-matched PyTorch + deps, and downloads the SAM checkpoint.
#      Missing items (checkpoint, Python itself) prompt the user before
#      downloading.
#   3. On success, launches the pipeline via auto_label.sh (renamed from
#      run_pipeline.sh, now auto_label.sh). Extra args are forwarded to the pipeline.
#
# Usage:
#   ./setup.sh                    # full setup, then launch pipeline
#   ./setup.sh --check-only       # run setup.py --check, do not launch
#   ./setup.sh -- --sam --batch x # args after "--" go to auto_label.sh
#   ./setup.sh --no-launch        # setup only, do not launch pipeline
#
# Requirements: bash 4+ (WSL2, Linux, macOS). On Windows run inside WSL2.
# =============================================================================

set -euo pipefail

# Resolve repo root from this script's location.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"
SETUP_PY="${REPO_ROOT}/sam3_auto_label/setup.py"
LAUNCH_SH="${REPO_ROOT}/auto_label.sh"

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
LAUNCH=1
CHECK_ONLY=0
PIPELINE_ARGS=()

while [ $# -gt 0 ]; do
    case "$1" in
        --check-only)
            CHECK_ONLY=1
            LAUNCH=0
            shift
            ;;
        --no-launch)
            LAUNCH=0
            shift
            ;;
        --)
            shift
            PIPELINE_ARGS+=("$@")
            break
            ;;
        *)
            PIPELINE_ARGS+=("$1")
            shift
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()  { printf '[setup.sh] %s\n' "$*"; }
warn() { printf '[setup.sh] WARNING: %s\n' "$*" >&2; }
die()  { printf '[setup.sh] ERROR: %s\n' "$*" >&2; exit 1; }

# Locate a Python interpreter to run setup.py. setup.py itself discovers the
# best interpreter for the venv, so here we only need *any* Python >= 3.8 to
# execute the script. Prefer 3.10-3.12 so setup.py's sys.executable is already
# in the preferred range.
find_runner_python() {
    local candidates=()
    # Preferred minors first (matches pinned deps).
    for v in 3.12 3.11 3.10; do
        command -v "python${v}" >/dev/null 2>&1 && candidates+=("python${v}")
    done
    # Generic fallbacks.
    command -v python3 >/dev/null 2>&1 && candidates+=(python3)
    command -v python  >/dev/null 2>&1 && candidates+=(python)

    for c in "${candidates[@]:-}"; do
        if "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' \
                >/dev/null 2>&1; then
            RUNNER_PY="$c"
            return 0
        fi
    done
    return 1
}

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
log "Auto-Label PPE Pipeline — setup + launch"
log "Repo root: ${REPO_ROOT}"
echo

[ -f "$SETUP_PY" ] || die "setup.py not found at ${SETUP_PY}"

if ! find_runner_python; then
    warn "No Python >= 3.8 found on PATH."
    if [ -t 0 ]; then
        read -r -p "Install Python 3.12 via apt now? [y/N] " ans
        case "$ans" in
            y|Y)
                sudo apt-get update -y
                sudo apt-get install -y python3.12 python3.12-venv python3-pip
                RUNNER_PY="python3.12"
                ;;
            *)
                die "A Python interpreter (>= 3.8) is required. Install one and rerun."
                ;;
        esac
    else
        die "A Python interpreter (>= 3.8) is required. Install one and rerun."
    fi
fi

log "Using runner Python: ${RUNNER_PY} ($("${RUNNER_PY}" --version 2>&1))"
echo

# ---------------------------------------------------------------------------
# Run the SAM environment setup
# ---------------------------------------------------------------------------
SETUP_FLAGS=()
[ "$CHECK_ONLY" -eq 1 ] && SETUP_FLAGS+=(--check)

log "Running sam3_auto_label/setup.py ${SETUP_FLAGS[*]:-}"
echo "-----------------------------------------------------------------------------"
# shellcheck disable=SC2086
( cd "$REPO_ROOT/sam3_auto_label" && "$RUNNER_PY" setup.py ${SETUP_FLAGS[*]:-} )
SETUP_RC=$?
echo "-----------------------------------------------------------------------------"

if [ "$SETUP_RC" -ne 0 ]; then
    die "setup.py exited with code ${SETUP_RC}. Resolve the issues above and rerun."
fi

if [ "$CHECK_ONLY" -eq 1 ]; then
    log "Check-only mode complete. Re-run without --check-only to install."
    exit 0
fi

log "Setup complete."

# ---------------------------------------------------------------------------
# Launch the pipeline
# ---------------------------------------------------------------------------
if [ "$LAUNCH" -ne 1 ]; then
    log "--no-launch set: skipping pipeline launch."
    log "Run ./auto_label.sh manually when ready."
    exit 0
fi

[ -x "$LAUNCH_SH" ] || [ -f "$LAUNCH_SH" ] || die \
    "auto_label.sh not found at ${LAUNCH_SH}. Create it (renamed from run_pipeline.sh)."

log "Launching pipeline: ${LAUNCH_SH} ${PIPELINE_ARGS[*]:-}"
echo
exec "$LAUNCH_SH" "${PIPELINE_ARGS[@]}"
