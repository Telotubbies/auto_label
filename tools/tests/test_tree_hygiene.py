"""Guards for the G3 tree clean-up (T-057): no leftover root test tree, no script
import outside the declared packages, and no documentation naming a linter this
repository does not ship.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "apps" / "frontend"
SCRIPTS = FRONTEND / "scripts"

IMPORT = re.compile(r"""^\s*import\s+(?:[^'"]*?\s+from\s+)?['"]([^'"]+)['"]""", re.MULTILINE)


def declared_packages() -> set[str]:
    manifest = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    return set(manifest.get("dependencies", {})) | set(manifest.get("devDependencies", {}))


def imported_packages(source: str) -> set[str]:
    found = set()
    for spec in IMPORT.findall(source):
        if spec.startswith((".", "/", "node:")):
            continue
        parts = spec.split("/")
        found.add("/".join(parts[:2]) if spec.startswith("@") else parts[0])
    return found


def test_root_tests_tree_is_gone() -> None:
    assert not (ROOT / "tests").exists(), "the leftover root tests/ tree must not come back"


def test_no_script_imports_a_dropped_module() -> None:
    packages = declared_packages()
    assert "playwright" not in packages

    for script in sorted(SCRIPTS.glob("*.mjs")):
        imports = imported_packages(script.read_text(encoding="utf-8"))
        assert "playwright" not in imports, f"{script.name} imports the dropped playwright package"
        missing = imports - packages
        assert not missing, f"{script.name} imports {sorted(missing)}, which package.json does not declare"


def test_docs_do_not_name_the_absent_linter() -> None:
    for path in (ROOT / "docs" / "STANDARDS.md", ROOT / "CONTRIBUTING.md"):
        assert "biome" not in path.read_text(encoding="utf-8").lower(), f"{path.name} still names the absent linter"
