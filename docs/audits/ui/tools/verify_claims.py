import json
import pathlib

d = json.loads(pathlib.Path("docs/audits/ui/data/scan.json").read_text(encoding="utf-8"))
print("console entries:", len(d.get("console", [])))
print("login_ok:", d.get("login_ok"))
over = [(r["name"], r["mode"], r["width"], r["scan"]["overflowX"]) for r in d["routes"] if r["scan"]["overflowX"] > 0]
print("routes with document overflow:", over)
mk = [(r["name"], r["scan"]["marketing"]) for r in d["routes"] + d["public"] if r["scan"]["marketing"]]
print("routes with marketing vocabulary:", mk)
em = [(r["name"], r["scan"]["emoji"]) for r in d["routes"] + d["public"] if r["scan"]["emoji"]]
print("routes with emoji:", em)
low = [(r["name"], r["mode"], r["scan"]["lowContrastCount"]) for r in d["routes"] if r["scan"]["lowContrastCount"]]
print("routes with >=1 measured low-contrast node:", len(low))
print("route passes:", len(d["routes"]), "public passes:", len(d["public"]))
