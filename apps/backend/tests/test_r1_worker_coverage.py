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


def test_env_example_claims_every_cpu_handler():
    """`cp .env.example .env` must not narrow the worker below the handler registry (C2)."""
    env = Path(__file__).resolve().parents[3] / "deploy" / ".env.example"
    if not env.exists():
        return
    m = re.search(r"^LD_LOCAL_JOBS=([a-z_,]+)$", env.read_text(encoding="utf-8"), re.MULTILINE)
    assert m, ".env.example must define LD_LOCAL_JOBS"
    claimed = {k.strip() for k in m.group(1).split(",") if k.strip()}
    missing = set(worker.HANDLERS) - set(config.REMOTE_JOB_KINDS) - claimed
    assert not missing, f"a copied .env.example never claims {sorted(missing)}"


def _compose_service(text: str, name: str) -> str:
    """The YAML block of one service: 2-space keys delimit services, deeper keys belong to the body."""
    m = re.search(rf"^  {name}:\n(.*?)(?=^  \S|\Z)", text, re.MULTILINE | re.DOTALL)
    assert m, f"docker-compose.yml has no {name} service"
    return m.group(0)


def test_compose_forwards_every_setting_the_mailer_reads():
    """B5: a mailer setting compose never forwards cannot be configured in the deployed stack."""
    compose = Path(__file__).resolve().parents[3] / "deploy" / "docker-compose.yml"
    mailer = Path(__file__).resolve().parents[1] / "app" / "mailer.py"
    if not compose.exists():
        return
    wanted = set(re.findall(r'os\.environ\.get\("(LD_SMTP_[A-Z]+)"', mailer.read_text(encoding="utf-8")))
    assert wanted, "mailer.py must read its settings from LD_SMTP_* env"
    api = _compose_service(compose.read_text(encoding="utf-8"), "api")
    missing = {k for k in wanted if f"{k}:" not in api}
    assert not missing, f"the compose api service never forwards {sorted(missing)}"
    assert "LD_SMTP_SSL:" in api, "implicit TLS must be settable on the service that sends mail"


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
