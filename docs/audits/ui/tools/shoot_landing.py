"""Landing page: scroll through so reveal-on-scroll sections paint, then capture section by section."""
import pathlib
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5173"
OUT = pathlib.Path("docs/audits/ui/shots")

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    for mode in ("light", "dark"):
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        pg = ctx.new_page()
        pg.goto(BASE + "/", wait_until="domcontentloaded")
        pg.evaluate("(m) => localStorage.setItem('ld:theme', JSON.stringify({mode: m}))", mode)
        pg.reload(wait_until="networkidle")
        pg.wait_for_timeout(800)
        h = pg.evaluate("() => document.documentElement.scrollHeight")
        y = 0
        while y < h:
            pg.mouse.wheel(0, 700)
            pg.wait_for_timeout(220)
            y += 700
        pg.wait_for_timeout(600)
        pg.screenshot(path=str(OUT / f"landing-{mode}-1440-scrolled.png"), full_page=True)
        print(mode, "height", h, "final scroll", pg.evaluate("() => window.scrollY"))
        ctx.close()
    b.close()
