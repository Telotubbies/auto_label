import pathlib
import re

REQUIRED = [
    "## User story", "## UX flow (LabelDesk words)", "## Backend changes", "## Frontend changes",
    "## Files", "## Tests to write first", "## Acceptance criteria", "## Notes for the implementer",
]
FIELDS = ["Wave", "Parity rows", "Size", "Role", "Skills", "R7 security review", "Depends on", "Feature flag"]

base = pathlib.Path("docs/research/roboflow-parity/backlog")
ok = True
total_hours = 0
for n in range(520, 526):
    p = base / f"T-{n}.md"
    if not p.exists():
        print("MISSING", p)
        ok = False
        continue
    t = p.read_text(encoding="utf-8")
    missing = [h for h in REQUIRED if h not in t]
    fields = [f for f in FIELDS if f"| {f} |" not in t]
    hours = re.search(r"→ (\d+(?:\.\d+)?) agent-hours", t)
    if hours:
        total_hours += float(hours.group(1))
    status = "ok" if not missing and not fields and hours else "PROBLEM"
    if status != "ok":
        ok = False
    print(f"T-{n}: {status} hours={hours.group(1) if hours else '?'} missing_sections={missing} missing_fields={fields}")

print("total hours:", total_hours)
print("first line of each card:")
for n in range(520, 526):
    print("  ", (base / f"T-{n}.md").read_text(encoding="utf-8").splitlines()[0])
print("ALL OK" if ok else "PROBLEMS FOUND")
