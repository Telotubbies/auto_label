"""The licence gate (T-1303): every backend and frontend package is grouped by licence.

A licence outside `security/licences-allow.txt` blocks; a missing licence blocks; AGPL-3.0 is allowed
because Ultralytics is deliberate, and the report says so.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_tool(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


licences = load_tool("check_licenses")


def test_allowlisted_licence_passes() -> None:
    code, report = licences.evaluate({"fastapi": "MIT", "numpy": "BSD"}, {"MIT", "BSD"})

    assert code == 0, report
    assert "MIT (1): fastapi" in report
    assert "BSD (1): numpy" in report


def test_unknown_licence_blocks() -> None:
    code, report = licences.evaluate({"mystery-pkg": "Proprietary-1.0"}, {"MIT"})

    assert code == 1
    assert "Proprietary-1.0" in report
    assert "mystery-pkg" in report
    assert "NOT ALLOWED" in report


def test_agpl_warns_and_names_ultralytics() -> None:
    code, report = licences.evaluate({"ultralytics": "AGPL-3.0"}, {"AGPL-3.0"})

    assert code == 0, report
    assert "AGPL-3.0" in report
    assert "Ultralytics" in report
    assert "deliberate" in report


def test_agpl_still_blocks_when_it_is_not_on_the_allowlist() -> None:
    code, report = licences.evaluate({"ultralytics": "AGPL-3.0"}, {"MIT"})

    assert code == 1
    assert "NOT ALLOWED" in report


def test_missing_licence_metadata_blocks() -> None:
    code, report = licences.evaluate({"mystery-pkg": None}, {"MIT"})

    assert code == 1
    assert "no licence metadata" in report.lower()


def test_npm_lock_side_is_read(tmp_path: Path) -> None:
    lock = tmp_path / "package-lock.json"
    lock.write_text(
        json.dumps(
            {
                "lockfileVersion": 3,
                "packages": {
                    "": {"name": "labeldesk-web", "version": "0.1.0"},
                    "node_modules/alpha": {"version": "1.0.0", "license": "MIT"},
                    "node_modules/@scope/beta": {"version": "2.0.0", "license": "ISC"},
                    "node_modules/mystery": {"version": "3.0.0"},
                },
            }
        ),
        encoding="utf-8",
    )

    found = licences.lockfile_licences(lock)

    assert found == {"alpha": "MIT", "@scope/beta": "ISC", "mystery": None}


def test_output_is_grouped_by_licence() -> None:
    _, report = licences.evaluate({"beta": "MIT", "alpha": "MIT", "gamma": "BSD"}, {"MIT", "BSD"})

    assert "MIT (2): alpha, beta" in report
    assert report.count("MIT (") == 1
