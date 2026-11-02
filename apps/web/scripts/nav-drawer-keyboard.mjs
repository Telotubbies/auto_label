// Task 51 evidence: the phone drawer is modal for keyboard users.
// Opens it from the top bar, checks focus moves in, Tab stays inside, Escape closes and
// focus returns to the menu button. Also captures light/dark/375 screenshots.
//
// Usage: node scripts/nav-drawer-keyboard.mjs [baseUrl] [outDir]
// Requires the API (default proxy :8010) and a Vite dev server serving this worktree.
import assert from 'node:assert/strict'
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'
import { chromium, request } from 'playwright'

const base = process.argv[2] ?? process.env.LD_WEB_URL ?? 'http://localhost:5181'
const out = process.argv[3] ?? 'artifacts/task-51'
const ws = process.env.LD_WS ?? 'labeldesk-demo'
const email = process.env.LD_EMAIL ?? 'demo@labeldesk.dev'
const password = process.env.LD_DEMO_PW ?? 'demo1234'

mkdirSync(out, { recursive: true })

const api = await request.newContext({ baseURL: base })
const login = await api.post('/api/auth/login', { data: { email, password } })
assert.ok(login.ok(), `login failed: ${login.status()} ${await login.text()}`)
const auth = await login.json()
const session = {
  ld_token: auth.token,
  ld_refresh: auth.refresh_token,
  ld_session: auth.session ?? '',
}
await api.dispose()

const browser = await chromium.launch({ headless: true })
const signedIn = async (viewport, theme = 'light') => {
  const context = await browser.newContext({ viewport })
  await context.addInitScript(([keys, mode]) => {
    for (const [key, value] of Object.entries(keys)) localStorage.setItem(key, value)
    localStorage.setItem('ld:theme', JSON.stringify({ mode }))
  }, [session, theme])
  const page = await context.newPage()
  // The shell polls GPU/jobs, so networkidle may never settle; wait for the rendered chrome instead.
  await page.goto(`${base}/${ws}`, { waitUntil: 'domcontentloaded' })
  await page.locator('header').first().waitFor({ state: 'visible', timeout: 15_000 })
  return { context, page }
}

// 375 px: open the drawer, assert the focus contract, capture it.
{
  const { context, page } = await signedIn({ width: 375, height: 812 })
  const menu = page.getByRole('button', { name: 'Open navigation menu' })
  await menu.waitFor({ state: 'visible' })
  assert.equal(await menu.getAttribute('aria-expanded'), 'false')
  await menu.click()

  const drawer = page.locator('#app-sidebar')
  await drawer.waitFor({ state: 'visible' })
  assert.equal(await menu.getAttribute('aria-expanded'), 'true')
  assert.equal(await menu.getAttribute('aria-controls'), 'app-sidebar')
  const focused = await page.evaluate(() => document.activeElement?.getAttribute('aria-label'))
  assert.equal(focused, 'Close navigation', 'opening the drawer must focus its close button')

  for (let i = 0; i < 6; i++) {
    await page.keyboard.press('Tab')
    const inside = await page.evaluate(() =>
      !!document.querySelector('#app-sidebar')?.contains(document.activeElement))
    assert.ok(inside, `Tab ${i + 1} escaped the open drawer`)
  }

  await page.screenshot({ path: join(out, 'nav-375-drawer-light.png') })
  await page.keyboard.press('Escape')
  await drawer.waitFor({ state: 'hidden' })
  await page.waitForFunction(() =>
    document.activeElement?.getAttribute('aria-label') === 'Open navigation menu')
  assert.equal(await menu.getAttribute('aria-expanded'), 'false')
  await page.waitForTimeout(100)
  await page.screenshot({ path: join(out, 'nav-375-closed-light.png') })
  await context.close()
}

// Desktop light/dark evidence of the reworked sidebar.
for (const mode of ['light', 'dark']) {
  const { context, page } = await signedIn({ width: 1440, height: 900 }, mode)
  await page.getByRole('navigation', { name: 'Workspace' }).waitFor({ state: 'visible' })
  await page.screenshot({ path: join(out, `nav-${mode}.png`) })
  await context.close()
}

await browser.close()
console.log('nav drawer keyboard test passed')
