from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "check_large_files.py"
MB = 1024 * 1024


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    result = run(["git", "-C", str(repo), *args], cwd=repo)
    assert result.returncode == 0, result.stderr
    return result


def commit(repo: Path, message: str = "commit") -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", message)
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def check(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return run([sys.executable, str(SCRIPT), "--repo", str(repo), *args], cwd=repo)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "large-files@example.test")
    git(path, "config", "user.name", "large files test")
    (path / "README.md").write_text("readme\n", encoding="utf-8")
    commit(path, "initial")
    return path


def test_small_added_file_passes(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD").stdout.strip()
    (repo / "notes.txt").write_text("small\n", encoding="utf-8")
    commit(repo, "small")

    result = check(repo, "--base", base, "--head", "HEAD")

    assert result.returncode == 0, result.stderr
    assert "no large files" in result.stdout


def test_added_file_over_the_limit_fails(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD").stdout.strip()
    (repo / "big.bin").write_bytes(b"x" * (3 * MB))
    commit(repo, "big")

    result = check(repo, "--base", base, "--head", "HEAD")

    assert result.returncode != 0
    assert "big.bin" in result.stdout
    assert "2.0 MB" in result.stdout


def test_added_data_file_fails_even_when_small(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD").stdout.strip()
    (repo / "data" / "raw").mkdir(parents=True)
    (repo / "data" / "raw" / "x.jpg").write_text("image\n", encoding="utf-8")
    commit(repo, "data")

    result = check(repo, "--base", base, "--head", "HEAD")

    assert result.returncode != 0
    assert "data/raw/x.jpg" in result.stdout
    assert "data/" in result.stdout


@pytest.mark.parametrize("name", ["model.pt", "model.onnx", "bundle.zip", "weights/check.ckpt"])
def test_added_model_weight_file_fails(repo: Path, name: str) -> None:
    base = git(repo, "rev-parse", "HEAD").stdout.strip()
    target = repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("weight\n", encoding="utf-8")
    commit(repo, "weights")

    result = check(repo, "--base", base, "--head", "HEAD")

    assert result.returncode != 0
    assert name in result.stdout


def test_preexisting_large_file_in_the_base_is_not_flagged(repo: Path) -> None:
    (repo / "old.bin").write_bytes(b"x" * (3 * MB))
    base = commit(repo, "old large file")
    (repo / "notes.txt").write_text("small\n", encoding="utf-8")
    commit(repo, "small")

    result = check(repo, "--base", base, "--head", "HEAD")

    assert result.returncode == 0, result.stderr


def test_missing_base_falls_back_to_the_tip_commit(repo: Path) -> None:
    (repo / "old.bin").write_bytes(b"x" * (3 * MB))
    commit(repo, "old large file")
    (repo / "notes.txt").write_text("small\n", encoding="utf-8")
    commit(repo, "small")

    result = check(repo, "--base", "0" * 40, "--head", "HEAD")

    assert result.returncode == 0, result.stderr


def test_root_commit_with_a_large_file_fails(repo: Path) -> None:
    root = repo.parent / "root-repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "large-files@example.test")
    git(root, "config", "user.name", "large files test")
    (root / "big.bin").write_bytes(b"x" * (3 * MB))
    commit(root, "root")

    result = check(root, "--base", "0" * 40, "--head", "HEAD")

    assert result.returncode != 0
    assert "big.bin" in result.stdout


def test_rename_into_data_fails(repo: Path) -> None:
    (repo / "model.txt").write_text("model\n", encoding="utf-8")
    commit(repo, "add model")
    base = git(repo, "rev-parse", "HEAD").stdout.strip()
    (repo / "data").mkdir()
    git(repo, "mv", "model.txt", "data/model.txt")
    commit(repo, "move into data")

    result = check(repo, "--base", base, "--head", "HEAD")

    assert result.returncode != 0
    assert "data/model.txt" in result.stdout
