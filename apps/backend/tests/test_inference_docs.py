"""T-1022: the operator runbook and the user page for the inference hub.

Both pages are Markdown, so these tests read them as text: they fail while a page is missing, and
again if a later edit drops a lock, a failure row, the estimate disclaimer or leaks a secret. No
app import: the docs are the product here, and a broken API must not hide a broken paragraph.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
RUNBOOK = REPO / "docs" / "INFERENCE-HUB.md"
# The card names `docs/inference-hub.md`; on a case-insensitive checkout (NTFS) that path is the same
# file as the runbook, so the user page carries the USERS suffix. `git mv` it back on a Linux host.
USER_PAGE = REPO / "docs" / "INFERENCE-HUB-USERS.md"

# The three locks, the worker's five env names, and one token that is never stored by the API.
FLAGS_AND_ENV = (
    "task_inference", "LD_INFERENCE_WORKSPACE", "LD_ALLOW_ENGINE_INSTALL",
    "LD_MODELS_DIR", "LD_MODELS_MAX_GB", "LD_ENGINES_DIR", "HF_TOKEN",
)
WORKER_FLAGS = ("--kinds", "--engines-dir", "--models-dir")
FAILURES = ("Driver mismatch", "Disk full", "Gated repo", "Host offline",
            "Checksum failed", "Stale plan")
SOURCES = (
    "https://blog.eleuther.ai/transformer-math/",
    "https://kipp.ly/transformer-inference-arithmetic/",
    "https://docs.vllm.ai/en/latest/configuration/conserving_memory.html",
)
TOKEN_LIKE = re.compile(r"hf_[A-Za-z0-9]{10,}")


def _read(page: Path) -> str:
    assert page.is_file(), f"missing page: {page}"
    return page.read_text(encoding="utf-8")


def _section(text: str, title: str) -> str:
    """The body of the ``##`` section titled ``title``, up to the next ``##``; a number may lead."""
    pattern = re.compile(r"^## (?:\d+\.\s*)?" + re.escape(title) + r"\s*$", re.MULTILINE)
    heading = pattern.search(text)
    assert heading, f"the runbook has no {title!r} section"
    end = text.find("\n## ", heading.end())
    return text[heading.end():] if end < 0 else text[heading.end():end]


def _rows(section: str) -> list[list[str]]:
    """A Markdown table's cells, header included; separator lines are dropped."""
    lines = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
    rows = [[cell.strip() for cell in line.strip("|").split("|")] for line in lines]
    return [row for row in rows if not all(set(cell) <= set("-: ") for cell in row)]


def test_runbook_names_every_flag_and_env():
    text = _read(RUNBOOK)
    missing = [name for name in FLAGS_AND_ENV + WORKER_FLAGS if name not in text]
    assert not missing, f"the runbook never names {missing}"


def test_runbook_has_a_rollback_section_and_a_troubleshooting_table():
    text = _read(RUNBOOK)
    rollback = _section(text, "Rollback")
    assert "task_inference" in rollback and "LD_ALLOW_ENGINE_INSTALL" in rollback, \
        "the rollback must name the flag it turns off and the worker lock it unsets"

    rows = _rows(_section(text, "Troubleshooting"))
    header, body = rows[0], rows[1:]
    assert len(body) == len(FAILURES), f"expected {len(FAILURES)} failure rows, got {len(body)}"
    first_cells = [row[0].strip("* ") for row in body]
    assert first_cells == list(FAILURES), first_cells
    # Symptom, cause, fix and the job id are what the operator acts on at 3 a.m.
    assert all(len(row) == len(header) and all(row[1:]) for row in body), rows


def test_user_page_states_that_numbers_are_estimates():
    text = _read(USER_PAGE)
    assert "estimate" in text, "the user page never calls the calculator's numbers an estimate"
    missing = [url for url in SOURCES if url not in text]
    assert not missing, f"the user page does not cite {missing}"


def test_no_page_contains_a_token_or_a_home_path():
    for page in (RUNBOOK, USER_PAGE):
        text = _read(page)
        assert not TOKEN_LIKE.search(text), f"{page.name} contains something shaped like a token"
        for marker in ("/home/", "C:\\Users"):
            assert marker not in text, f"{page.name} contains an absolute home path: {marker}"
