// Task G5 flow: stack order persists across reload, the Objects list is virtualized, the canvas
// splits into three Konva layers and culls shapes outside the viewport. Measures 1,000 annotations.
//   node scripts/editor-g5-flow.mjs [baseUrl] [screenshotDir]
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import { chromium, request } from 'playwright'

const base = process.argv[2] ?? 'http://localhost:5320'
const shots = process.argv[3] ?? 'g5-shots'
const WS = 'labeldesk-demo', PR = 'ppe-detection'
const email = process.env.LD_DEMO_EMAIL ?? 'demo@labeldesk.dev'
const password = process.env.LD_DEMO_PW ?? 'demo1234'

/** A synthetic photo: a light sky, a dark band and a red marker so the canvas has real pixels. */
async function sampleImage(browser, tint = 0) {
  const page = await browser.newPage({ viewport: { width: 320, height: 240 }, deviceScaleFactor: 1 })
  const salt = Math.floor(Math.random() * 255)
  await page.setContent(
    `<body style="margin:0;background:#dfe7ee">` +
    `<svg width="320" height="240" xmlns="http://www.w3.org/2000/svg">` +
    `<rect x="0" y="150" width="320" height="90" fill="#33413a"/>` +
    `<circle cx="${80 + tint * 40}" cy="90" r="42" fill="#c9a227"/>` +
    `<rect x="${210 - tint * 30}" y="40" width="60" height="120" fill="#8b3a2f"/>` +
    `<rect x="0" y="0" width="3" height="3" fill="rgb(${salt},0,0)"/></svg></body>`,
  )
  const png = await page.screenshot()
  await page.close()
  return png
}

const api = await request.newContext({ baseURL: base })
const login = await api.post('/api/auth/login', { data: { email, password } })
assert.equal(login.status(), 200, 'demo login failed')
const token = (await login.json()).token
const auth = { Authorization: `Bearer ${token}` }
const classes = await (await api.get(`/api/ws/${WS}/projects/${PR}/classes`, { headers: auth })).json()
assert.ok(classes.length >= 2, `need at least 2 classes, got ${classes.length}`)

const upload = async (name, tint) => {
  const browser0 = await chromium.launch()
  const buffer = await sampleImage(browser0, tint)
  await browser0.close()
  const up = await api.post(`/api/ws/${WS}/projects/${PR}/upload`, {
    headers: auth,
    multipart: { batch_name: 'g5-flow', files: { name, mimeType: 'image/png', buffer } },
  })
  assert.equal(up.status(), 200, `upload failed: ${await up.text()}`)
  const body = await up.json()
  assert.equal(body.uploaded, 1, `upload did not create an image: ${JSON.stringify(body.failed)}`)
  return body.images[0].id
}

await mkdir(shots, { recursive: true })
const imageA = await upload('g5-order.png', 0)
const pathA = `/${WS}/${PR}/images/${imageA}`
const imageB = await upload('g5-thousand.png', 1)
const pathB = `/${WS}/${PR}/images/${imageB}`

const check = (name, value = true) => console.log(`  ok  ${name}${value === true ? '' : ` ${JSON.stringify(value)}`}`)
const idsByZ = (page) =>
  page.getByTestId('object-row').evaluateAll((els) =>
    Object.fromEntries(els.map((e) => [e.dataset.z, e.dataset.objectId])))
const stageMetrics = (page) =>
  page.getByTestId('stage-filter').evaluate((el) => ({
    rendered: Number(el.dataset.rendered),
    total: Number(el.dataset.total),
    culled: Number(el.dataset.culled),
    selectedRendered: el.dataset.selectedRendered,
  }))

const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: 'light' })
await ctx.addInitScript(({ t }) => localStorage.setItem('ld_token', t), { t: token })
const page = await ctx.newPage()
const failures = []
page.on('console', (m) => m.type() === 'error' && failures.push(m.text()))
page.on('pageerror', (e) => failures.push(String(e)))

try {
  // ---------- stack order ----------
  await page.goto(base + pathA, { waitUntil: 'networkidle' })
  await page.getByTestId('canvas-area').locator('canvas').first().waitFor({ state: 'visible', timeout: 15_000 })
  await page.getByRole('button', { name: 'Objects' }).click()
  await page.getByTestId('object-empty').waitFor({ timeout: 5_000 })
  assert.equal(await page.getByTestId('object-count').innerText(), '0 objects')
  check('empty state and count', true)

  // Three boxes, drawn with the two-click tool.
  const area = page.getByTestId('canvas-area')
  const box = await area.boundingBox()
  assert.ok(box && box.width > 300 && box.height > 300, 'canvas area too small')
  const click = (fx, fy) => page.mouse.click(box.x + box.width * fx, box.y + box.height * fy)
  for (const [x, y] of [[0.2, 0.2], [0.45, 0.45], [0.7, 0.7]]) {
    await click(x, y)
    await click(x + 0.15, y + 0.15)
  }
  const rows = page.getByTestId('object-row')
  await rows.first().waitFor({ timeout: 5_000 })
  assert.equal(await rows.count(), 3, 'three boxes should make three objects')
  assert.equal(await page.getByTestId('object-count').innerText(), '3 objects')
  const initial = await idsByZ(page)
  assert.deepEqual(Object.keys(initial).sort(), ['1', '2', '3'])
  // The list is front-most first: the newest box sits at the top.
  assert.equal(initial['3'], (await rows.first().getAttribute('data-object-id')))
  check('visible order index', initial)
  // Wait for the drawing autosave so the next PUT is the reorder.
  await page.waitForTimeout(1200)

  // Select the middle object and send it backward. Selection alone must not reorder the stack.
  await page.locator('[data-testid="object-row"][data-z="2"] [data-testid="object-select"]').click()
  assert.deepEqual(await idsByZ(page), initial, 'selecting an object must not reorder it')
  assert.equal(await page.getByTestId('order-position').innerText(), '2 of 3 · top is front')
  const reorderSaved = page.waitForResponse((r) => r.url().includes('/annotations') && r.request().method() === 'PUT')
  await page.getByTestId('order-backward').click()
  const savedAt = Date.now()
  await reorderSaved
  const afterMove = await idsByZ(page)
  assert.equal(afterMove['3'], initial['3'], 'the front object stays in front')
  assert.equal(afterMove['2'], initial['1'], 'the object that was at the back moves up one')
  assert.equal(afterMove['1'], initial['2'], 'the selected object moves behind it')
  assert.equal(await page.getByTestId('order-position').innerText(), '1 of 3 · top is front')
  check('send backward', { afterMove, saveMs: Date.now() - savedAt })

  // Order survives the reload the save endpoint replaces.
  await page.reload({ waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'Objects' }).click()
  await rows.first().waitFor({ timeout: 10_000 })
  assert.deepEqual(await idsByZ(page), afterMove, 'stack order must survive a reload')
  check('order persists across reload', true)

  // Relabel maps over the array: order unchanged.
  await page.locator('[data-testid="object-row"][data-z="1"] [data-testid="object-select"]').click()
  await page.keyboard.press('2')
  await page.waitForTimeout(100)
  assert.match(await page.locator('[data-testid="object-row"][data-z="1"]').innerText(), new RegExp(classes[1].name))
  assert.deepEqual(await idsByZ(page), afterMove, 'relabelling must not reorder the stack')
  check('relabel keeps the order', true)

  // Keyboard navigation survives virtualization; hide and lock still work.
  await page.locator('[data-testid="object-row"][data-z="3"] [data-testid="object-select"]').focus()
  await page.keyboard.press('ArrowDown')
  assert.equal(await page.locator('[data-testid="object-row"][data-z="2"] [data-testid="object-select"]').getAttribute('aria-current'), 'true')

  // The Transformer lives in the preview layer while its node sits in the shapes layer; dragging
  // the bottom-right anchor must resize the selected object (box B spans 0.45..0.60 on both axes).
  const zoomLevel = Number((await page.getByTestId('zoom-level').innerText()).replace('%', '')) / 100
  const areaBox = await area.boundingBox()
  const field = async (label) => Number(await page.getByLabel(label, { exact: true }).inputValue())
  const g = { x: await field('X'), y: await field('Y'), w: await field('Width'), h: await field('Height') }
  const anchorX = areaBox.x + (areaBox.width - 1000 * zoomLevel) / 2 + ((g.x + g.w) / 100) * 1000 * zoomLevel
  const anchorY = areaBox.y + (areaBox.height - 750 * zoomLevel) / 2 + ((g.y + g.h) / 100) * 750 * zoomLevel
  const widthField = page.getByLabel('Width', { exact: true })
  const widthBefore = g.w
  await page.mouse.move(anchorX, anchorY)
  await page.mouse.down()
  await page.mouse.move(anchorX + 36, anchorY + 24, { steps: 8 })
  await page.mouse.up()
  await page.waitForTimeout(250)
  const widthAfter = Number(await widthField.inputValue())
  assert.ok(widthAfter > widthBefore, `the preview-layer Transformer must resize the shape (${widthBefore} -> ${widthAfter})`)
  assert.equal(await rows.count(), 3, 'dragging an anchor must not start a new box')
  check('transformer drag across layers', { before: widthBefore, after: widthAfter })

  // Dragging the shape itself must move the annotation, not pan the stage (dragend bubbles to Stage).
  const stagePos = () => page.getByTestId('stage-filter').evaluate((el) => `${el.dataset.stageX},${el.dataset.stageY}`)
  const stageBefore = await stagePos()
  const moved = { x: await field('X'), y: await field('Y'), w: await field('Width'), h: await field('Height') }
  const centreX = areaBox.x + (areaBox.width - 1000 * zoomLevel) / 2 + ((moved.x + moved.w / 2) / 100) * 1000 * zoomLevel
  const centreY = areaBox.y + (areaBox.height - 750 * zoomLevel) / 2 + ((moved.y + moved.h / 2) / 100) * 750 * zoomLevel
  await page.mouse.move(centreX, centreY)
  await page.mouse.down()
  await page.mouse.move(centreX + 30, centreY, { steps: 6 })
  await page.mouse.up()
  await page.waitForTimeout(250)
  assert.ok((await field('X')) > moved.x + 1, 'dragging the shape must move it')
  assert.equal(await stagePos(), stageBefore, 'a shape drag must not pan the stage')
  check('shape drag keeps the stage still', true)

  const topRow = page.locator('[data-testid="object-row"][data-z="3"]')
  await topRow.getByTestId('object-hide').click()
  assert.equal(await topRow.getByTestId('object-hide').getAttribute('aria-pressed'), 'true')
  assert.match(await topRow.innerText(), new RegExp(classes[0].name))
  assert.ok((await topRow.innerText()).includes(classes[0].name), 'hidden row keeps its label')
  await topRow.getByTestId('object-lock').click()
  assert.equal(await topRow.getByTestId('object-lock').getAttribute('aria-pressed'), 'true')
  await page.screenshot({ path: `${shots}/objects-light.png` })
  check('keyboard nav, hide and lock', true)

  // ---------- 1,000 annotations ----------
  const many = Array.from({ length: 1000 }, (_, i) => ({
    id: `g5-${String(i).padStart(4, '0')}`,
    classId: classes[i % classes.length].id,
    shape: { kind: 'bbox', x: (i % 40) / 40, y: Math.floor(i / 40) / 25, w: 0.02, h: 0.03 },
    source: 'human',
  }))
  const put = await api.put(`/api/images/${imageB}/annotations`, { headers: auth, data: { annotations: many } })
  assert.equal(put.status(), 200, `1,000-annotation PUT failed: ${await put.text()}`)

  await page.goto(base + pathB, { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'Objects' }).click()
  await page.waitForFunction(() => document.querySelector('[data-testid="object-count"]')?.textContent?.includes('1000 objects'), null, { timeout: 15_000 })
  const renderedRows = await page.getByTestId('object-row').count()
  assert.ok(renderedRows > 0 && renderedRows < 60, `the list must be virtualized, got ${renderedRows} rows`)
  const layerCount = await page.getByTestId('canvas-area').locator('canvas').count()
  assert.equal(layerCount, 3, `the canvas must have three Konva layers, got ${layerCount}`)

  /** Select a row and measure click -> two paints, in the page's own clock. */
  const measureSelect = (z) => page.evaluate(async (position) => {
    const btn = document.querySelector(`[data-testid="object-row"][data-z="${position}"] [data-testid="object-select"]`)
    if (!btn) return null
    const t0 = performance.now()
    btn.click()
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))
    return performance.now() - t0
  }, z)
  const median = (xs) => xs.filter((x) => x != null).sort((a, b) => a - b)[Math.floor(xs.filter((x) => x != null).length / 2)]
  const fitMetrics = await stageMetrics(page)
  const visibleZs = () => page.getByTestId('object-row').evaluateAll((els) => els.map((e) => Number(e.dataset.z)))
  const fitZs = (await visibleZs()).slice(0, 5)
  const fitTimings = []
  for (const z of fitZs) fitTimings.push(await measureSelect(z))
  const fitMs = median(fitTimings)
  assert.equal(fitMetrics.total, 1000)

  // Zoom in until the viewport covers a fraction of the image; culling must drop nodes.
  const zoomIn = page.getByRole('button', { name: 'Zoom in' })
  for (let i = 0; i < 20; i++) await zoomIn.click()
  await page.waitForTimeout(200)
  const zoomed = await stageMetrics(page)
  assert.ok(zoomed.culled > 500, `expected most shapes culled, got ${zoomed.culled}`)
  assert.ok(zoomed.rendered < 400, `expected far fewer nodes, got ${zoomed.rendered}`)

  // The selected annotation stays mounted even when its box leaves the viewport: pick the back
  // object (top-left of the image, outside the zoomed centre) via the list's End key.
  await page.locator('[data-testid="object-row"] [data-testid="object-select"]').first().focus()
  await page.keyboard.press('End')
  const selectedMetrics = await stageMetrics(page)
  assert.equal(selectedMetrics.selectedRendered, 'true', 'the Transformer target must always render')
  const zoomTimings = []
  for (const z of (await visibleZs()).slice(0, 5)) zoomTimings.push(await measureSelect(z))
  const zoomMs = median(zoomTimings)
  // Put the selection back on the back-most object so the screenshot shows a culled selected box.
  await page.locator('[data-testid="object-row"] [data-testid="object-select"]').first().focus()
  await page.keyboard.press('End')
  await page.waitForTimeout(250)
  await page.screenshot({ path: `${shots}/objects-culled-light.png` })
  check('culling and 3 layers', {
    listRows: renderedRows, layers: layerCount,
    fitNodes: fitMetrics.rendered, zoomedNodes: zoomed.rendered, culled: zoomed.culled,
    fitSelectMs: Number(fitMs.toFixed(2)), zoomSelectMs: Number(zoomMs.toFixed(2)),
  })

  assert.deepEqual(failures, [], `console errors: ${failures.join(' | ')}`)
  check('console clean', true)
  await ctx.close()

  // ---------- dark ----------
  const dark = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: 'dark' })
  await dark.addInitScript(({ t }) => {
    localStorage.setItem('ld_token', t)
    localStorage.setItem('ld:theme', JSON.stringify({ mode: 'dark' }))
  }, { t: token })
  const darkPage = await dark.newPage()
  await darkPage.goto(base + pathB, { waitUntil: 'networkidle' })
  assert.equal(await darkPage.evaluate(() => document.documentElement.classList.contains('dark')), true)
  await darkPage.getByRole('button', { name: 'Objects' }).click()
  await darkPage.getByTestId('object-count').waitFor({ timeout: 10_000 })
  await darkPage.locator('[data-testid="object-row"] [data-testid="object-select"]').first().click()
  await darkPage.waitForTimeout(300)
  await darkPage.screenshot({ path: `${shots}/objects-dark.png` })
  await dark.close()

  // ---------- 375 px ----------
  const narrow = await browser.newContext({ viewport: { width: 375, height: 812 }, colorScheme: 'light' })
  await narrow.addInitScript(({ t }) => localStorage.setItem('ld_token', t), { t: token })
  const small = await narrow.newPage()
  await small.goto(base + pathB, { waitUntil: 'networkidle' })
  await small.getByRole('button', { name: 'Toggle annotation panels' }).click()
  await small.getByRole('button', { name: 'Objects' }).click()
  await small.getByTestId('object-count').waitFor({ timeout: 10_000 })
  await small.locator('[data-testid="object-row"] [data-testid="object-select"]').first().click()
  await small.evaluate(() => window.scrollTo(0, 0))
  const listBox = await small.getByTestId('object-list').boundingBox()
  assert.ok(listBox && listBox.x >= 0 && listBox.x + listBox.width <= 375, `object list must fit 375 px: ${JSON.stringify(listBox)}`)
  assert.ok((await small.getByTestId('object-row').count()) > 0)
  assert.equal(await small.getByTestId('object-count').innerText(), '1000 objects')
  await small.screenshot({ path: `${shots}/objects-375.png` })
  check('375 px object list', listBox)
  await narrow.close()
} finally {
  await browser.close()
  await api.dispose()
}
console.log(JSON.stringify({ imageA, imageB, shots, ok: true }))
