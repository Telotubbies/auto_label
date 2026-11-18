"""UI audit capture: every route, light + dark, 1440 and 375.

Read-only: navigates the running dev app, writes screenshots and a JSON report under docs/audits/ui/.
Run: python docs/audits/ui/tools/shoot.py
"""
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE = "http://localhost:5173"
WS = "labeldesk-demo"
PROJ = "ppe-detection"
OUT = pathlib.Path("docs/audits/ui/shots")
DATA = pathlib.Path("docs/audits/ui/data")
OUT.mkdir(parents=True, exist_ok=True)
DATA.mkdir(parents=True, exist_ok=True)

PUBLIC = [
    ("landing", "/"),
    ("login", "/login"),
    ("signup", "/signup"),
    ("forgot", "/forgot"),
]

ROUTES = [
    ("ws-home", f"/{WS}"),
    ("ws-models", f"/{WS}/models"),
    ("ws-playground", f"/{WS}/playground"),
    ("ws-deployments", f"/{WS}/deployments"),
    ("ws-activity", f"/{WS}/activity"),
    ("ws-audit", f"/{WS}/audit"),
    ("ws-settings", f"/{WS}/settings"),
    ("ws-members", f"/{WS}/settings/members"),
    ("ws-usage", f"/{WS}/settings/usage"),
    ("ws-apikeys", f"/{WS}/settings/api"),
    ("ws-roles", f"/{WS}/settings/roles"),
    ("ws-trash", f"/{WS}/settings/trash"),
    ("ws-dpa", f"/{WS}/legal/dpa"),
    ("p-upload", f"/{WS}/{PROJ}/upload"),
    ("p-dataset", f"/{WS}/{PROJ}/browse"),
    ("p-versions", f"/{WS}/{PROJ}/versions"),
    ("p-insights", f"/{WS}/{PROJ}/insights"),
    ("p-classes", f"/{WS}/{PROJ}/classes"),
    ("p-model-insights", f"/{WS}/{PROJ}/model-insights"),
    ("p-annotate", f"/{WS}/{PROJ}/annotate"),
    ("p-train", f"/{WS}/{PROJ}/train"),
    ("p-models", f"/{WS}/{PROJ}/models"),
    ("p-deploy", f"/{WS}/{PROJ}/deploy"),
    ("p-settings", f"/{WS}/{PROJ}/settings"),
    ("p-settings-access", f"/{WS}/{PROJ}/settings?tab=access"),
    # flag-gated: kept to prove what a signed-in admin sees when the flag is off
    ("p-streams-flagged", f"/{WS}/{PROJ}/streams"),
    ("p-qa-flagged", f"/{WS}/{PROJ}/qa"),
]

# Injected on every page: contrast + type + copy scan.
SCAN = r"""
() => {
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const ctx = cv.getContext('2d', { willReadFrequently: true });
  const toRgba = (color) => {
    ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = '#000'; ctx.fillStyle = color; ctx.fillRect(0, 0, 1, 1);
    const d = ctx.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2], d[3] / 255];
  };
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const over = (fg, bg) => [0, 1, 2].map(i => Math.round(fg[i] * fg[3] + bg[i] * (1 - fg[3])));
  const ratio = (a, b) => { const l1 = lum(a), l2 = lum(b); return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05); };
  const path = (el) => { const p = []; let n = el;
    while (n && n.nodeType === 1 && p.length < 5) { let s = n.tagName.toLowerCase();
      if (n.id) s += '#' + n.id;
      const cl = (n.className && typeof n.className === 'string') ? n.className.trim().split(/\s+/).slice(0, 3).join('.') : '';
      if (cl) s += '.' + cl; p.unshift(s); n = n.parentElement; } return p.join('>'); };

  const low = [], tiny = []; let unknownBg = 0;
  const els = Array.from(document.querySelectorAll('body *'));
  for (const el of els) {
    const tag = el.tagName.toLowerCase();
    if (tag === 'script' || tag === 'style' || tag === 'svg' || el.closest('svg')) continue;
    const direct = Array.from(el.childNodes).some(n => n.nodeType === 3 && n.textContent.trim().length > 1);
    if (!direct) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) < 0.15) continue;
    const size = parseFloat(cs.fontSize);
    if (size < 12) tiny.push({ sel: path(el), text: el.textContent.trim().slice(0, 60), px: size });
    const fg = toRgba(cs.color);
    let node = el, bg = null, blocked = false;
    while (node && node !== document.documentElement) {
      const s = getComputedStyle(node);
      if (s.backgroundImage && s.backgroundImage !== 'none') { blocked = true; break; }
      const b = toRgba(s.backgroundColor);
      if (b[3] > 0.85) { bg = b; break; }
      node = node.parentElement;
    }
    if (blocked) { unknownBg++; continue; }
    if (!bg) bg = [255, 255, 255, 1];
    const fgC = fg[3] < 1 ? over(fg, bg) : [fg[0], fg[1], fg[2]];
    const cr = ratio(fgC, [bg[0], bg[1], bg[2]]);
    const bold = parseInt(cs.fontWeight, 10) >= 700;
    const large = size >= 24 || (bold && size >= 18.66);
    const need = large ? 3 : 4.5;
    if (cr < need) low.push({ sel: path(el), text: el.textContent.trim().slice(0, 60), px: size, ratio: Math.round(cr * 100) / 100, need });
  }
  const headings = Array.from(document.querySelectorAll('h1,h2')).map(h => ({ tag: h.tagName, text: h.textContent.trim().slice(0, 90) })).filter(h => h.text);
  const text = document.body.innerText || '';
  const marketing = ['Unlock', 'Seamless', 'Supercharge', 'Empower', 'Effortless', 'Revolution', 'AI-powered', 'Next-gen', 'Elevate', 'Transform your', 'Game-chang', 'Cutting-edge', 'Best-in-class', 'World-class', 'Leverage', 'Blazing', 'Simply', 'Just '].filter(w => text.includes(w));
  const emoji = (text.match(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu) || []).slice(0, 10);
  const buttons = Array.from(document.querySelectorAll('button,a[role=button],a')).filter(b => { const r = b.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
  const small = buttons.filter(b => { const r = b.getBoundingClientRect(); return (r.width < 24 || r.height < 24); }).length;
  return {
    lowContrast: low.slice(0, 40), lowContrastCount: low.length,
    tinyText: tiny.slice(0, 25), tinyTextCount: tiny.length,
    unknownBg, headings, marketing, emoji,
    overflowX: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
    docHeight: document.documentElement.scrollHeight,
    smallTargets: small, buttons: buttons.length,
  };
}
"""


def settle(page, ms=900):
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(ms)


def main():
    report = {"public": [], "routes": []}
    console = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.on("console", lambda m: console.append({"type": m.type, "text": m.text[:300], "url": page.url}) if m.type == "error" else None)
        page.on("pageerror", lambda e: console.append({"type": "pageerror", "text": str(e)[:300], "url": page.url}))

        # signed-out surfaces
        for name, path in PUBLIC:
            page.goto(BASE + path, wait_until="domcontentloaded")
            settle(page)
            page.screenshot(path=str(OUT / f"{name}-light-1440.png"), full_page=True)
            report["public"].append({"name": name, "path": path, "scan": page.evaluate(SCAN)})

        # log in through the real form so the flow itself is audited
        page.goto(BASE + "/login", wait_until="domcontentloaded")
        settle(page)
        page.fill("input[type=email]", "demo@labeldesk.dev")
        page.fill("input[type=password]", "demo1234")
        page.click("button[type=submit]")
        page.wait_for_timeout(2500)
        logged = page.evaluate("() => !!localStorage.getItem('ld_token')")
        report["login_ok"] = logged
        if not logged:
            print("LOGIN FAILED", file=sys.stderr)
            browser.close()
            return 1

        state = ctx.storage_state()

        def shoot(ctx_, mode, w, h, tag):
            pg = ctx_.new_page()
            errs = []
            pg.on("console", lambda m: errs.append(m.text[:200]) if m.type == "error" else None)
            pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            pg.goto(BASE + "/login", wait_until="domcontentloaded")
            pg.evaluate("(m) => localStorage.setItem('ld:theme', JSON.stringify({mode: m}))", mode)
            for name, path in ROUTES:
                pg.goto(BASE + path, wait_until="domcontentloaded")
                settle(pg)
                final = pg.url.replace(BASE, "")
                scan = pg.evaluate(SCAN)
                pg.screenshot(path=str(OUT / f"{name}-{tag}.png"), full_page=True)
                report["routes"].append({"name": name, "path": path, "mode": mode, "width": w, "final": final, "scan": scan, "errors": errs[-6:]})
                errs.clear()
            pg.close()

        shoot(ctx, "light", 1440, 900, "light-1440")

        # dark pass: same context, theme pref persisted
        ctxd = browser.new_context(viewport={"width": 1440, "height": 900}, storage_state=state)
        shoot(ctxd, "dark", 1440, 900, "dark-1440")
        ctxd.close()

        # 375 px pass
        mob = browser.new_context(viewport={"width": 375, "height": 812}, storage_state=state, is_mobile=True, has_touch=True)
        shoot(mob, "light", 375, 812, "light-375")
        mob.close()
        mobd = browser.new_context(viewport={"width": 375, "height": 812}, storage_state=state, is_mobile=True, has_touch=True)
        shoot(mobd, "dark", 375, 812, "dark-375")
        mobd.close()

        report["console"] = console[-80:]
        browser.close()

    (DATA / "scan.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"routes captured: {len(report['routes'])}; public: {len(report['public'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
