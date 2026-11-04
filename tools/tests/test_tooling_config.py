from __future__ import annotations

from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
PRE_COMMIT = ROOT / ".pre-commit-config.yaml"
CI = ROOT / ".github" / "workflows" / "ci.yml"


def test_pre_commit_ruff_hooks_only_lint_tools() -> None:
    config = yaml.safe_load(PRE_COMMIT.read_text(encoding="utf-8"))
    hooks = {hook["id"]: hook for repo in config["repos"] for hook in repo["hooks"]}

    assert hooks["ruff"]["files"] == "^tools/"
    assert hooks["ruff-format"]["files"] == "^tools/"
    text = PRE_COMMIT.read_text(encoding="utf-8")
    assert "TODO(lint-chore)" in text
    assert "progress.md:181" in text


def test_ci_workflow_states_its_partial_scope() -> None:
    if not CI.is_file():
        pytest.skip("ci.yml is outside this sparse profile; the integrator and CI see it")
    text = CI.read_text(encoding="utf-8")
    config = yaml.safe_load(text)
    jobs = config["jobs"]

    assert "progress.md:181" in text
    api_runs = [step.get("run", "") for step in jobs["api"]["steps"]]
    assert any("compileall" in run for run in api_runs)
    assert not any("ruff" in run for run in api_runs)
    tools_runs = [step.get("run", "") for step in jobs["tools"]["steps"]]
    assert any("ruff check" in run for run in tools_runs)
