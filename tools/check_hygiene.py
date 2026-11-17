#!/usr/bin/env python3
"""Fail on the damage a merge leaves behind in `apps/` and `packages/`.

Every rule the merge captain used to fix by hand has a check here:

    python tools/check_hygiene.py        # exits 1 and prints path:line: rule: hint

Rules: a UTF-8 BOM, cp874 mojibake in a file that is meant to be English, conflict markers, one
import line twice in a TS/TSX file, and a raw colour in a component (theme tokens live in
`lib/theme.ts` and `index.css`, per design/labeldesk-v3/VISUAL-OVERRIDE.md).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SCAN_DIRS = ("apps", "packages")
# Text files a merge can damage. `.txt` and images are data, not source: a BOM there is harmless.
TEXT_SUFFIXES = frozenset(
    {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".css",
        ".json",
        ".yml",
        ".yaml",
        ".toml",
        ".sh",
        ".sql",
        ".html",
    }
)
MOJIBAKE_SEQUENCES = ("เธ", "โ’", "ยท")
# Thai is the point of the Thai catalogue, so it is never mojibake there.
MOJIBAKE_SAFE = frozenset({"apps/frontend/src/lib/i18n.ts"})
# VISUAL-OVERRIDE.md §1-2 keeps the chart, canvas and video surfaces solid, and a canvas cannot resolve a
# CSS variable. Each entry names why; T-495 owns folding these onto the one colour source.
RAW_COLOUR_ALLOWED = {
    "apps/frontend/src/features/editor/Editor.tsx": "Konva canvas strokes",
    "apps/frontend/src/features/evaluation/EvalPanel.tsx": "text over the viridis scale",
    "apps/frontend/src/features/insights/charts.tsx": "canvas colour normaliser",
    "apps/frontend/src/features/playground/Playground.tsx": "canvas boxes",
    "apps/frontend/src/features/project/AutoLabelDialog.tsx": "canvas colour fallback",
    "apps/frontend/src/features/project/Deploy.tsx": "canvas boxes",
    "apps/frontend/src/features/project/VideoTimeline.tsx": "canvas colour fallback",
    "apps/frontend/src/features/settings/Settings.tsx": "HCT seed swatches, the theme source",
    "apps/frontend/src/features/streams/ZoneEditor.tsx": "SVG overlay on the video frame",
}
CONFLICT_MARKER = re.compile(r"^(?:<<<<<<< |=======$|>>>>>>> )")
IMPORT_LINE = re.compile(r"^\s*import\s[^\n]*?\bfrom\s+['\"][^'\"]+['\"];?$")
RAW_COLOUR = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b|rgba?\(")
THAI = re.compile("[\u0e00-\u0e7f]")
HINTS = {
    "bom": "strip the byte-order mark; an editor added it on save",
    "mojibake": "cp874 bytes replaced '·' or '→'; retype the line as UTF-8",
    "conflict-marker": "a merge left a conflict marker here; resolve it",
    "duplicate-import": "the same import line appears twice; drop one",
    "raw-colour": "use a token from lib/theme.ts or index.css, or allow-list the file with a reason",
}


def _tracked(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", *SCAN_DIRS],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        print(f"check_hygiene: error: {result.stderr.strip() or 'git ls-files failed'}", file=sys.stderr)
        raise SystemExit(2)
    return [path for path in result.stdout.split("\0") if path]


def _is_english(text: str) -> bool:
    """A real Thai word is three characters or more, so a file carrying one is Thai, not broken English."""
    for sequence in MOJIBAKE_SEQUENCES:
        text = text.replace(sequence, "")
    return len(THAI.findall(text)) < 3


def _lines(path: str, text: str) -> list[str]:
    findings = []
    if text.startswith("\ufeff"):
        findings.append(f"{path}:1: bom: {HINTS['bom']}")
        text = text[1:]
    if path not in MOJIBAKE_SAFE and _is_english(text):
        for sequence in MOJIBAKE_SEQUENCES:
            for number, line in enumerate(text.splitlines(), 1):
                if sequence in line:
                    findings.append(f"{path}:{number}: mojibake: {HINTS['mojibake']}")
                    break
    seen: dict[str, int] = {}
    for number, line in enumerate(text.splitlines(), 1):
        if CONFLICT_MARKER.match(line):
            findings.append(f"{path}:{number}: conflict-marker: {HINTS['conflict-marker']}")
        if path.endswith((".ts", ".tsx")) and IMPORT_LINE.match(line):
            import_line = line.strip()
            if import_line in seen:
                findings.append(f"{path}:{number}: duplicate-import: {HINTS['duplicate-import']}")
            else:
                seen[import_line] = number
        if path.startswith("apps/frontend/src/") and path.endswith(".tsx") and path not in RAW_COLOUR_ALLOWED:
            if RAW_COLOUR.search(line):
                findings.append(f"{path}:{number}: raw-colour: {HINTS['raw-colour']}")
    return findings


def check(root: Path) -> list[str]:
    findings: list[str] = []
    scanned = 0
    for path in _tracked(root):
        if Path(path).suffix.lower() not in TEXT_SUFFIXES:
            continue
        scanned += 1
        text = (root / path).read_bytes().decode("utf-8", errors="replace")
        findings.extend(_lines(path, text))
    if not findings:
        print(f"hygiene: clean ({scanned} files)")
    return findings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_hygiene",
        description="Reject BOMs, mojibake, conflict markers, duplicate imports and raw colours.",
    )
    parser.add_argument("--root", type=Path, default=Path("."), help="repository root (default: .)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    findings = check(args.root)
    for finding in findings:
        print(finding)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
