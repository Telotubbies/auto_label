"""The security gate (T-1303): SAST rules, CVEs, secrets and licences fail a merge.

The gate is one `security` job in `.github/workflows/ci.yml` plus the rule set in `ruff.toml`, the
secret allowlist in `.gitleaks.toml` and the CVE waivers in `security/audit-ignore.txt`.
"""

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
CI = ROOT / ".github" / "workflows" / "ci.yml"
RUFF_CONFIG = ROOT / "ruff.toml"
GITLEAKS_CONFIG = ROOT / ".gitleaks.toml"
AUDIT_IGNORE = ROOT / "security" / "audit-ignore.txt"

# The one waiver format the file documents: <id> | <YYYY-MM-DD expiry> | <reason>.
AUDIT_WAIVER = re.compile(r"^[A-Za-z][A-Za-z0-9-]+ \| \d{4}-\d{2}-\d{2} \| \S.*$")
S105 = "S105"


def job_runs(config: dict, name: str) -> str:
    return "\n".join(str(step.get("run", "")) for step in config["jobs"][name]["steps"])


def ruff_present() -> bool:
    if importlib.util.find_spec("ruff") is not None:
        return True
    if os.environ.get("CI"):
        pytest.fail("the api and tools jobs install ruff; a missing ruff must not skip the gate in CI")
    pytest.skip("ruff is not installed locally; CI runs this check")


def test_the_security_job_is_in_the_gate() -> None:
    config = yaml.safe_load(CI.read_text(encoding="utf-8"))

    assert "security" in config["jobs"]["gate"]["needs"]
    runs = job_runs(config, "security")
    assert "gitleaks dir ." in runs
    assert "pip_audit" in runs or "pip-audit" in runs
    assert "tools/check_licenses.py" in runs

    web = job_runs(config, "web")
    assert "npm audit --omit=dev --audit-level=high" in web
    assert "npm audit --audit-level=high || true" in web


def test_a_hardcoded_password_fails_ruff_s(tmp_path: Path) -> None:
    ruff_present()
    fixture = tmp_path / "hardcoded_password.py"
    fixture.write_text('password = "hunter2"\n', encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--config", str(RUFF_CONFIG), str(fixture)],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0, result.stdout + result.stderr
    assert S105 in result.stdout


def test_ruff_still_passes_on_the_repo() -> None:
    ruff_present()
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


def test_gitleaks_config_is_valid_and_scoped() -> None:
    config = tomllib.loads(GITLEAKS_CONFIG.read_text(encoding="utf-8"))

    assert config["extend"]["useDefault"] is True
    allowlists = [entry for entry in [config.get("allowlist")] if entry]
    for rule in config.get("rules", []):
        allowlists.extend(rule.get("allowlists", []))
    assert allowlists, "the config must ship a scoped allowlist for the known test fixtures"
    for entry in allowlists:
        assert entry.get("paths"), f"an allowlist entry without a path is too broad: {entry}"


def test_audit_ignore_entries_have_a_reason_and_a_date() -> None:
    text = AUDIT_IGNORE.read_text(encoding="utf-8")
    entries = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]

    for line in entries:
        assert AUDIT_WAIVER.match(line), f"waiver must read '<id> | <YYYY-MM-DD> | <reason>': {line!r}"
    assert "<id> | <YYYY-MM-DD> | <reason>" in text
