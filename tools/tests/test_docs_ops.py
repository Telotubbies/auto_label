"""Mechanical guards for the application threat model (T-1306).

The model is prose, so these four checks keep it reviewable: eleven boundaries
in the security plan's order, a disposition on every STRIDE row, no card id
that does not exist, and a reason on every out-of-scope row.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "ops" / "THREAT-MODEL.md"
BACKLOG = ROOT / "docs" / "research" / "roboflow-parity" / "backlog"

BOUNDARIES = [
    "Auth/session",
    "RBAC and workspace isolation",
    "API keys",
    "Uploads",
    "safefetch/SSRF",
    "Webhooks and connectors",
    "PLC/OT",
    "MCP",
    "Workers and installers",
    "Secrets",
    "Dependency supply chain",
]


def _text() -> str:
    return DOC.read_text(encoding="utf-8")


def _section(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def _rows(block: str) -> list[list[str]]:
    """Data rows of the markdown tables in ``block`` (header and separator dropped)."""
    rows = []
    for line in block.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or set(cells[0]) <= set("-: ") or cells[0] == "Threat":
            continue
        rows.append(cells)
    return rows


def test_every_boundary_has_a_stride_table() -> None:
    headings = [line[4:].strip() for line in _text().splitlines() if line.startswith("### ")]

    assert headings == [f"{i}. {name}" for i, name in enumerate(BOUNDARIES, start=1)]
    assert _text().count("| Threat | Impact | Existing control | Residual risk | Disposition |") == 11


def test_every_row_cites_a_control_or_a_card() -> None:
    section = _section(_text(), "## 3.", "## 4.")

    for boundary in section.split("### ")[1:]:
        for cells in _rows(boundary):
            assert len(cells) == 5, f"{boundary.splitlines()[0]}: {cells}"
            assert cells[2], f"{boundary.splitlines()[0]}: empty control"
            assert re.fullmatch(r"T-\d{3,4}|accepted — .+", cells[4]), (
                f"{boundary.splitlines()[0]}: disposition {cells[4]!r}"
            )


def test_no_card_is_cited_that_does_not_exist() -> None:
    missing = sorted({card for card in re.findall(r"T-\d{3,4}", _text()) if not (BACKLOG / f"{card}.md").is_file()})

    assert not missing, f"cited cards with no file: {missing}"


def test_out_of_scope_rows_have_a_reason() -> None:
    rows = _rows(_section(_text(), "## 5.", "## 6."))

    assert rows, "the out-of-scope section has no table"
    for cells in rows:
        assert len(cells) >= 2 and len(cells[1]) > 10, f"no reason: {cells}"
