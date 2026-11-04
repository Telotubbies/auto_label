// Before/after probe for the 1,000-annotation fixture. Works on the pre-G5 editor too, so the same
// script produces the "before" numbers on a stashed tree. Prints JSON only.
//   node scripts/g5-baseline.mjs [baseUrl]
import { chromium, request } from 'playwright'

const base = process.argv[2] ?? 'http://localhost:5320'
const api = await request.newContext({ baseURL: base })
const login = await api.post('/api/auth/login', { data: { email: 'demo@labeldesk.dev', password: 'demo1234' } })
const token = (await login.json()).token
const auth = { Authorization: `Bearer ${token}` }
const list = await (await api.get('/api/ws/labeldesk-demo/projects/ppe-detection/images?limit=1000&sort=newest', { headers: auth })).json()
const image = list.items.find((i) => i.name === 'g5-thousand.png' && i.annotationCount === 1000)
if (!image) throw new Error('no 1,000-annotation fixture found')

const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
await ctx.addInitScript(({ t }) => localStorage.setItem('ld_token', t), { t: token })
const page = await ctx.newPage()
await page.goto(`${base}/labeldesk-demo/ppe-detection/images/${image.id}`, { waitUntil: 'networkidle' })
await page.getByTestId('canvas-area').locator('canvas').first().waitFor({ timeout: 15_000 })
await page.getByRole('button', { name: 'Objects' }).click()
await page.getByTestId('object-row').first().waitFor({ timeout: 15_000 })
const rows = await page.getByTestId('object-row').count()
const zoom = await page.getByTestId('zoom-level').innerText().catch(() => 'fit')
const timings = []
for (let i = 0; i < 5; i++) {
  timings.push(await page.evaluate(async (index) => {
    const btn = document.querySelectorAll('[data-testid="object-select"]')[index]
    const t0 = performance.now()
    btn.click()
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))
    return performance.now() - t0
  }, i))
}
timings.sort((a, b) => a - b)
console.log(JSON.stringify({
  image: image.id, rows, zoom,
  selectMsMedian: Number(timings[2].toFixed(2)), selectMs: timings.map((n) => Number(n.toFixed(1))),
}))
await browser.close()
await api.dispose()
