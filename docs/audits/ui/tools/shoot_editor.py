"""Editor + interaction captures: open the editor from the dataset grid, focus states, mobile menu."""
import pathlib
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5173"
OUT = pathlib.Path("docs/audits/ui/shots")
OUT.mkdir(parents=True, exist_ok=True)


def settle(page, ms=1200):
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(ms)


with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    pg.goto(BASE + "/login", wait_until="domcontentloaded")
    settle(pg)
    pg.fill("input[type=email]", "demo@labeldesk.dev")
    pg.fill("input[type=password]", "demo1234")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(2500)

    # light: dataset grid -> open the first tile
    pg.goto(BASE + "/labeldesk-demo/ppe-detection/browse", wait_until="domcontentloaded")
    settle(pg)
    # focus ring proof: tab a few times and shoot
    pg.keyboard.press("Tab")
    pg.keyboard.press("Tab")
    pg.keyboard.press("Tab")
    pg.screenshot(path=str(OUT / "focus-ring-tab-light-1440.png"))

    tile = pg.locator("div[role=button][aria-label^='Open ']").first
    tile.click()
    pg.wait_for_timeout(3000)
    print("editor url:", pg.url)
    if "/images/" in pg.url:
        pg.goto(pg.url, wait_until="domcontentloaded")
        settle(pg, 2500)
        pg.screenshot(path=str(OUT / "editor-light-1440.png"), full_page=True)
        pg.evaluate("() => localStorage.setItem('ld:theme', JSON.stringify({mode:'dark'}))")
        pg.reload(wait_until="domcontentloaded")
        settle(pg, 2500)
        pg.screenshot(path=str(OUT / "editor-dark-1440.png"), full_page=True)
    pg.close()

    # 375 px: sidebar becomes a drawer; capture the open state
    m = b.new_context(viewport={"width": 375, "height": 812}, is_mobile=True, has_touch=True)
    mp = m.new_page()
    mp.goto(BASE + "/login", wait_until="domcontentloaded")
    settle(mp)
    mp.fill("input[type=email]", "demo@labeldesk.dev")
    mp.fill("input[type=password]", "demo1234")
    mp.click("button[type=submit]")
    mp.wait_for_timeout(2500)
    mp.goto(BASE + "/labeldesk-demo/ppe-detection/browse", wait_until="domcontentloaded")
    settle(mp)
    mp.screenshot(path=str(OUT / "m-dataset-375.png"), full_page=True)
    # try to open whatever menu button exists
    for sel in ("[aria-label*='menu' i]", "button[aria-label*='Menu' i]", "header button", "[data-testid='menu']"):
        loc = mp.locator(sel)
        if loc.count():
            try:
                loc.first.click(timeout=1500)
                mp.wait_for_timeout(600)
                mp.screenshot(path=str(OUT / "m-menu-open-375.png"))
                print("opened menu via", sel)
                break
            except Exception as exc:
                print("menu click failed", sel, exc)
    m.close()
    b.close()
