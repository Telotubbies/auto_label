"""TC-10: No secrets in code.
TC-11: shell=True eliminated.

Static scans across all .py, .sh, and .yaml files in the repository.
These tests enforce the security audit findings from 2026-09-10.
"""
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.static

# Directories to skip during the scan (vendored, venv, cache, etc.)
SKIP_DIRS = {
    "sam3_venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache",
    ".git", "node_modules", "sam3",  # sam3 = vendored SAM 3.1 source
    ".venv_windows", ".venv", "venv",  # virtual environments
}

# File extensions to scan
SCAN_EXTENSIONS = {".py", ".sh", ".yaml", ".yml"}


def _scanable_files(repo_root: Path):
    """Yield all source files that should be scanned for secrets/injection."""
    for path in repo_root.rglob("*"):
        if not path.suffix in SCAN_EXTENSIONS:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            if not path.is_file():
                continue
        except OSError:
            # Broken symlinks or inaccessible files (e.g. WSL venv on Windows)
            continue
        yield path


# Patterns that look like hardcoded secrets (ISO 27001 A.14.2.1)
SECRET_PATTERNS = [
    # API keys / tokens (common formats)
    (re.compile(r'(?:api[_-]?key|api[_-]?secret|access[_-]?token|secret[_-]?key)\s*[=:]\s*["\'][A-Za-z0-9+/=]{20,}["\']', re.IGNORECASE), "API key/secret assignment"),
    (re.compile(r'(?:password|passwd|pwd)\s*[=:]\s*["\'][^"\']{4,}["\']', re.IGNORECASE), "Password assignment"),
    (re.compile(r'(?:aws_secret_access_key|aws_access_key_id)\s*[=:]\s*["\'][A-Za-z0-9/+]{16,}["\']', re.IGNORECASE), "AWS credential"),
    (re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----'), "Private key block"),
    (re.compile(r'ghp_[A-Za-z0-9]{36}'), "GitHub personal access token"),
    (re.compile(r'sk-[A-Za-z0-9]{20,}'), "OpenAI-style API key"),
]


class TestNoSecretsInCode:
    """TC-10: No passwords, keys, or tokens in source files."""

    def test_no_hardcoded_secrets(self, repo_root):
        findings = []
        for filepath in _scanable_files(repo_root):
            try:
                content = filepath.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError, OSError):
                continue
            for pattern, label in SECRET_PATTERNS:
                for match in pattern.finditer(content):
                    # Skip comments that are clearly documentation examples
                    line_start = content.rfind("\n", 0, match.start()) + 1
                    line = content[line_start: content.find("\n", match.start())]
                    stripped = line.lstrip()
                    if stripped.startswith("#") or stripped.startswith("//"):
                        continue
                    findings.append((filepath.relative_to(repo_root), line.strip(), label))

        assert not findings, (
            f"Found {len(findings)} potential secret(s) in source code:\n"
            + "\n".join(f"  {f}: {label} — {line}" for f, line, label in findings)
        )

    def test_no_secrets_in_yaml_configs(self, repo_root):
        """YAML configs must not contain password/token fields."""
        findings = []
        for path in repo_root.rglob("*.yaml"):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue
            for pattern, label in SECRET_PATTERNS:
                for match in pattern.finditer(content):
                    findings.append((path.relative_to(repo_root), label))
        assert not findings, f"Secrets found in YAML: {findings}"


class TestNoShellTrue:
    """TC-11: shell=True must be eliminated from pipeline_cli.py (ISO 27001 A.14.2.5)."""

    def test_no_shell_true_in_pipeline_cli(self, repo_root):
        cli_path = repo_root / "pipeline_cli.py"
        content = cli_path.read_text(encoding="utf-8")
        # Find all shell=True occurrences, excluding comments
        findings = []
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if "shell=True" in line:
                findings.append((i, line.strip()))
        assert not findings, (
            f"shell=True found in pipeline_cli.py (command injection risk):\n"
            + "\n".join(f"  line {n}: {line}" for n, line in findings)
        )

    def test_no_shell_true_in_all_python(self, repo_root):
        """No project source Python file should use shell=True (tests excluded)."""
        findings = []
        for path in repo_root.rglob("*.py"):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            # Exclude test files — they legitimately reference shell=True in assertions
            if "tests" in path.parts:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError, OSError):
                continue
            for i, line in enumerate(content.splitlines(), 1):
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    continue
                if "shell=True" in line:
                    findings.append((path.relative_to(repo_root), i, line.strip()))
        assert not findings, (
            f"shell=True found in Python files:\n"
            + "\n".join(f"  {f}:{n}: {line}" for f, n, line in findings)
        )
