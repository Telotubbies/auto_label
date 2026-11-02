// Task 51 evidence (fix round 2, I2): the legacy /analytics and /access URLs are a named deliverable.
// The source scan in tests/nav.test.mjs cannot resolve <Navigate to="../…">, so this exercises both
// redirects in a real browser and asserts the final URL, its query string and the rendered panel.
//
// Usage: node scripts/nav-legacy-redirects.mjs [baseUrl]
// Requires the API (default proxy :8010) and a Vite dev server serving this worktree.
import assert from 'node:assert/strict'
import { chromium, request } from 'playwright'

const base = process.argv[2] ?? process.env.LD_WEB_URL ?? 'http://localhost:5181'
const ws = process.env.LD_WS ?? 'labeldesk-demo'
const project = process.env.LD_PROJECT ?? 'ppe-detection'
const email = process.env.LD_EMAIL ?? 'demo@labeldesk.dev'
const password = process.env.LD_DEMO_PW ?? 'demo1234'
const root = `${base}/${ws}/${project}`

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
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
await context.addInitScript((keys) => {
  for (const [key, value] of Object.entries(keys)) localStorage.setItem(key, value)
}, session)
const page = await context.newPage()
const results = []

try {
  // /analytics → insights?tab=health, with the Dataset health tab selected.
  await page.goto(`${root}/analytics`, { waitUntil: 'domcontentloaded' })
  await page.waitForURL(/\/insights\?tab=health$/, { timeout: 20_000 })
  const insights = new URL(page.url())
  assert.equal(insights.pathname, `/${ws}/${project}/insights`, 'analytics landed on the wrong path')
  assert.equal(insights.searchParams.get('tab'), 'health', 'analytics lost the health tab')
  await page.locator('#insights-tab-health[aria-selected="true"]').waitFor({ state: 'visible', timeout: 20_000 })
  await page.getByRole('tabpanel', { name: 'Dataset health' }).waitFor({ state: 'visible', timeout: 20_000 })
  results.push({ from: '/analytics', to: `${insights.pathname}${insights.search}`, tab: 'health selected' })

  // /access → settings?tab=access, with the Project access panel rendered.
  await page.goto(`${root}/access`, { waitUntil: 'domcontentloaded' })
  await page.waitForURL(/\/settings\?tab=access$/, { timeout: 20_000 })
  const access = new URL(page.url())
  assert.equal(access.pathname, `/${ws}/${project}/settings`, 'access landed on the wrong path')
  assert.equal(access.searchParams.get('tab'), 'access', 'access lost the access tab')
  await page.getByRole('heading', { name: 'Project access' }).waitFor({ state: 'visible', timeout: 20_000 })
  results.push({ from: '/access', to: `${access.pathname}${access.search}`, tab: 'Project access rendered' })

  console.log(JSON.stringify({ ok: true, ws, project, results }, null, 2))
} catch (e) {
  console.log(JSON.stringify({ ok: false, landedOn: page.url(), error: String(e).split('\n')[0] }, null, 2))
  process.exitCode = 1
} finally {
  await browser.close()
}
