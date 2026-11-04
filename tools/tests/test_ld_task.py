from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import pytest


TOOL = Path(__file__).resolve().parents[1] / "ld-task"


def load_tool() -> ModuleType:
    loader = importlib.machinery.SourceFileLoader("ld_task", str(TOOL))
    spec = importlib.util.spec_from_loader("ld_task", loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


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


def write_env(path: Path, values: dict[str, str]) -> None:
    lines = []
    for key, value in values.items():
        text = str(value).replace("\\", "/")
        lines.append(f'{key}="{text}"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
        "apps/frontend/index.html": "web",
        "apps/backend/main.py": "api",
        "apps/worker/worker.py": "worker",
        "apps/inference/inference.py": "inference",
        "docs/README.md": "docs",
        "deploy/compose.yaml": "deploy",
        "tools/keep.txt": "tools",
        "data/raw/x.jpg": "image",
        "yolo26_ppe/models/x.pt": "weights",
        "sam3_auto_label/run.py": "sam",
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


def repo_root() -> Path:
    result = run(["git", "rev-parse", "--show-toplevel"], cwd=TOOL.parent)
    assert result.returncode == 0, result.stderr
    return Path(result.stdout.strip()).resolve()


@pytest.fixture
def heavy_clone(sandbox: Sandbox, tmp_path: Path) -> Sandbox:
    """A real clone of a throwaway repo that tracks data/ and yolo26_ppe/.

    The source is the synthetic sandbox, not this repository: the approved history
    rewrite removes those folders from HEAD, and the exclusion contract must stay
    testable after it lands. --shared keeps the object store in the source;
    --no-checkout means only the sparse profiles are written out.
    """
    clone = tmp_path / "heavy clone"
    cloned = run(["git", "clone", "--shared", "--no-checkout", "-q", str(sandbox.repo), str(clone)], cwd=tmp_path)
    assert cloned.returncode == 0, cloned.stderr
    branch = run(["git", "-C", str(clone), "rev-parse", "--abbrev-ref", "HEAD"], cwd=clone).stdout.strip()
    root = tmp_path / "clone-roots"
    return Sandbox(
        repo=clone,
        worktrees=root / "worktrees",
        tmp=root / "task-tmp",
        cache=root / "cache",
        env={
            "LD_REPO_ROOT": str(clone),
            "LD_WORKTREES_ROOT": str(root / "worktrees"),
            "LD_TMP_ROOT": str(root / "task-tmp"),
            "LD_CACHE_ROOT": str(root / "cache"),
            "LD_TASK_BASE_REF": branch,
        },
    )


@pytest.mark.parametrize(
    ("profile", "present"),
    [
        ("frontend", ["apps/frontend"]),
        ("backend", ["apps/backend", "tools"]),
        ("full", ["apps", "deploy"]),
    ],
)
def test_cloned_worktree_omits_data_and_yolo_weights(
    heavy_clone: Sandbox,
    profile: str,
    present: list[str],
) -> None:
    tracked = run(
        ["git", "-C", str(heavy_clone.repo), "ls-tree", "-d", "--name-only", "HEAD"],
        cwd=heavy_clone.repo,
    )
    assert tracked.returncode == 0, tracked.stderr
    top_level = tracked.stdout.split()
    assert "data" in top_level and "yolo26_ppe" in top_level, "precondition: the fixture tracks the heavy folders"

    team = {"frontend": "frontend", "backend": "backend", "full": "platform"}[profile]
    result = heavy_clone.tool("new", team, "Z9", profile, profile)

    assert result.returncode == 0, result.stderr
    worktree = heavy_clone.worktree(team, f"Z9-{profile}")
    assert not (worktree / "data").exists()
    assert not (worktree / "yolo26_ppe").exists()
    for path in present:
        assert (worktree / path).exists(), path


def test_sparse_profile_paths_exist_in_the_repository_tree() -> None:
    module = load_tool()
    root = repo_root()

    for profile, paths in module.SPARSE_PROFILES.items():
        assert paths, profile
        for path in paths:
            found = run(
                ["git", "-C", str(root), "ls-tree", "-d", "--name-only", "HEAD", "--", path],
                cwd=root,
            )
            assert found.returncode == 0, found.stderr
            assert found.stdout.strip(), f"profile {profile}: {path} does not exist in HEAD"


def test_new_creates_sparse_worktree_with_ports_and_temp_paths(
    sandbox: Sandbox,
) -> None:
    result = sandbox.tool("new", "backend", "B1", "ports", "backend")

    assert result.returncode == 0, result.stderr
    worktree = sandbox.worktree("backend", "B1-ports")
    assert (worktree / "apps/backend/main.py").is_file()
    assert (worktree / "docs/README.md").is_file()
    assert (worktree / "tools/keep.txt").is_file()
    assert not (worktree / "apps/frontend").exists()
    assert not (worktree / "apps/worker").exists()
    assert not (worktree / "data").exists()
    assert not (worktree / "yolo26_ppe").exists()
    assert not (worktree / "sam3_auto_label").exists()

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
    assert Path(values["LD_PRETRAINED_DIR"]) == sandbox.cache / "weights"
    assert "LD_WEIGHTS_DIR" not in values
    assert "LD_CACHE_DIR" not in values
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
    assert (second / "apps/frontend/index.html").is_file()
    assert not (second / "apps/backend").exists()
    assert not (second / "data").exists()
    assert not (second / "yolo26_ppe").exists()


def test_new_ml_profile_checks_out_ml_code_but_not_data(sandbox: Sandbox) -> None:
    result = sandbox.tool("new", "ml", "M1", "train", "ml")

    assert result.returncode == 0, result.stderr
    worktree = sandbox.worktree("ml", "M1-train")
    assert (worktree / "yolo26_ppe/models/x.pt").is_file()
    assert (worktree / "sam3_auto_label/run.py").is_file()
    assert (worktree / "tools/keep.txt").is_file()
    assert (worktree / "docs/README.md").is_file()
    assert not (worktree / "data").exists()
    assert not (worktree / "apps").exists()


def test_new_rejects_a_profile_path_missing_from_the_tree(sandbox: Sandbox) -> None:
    git(sandbox.repo, "rm", "-r", "-q", "apps/frontend")
    git(sandbox.repo, "commit", "-qm", "drop web")

    result = sandbox.tool("new", "frontend", "F1", "ui", "frontend")

    assert result.returncode != 0
    assert "does not exist" in result.stderr
    assert "apps/frontend" in result.stderr
    assert not sandbox.worktree("frontend", "F1-ui").exists()
    assert not (sandbox.tmp / "task" / "frontend" / "F1-ui").exists()


def test_new_rejects_a_profile_that_matches_nothing(sandbox: Sandbox) -> None:
    git(sandbox.repo, "rm", "-r", "-q", "apps/frontend", "docs")
    git(sandbox.repo, "commit", "-qm", "drop every frontend path")

    result = sandbox.tool("new", "frontend", "F1", "ui", "frontend")

    assert result.returncode != 0
    assert "does not exist" in result.stderr
    assert not sandbox.worktree("frontend", "F1-ui").exists()


def test_profile_paths_rejects_an_empty_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_tool()
    monkeypatch.setitem(module.SPARSE_PROFILES, "empty", [])

    with pytest.raises(module.LdTaskError, match="is empty"):
        module._profile_paths(Path("."), "HEAD", "HEAD", "empty")


def test_env_file_documents_the_real_port_mechanism(sandbox: Sandbox) -> None:
    assert sandbox.tool("new", "frontend", "F1", "ui", "frontend").returncode == 0
    header = (sandbox.worktree("frontend", "F1-ui") / ".env.task").read_text(encoding="utf-8")

    assert 'npm run dev -- --port "$LD_WEB_PORT"' in header
    assert 'uvicorn app.main:app --port "$LD_API_PORT"' in header
    assert "vite.config.ts" in header


def test_new_rejects_an_unknown_profile(sandbox: Sandbox) -> None:
    result = sandbox.tool("new", "backend", "B1", "ports", "nope")

    assert result.returncode != 0
    assert "unknown profile" in result.stderr
    assert not sandbox.worktree("backend", "B1-ports").exists()


def test_done_refuses_an_unmerged_branch(sandbox: Sandbox) -> None:
    assert sandbox.tool("new", "backend", "B1", "ports", "backend").returncode == 0
    worktree = sandbox.worktree("backend", "B1-ports")
    (worktree / "apps/backend/extra.py").write_text("x = 1\n", encoding="utf-8")
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
    (worktree / "apps/backend/extra.py").write_text("x = 1\n", encoding="utf-8")
    git(worktree, "add", "-A")
    git(worktree, "commit", "-qm", "task work")
    git(sandbox.repo, "merge", "--no-ff", "-m", "merge B1", "task/backend/B1-ports")

    junk = worktree / "apps/backend/untracked.py"
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
    (worktree / "apps/backend/extra.py").write_text("x = 1\n", encoding="utf-8")
    git(worktree, "add", "-A")
    git(worktree, "commit", "-qm", "unmerged work")

    result = sandbox.tool("list")

    assert result.returncode == 0, result.stderr
    assert "B1" in result.stdout
    assert "task/backend/B1-ports" in result.stdout
    assert "8201" in result.stdout
    assert "no" in result.stdout


def commit_and_merge(sandbox: Sandbox, worktree: Path) -> None:
    (worktree / "apps/backend/extra.py").write_text("x = 1\n", encoding="utf-8")
    git(worktree, "add", "-A")
    git(worktree, "commit", "-qm", "task work")
    git(sandbox.repo, "merge", "--no-ff", "-m", "merge task", "task/backend/B1-ports")


def test_done_refuses_a_temp_tree_outside_the_tmp_root(sandbox: Sandbox) -> None:
    assert sandbox.tool("new", "backend", "B1", "ports", "backend").returncode == 0
    worktree = sandbox.worktree("backend", "B1-ports")
    commit_and_merge(sandbox, worktree)

    sentinel = sandbox.repo.parent / "sentinel"
    sentinel.mkdir()
    precious = sentinel / "precious.txt"
    precious.write_text("keep\n", encoding="utf-8")
    values = read_env(worktree / ".env.task")
    values["LD_TASK_TMP"] = str(sentinel)
    write_env(worktree / ".env.task", values)

    result = sandbox.tool("done", "B1")

    assert result.returncode != 0
    assert "refusing" in result.stderr
    assert precious.read_text(encoding="utf-8") == "keep\n"
    assert worktree.is_dir()
    assert (sandbox.tmp / "task" / "backend" / "B1-ports").is_dir()


def test_done_refuses_the_tmp_root_itself(sandbox: Sandbox) -> None:
    assert sandbox.tool("new", "backend", "B1", "ports", "backend").returncode == 0
    worktree = sandbox.worktree("backend", "B1-ports")
    commit_and_merge(sandbox, worktree)

    values = read_env(worktree / ".env.task")
    values["LD_TASK_TMP"] = str(sandbox.tmp)
    write_env(worktree / ".env.task", values)

    result = sandbox.tool("done", "B1")

    assert result.returncode != 0
    assert "refusing" in result.stderr
    assert (sandbox.tmp / "task" / "backend" / "B1-ports").is_dir()
    assert worktree.is_dir()


def test_done_refuses_a_worktree_that_belongs_to_another_task(sandbox: Sandbox) -> None:
    assert sandbox.tool("new", "backend", "B1", "ports", "backend").returncode == 0
    assert sandbox.tool("new", "backend", "B2", "other", "backend").returncode == 0
    worktree = sandbox.worktree("backend", "B1-ports")
    other = sandbox.worktree("backend", "B2-other")
    commit_and_merge(sandbox, worktree)

    values = read_env(worktree / ".env.task")
    values["LD_TASK_WORKTREE"] = str(other)
    write_env(worktree / ".env.task", values)

    result = sandbox.tool("done", "B1")

    assert result.returncode != 0
    assert "refusing" in result.stderr
    assert (other / ".env.task").is_file()
    assert other.is_dir()
    assert (worktree / ".env.task").is_file()


def test_done_refuses_an_invalid_branch_in_the_env_file(sandbox: Sandbox) -> None:
    assert sandbox.tool("new", "backend", "B1", "ports", "backend").returncode == 0
    worktree = sandbox.worktree("backend", "B1-ports")
    commit_and_merge(sandbox, worktree)

    values = read_env(worktree / ".env.task")
    values["LD_TASK_BRANCH"] = "task/backend/../../escape"
    write_env(worktree / ".env.task", values)

    result = sandbox.tool("done", "B1")

    assert result.returncode != 0
    assert "not a task branch" in result.stderr
    assert worktree.is_dir()


def test_done_keeps_the_task_record_when_the_worktree_is_locked(sandbox: Sandbox) -> None:
    assert sandbox.tool("new", "backend", "B1", "ports", "backend").returncode == 0
    worktree = sandbox.worktree("backend", "B1-ports")
    commit_and_merge(sandbox, worktree)
    git(sandbox.repo, "worktree", "lock", str(worktree))

    result = sandbox.tool("done", "B1")

    assert result.returncode != 0
    assert "locked" in result.stderr
    assert (worktree / ".env.task").is_file()
    assert "B1" in sandbox.tool("list").stdout

    git(sandbox.repo, "worktree", "unlock", str(worktree))
    removed = sandbox.tool("done", "B1")

    assert removed.returncode == 0, removed.stderr
    assert not worktree.exists()
    assert not (sandbox.tmp / "task" / "backend" / "B1-ports").exists()


def test_done_accepts_the_branch_name_as_the_selector(sandbox: Sandbox) -> None:
    assert sandbox.tool("new", "backend", "B1", "ports", "backend").returncode == 0
    worktree = sandbox.worktree("backend", "B1-ports")
    commit_and_merge(sandbox, worktree)

    result = sandbox.tool("done", "task/backend/B1-ports")

    assert result.returncode == 0, result.stderr
    assert not worktree.exists()


def test_done_refuses_a_consistent_record_for_another_task(sandbox: Sandbox) -> None:
    assert sandbox.tool("new", "backend", "B1", "ports", "backend").returncode == 0
    assert sandbox.tool("new", "backend", "B2", "two", "backend").returncode == 0
    first = sandbox.worktree("backend", "B1-ports")
    second = sandbox.worktree("backend", "B2-two")
    (second / "apps/backend/extra.py").write_text("x = 1\n", encoding="utf-8")
    git(second, "add", "-A")
    git(second, "commit", "-qm", "B2 work")
    git(sandbox.repo, "merge", "--no-ff", "-m", "merge B2", "task/backend/B2-two")

    # The probe from the re-review: B1's record is internally consistent, but it
    # names B2's branch, worktree and temp with B1's id.
    values = read_env(second / ".env.task")
    values["LD_TASK_ID"] = "B1"
    write_env(first / ".env.task", values)

    result = sandbox.tool("done", "B1")

    assert result.returncode != 0
    assert "refusing" in result.stderr
    assert second.is_dir()
    assert (second / ".env.task").is_file()
    assert (sandbox.tmp / "task" / "backend" / "B2-two").is_dir()
    assert "task/backend/B2-two" in git(sandbox.repo, "branch", "--list").stdout
    assert first.is_dir()
    assert (first / ".env.task").is_file()


def test_done_restores_the_record_when_temp_removal_fails(
    sandbox: Sandbox,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert sandbox.tool("new", "backend", "B1", "ports", "backend").returncode == 0
    worktree = sandbox.worktree("backend", "B1-ports")
    commit_and_merge(sandbox, worktree)
    temp = sandbox.tmp / "task" / "backend" / "B1-ports"

    module = load_tool()
    monkeypatch.setattr(module, "WORKTREES_ROOT", sandbox.worktrees)
    monkeypatch.setattr(module, "TMP_ROOT", sandbox.tmp)
    real_remove = module._remove_temp
    failures = {"left": 1}

    def flaky_remove(path: Path) -> None:
        if failures["left"]:
            failures["left"] -= 1
            raise OSError("simulated rmtree failure")
        real_remove(path)

    monkeypatch.setattr(module, "_remove_temp", flaky_remove)

    with pytest.raises(module.LdTaskError, match="restored"):
        module.finish_task("B1")

    assert (worktree / ".env.task").is_file()
    assert not (worktree / ".git").exists()
    assert temp.is_dir()
    assert "B1" in sandbox.tool("list").stdout

    module.finish_task("B1")

    assert not worktree.exists()
    assert not temp.exists()
    assert "task/backend/B1-ports" not in git(sandbox.repo, "branch", "--list").stdout


def test_done_restores_the_record_when_branch_deletion_fails(
    sandbox: Sandbox,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert sandbox.tool("new", "backend", "B1", "ports", "backend").returncode == 0
    worktree = sandbox.worktree("backend", "B1-ports")
    commit_and_merge(sandbox, worktree)
    temp = sandbox.tmp / "task" / "backend" / "B1-ports"

    module = load_tool()
    monkeypatch.setattr(module, "WORKTREES_ROOT", sandbox.worktrees)
    monkeypatch.setattr(module, "TMP_ROOT", sandbox.tmp)
    real_git = module._git
    failures = {"left": 1}

    def flaky_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        if args[:2] == ("branch", "-D") and failures["left"]:
            failures["left"] -= 1
            raise module.LdTaskError("simulated branch delete failure")
        return real_git(repo, *args, check=check)

    monkeypatch.setattr(module, "_git", flaky_git)

    with pytest.raises(module.LdTaskError, match="restored"):
        module.finish_task("B1")

    assert (worktree / ".env.task").is_file()
    assert not (worktree / ".git").exists()
    assert not temp.exists()
    assert "B1" in sandbox.tool("list").stdout

    module.finish_task("B1")

    assert not worktree.exists()
    assert not temp.exists()
    assert "task/backend/B1-ports" not in git(sandbox.repo, "branch", "--list").stdout


def test_remove_temp_clears_read_only_files(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_tool()
    monkeypatch.setattr(module, "TMP_ROOT", sandbox.tmp)
    temp = sandbox.tmp / "task" / "backend" / "B1-ports"
    temp.mkdir(parents=True)
    locked = temp / "objects.pack"
    locked.write_text("x", encoding="utf-8")
    os.chmod(locked, stat.S_IREAD)

    module._remove_temp(temp)

    assert not temp.exists()


def test_done_refuses_a_tracked_modified_task_env(sandbox: Sandbox) -> None:
    assert sandbox.tool("new", "backend", "B1", "ports", "backend").returncode == 0
    worktree = sandbox.worktree("backend", "B1-ports")
    git(worktree, "add", "-f", ".env.task")
    git(worktree, "commit", "-qm", "track the task env")
    git(sandbox.repo, "merge", "--no-ff", "-m", "merge B1", "task/backend/B1-ports")

    env_file = worktree / ".env.task"
    env_file.write_text(env_file.read_text(encoding="utf-8") + "# edited\n", encoding="utf-8")
    result = sandbox.tool("done", "B1")

    assert result.returncode != 0
    assert "not clean" in result.stderr
    assert env_file.is_file()
    assert worktree.is_dir()


def test_done_accepts_a_cherry_picked_branch(sandbox: Sandbox) -> None:
    assert sandbox.tool("new", "backend", "B1", "ports", "backend").returncode == 0
    worktree = sandbox.worktree("backend", "B1-ports")
    (worktree / "apps/backend/extra.py").write_text("x = 1\n", encoding="utf-8")
    git(worktree, "add", "-A")
    # An older committer date keeps the cherry-picked commit from hashing to the
    # same object when both commits land in the same second.
    committed = run(
        ["git", "-C", str(worktree), "commit", "-qm", "task work"],
        cwd=worktree,
        env={
            "GIT_AUTHOR_DATE": "2020-01-01T00:00:00 +0000",
            "GIT_COMMITTER_DATE": "2020-01-01T00:00:00 +0000",
        },
    )
    assert committed.returncode == 0, committed.stderr
    commit = git(worktree, "rev-parse", "HEAD").stdout.strip()
    git(sandbox.repo, "cherry-pick", commit)
    ancestor = run(
        ["git", "-C", str(sandbox.repo), "merge-base", "--is-ancestor", "task/backend/B1-ports", "integ"],
        cwd=sandbox.repo,
    )
    assert ancestor.returncode != 0, "the cherry-picked branch must not be an ancestor"

    result = sandbox.tool("done", "B1")

    assert result.returncode == 0, result.stderr
    assert not worktree.exists()
    assert not (sandbox.tmp / "task" / "backend" / "B1-ports").exists()
    assert "task/backend/B1-ports" not in git(sandbox.repo, "branch", "--list").stdout
