from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")


ROOT = Path(__file__).resolve().parents[2]
PRE_COMMIT = ROOT / ".pre-commit-config.yaml"
CI = ROOT / ".github" / "workflows" / "ci.yml"


def load_ci() -> dict:
    if not CI.is_file():
        pytest.skip("ci.yml is outside this sparse profile; the integrator and CI see it")
    return yaml.safe_load(CI.read_text(encoding="utf-8"))


def test_pre_commit_ruff_hooks_only_lint_tools() -> None:
    config = yaml.safe_load(PRE_COMMIT.read_text(encoding="utf-8"))
    hooks = {hook["id"]: hook for repo in config["repos"] for hook in repo["hooks"]}

    assert hooks["ruff"]["files"] == "^tools/"
    assert hooks["ruff-format"]["files"] == "^tools/"
    text = PRE_COMMIT.read_text(encoding="utf-8")
    assert "TODO(lint-chore)" in text
    assert "progress.md:181" in text


def test_ci_triggers_on_pull_requests_and_the_shared_branches() -> None:
    config = load_ci()
    # PyYAML reads the bare key "on" as the boolean True (YAML 1.1).
    triggers = config.get("on") or config.get(True)
    assert "pull_request" in triggers
    branches = triggers["push"]["branches"]
    assert "main" in branches
    assert "feat/labeldesk-v2" in branches


def test_ci_runs_the_full_api_suite() -> None:
    config = load_ci()
    steps = config["jobs"]["api"]["steps"]
    runs = [step.get("run", "") for step in steps]

    assert any("python -m pytest" in run for run in runs)
    assert any("requirements.txt" in run for run in runs)
    setup = [step for step in steps if str(step.get("uses", "")).startswith("actions/setup-python")]
    assert setup and setup[0]["with"]["python-version"] == "3.11"
    # TODO(lint-chore): drop this once progress.md:181 adds ruff to the api job.
    assert not any("ruff" in run for run in runs)


def test_ci_builds_and_tests_the_web_app() -> None:
    config = load_ci()
    runs = [step.get("run", "") for step in config["jobs"]["web"]["steps"]]

    assert any("npm ci" in run for run in runs)
    assert any("npm run build" in run for run in runs)
    assert any("npm test" in run for run in runs)


def test_ci_runs_the_large_file_guard_and_tools_lint() -> None:
    config = load_ci()
    large_runs = [step.get("run", "") for step in config["jobs"]["large-files"]["steps"]]
    tools_runs = [step.get("run", "") for step in config["jobs"]["tools"]["steps"]]

    assert any("tools/check_large_files.py" in run for run in large_runs)
    assert any("ruff check" in run for run in tools_runs)
    assert any("ruff format --check" in run and "tools" in run for run in tools_runs)
    assert any("pytest tools/tests" in run for run in tools_runs)
