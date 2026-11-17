"""Guards for tools/check_hygiene.py (T-1103): one failing fixture per rule, then a clean tree.

The last test scans this repository, so `pytest tools/tests` (the CI tools job and the pre-push hook)
runs the checker over the real tree as well.
"""

from __future__ import annotations

import codecs
import os
import re
import subprocess
import sys
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "check_hygiene.py"
ROOT = Path(__file__).resolve().parents[2]
CLEAN_TSX = "import { Card } from './components/card'\n\nexport const TONE = 'bg-success/15 text-success'\n"


def tree(tmp_path: Path, files: dict[str, bytes | str]) -> Path:
    """A staged-only git repo: the checker reads `git ls-files`, so `add` is enough."""
    repo = tmp_path / "repo"
    for rel, body in files.items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body.encode("utf-8") if isinstance(body, str) else body)
    repo.mkdir(exist_ok=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    return repo


def check(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def assert_reports(result: subprocess.CompletedProcess[str], path: str, line: int, rule: str) -> None:
    assert result.returncode == 1, result.stdout + result.stderr
    pattern = rf"^{re.escape(path)}:{line}: {rule}: \S"
    assert re.search(pattern, result.stdout, re.MULTILINE), result.stdout


def test_clean_tree_passes(tmp_path: Path) -> None:
    repo = tree(
        tmp_path,
        {"apps/frontend/src/App.tsx": CLEAN_TSX, "apps/backend/app/main.py": 'print("ok")\n'},
    )

    result = check(repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "clean" in result.stdout


def test_bom_in_a_source_file_fails(tmp_path: Path) -> None:
    repo = tree(tmp_path, {"apps/frontend/src/api.ts": codecs.BOM_UTF8 + b"export const x = 1\n"})

    result = check(repo)

    assert_reports(result, "apps/frontend/src/api.ts", 1, "bom")


def test_bom_in_a_licence_text_is_ignored(tmp_path: Path) -> None:
    repo = tree(tmp_path, {"apps/frontend/public/licenses.txt": codecs.BOM_UTF8 + b"MIT\n"})

    result = check(repo)

    assert result.returncode == 0, result.stdout + result.stderr


def test_mojibake_in_an_english_file_fails(tmp_path: Path) -> None:
    repo = tree(tmp_path, {"apps/backend/app/services/ocr.py": 'FIELDS = ["batch \u0e22\u0e17 assignee"]\n'})

    result = check(repo)

    assert_reports(result, "apps/backend/app/services/ocr.py", 1, "mojibake")


def test_real_thai_words_are_not_mojibake(tmp_path: Path) -> None:
    # "ป้ายทะเบียน" and "ปลายทาง" carry the ยท pair in real Thai; a Thai file is not a broken English one.
    repo = tree(
        tmp_path,
        {
            "apps/backend/tests/test_plate.py": 'PLATE = "\u0e1b\u0e49\u0e32\u0e22\u0e17\u0e30\u0e40\u0e1a\u0e35\u0e22\u0e19"\n'
        },
    )

    result = check(repo)

    assert result.returncode == 0, result.stdout + result.stderr


def test_conflict_markers_fail(tmp_path: Path) -> None:
    repo = tree(
        tmp_path,
        {"apps/frontend/src/App.tsx": ("<<<<<<< HEAD\nconst a = 1\n=======\nconst a = 2\n>>>>>>> t/1103\n")},
    )

    result = check(repo)

    assert result.returncode == 1
    assert len(re.findall(r"^apps/frontend/src/App.tsx:\d+: conflict-marker:", result.stdout, re.MULTILINE)) == 3


def test_duplicate_import_fails(tmp_path: Path) -> None:
    repo = tree(
        tmp_path,
        {
            "apps/frontend/src/App.tsx": (
                "import { Card } from './components/card'\nimport { Glass } from './components/glass'\n"
                "import { Card } from './components/card'\n"
            )
        },
    )

    result = check(repo)

    assert_reports(result, "apps/frontend/src/App.tsx", 3, "duplicate-import")


def test_raw_colour_in_a_component_fails(tmp_path: Path) -> None:
    repo = tree(
        tmp_path,
        {
            "apps/frontend/src/features/x/Badge.tsx": "export const Badge = () => <span style={{ color: '#8b5cf6' }} />\n"
        },
    )

    result = check(repo)

    assert_reports(result, "apps/frontend/src/features/x/Badge.tsx", 1, "raw-colour")


def test_raw_colour_in_a_module_is_ignored(tmp_path: Path) -> None:
    # lib/theme.ts is the one colour source; the rule only guards components.
    repo = tree(tmp_path, {"apps/frontend/src/lib/palette.ts": "export const SEED = '#3b6cf6'\n"})

    result = check(repo)

    assert result.returncode == 0, result.stdout + result.stderr


def test_allow_listed_canvas_file_passes(tmp_path: Path) -> None:
    repo = tree(
        tmp_path,
        {"apps/frontend/src/features/editor/Editor.tsx": "const STROKE = '#7c3aed'\n"},
    )

    result = check(repo)

    assert result.returncode == 0, result.stdout + result.stderr


def test_untracked_file_is_not_scanned(tmp_path: Path) -> None:
    repo = tree(tmp_path, {"apps/frontend/src/App.tsx": CLEAN_TSX})
    (repo / "apps/frontend/src/Scratch.tsx").write_text("const x = '#fff'\n", encoding="utf-8")

    result = check(repo)

    assert result.returncode == 0, result.stdout + result.stderr


def test_current_tree_is_clean_and_fast() -> None:
    started = time.perf_counter()

    result = check(ROOT)

    elapsed = time.perf_counter() - started
    assert result.returncode == 0, result.stdout + result.stderr
    assert "clean" in result.stdout
    assert elapsed < 10, f"the checker took {elapsed:.1f}s on the repository"
