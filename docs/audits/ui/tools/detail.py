import json, pathlib, collections

d = json.loads(pathlib.Path("docs/audits/ui/data/scan.json").read_text(encoding="utf-8"))
rows = collections.defaultdict(dict)
for r in d["routes"]:
    rows[r["name"]][f"{r['mode']}-{r['width']}"] = r

print("== LOW CONTRAST DETAIL ==")
for name, modes in rows.items():
    for k, r in modes.items():
        for f in r["scan"]["lowContrast"]:
            print(f"{name:18} {k:11} {f['ratio']:5}/{f['need']} {f['px']:4}px {f['text'][:45]!r}  {f['sel'][:90]}")

print("\n== TINY TEXT (<12px) DETAIL (light-1440) ==")
for name, modes in rows.items():
    r = modes.get("light-1440")
    if not r: continue
    if not r["scan"]["tinyText"]: continue
    print(f"-- {name} ({r['scan']['tinyTextCount']}) --")
    for f in r["scan"]["tinyText"][:8]:
        print(f"   {f['px']:5}px {f['text'][:50]!r} {f['sel'][:80]}")

print("\n== HEADINGS ==")
for name, modes in rows.items():
    r = modes.get("light-1440")
    if not r: continue
    hs = [(h["tag"], h["text"]) for h in r["scan"]["headings"]]
    print(f"{name:18} {hs}")
