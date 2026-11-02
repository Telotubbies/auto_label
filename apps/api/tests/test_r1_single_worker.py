"""I5: in-process state (selections, rate limits, GPU ledger) needs a single uvicorn worker."""
from pathlib import Path


def test_api_runs_one_uvicorn_worker():
    dockerfile = Path(__file__).resolve().parents[1] / "Dockerfile"
    text = dockerfile.read_text(encoding="utf-8")
    assert '"--workers", "1"' in text
