"""Export the FastAPI OpenAPI document as the committed front/back contract.

Usage (either cwd works):

    python tools/export_openapi.py              # repo root
    python ../../tools/export_openapi.py        # apps/backend

The document is committed at apps/backend/openapi.json so the frontend type
generator and its build check need no Python. apps/backend/tests/test_openapi_contract.py
fails when the committed copy drifts from the app.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "apps" / "backend"
OUT = BACKEND_DIR / "openapi.json"


def openapi_spec() -> dict:
    """Import the app against a throwaway data dir so export never touches real data."""
    os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-openapi-"))
    os.environ.setdefault("LD_EMBEDDED_WORKER", "1")
    os.environ.setdefault("LD_WORKER_TOKEN", "openapi-export-token-0123456789abcdef")
    os.environ.setdefault("LD_SAM_ENABLED", "0")
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    from app.main import app  # imported late: env must be set first

    return app.openapi()


def render(spec: dict) -> str:
    """The committed document text: sorted keys, no host, no machine-specific ordering."""
    # `servers` names a deployment host; the contract is about shapes, not where they live.
    document = {key: value for key, value in spec.items() if key != "servers"}
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    text = render(openapi_spec())
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT} ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
