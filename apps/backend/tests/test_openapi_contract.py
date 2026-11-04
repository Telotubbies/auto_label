"""The committed OpenAPI document is the front/back contract — keep it in lockstep with the app."""
import importlib.util
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("LD_EMBEDDED_WORKER", "1")
os.environ.setdefault("LD_WORKER_TOKEN", "test-worker-token-0123456789abcdef")
os.environ.setdefault("LD_SAM_ENABLED", "0")

REPO_ROOT = Path(__file__).resolve().parents[3]
EXPORT_OPENAPI = REPO_ROOT / "tools" / "export_openapi.py"
OPENAPI = REPO_ROOT / "apps" / "backend" / "openapi.json"

from app.main import app  # noqa: E402


def load_exporter():
    spec = importlib.util.spec_from_file_location("export_openapi_under_test", EXPORT_OPENAPI)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_openapi_document_matches_the_app():
    text = OPENAPI.read_text(encoding="utf-8")
    assert text == load_exporter().render(app.openapi()), (
        "run `python tools/export_openapi.py` — the committed OpenAPI document is stale"
    )


def test_export_is_deterministic_and_host_free():
    exporter = load_exporter()
    text = exporter.render(app.openapi())
    assert '"servers"' not in text, "the contract must not pin a host"
    assert exporter.render(json.loads(text)) == text, "re-exporting the committed document must not change it"
