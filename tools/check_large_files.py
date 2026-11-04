#!/usr/bin/env python3
"""Fail when a commit adds data, model weights or an oversized file.

CI runs this over the commits in a push or pull request, so pre-existing large
files do not block unrelated work:

    python tools/check_large_files.py --base "$BASE_SHA" --head HEAD
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# The empty tree object is a fixed SHA in every repository; a root commit has no
# parent, so diffing against it treats every file in that commit as added.
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
FORBIDDEN_PREFIXES = ("data/", "yolo26_ppe/models/", "sam3_auto_label/checkpoints/")
FORBIDDEN_SUFFIXES = (
    ".pt",
    ".pth",
    ".onnx",
    ".engine",
    ".ckpt",
    ".safetensors",
    ".zip",
    ".tar",
    ".tar.gz",
    ".tgz",
)
DEFAULT_MAX_KB = 2048


class CheckError(RuntimeError):
    pass


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and result.returncode != 0:
        raise CheckError(result.stderr.strip() or "git failed")
    return result


def _rev(repo: Path, rev: str) -> str | None:
    if not rev:
        return None
    result = _git(repo, "rev-parse", "--verify", f"{rev}^{{commit}}", check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _base_for(repo: Path, base: str, head_sha: str) -> str:
    resolved = _rev(repo, base)
    if resolved:
        return resolved
    parent = _rev(repo, f"{head_sha}^")
    return parent or EMPTY_TREE


def _added_paths(repo: Path, base: str, head: str) -> list[str]:
    result = _git(repo, "diff", "--name-only", "--diff-filter=AR", "-z", base, head)
    return [path for path in result.stdout.split("\0") if path]


def _tree_sizes(repo: Path, head: str) -> dict[str, int]:
    result = _git(repo, "ls-tree", "-r", "-l", "-z", head)
    sizes: dict[str, int] = {}
    for record in result.stdout.split("\0"):
        if not record:
            continue
        meta, _, path = record.partition("\t")
        fields = meta.split()
        if len(fields) < 4 or not fields[3].isdigit():
            continue
        sizes[path] = int(fields[3])
    return sizes


def _violation(path: str, size: int, max_bytes: int) -> str | None:
    normalized = path.replace("\\", "/")
    for prefix in FORBIDDEN_PREFIXES:
        if normalized.startswith(prefix):
            return f"forbidden path '{prefix}'"
    lower = normalized.lower()
    for suffix in FORBIDDEN_SUFFIXES:
        if lower.endswith(suffix):
            return f"forbidden suffix '{suffix}'"
    if size > max_bytes:
        return f"{size / 1024 / 1024:.1f} MB > {max_bytes / 1024 / 1024:.1f} MB"
    return None


def check(repo: Path, base: str, head: str, max_kb: int) -> int:
    head_sha = _rev(repo, head)
    if head_sha is None:
        raise CheckError(f"unknown revision '{head}'")
    base_sha = _base_for(repo, base, head_sha)
    paths = _added_paths(repo, base_sha, head_sha)
    sizes = _tree_sizes(repo, head_sha)
    max_bytes = max_kb * 1024

    failures = []
    for path in paths:
        reason = _violation(path, sizes.get(path, 0), max_bytes)
        if reason:
            failures.append(f"{path}: {reason}")

    for line in failures:
        print(line)
    if failures:
        return 1
    print(f"no large files added ({len(paths)} added or renamed)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_large_files",
        description="Reject added data, model weights and files over --max-kb.",
    )
    parser.add_argument("--repo", type=Path, default=Path("."), help="repository to inspect (default: .)")
    parser.add_argument(
        "--base",
        default="",
        help="base revision; an unknown or empty value falls back to HEAD^ (or the empty tree)",
    )
    parser.add_argument("--head", default="HEAD", help="head revision (default: HEAD)")
    parser.add_argument("--max-kb", type=int, default=DEFAULT_MAX_KB, help="size limit in KiB (default: 2048)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return check(args.repo, args.base, args.head, args.max_kb)
    except CheckError as error:
        print(f"check_large_files: error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
