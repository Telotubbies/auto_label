// Task 40 screenshots: sign in, seed two OT outputs through the API, capture light/dark/375.
// Usage: node scripts/ot-shot.mjs <webUrl> <apiUrl> <outDir>
// Requires the API on the apiUrl and the Vite dev server on the webUrl.
import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'

const [web = 'http://localhost:5173', api = 'http://localhost:8010', out = '.'] = process.argv.slice(2)
const WS = 'labeldesk-demo'
const PR = 'ppe-detection'
mkdirSync(out, { recursive: true })

const browser = await chromium.launch()
const results = []
for (const [name, width, scheme] of [['light', 1440, 'light'], ['dark', 1440, 'dark'], ['375', 375, 'light']]) {
  const context = await browser.newContext({
    viewport: { width, height: 1000 }, colorScheme: scheme, reducedMotion: 'reduce', deviceScaleFactor: 1,
  })
  const page = await context.newPage()
  await page.addInitScript((mode) => localStorage.setItem('ld:theme', JSON.stringify({ mode })), scheme)
  await page.goto(`${web}/login`, { waitUntil: 'domcontentloaded' })
  await page.fill('#login-email', 'demo@labeldesk.dev')
  await page.fill('#login-password', 'demo1234')
  await page.click('button[type=submit]')
  await page.waitForFunction(() => !!localStorage.getItem('ld_token'), null, { timeout: 15000 })
  const auth = await context.request.post(`${api}/api/auth/login`,
    { data: { email: 'demo@labeldesk.dev', password: 'demo1234' } })
  const token = (await auth.json()).token
  const headers = { Authorization: `Bearer ${token}` }
  // Reproducible on a fresh workspace: enable the flag before capturing the tab.
  const flag = await context.request.put(`${api}/api/ws/${WS}/flags/task_40`, { headers, data: { enabled: true } })
  if (!flag.ok()) console.error('flag enable failed', flag.status(), await flag.text())
  const base = `${api}/api/ws/${WS}/projects/${PR}/ot-outputs`
  const existing = await context.request.get(base, { headers })
  if (!existing.ok()) console.error('list failed', existing.status(), await existing.text())
  if (existing.ok() && (await existing.json()).length === 0) {
    const bodies = [
      { name: 'Reject gate · line 1', protocol: 'modbus',
        endpoint: { host: '10.20.0.14', port: 502, unit_id: 1, register: 'coil', address: 10 },
        event_filter: { kinds: ['zone', 'line'], classes: ['defect'] },
        latency_budget_ms: 200, pulse_ms: 80 },
      { name: 'Sorting cell · MQTT', protocol: 'mqtt',
        endpoint: { host: '10.20.0.30', port: 1883, topic: 'line1/reject' },
        event_filter: { kinds: ['zone'], classes: [] }, latency_budget_ms: 300, pulse_ms: 120 },
    ]
    for (const body of bodies) {
      const r = await context.request.post(base, { headers, data: body })
      if (!r.ok()) console.error('seed failed', r.status(), await r.text())
    }
  }
  await page.goto(`${web}/${WS}/${PR}/settings?tab=ot`, { waitUntil: 'domcontentloaded' })
  try {
    await page.getByRole('heading', { name: 'PLC / OT output' }).waitFor({ timeout: 15000 })
  } catch (e) {
    await page.screenshot({ path: `${out}/debug-${name}.png`, fullPage: true })
    console.error('heading missing', page.url(), await page.locator('h1,h2').allTextContents())
    throw e
  }
  await page.waitForTimeout(900)
  const file = `${out}/ot-outputs-${name}.png`
  await page.screenshot({ path: file, fullPage: true })
  results.push(file)
  await context.close()
}
await browser.close()
console.log(results.join('\n'))
