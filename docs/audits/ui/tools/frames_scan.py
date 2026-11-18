import hashlib, pathlib, collections

frames = sorted(pathlib.Path("design/labeldesk-v3/frames").glob("*.png"))
by_hash = collections.defaultdict(list)
rows = []
for f in frames:
    h = hashlib.sha1(f.read_bytes()).hexdigest()[:12]
    by_hash[h].append(f.name)
    rows.append((f.name, f.stat().st_size, h))
print("frames:", len(frames))
print("\n== identical files (same bytes) ==")
for h, names in by_hash.items():
    if len(names) > 1:
        print(h, names)
print("\n== size-identical but different bytes ==")
bysize = collections.defaultdict(list)
for n, s, h in rows:
    bysize[s].append(n)
for s, names in bysize.items():
    if len(names) > 1:
        print(s, names)
