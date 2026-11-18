from playwright.sync_api import sync_playwright

BASE = "http://localhost:5173"
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    pg.goto(BASE + "/login")
    pg.wait_for_timeout(1200)
    pg.fill("input[type=email]", "demo@labeldesk.dev")
    pg.fill("input[type=password]", "demo1234")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(2500)
    pg.goto(BASE + "/labeldesk-demo/ppe-detection/browse")
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(1500)
    print(pg.evaluate("""() => {
      const out = [];
      document.querySelectorAll('*').forEach(el => {
        const a = [...el.attributes].filter(x => /image|tile|card|grid-item/i.test(x.name)).map(x => x.name + '=' + x.value);
        if (a.length) out.push(el.tagName + '.' + (el.className || '').toString().slice(0, 40) + ' :: ' + a.join(' '));
      });
      return out.slice(0, 12);
    }"""))
    pg.mouse.click(400, 400)
    pg.wait_for_timeout(2500)
    print("url after click:", pg.url)
    b.close()
