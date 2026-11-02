from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest


TOOL = Path(__file__).resolve().parents[1] / "ld-task"


def run(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(command, cwd=cwd, env=merged, text=True, capture_output=True, check=False)


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    result = run(["git", "-C", str(repo), *args], cwd=repo)
    assert result.returncode == 0, result.stderr
    return result


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        assert separator, line
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


@dataclass
class Sandbox:
    repo: Path
    worktrees: Path
    tmp: Path
    cache: Path
    env: dict[str, str]

    def tool(self, *args: str) -> subprocess.CompletedProcess[str]:
        return run([sys.executable, str(TOOL), *args], cwd=self.repo, env=self.env)

    def worktree(self, team: str, task: str) -> Path:
        return self.worktrees / "task" / team / task


@pytest.fixture
def sandbox(tmp_path: Path) -> Sandbox:
    root = tmp_path / "sand box"
    repo = root / "repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "integ")
    git(repo, "config", "user.email", "ld-task@example.test")
    git(repo, "config", "user.name", "ld-task test")

    files = {
        "apps/web/index.html": "web",
        "apps/api/main.py": "api",
        "apps/worker/worker.py": "worker",
        "apps/inference/inference.py": "inference",
        "packages/lib.py": "pkg",
        "docs/README.md": "docs",
        "tools/keep.txt": "tools",
        "ml/train.py": "ml",
        ".gitignore": ".env.task\n",
    }
    for relative, content in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "initial")

    return Sandbox(
        repo=repo,
        worktrees=root / "worktrees",
        tmp=root / "task-tmp",
        cache=root / "cache",
        env={
            "LD_REPO_ROOT": str(repo),
            "LD_WORKTREES_ROOT": str(root / "worktrees"),
            "LD_TMP_ROOT": str(root / "task-tmp"),
            "LD_CACHE_ROOT": str(root / "cache"),
            "LD_TASK_BASE_REF": "integ",
        },
    )


def test_new_creates_sparse_worktree_with_ports_and_temp_paths(
    sandbox: Sandbox,
) -> None:
    result = sandbox.tool("new", "backend", "B1", "ports", "backend")

    assert result.returncode == 0, result.stderr
    worktree = sandbox.worktree("backend", "B1-ports")
    assert (worktree / "apps/api/main.py").is_file()
    assert (worktree / "packages/lib.py").is_file()
    assert (worktree / "docs/README.md").is_file()
    assert (worktree / "tools/keep.txt").is_file()
    assert not (worktree / "apps/web").exists()
    assert not (worktree / "apps/worker").exists()

    values = read_env(worktree / ".env.task")
    assert values["LD_TASK_BRANCH"] == "task/backend/B1-ports"
    assert values["LD_TASK_TEAM"] == "backend"
    assert values["LD_TASK_ID"] == "B1"
    assert values["LD_TASK_PROFILE"] == "backend"
    assert values["LD_TASK_SLOT"] == "1"
    assert values["LD_API_PORT"] == "8201"
    assert values["LD_WEB_PORT"] == "5401"
    assert values["LD_API_PROXY"] == "http://127.0.0.1:8201"

    task_tmp = sandbox.tmp / "task" / "backend" / "B1-ports"
    assert Path(values["LD_DATA_DIR"]) == task_tmp / "data"
    assert Path(values["TMP"]) == task_tmp / "tmp"
    assert Path(values["TEMP"]) == task_tmp / "tmp"
    assert Path(values["LD_TEST_TMP"]) == task_tmp / "test"
    assert Path(values["NPM_CONFIG_CACHE"]) == sandbox.cache / "npm"
    assert Path(values["UV_CACHE_DIR"]) == sandbox.cache / "uv"
    assert Path(values["LD_WEIGHTS_DIR"]) == sandbox.cache / "weights"
    for directory in (
        task_tmp / "data",
        task_tmp / "tmp",
        task_tmp / "test",
        sandbox.cache / "npm",
        sandbox.cache / "uv",
        sandbox.cache / "weights",
    ):
        assert directory.is_dir(), directory

    assert git(worktree, "status", "--porcelain", "--untracked-files=all").stdout == ""
    branches = git(sandbox.repo, "branch", "--list", "task/backend/B1-ports").stdout
    assert "task/backend/B1-ports" in branches


def test_new_allocates_the_next_free_slot(sandbox: Sandbox) -> None:
    assert sandbox.tool("new", "backend", "B1", "ports", "backend").returncode == 0
    assert sandbox.tool("new", "frontend", "F1", "ui", "frontend").returncode == 0

    second = sandbox.worktree("frontend", "F1-ui")
    values = read_env(second / ".env.task")
    assert values["LD_TASK_SLOT"] == "2"
    assert values["LD_API_PORT"] == "8202"
    assert values["LD_WEB_PORT"] == "5402"
    assert (second / "apps/web/index.html").is_file()
    assert not (second / "apps/api").exists()


def test_new_rejects_an_unknown_profile(sandbox: Sandbox) -> None:
    result = sandbox.tool("new", "backend", "B1", "ports", "nope")

    assert result.returncode != 0
    assert "unknown profile" in result.stderr
    assert not sandbox.worktree("backend", "B1-ports").exists()


def test_done_refuses_an_unmerged_branch(sandbox: Sandbox) -> None:
    assert sandbox.tool("new", "backend", "B1", "ports", "backend").returncode == 0
    worktree = sandbox.worktree("backend", "B1-ports")
    (worktree / "apps/api/extra.py").write_text("x = 1\n", encoding="utf-8")
    git(worktree, "add", "-A")
    git(worktree, "commit", "-qm", "unmerged work")

    result = sandbox.tool("done", "B1")

    assert result.returncode != 0
    assert "not merged" in result.stderr
    assert worktree.is_dir()
    assert (sandbox.tmp / "task" / "backend" / "B1-ports").is_dir()


def test_done_refuses_dirty_then_removes_merged_worktree(sandbox: Sandbox) -> None:
    assert sandbox.tool("new", "backend", "B1", "ports", "backend").returncode == 0
    worktree = sandbox.worktree("backend", "B1-ports")
    (worktree / "apps/api/extra.py").write_text("x = 1\n", encoding="utf-8")
    git(worktree, "add", "-A")
    git(worktree, "commit", "-qm", "task work")
    git(sandbox.repo, "merge", "--no-ff", "-m", "merge B1", "task/backend/B1-ports")

    junk = worktree / "apps/api/untracked.py"
    junk.write_text("junk\n", encoding="utf-8")
    refused = sandbox.tool("done", "B1")

    assert refused.returncode != 0
    assert "not clean" in refused.stderr
    assert junk.is_file()
    assert worktree.is_dir()

    junk.unlink()
    removed = sandbox.tool("done", "B1")

    assert removed.returncode == 0, removed.stderr
    assert not worktree.exists()
    assert not (sandbox.tmp / "task" / "backend" / "B1-ports").exists()
    assert "task/backend/B1-ports" not in git(sandbox.repo, "branch", "--list").stdout


def test_done_tolerates_task_env_when_branch_lacks_gitignore(sandbox: Sandbox) -> None:
    git(sandbox.repo, "rm", "-q", ".gitignore")
    git(sandbox.repo, "commit", "-qm", "drop gitignore")
    assert sandbox.tool("new", "backend", "B1", "ports", "backend").returncode == 0
    worktree = sandbox.worktree("backend", "B1-ports")
    assert "?? .env.task" in git(worktree, "status", "--porcelain", "--untracked-files=all").stdout

    git(sandbox.repo, "merge", "--no-ff", "-m", "merge B1", "task/backend/B1-ports")
    removed = sandbox.tool("done", "B1")

    assert removed.returncode == 0, removed.stderr
    assert not worktree.exists()


def test_list_reports_task_state(sandbox: Sandbox) -> None:
    assert sandbox.tool("new", "backend", "B1", "ports", "backend").returncode == 0
    worktree = sandbox.worktree("backend", "B1-ports")
    (worktree / "apps/api/extra.py").write_text("x = 1\n", encoding="utf-8")
    git(worktree, "add", "-A")
    git(worktree, "commit", "-qm", "unmerged work")

    result = sandbox.tool("list")

    assert result.returncode == 0, result.stderr
    assert "B1" in result.stdout
    assert "task/backend/B1-ports" in result.stdout
    assert "8201" in result.stdout
    assert "no" in result.stdout
