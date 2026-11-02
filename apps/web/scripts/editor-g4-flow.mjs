// Task G4 flow: class search + filtered numeric hotkeys, Smart Polygon simplification slider, and
// remappable shortcuts with a duplicate-key guard. Also writes light / dark / 375 px screenshots.
//   node scripts/editor-g4-flow.mjs [baseUrl] [screenshotDir]
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import { chromium, request } from 'playwright'

const base = process.argv[2] ?? 'http://localhost:5320'
const shots = process.argv[3] ?? 'g4-shots'
const WS = 'labeldesk-demo', PR = 'ppe-detection'
const email = process.env.LD_DEMO_EMAIL ?? 'demo@labeldesk.dev'
const password = process.env.LD_DEMO_PW ?? 'demo1234'

/** A toothed blob: a curved, high-vertex contour so the simplification slider visibly changes the count. */
async function sampleImage(browser) {
  const page = await browser.newPage({ viewport: { width: 320, height: 240 }, deviceScaleFactor: 1 })
  const teeth = 16, cx = 160, cy = 120, r1 = 58, r2 = 38
  const points = Array.from({ length: teeth * 2 }, (_, i) => {
    const a = (Math.PI * 2 * i) / (teeth * 2)
    const r = i % 2 ? r2 : r1
    return `${(cx + Math.cos(a) * r).toFixed(1)},${(cy + Math.sin(a) * r).toFixed(1)}`
  }).join(' ')
  const tint = Math.floor(Math.random() * 255)
  await page.setContent(
    `<body style="margin:0;background:#fff">` +
    `<svg width="320" height="240" xmlns="http://www.w3.org/2000/svg">` +
    `<polygon points="${points}" fill="#111"/>` +
    `<rect x="0" y="0" width="3" height="3" fill="rgb(${tint},0,0)"/></svg></body>`,
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
assert.ok(classes.length >= 4, `need at least 4 classes, got ${classes.length}`)

await mkdir(shots, { recursive: true })
const browser = await chromium.launch()
const up = await api.post(`/api/ws/${WS}/projects/${PR}/upload`, {
  headers: auth,
  multipart: { batch_name: 'g4-flow', files: { name: 'g4-shape.png', mimeType: 'image/png', buffer: await sampleImage(browser) } },
})
assert.equal(up.status(), 200, `upload failed: ${await up.text()}`)
const uploaded = await up.json()
assert.equal(uploaded.uploaded, 1, `upload did not create an image: ${JSON.stringify(uploaded.failed)}`)
const imageId = uploaded.images[0].id
const editorPath = `/${WS}/${PR}/images/${imageId}`

const check = (name, value = true) => console.log(`  ok  ${name}${value === true ? '' : ` ${JSON.stringify(value)}`}`)

try {
  // ---------- light, 1440 ----------
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: 'light' })
  await ctx.addInitScript(({ t }) => localStorage.setItem('ld_token', t), { t: token })
  const page = await ctx.newPage()
  const failures = []
  page.on('console', (m) => m.type() === 'error' && failures.push(m.text()))
  page.on('pageerror', (e) => failures.push(String(e)))

  await page.goto(base + editorPath, { waitUntil: 'networkidle' })
  const search = page.getByTestId('class-search')
  await search.waitFor({ timeout: 15_000 })
  const allRows = await page.getByTestId('class-option').count()
  assert.equal(allRows, classes.length, 'classes panel must list every project class')
  /** React commits the filtered list asynchronously; wait for the row count instead of racing it. */
  const waitRows = (n) =>
    page.waitForFunction((count) => document.querySelectorAll('[data-testid="class-option"]').length === count, n, { timeout: 5_000 })
  const setQuery = async (q) => { await search.fill(q); await page.waitForTimeout(50) }

  // 1) "/" focuses the search while the canvas has the keys.
  await page.keyboard.press('/')
  assert.equal(await search.evaluate((el) => el === document.activeElement), true, "'/' must focus the class search")

  // 2) Filtering is case-insensitive + trimmed, and the live region reports the count.
  await setQuery('  HEL  ')
  await waitRows(1)
  assert.equal(await page.getByTestId('class-option').count(), 1, 'one class matches "hel"')
  assert.equal(await page.getByTestId('class-count').innerText(), `1 of ${classes.length} classes`)
  assert.equal(await page.getByTestId('class-option').first().getAttribute('data-hotkey'), '1')

  // 3) No match -> explicit empty state; tags and the count line do not move (no layout shift).
  const countBox = await page.getByTestId('class-count').boundingBox()
  const tagsBox = await page.getByRole('heading', { name: 'Tags' }).boundingBox()
  await setQuery('zzz')
  await waitRows(0)
  assert.equal(await page.getByTestId('class-option').count(), 0)
  assert.equal(await page.getByTestId('class-empty').innerText(), 'No class matches')
  assert.equal(await page.getByTestId('class-count').innerText(), 'No class matches')
  const countBox2 = await page.getByTestId('class-count').boundingBox()
  const tagsBox2 = await page.getByRole('heading', { name: 'Tags' }).boundingBox()
  assert.equal(Math.round(countBox.y), Math.round(countBox2.y), 'the count line must not move')
  assert.equal(Math.round(tagsBox.y), Math.round(tagsBox2.y), 'filtering must not shift the panel footer')
  check('search: filter, count, empty state, no shift', true)

  // 4) Escape clears the query and returns the keys to the canvas.
  await setQuery('hel')
  await waitRows(1)
  await search.press('Escape')
  await waitRows(classes.length)
  assert.equal(await search.inputValue(), '')
  assert.equal(await page.getByTestId('class-option').count(), classes.length)
  assert.equal(await search.evaluate((el) => el === document.activeElement), false, 'Escape must blur the field')
  check('search: Escape clears', true)

  // 5) Draw a box (default class = first class), then relabel it with "1" while a filter is active.
  await page.getByTestId('tool-bbox').click()
  const area = page.getByTestId('canvas-area')
  await area.locator('canvas').first().waitFor({ state: 'visible' })
  const box = await area.boundingBox()
  assert.ok(box && box.width > 300 && box.height > 300, 'canvas area too small')
  await page.mouse.click(box.x + box.width * 0.3, box.y + box.height * 0.3)
  await page.mouse.click(box.x + box.width * 0.55, box.y + box.height * 0.55)
  await page.getByRole('button', { name: 'Objects' }).click()
  const rows = page.getByTestId('object-row')
  await rows.first().waitFor({ timeout: 5_000 })
  assert.equal(await rows.count(), 1, 'two clicks should create one box')
  const defaultName = await rows.first().innerText()
  assert.match(defaultName, new RegExp(classes[0].name), 'the new box starts on the first class')
  await rows.first().getByTestId('object-select').click()   // select it so 1–9 relabel this annotation

  await page.getByRole('button', { name: 'Classes' }).click()
  await setQuery('h')                          // visible: helmet, harness
  await waitRows(2)
  const visibleNames = await page.getByTestId('class-option').evaluateAll((els) => els.map((e) => e.textContent.trim()))
  assert.equal(visibleNames.length, 2, `filter "h" should show 2 rows, got ${JSON.stringify(visibleNames)}`)
  assert.match(visibleNames[0], /helmet/, 'helmet is the first visible row')
  assert.equal(await page.getByTestId('class-option').first().getAttribute('data-hotkey'), '1')
  await page.getByRole('heading', { name: /Annotations/ }).click()   // blur, keep the filter
  await page.keyboard.press('1')
  await page.getByRole('button', { name: 'Objects' }).click()
  assert.match(await rows.first().innerText(), /helmet/, '1 must map to the first *visible* row')
  check('numeric hotkey follows the filtered order', true)

  // 5b) The filter must stop driving 1–9 as soon as the filtered rows leave the screen.
  await page.keyboard.press('1')                          // Objects tab, filter inactive -> person
  assert.match(await rows.first().innerText(), /person/, 'a hidden filter must not reorder the hotkeys')
  await page.getByRole('button', { name: 'Classes' }).click()
  await setQuery('h')
  await waitRows(2)
  await page.getByRole('button', { name: 'Objects' }).click()   // rows now hidden, query still in state
  await page.keyboard.press('2')                          // project order -> helmet (bug: harness)
  const hiddenList = await rows.first().innerText()
  assert.match(hiddenList, /helmet/, 'a hidden filter must not reorder the hotkeys')
  assert.doesNotMatch(hiddenList, /harness/)
  check('hotkeys ignore a hidden filter', true)

  // 6) Light screenshot with the filter applied.
  await page.getByRole('button', { name: 'Classes' }).click()
  await setQuery('h')
  await waitRows(2)
  await page.screenshot({ path: `${shots}/editor-light.png` })

  // 7) Smart Polygon: slider re-simplifies the same clicks and lowers the vertex count.
  await setQuery('')
  await page.getByTestId('tool-smart').click()
  await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.5)
  await page.getByTestId('simplify-control').waitFor({ timeout: 30_000 })
  const pointsText = async () => Number((await page.getByTestId('simplify-points').innerText()).match(/\d+/)[0])
  const before = await pointsText()
  assert.ok(before > 3, `expected a detailed preview, got ${before} points`)
  const slider = page.getByTestId('simplify-slider')
  assert.equal(await slider.inputValue(), '0.004', 'the slider starts on the default epsilon')
  // Drive the slider from the keyboard so it owns focus, exactly like a real adjustment.
  await slider.focus()
  await page.keyboard.press('End')                        // native: jump to 0.02 and fire the request
  await page.waitForFunction((prev) => {
    const el = document.querySelector('[data-testid="simplify-points"]')
    return el && Number(el.textContent.match(/\d+/)[0]) < prev
  }, before, { timeout: 20_000 })
  const after = await pointsText()
  assert.ok(after < before, `a coarser epsilon must simplify (${before} -> ${after})`)
  // A request must not steal focus: if it did, the next arrow would navigate to another image and
  // drop the preview being tuned.
  assert.equal(await slider.evaluate((el) => el === document.activeElement), true, 'the slider must keep focus across a request')
  const imageUrl = page.url()
  await page.keyboard.press('ArrowLeft')
  await page.waitForTimeout(500)
  assert.equal(page.url(), imageUrl, 'an arrow on the slider must adjust it, not change image')
  assert.equal(await slider.evaluate((el) => el === document.activeElement), true, 'focus must still be on the slider')
  check('slider keeps focus during requests', true)
  await page.waitForFunction(() => {
    const el = document.querySelector('[data-testid="simplify-slider"]')
    return el && !el.getAttribute('aria-busy')
  }, null, { timeout: 10_000 })                           // the second re-request has settled
  await page.screenshot({ path: `${shots}/simplify-light.png` })
  await page.keyboard.press('Enter')
  await page.getByRole('button', { name: 'Objects' }).click()
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="object-row"]').length === 2, null, { timeout: 10_000 })
  check('smart polygon slider', { before, after })

  // 8) The committed shape is undoable (Ctrl+Z) and redoable.
  await page.keyboard.press('Control+z')
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="object-row"]').length === 1, null, { timeout: 5_000 })
  await page.keyboard.press('Control+Shift+z')
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="object-row"]').length === 2, null, { timeout: 5_000 })
  check('undo after commit', true)

  // 9) Remap the bounding-box key to N, save, and use it.
  await page.keyboard.press('?')
  const dialog = page.getByRole('dialog')
  await dialog.waitFor({ timeout: 5_000 })
  await page.getByRole('button', { name: 'Change shortcut for Bounding box tool' }).click()
  await page.keyboard.press('n')
  await page.waitForTimeout(100)
  assert.match(await dialog.innerText(), /N/, 'the draft must show the new key')
  await page.screenshot({ path: `${shots}/shortcuts-light.png` })
  await page.getByRole('button', { name: 'Save shortcuts' }).click()
  await dialog.waitFor({ state: 'detached', timeout: 5_000 })

  await page.getByTestId('tool-pan').click()
  await page.keyboard.press('n')
  assert.equal(await page.getByTestId('tool-bbox').getAttribute('aria-pressed'), 'true', 'N must switch to the box tool')
  await page.getByTestId('tool-pan').click()
  await page.keyboard.press('b')
  assert.equal(await page.getByTestId('tool-bbox').getAttribute('aria-pressed'), 'false', 'B must be free again')
  check('shortcut remap applied', true)

  // 10) Persistence survives a reload.
  await page.reload({ waitUntil: 'networkidle' })
  const stored = await page.evaluate(() => localStorage.getItem('ld:editor-shortcuts'))
  assert.match(stored ?? '', /"bbox":"n"/, `localStorage should hold the remap: ${stored}`)
  await page.getByTestId('tool-pan').click()
  await page.keyboard.press('n')
  assert.equal(await page.getByTestId('tool-bbox').getAttribute('aria-pressed'), 'true', 'the remap must survive a reload')
  check('shortcut remap persists', true)

  // 11) Duplicate keys warn and block saving; Cancel discards the draft.
  await page.keyboard.press('?')
  await dialog.waitFor({ timeout: 5_000 })
  await page.getByRole('button', { name: 'Change shortcut for Pan / move canvas' }).click()
  await page.keyboard.press('n')
  const alert = dialog.getByRole('alert')
  await alert.waitFor({ timeout: 5_000 })
  assert.match(await alert.innerText(), /already used by Bounding box tool/)
  assert.equal(await page.getByRole('button', { name: 'Save shortcuts' }).isDisabled(), true, 'a duplicate must block saving')
  await page.getByRole('button', { name: 'Reset to defaults' }).click()
  assert.equal(await page.getByRole('button', { name: 'Save shortcuts' }).isDisabled(), false, 'reset clears the duplicate')
  await page.getByRole('button', { name: 'Cancel' }).click()
  await dialog.waitFor({ state: 'detached', timeout: 5_000 })
  await page.getByTestId('tool-pan').click()
  await page.keyboard.press('n')
  assert.equal(await page.getByTestId('tool-bbox').getAttribute('aria-pressed'), 'true', 'Cancel must discard the draft')
  check('duplicate key blocks saving', true)

  // 12) Keyboard-only path still works: ? toggles help, Esc closes it.
  await page.keyboard.press('?')
  await dialog.waitFor({ timeout: 5_000 })
  await page.keyboard.press('Escape')
  await dialog.waitFor({ state: 'detached', timeout: 5_000 })
  check('? and Esc still work', true)

  // 13) Dark screenshot of the same panel state.
  await page.getByRole('button', { name: 'Classes' }).click()
  await page.evaluate(() => localStorage.setItem('ld:theme', JSON.stringify({ mode: 'dark' })))
  await page.reload({ waitUntil: 'networkidle' })
  assert.equal(await page.evaluate(() => document.documentElement.classList.contains('dark')), true, 'dark mode did not apply')
  await page.getByTestId('class-search').waitFor({ timeout: 10_000 })
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="class-option"]').length > 0, null, { timeout: 10_000 })
  await page.getByTestId('class-search').fill('h')
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="class-option"]').length === 2, null, { timeout: 10_000 })
  await page.screenshot({ path: `${shots}/editor-dark.png` })
  await page.getByRole('heading', { name: /Annotations/ }).click()   // blur the search field
  await page.keyboard.press('?')
  await page.getByRole('dialog').waitFor({ timeout: 5_000 })
  await page.waitForTimeout(400)
  await page.screenshot({ path: `${shots}/shortcuts-dark.png` })
  await page.keyboard.press('Escape')

  assert.deepEqual(failures, [], `console errors: ${failures.join(' | ')}`)
  check('console clean', true)
  await ctx.close()

  // ---------- 375 px ----------
  const narrow = await browser.newContext({ viewport: { width: 375, height: 812 }, colorScheme: 'light' })
  await narrow.addInitScript(({ t }) => localStorage.setItem('ld_token', t), { t: token })
  const small = await narrow.newPage()
  await small.goto(base + editorPath, { waitUntil: 'networkidle' })
  await small.getByRole('button', { name: 'Toggle annotation panels' }).click()
  await small.getByTestId('class-search').waitFor({ timeout: 10_000 })
  await small.getByTestId('class-search').fill('h')
  await small.waitForFunction(() => document.querySelectorAll('[data-testid="class-option"]').length === 2, null, { timeout: 10_000 })
  assert.equal(await small.getByTestId('class-option').count(), 2)
  // The panel itself must fit 375 px. (The editor top toolbar is 432 px wide and overflows —
  // pre-existing, tracked for the final impeccable pass, not this task.)
  await small.evaluate(() => window.scrollTo(0, 0))
  const searchBox = await small.getByTestId('class-search').boundingBox()
  assert.ok(searchBox && searchBox.x >= 0 && searchBox.x + searchBox.width <= 375, `class search must fit 375 px: ${JSON.stringify(searchBox)}`)
  await small.screenshot({ path: `${shots}/editor-375.png` })

  // The simplify card must stay inside the canvas column at 375 px, drawer closed.
  await small.getByRole('button', { name: 'Toggle annotation panels' }).click()
  await small.waitForTimeout(400)                     // let the ResizeObserver re-fit the stage
  await small.evaluate(() => window.scrollTo(0, 0))    // the 432 px header can leave the page scrolled
  await small.getByTestId('tool-smart').click()
  const narrowArea = await small.getByTestId('canvas-area').boundingBox()
  await small.mouse.click(narrowArea.x + narrowArea.width * 0.5, narrowArea.y + narrowArea.height * 0.5)
  await small.getByTestId('simplify-control').waitFor({ timeout: 30_000 }).catch(async () => {
    const alert = await small.locator('[role="alert"]').first().innerText().catch(() => 'none')
    throw new Error(`no simplify card at 375 px; alert=${alert}`)
  })
  const card = await small.getByTestId('simplify-control').boundingBox()
  assert.ok(card && card.x >= 0 && card.x + card.width <= 375, `simplify card must fit 375 px: ${JSON.stringify(card)}`)
  await small.screenshot({ path: `${shots}/simplify-375.png` })
  check('375 px drawer', true)
  await narrow.close()
} finally {
  await browser.close()
  await api.dispose()
}
console.log(JSON.stringify({ imageId, editorPath, shots, ok: true }))
