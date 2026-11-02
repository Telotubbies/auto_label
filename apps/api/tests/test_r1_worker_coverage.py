"""C2: every CPU job kind must have an executor in the documented deployment."""
import asyncio
import re
from pathlib import Path

import pytest

from app import config, worker


def test_missing_handlers_is_empty_by_default():
    assert worker.missing_handlers() == set()


def test_missing_handlers_reports_narrowed_lists(monkeypatch):
    kinds = [k for k in config.LOCAL_JOB_KINDS if k not in ("health", "insights_images")]
    monkeypatch.setattr(worker, "LOCAL_JOB_KINDS", kinds)
    assert worker.missing_handlers() == {"health", "insights_images"}
    try:
        worker.assert_handlers_claimed()
    except RuntimeError as e:
        assert "health" in str(e)
    else:                                   # pragma: no cover - the assertion is the point
        raise AssertionError("a worker with unclaimed handlers must refuse to start")


def test_compose_worker_claims_every_cpu_handler():
    """The compose env is how production narrows the list; it must still cover every handler."""
    compose = Path(__file__).resolve().parents[3] / "deploy" / "docker-compose.yml"
    if not compose.exists():
        return
    text = compose.read_text(encoding="utf-8")
    m = re.search(r"LD_LOCAL_JOBS:\s*\$\{LD_LOCAL_JOBS:-([^}]+)\}", text)
    assert m, "compose must define the worker's LD_LOCAL_JOBS"
    claimed = {k.strip() for k in m.group(1).split(",") if k.strip()}
    missing = set(worker.HANDLERS) - set(config.REMOTE_JOB_KINDS) - claimed
    assert not missing, f"compose worker never claims {sorted(missing)}"


def test_no_gpu_docs_list_claims_every_cpu_handler():
    """DEPLOY.md's no-GPU recipe must match the startup assertion, not crash the worker (Important 3)."""
    doc = Path(__file__).resolve().parents[3] / "docs" / "DEPLOY.md"
    m = re.search(r"LD_LOCAL_JOBS=([a-z_,]+)", doc.read_text(encoding="utf-8"))
    assert m, "docs/DEPLOY.md must document the no-GPU LD_LOCAL_JOBS list"
    claimed = {k.strip() for k in m.group(1).split(",") if k.strip()}
    missing = set(worker.HANDLERS) - set(config.REMOTE_JOB_KINDS) - claimed
    assert not missing, f"the no-GPU docs list never claims {sorted(missing)}"


def test_embedded_api_refuses_to_start_without_an_executor(monkeypatch):
    """The embedded thread must be checked before it starts, or the API stays up with no executor."""
    from app import main

    monkeypatch.setattr(main, "EMBEDDED_WORKER", True)
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(worker, "start_background", lambda: None)
    monkeypatch.setattr(worker, "LOCAL_JOB_KINDS", [k for k in worker.LOCAL_JOB_KINDS if k != "health"])

    async def start():
        async with main.lifespan(main.app):
            raise AssertionError("lifespan must not start a worker with a missing executor")

    with pytest.raises(RuntimeError, match="health"):
        asyncio.run(start())
