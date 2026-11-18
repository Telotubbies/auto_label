import pathlib
import re

t = pathlib.Path("docs/audits/ui/UI-AUDIT.md").read_text(encoding="utf-8")
app = re.findall(r"^\| (A\d+) \|", t, re.M)
frm = re.findall(r"^\| (F\d+) \|", t, re.M)
print("app findings:", len(app), app[0], "->", app[-1])
print("frame findings:", len(frm), frm[0], "->", frm[-1])
sev = re.findall(r"^\| (?:A|F)\d+ \|.*?\| (C|I|m) \|", t, re.M)
from collections import Counter
print("severity counts:", Counter(sev))
print("claimed in scoreboard: I 25, m 29, total 54")
# top 15 check
top = re.search(r"## 4\. Top 15.*?\n(.*?)\n## 5", t, re.S).group(1)
print("top-list entries:", len(re.findall(r"^\d+\. \*\*", top, re.M)))
