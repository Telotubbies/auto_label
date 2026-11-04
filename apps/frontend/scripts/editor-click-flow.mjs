// Editor click-only flow (WCAG 2.5.7 Dragging Movements): draw a box with two clicks, then a Smart
// Polygon with one click + Enter, hide/lock objects, change display brightness, and check the
// Approve button's text contrast in light and dark. No drag gesture is used anywhere.
//   node scripts/editor-click-flow.mjs [baseUrl]
import assert from 'node:assert/strict'
import { chromium, request } from 'playwright'

const base = process.argv[2] ?? 'http://localhost:5180'
const WS = 'labeldesk-demo', PR = 'ppe-detection'
const email = process.env.LD_DEMO_EMAIL ?? 'demo@labeldesk.dev'
const password = process.env.LD_DEMO_PW ?? 'demo1234'

// A unique 320×240 white canvas with a black blob so GrabCut has an obvious foreground at the centre.
async function sampleImage(browser) {
  const page = await browser.newPage({ viewport: { width: 320, height: 240 }, deviceScaleFactor: 1 })
  const tint = Math.floor(Math.random() * 255)
  await page.setContent(
    `<body style="margin:0;background:#fff"><div style="position:absolute;left:80px;top:50px;width:170px;height:140px;background:#000"></div>` +
    `<div style="position:absolute;left:0;top:0;width:4px;height:4px;background:rgb(${tint},0,0)"></div></body>`,
  )
  const png = await page.screenshot()
  await page.close()
  return png
}

/** WCAG 2.2 relative luminance / contrast for `rgb(...)` strings. */
/** WCAG 2.2 relative luminance / contrast for `rgb(...)` strings. */
function luminance(rgb) {
  const [r, g, b] = rgb.match(/\d+(\.\d+)?/g).slice(0, 3).map(Number).map((v) => {
    const s = v / 255
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
function ratio(a, b) {
  const [x, y] = [luminance(a), luminance(b)].sort((m, n) => n - m)
  return (x + 0.05) / (y + 0.05)
}

const api = await request.newContext({ baseURL: base })
const login = await api.post('/api/auth/login', { data: { email, password } })
assert.equal(login.status(), 200, 'demo login failed')
const token = (await login.json()).token
const auth = { Authorization: `Bearer ${token}` }
const classes = await (await api.get(`/api/ws/${WS}/projects/${PR}/classes`, { headers: auth })).json()
assert.ok(classes.length > 0, 'demo project has no classes')

const browser = await chromium.launch()
const up = await api.post(`/api/ws/${WS}/projects/${PR}/upload`, {
  headers: auth,
  multipart: { batch_name: 'click-flow', files: { name: 'click-flow.png', mimeType: 'image/png', buffer: await sampleImage(browser) } },
})
assert.equal(up.status(), 200, `upload failed: ${await up.text()}`)
const uploaded = await up.json()
assert.equal(uploaded.uploaded, 1, `upload did not create an image: ${JSON.stringify(uploaded.failed)}`)
const imageId = uploaded.images[0].id
const editorPath = `/${WS}/${PR}/images/${imageId}`

const results = {}
const check = (name, value) => { results[name] = value; console.log(`  ok  ${name}`) }

try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: 'light' })
  await context.addInitScript(({ t }) => localStorage.setItem('ld_token', t), { t: token })
  const page = await context.newPage()
  const failures = []
  page.on('console', (m) => m.type() === 'error' && failures.push(m.text()))

  // 0) Upload summary: one good image + one corrupt file, both selected through the file picker.
  await page.goto(`${base}/${WS}/${PR}/upload`, { waitUntil: 'networkidle' })
  await page.locator('input[type=file]').first().setInputFiles([
    { name: 'ok.png', mimeType: 'image/png', buffer: await sampleImage(browser) },
    { name: 'broken.jpg', mimeType: 'image/jpeg', buffer: Buffer.from('not an image') },
  ])
  await page.getByRole('button', { name: 'Save and Continue' }).click()
  const summary = page.getByTestId('upload-summary')
  await summary.waitFor({ timeout: 20_000 })
  const summaryText = await summary.innerText()
  assert.match(summaryText, /Uploaded 1 · duplicates skipped 0 · failed 1/, `unexpected summary: ${summaryText}`)
  assert.match(summaryText, /unreadable image \(1 file\)/, `missing failure reason: ${summaryText}`)
  check('upload summary', true)

  await page.goto(base + editorPath, { waitUntil: 'networkidle' })
  const area = page.getByTestId('canvas-area')
  await area.waitFor({ state: 'visible' })
  await area.locator('canvas').first().waitFor({ state: 'visible' })
  const box = await area.boundingBox()
  assert.ok(box && box.width > 300 && box.height > 300, 'canvas area too small')

  // 1) Two clicks draw a box; no drag anywhere in this script.
  await page.getByTestId('tool-bbox').click()
  await page.mouse.click(box.x + box.width * 0.35, box.y + box.height * 0.35)
  await page.mouse.click(box.x + box.width * 0.60, box.y + box.height * 0.60)
  await page.getByRole('button', { name: 'Objects' }).click()
  const rows = page.getByTestId('object-row')
  await rows.first().waitFor({ timeout: 5_000 })
  assert.equal(await rows.count(), 1, 'two clicks should create exactly one box')
  check('two-click bbox', true)

  // 2) Smart Polygon: one click previews, right-click inside shrinks, Enter commits. Nothing is added before Enter.
  await page.getByTestId('tool-smart').click()
  const cx = box.x + box.width * 0.5, cy = box.y + box.height * 0.5
  await page.mouse.click(cx, cy)
  await page.getByText(/Enter to commit/).waitFor({ timeout: 20_000 })
  assert.equal(await rows.count(), 1, 'smart polygon must preview, not auto-commit')
  await page.mouse.click(cx + box.width * 0.05, cy, { button: 'right' })
  await page.getByText(/2 points/).waitFor({ timeout: 20_000 })
  assert.equal(await rows.count(), 1, 'a negative click must refine, not commit')
  await page.keyboard.press('Enter')
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="object-row"]').length === 2, null, { timeout: 5_000 })
  check('smart polygon click + Enter', true)

  // 3) Hide / lock from the object list.
  const hide = page.getByTestId('object-hide').first()
  await hide.click()
  assert.equal(await hide.getAttribute('aria-pressed'), 'true', 'hide toggle must report pressed')
  const lock = page.getByTestId('object-lock').first()
  await lock.click()
  assert.equal(await lock.getAttribute('aria-pressed'), 'true', 'lock toggle must report pressed')
  check('object hide/lock', true)

  // 4) Display-only filter on the Konva stage.
  await page.getByRole('button', { name: /Display/ }).click()
  await page.getByLabel('Brightness').fill('120')
  await page.getByLabel('Contrast').fill('90')
  const filter = await page.getByTestId('stage-filter').evaluate((el) => getComputedStyle(el).filter)
  assert.match(filter, /brightness\(1\.2\)/, `unexpected filter: ${filter}`)
  assert.match(filter, /contrast\(0\.9\)/, `unexpected filter: ${filter}`)
  await page.getByRole('button', { name: 'Reset' }).click()
  check('display filter', true)

  // 5) Approve button contrast ≥ 4.5:1 in light and dark (was 3.21:1).
  const approveContrast = async () => page.getByRole('button', { name: 'Approve' }).evaluate((el) => {
    const cs = getComputedStyle(el)
    const c = document.createElement('canvas').getContext('2d')
    const rgb = (css) => { c.fillStyle = css; c.fillRect(0, 0, 1, 1); const d = c.getImageData(0, 0, 1, 1).data; return `rgb(${d[0]}, ${d[1]}, ${d[2]})` }
    return { color: rgb(cs.color), background: rgb(cs.backgroundColor) }
  })
  const light = await approveContrast()
  const lightRatio = ratio(light.color, light.background)
  assert.ok(lightRatio >= 4.5, `light Approve contrast ${lightRatio.toFixed(2)} < 4.5`)
  await page.evaluate(() => localStorage.setItem('ld:theme', JSON.stringify({ mode: 'dark' })))
  await page.reload({ waitUntil: 'networkidle' })
  assert.equal(await page.evaluate(() => document.documentElement.classList.contains('dark')), true, 'editor did not switch to dark')
  const dark = await approveContrast()
  const darkRatio = ratio(dark.color, dark.background)
  assert.ok(darkRatio >= 4.5, `dark Approve contrast ${darkRatio.toFixed(2)} < 4.5`)
  check('approve contrast', { light: +lightRatio.toFixed(2), dark: +darkRatio.toFixed(2) })

  // 6) AI provenance: a dashed sam3 shape becomes solid with source human after a human edit.
  const upAi = await api.post(`/api/ws/${WS}/projects/${PR}/upload`, {
    headers: auth,
    multipart: { batch_name: 'ai-provenance', files: { name: 'ai-provenance.png', mimeType: 'image/png', buffer: await sampleImage(browser) } },
  })
  assert.equal(upAi.status(), 200, `AI image upload failed: ${await upAi.text()}`)
  const aiImage = (await upAi.json()).images[0].id
  const aiClass = classes[0]
  const humanClass = classes[1] ?? classes[0]
  const putAi = await api.put(`/api/images/${aiImage}/annotations`, {
    headers: auth,
    data: { annotations: [{ id: 'ai-1', classId: aiClass.id, shape: { kind: 'bbox', x: .2, y: .2, w: .3, h: .3 }, source: 'sam3', confidence: .42 }] },
  })
  assert.equal(putAi.status(), 200, `seeding an AI annotation failed: ${await putAi.text()}`)
  await page.goto(`${base}/${WS}/${PR}/images/${aiImage}`, { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'Objects' }).click()
  assert.equal(await page.getByTestId('stage-filter').getAttribute('data-ai'), '1', 'AI shape must be dashed')
  assert.match(await page.getByTestId('object-row').first().innerText(), /sam3/, 'AI source chip missing')
  await page.getByTestId('object-row').first().getByTestId('object-select').click()
  await page.getByRole('button', { name: 'Classes' }).click()
  await page.getByTestId('class-option').filter({ hasText: humanClass.name }).first().click()
  await page.getByRole('button', { name: 'Objects' }).click()
  assert.equal(await page.getByTestId('stage-filter').getAttribute('data-ai'), '0', 'edited shape must be solid')
  assert.doesNotMatch(await page.getByTestId('object-row').first().innerText(), /sam3/, 'source chip should be gone')
  await page.waitForTimeout(900)   // autosave
  const saved = await (await api.get(`/api/images/${aiImage}`, { headers: auth })).json()
  assert.equal(saved.annotations[0].source, 'human', 'edited annotation must persist source human')
  check('AI provenance -> human on edit', true)

  assert.deepEqual(failures, [], `console errors: ${failures.join(' | ')}`)
  check('console clean', true)
  await context.close()
} finally {
  await browser.close()
  await api.dispose()
}
console.log(JSON.stringify({ imageId, editorPath, results, ok: true }, null, 2))
