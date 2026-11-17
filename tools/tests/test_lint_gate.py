"""The backend lint gate: one honest rule set, a CI step and a pre-commit hook that enforce it."""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")


ROOT = Path(__file__).resolve().parents[2]
RUFF_CONFIG = ROOT / "ruff.toml"
CI = ROOT / ".github" / "workflows" / "ci.yml"
PRE_COMMIT = ROOT / ".pre-commit-config.yaml"


def test_ruff_config_selects_pyflakes_and_bandit() -> None:
    config = tomllib.loads(RUFF_CONFIG.read_text(encoding="utf-8"))

    assert config["line-length"] == 120
    # Pyflakes plus flake8-bandit (T-1303). A wider set later is a deliberate edit, not an accident.
    assert config["lint"]["select"] == ["F", "S"]


def test_api_job_runs_backend_lint() -> None:
    config = yaml.safe_load(CI.read_text(encoding="utf-8"))
    runs = [step.get("run", "") for step in config["jobs"]["api"]["steps"]]

    assert any("ruff check" in run and "apps/backend" in run for run in runs)


def test_pre_commit_lints_backend_but_does_not_format_it() -> None:
    config = yaml.safe_load(PRE_COMMIT.read_text(encoding="utf-8"))
    hooks = {hook["id"]: hook for repo in config["repos"] for hook in repo["hooks"]}

    assert re.search(hooks["ruff-check"]["files"], "apps/backend/app/main.py")
    assert not re.search(hooks["ruff-format"]["files"], "apps/backend/app/main.py")
    assert not re.search(hooks["ruff-format"]["files"], "apps/backend/app/models/project.py")


def test_backend_is_clean() -> None:
    if importlib.util.find_spec("ruff") is None:
        if os.environ.get("CI"):
            pytest.fail("the api job installs ruff; a missing ruff must not skip the gate in CI")
        pytest.skip("ruff is not installed locally; CI runs this check")
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "apps/backend"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
