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


# --- T-1307: the ASVS L2 and API Top 10 gap map -----------------------------------------------

GAPS = ROOT / "docs" / "ops" / "ASVS-GAPS.md"
ASVS_HEAD = "## 2. ASVS 4.0.3 Level 2"
API_HEAD = "## 3. OWASP API Security Top 10"
SUMMARY_HEAD = "## 4. Coverage summary"
OWNER_HEAD = "## 6. Questions"
STATES = ("satisfied", "card", "accepted")


def _map() -> str:
    assert GAPS.is_file(), "docs/ops/ASVS-GAPS.md is the gap map T-1307 asks for"
    text = GAPS.read_text(encoding="utf-8")
    for head in (ASVS_HEAD, API_HEAD, SUMMARY_HEAD, OWNER_HEAD):
        assert head in text, f"the map lost its section {head!r}"
    return text


def _gap_table(text: str, start: str, end: str) -> list[list[str]]:
    """Rows of a five-column gap table: id, then the row, then state, then the disposition."""
    rows = []
    for line in _section(text, start, end).splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 5 or cells[0] == "Id" or set(cells[0]) <= set("-: "):
            continue
        rows.append(cells)
    return rows


def _gap_tables() -> tuple[list[list[str]], list[list[str]]]:
    text = _map()
    return _gap_table(text, ASVS_HEAD, API_HEAD), _gap_table(text, API_HEAD, SUMMARY_HEAD)


def test_every_api_top_ten_row_exists() -> None:
    rows = _gap_tables()[1]

    assert [row[0] for row in rows] == [f"API{i}" for i in range(1, 11)]
    for row in rows:
        assert len(row[1]) > 5, f"{row[0]}: no route family"
        assert len(row[2]) > 5, f"{row[0]}: no guard named"


def test_every_gap_row_has_a_card_or_accepted() -> None:
    rows = [row for table in _gap_tables() for row in table]

    assert len(rows) >= 25, f"a map of {len(rows)} rows does not cover 14 chapters and ten API rows"
    for row in rows:
        assert row[3] in STATES, f"{row[0]}: unknown state {row[3]!r}"
        if row[3] == "satisfied":
            continue
        if row[3] == "card":
            assert re.fullmatch(r"T-\d{3,4}", row[4]), f"{row[0]}: {row[4]!r} is not one card id"
            assert (BACKLOG / f"{row[4]}.md").is_file(), f"{row[0]}: no card file for {row[4]}"
        else:
            assert len(row[4]) >= 20, f"{row[0]}: accepted with no reason: {row[4]!r}"


def test_no_row_claims_satisfied_without_evidence() -> None:
    for row in [row for table in _gap_tables() for row in table if row[3] == "satisfied"]:
        cites = re.findall(r"`([^`]+)`", row[4])

        assert cites, f"{row[0]}: satisfied with no backticked cite"
        for cite in cites:
            assert (ROOT / cite.split(":")[0]).exists(), f"{row[0]}: cite is not a path in the repo: {cite}"


def test_summary_counts_match_the_tables() -> None:
    text = _map()
    asvs_rows, api_rows = _gap_tables()
    counted: dict[str, list[int]] = {}
    for row in asvs_rows + api_rows:
        scope = "API" if row[0].startswith("API") else row[0].split(".")[0]
        counts = counted.setdefault(scope, [0, 0, 0, 0])  # satisfied, test-guarded, card, accepted
        if row[3] == "satisfied":
            counts[0] += 1
            counts[1] += "tests/" in row[4]
        elif row[3] == "card":
            counts[2] += 1
        else:
            counts[3] += 1

    summary = _section(text, SUMMARY_HEAD, OWNER_HEAD)
    claimed = {
        match[0]: [int(value) for value in match[1:]]
        for match in re.findall(r"^\| (V\d+|API|Total) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|$", summary, re.M)
    }

    assert set(claimed) == set(counted) | {"Total"}, f"summary lists {sorted(claimed)}, tables hold {sorted(counted)}"
    for scope, counts in counted.items():
        assert claimed[scope] == counts, f"{scope}: summary says {claimed[scope]}, the rows count {counts}"
    total = [sum(counts[i] for counts in counted.values()) for i in range(4)]
    assert claimed["Total"] == total, f"the total says {claimed['Total']}, the rows add up to {total}"
