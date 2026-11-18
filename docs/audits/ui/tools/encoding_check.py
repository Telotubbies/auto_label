import pathlib
import re

roots = [pathlib.Path("apps/frontend/src")]
bad = []
for root in roots:
    for f in root.rglob("*.tsx"):
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            bad.append((str(f), "NOT UTF-8", str(e)))
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if "\ufffd" in line:
                bad.append((str(f), i, line.strip()[:140]))
print("files/lines with U+FFFD replacement char:", len(bad))
for b in bad[:40]:
    print(b)
