#!/usr/bin/env python3
"""Group every dependency by licence and fail on an unknown one (T-1303).

    python tools/check_licenses.py      # exits 1 on a missing or non-allowlisted licence

Backend packages come from the distributions installed for `apps/backend/requirements.txt` (the CI
security job installs them with `--no-deps`, so the names are exactly what the file asks for). The web
side is read from `apps/frontend/package-lock.json`, which needs no `npm install`.

`security/licences-allow.txt` holds the licences the owner accepts, one per line. AGPL-3.0 is on that
list because Ultralytics is deliberate; the report repeats the reason so it cannot be forgotten.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "apps" / "backend" / "requirements.txt"
LOCKFILE = ROOT / "apps" / "frontend" / "package-lock.json"
ALLOWLIST = ROOT / "security" / "licences-allow.txt"

NO_LICENCE = "(no licence)"
AGPL = "AGPL-3.0"
AGPL_NOTE = "Ultralytics — deliberate, badge kept"

# Combined expressions ("MIT AND ISC", "Apache-2.0 OR BSD-3-Clause") collapse to their first family;
# every family that can appear there is on the allowlist, so the grouping loses nothing a reviewer needs.
FAMILIES = (
    ("agpl", AGPL),
    ("lgpl", "LGPL"),
    ("0bsd", "0BSD"),
    ("mit-cmu", "MIT-CMU"),
    ("apache", "Apache-2.0"),
    ("bsd", "BSD"),
    ("mit", "MIT"),
    ("isc", "ISC"),
    ("mpl", "MPL-2.0"),
    ("mozilla", "MPL-2.0"),
    ("python software foundation", "PSF"),
    ("psf", "PSF"),
    ("cc-by", "CC-BY-4.0"),
    ("gpl", "GPL"),
)
# A `License` field longer than this is a licence text, not an identifier: use the classifier instead.
MAX_IDENTIFIER = 120


def normalize_licence(raw: str | None) -> str | None:
    """Map whatever metadata says onto one allowlist family, or None when it names nothing."""
    text = (raw or "").lower()
    for needle, family in FAMILIES:
        if needle in text:
            return family
    return None


def requirement_names(path: Path = REQUIREMENTS) -> list[str]:
    names = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if not line or line.startswith("-"):
            continue
        name = re.split(r"[<>=!~\[; ]", line, 1)[0].strip()
        if name:
            names.append(name)
    return names


def licence_from_metadata(meta: metadata.PackageMetadata) -> str | None:
    raw = (meta.get("License-Expression") or meta.get("License") or "").strip()
    if len(raw) > MAX_IDENTIFIER:
        raw = ""
    if not raw:
        raw = " ".join(c for c in (meta.get_all("Classifier") or []) if c.startswith("License"))
    return normalize_licence(raw)


def backend_licences(path: Path = REQUIREMENTS) -> dict[str, str | None]:
    found: dict[str, str | None] = {}
    for name in requirement_names(path):
        try:
            meta = metadata.metadata(name)
        except metadata.PackageNotFoundError:
            found[name] = None
            continue
        found[meta.get("Name") or name] = licence_from_metadata(meta)
    return found


def lockfile_licences(path: Path = LOCKFILE) -> dict[str, str | None]:
    packages = json.loads(path.read_text(encoding="utf-8")).get("packages", {})
    found: dict[str, str | None] = {}
    for key, meta in packages.items():
        if not key or meta.get("link"):
            continue
        found[key.rsplit("node_modules/", 1)[-1]] = normalize_licence(meta.get("license"))
    return found


def read_allowlist(path: Path = ALLOWLIST) -> set[str]:
    allowed = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        licence = line.split("#")[0].strip()
        if licence:
            allowed.add(licence)
    return allowed


def evaluate(packages: dict[str, str | None], allowed: set[str]) -> tuple[int, str]:
    """Group packages under their licence, print one row per licence, and return the gate's verdict."""
    groups: dict[str, list[str]] = defaultdict(list)
    for name, licence in packages.items():
        groups[licence or NO_LICENCE].append(name)

    problems = 0
    lines = []
    for licence in sorted(groups):
        names = sorted(groups[licence])
        if licence == NO_LICENCE:
            note, problems = "  — NO LICENCE METADATA", problems + 1
        elif licence not in allowed:
            note, problems = "  — NOT ALLOWED", problems + 1
        elif licence == AGPL:
            note = f"  — WARNING: {AGPL_NOTE}"
        else:
            note = ""
        lines.append(f"{licence} ({len(names)}): {', '.join(names)}{note}")

    lines.append(f"{len(packages)} packages, {len(groups)} licences, {problems} problem(s)")
    return (1 if problems else 0), "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(prog="check_licenses", description="Group dependencies by licence.").parse_args(argv)
    packages = backend_licences() | lockfile_licences()
    code, report = evaluate(packages, read_allowlist())
    print(report)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
