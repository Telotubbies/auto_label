import json, pathlib, collections

d = json.loads(pathlib.Path("docs/audits/ui/data/scan.json").read_text(encoding="utf-8"))

print("== public ==")
for p in d["public"]:
    s = p["scan"]
    print(f"{p['name']:12} tiny={s['tinyTextCount']:3} low={s['lowContrastCount']:3} ovf={s['overflowX']} smallT={s['smallTargets']}/{s['buttons']} mk={s['marketing']}")

print("\n== redirects (final != path) ==")
seen = set()
for r in d["routes"]:
    if r["final"].split("?")[0] != r["path"].split("?")[0]:
        k = (r["name"], r["final"])
        if k not in seen:
            seen.add(k); print(f"{r['name']:20} {r['path']:45} -> {r['final']}")

print("\n== per route (light 1440 / dark 1440 / 375 light) ==")
rows = collections.defaultdict(dict)
for r in d["routes"]:
    rows[r["name"]][f"{r['mode']}-{r['width']}"] = r
for name, modes in rows.items():
    out = []
    for k in ("light-1440", "dark-1440", "light-375", "dark-375"):
        r = modes.get(k)
        if not r: continue
        s = r["scan"]
        out.append(f"{k}: low={s['lowContrastCount']:2} tiny={s['tinyTextCount']:2} ovf={s['overflowX']:3} tgt={s['smallTargets']:2}")
    print(f"{name:20} " + " | ".join(out))

print("\n== console errors ==")
for c in d["console"][-40:]:
    print(f"{c['type']:9} {c['url'][-45:]:45} {c['text'][:120]}")

print("\n== marketing words by route ==")
for r in d["routes"]:
    if r["scan"]["marketing"]:
        print(r["name"], r["mode"], r["width"], r["scan"]["marketing"])

print("\n== emoji ==")
for r in d["routes"]:
    if r["scan"]["emoji"]:
        print(r["name"], r["mode"], r["width"], r["scan"]["emoji"])
