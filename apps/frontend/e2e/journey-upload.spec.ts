// T-1203 — J3: the upload page predicts what a drop will do before it runs (duplicates, refusals,
// the split, the batch name) and reports what it did after, so the first upload is not a support
// ticket. Files, a URL and a video's frames, in LabelDesk's own words.
//
// This file adds no product code: the upload page, the frame-extraction dialog and the dataset grid
// are the subject. Wave Q measures; it never repairs.
import { expect, test, type APIRequestContext, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { record, seeded, setFlags, signIn, stubApi } from './fixtures/harness'

const FIX = path.join(import.meta.dirname, 'fixtures')
const ONE = path.join(FIX, 'one.jpg')            // 640×480, shared with core-loop.spec.ts
const DUP = path.join(FIX, 'duplicate.jpg')      // byte-identical to one.jpg: this card's own file
const SMALL = path.join(FIX, 'small.png')        // 32×32, the pre-flight count
const FRAME = path.join(FIX, 'frame.jpg')        // the video leg's bytes (a PNG named .jpg)

// One project per run: the demo project already holds a one.jpg from core-loop, so a shared project
// would change the duplicate count depending on which spec ran first.
const runId = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`

const uploadUrl = (slug: string) => `/${seeded.workspace}/p/${slug}/upload`

// The refusal of the file leg is client-side (a .psd is not an image) and the URL legs stub their
// POST, so any console error is a defect of the page under test.
function watchErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()) })
  page.on('pageerror', (error) => errors.push(error.message))
  return errors
}

async function demoToken(request: APIRequestContext): Promise<string> {
  const login = await request.post('/api/auth/login', {
    data: { email: seeded.email, password: seeded.password },
  })
  if (!login.ok()) throw new Error(`the demo login answered ${login.status()}: is the API up?`)
  return ((await login.json()) as { token: string }).token
}

/** A project of this run's own, made through the shipped route: setup, never a journey assertion. */
async function newProject(request: APIRequestContext, label: string): Promise<string> {
  const token = await demoToken(request)
  const res = await request.post(`/api/ws/${seeded.workspace}/projects`, {
    data: { name: `${label} ${runId}`, type: 'object-detection' },
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok()) throw new Error(`create project answered ${res.status()}: ${await res.text()}`)
  return ((await res.json()) as { slug: string }).slug
}

// The demo workspace is on the three-project free plan; every project this file made is moved to the
// trash with the shipped delete action (reversible), and nothing this run did not create is touched.
test.afterEach(async ({ request }) => {
  let token: string
  try { token = await demoToken(request) } catch { return }
  const headers = { Authorization: `Bearer ${token}` }
  const list = await request.get(`/api/ws/${seeded.workspace}/projects`, { headers })
  if (!list.ok()) return
  for (const p of (await list.json()) as { slug: string }[]) {
    if (p.slug.includes(runId)) {
      await request.delete(`/api/ws/${seeded.workspace}/projects/${p.slug}`, { headers })
    }
  }
})

test.beforeEach(() => record.reset())

const uploadInput = (page: Page) => page.locator('input[type=file]').first()
const dropZone = (page: Page) => page.getByText(/Drag and drop images, folders or zips/i).first()
/** The card's pre-flight line: "40 images · 3 duplicates will be skipped · 0 too large". */
const preflight = (page: Page) => page.getByText(/duplicates? will be skipped/i).first()
const saveButton = (page: Page) => page.getByRole('button', { name: /^(Save and Continue|Saving|Uploading|Adding)/i })
/** The card's result sheet: "Added 2 · duplicates 1 · failed 0" with per-file reasons under it. */
const resultSheet = (page: Page) => page.getByText(/Added \d+ · duplicates \d+ · failed \d+/i).first()
/** The same panel in today's words: the layout and isolation legs measure it, copy is J3's subject. */
const anySheet = (page: Page) =>
  page.getByText(/(Added|Uploaded) \d+ · duplicates( skipped)? \d+ · failed \d+/i).first()

/** A file that is not an image: the card's refusal case. The bytes never matter. */
const refusedFile = () => ({ name: 'scan.psd', mimeType: 'image/vnd.adobe.photoshop', buffer: Buffer.from('8BPS') })

/** A fixture as an input payload; Playwright accepts one form per call, never paths mixed with buffers. */
const asFile = (file: string, mimeType: string) => ({
  name: path.basename(file), mimeType, buffer: readFileSync(file),
})
const jpg = (file: string) => asFile(file, 'image/jpeg')

/** Drag a file onto the zone the way a browser delivers it: a DataTransfer with one File in it. */
async function dragIn(page: Page, file: { name: string; mimeType: string; buffer: Buffer }): Promise<void> {
  const dataTransfer = await page.evaluateHandle(({ name, type, b64 }) => {
    const bin = atob(b64)
    const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0))
    const dt = new DataTransfer()
    dt.items.add(new File([bytes], name, { type }))
    return dt
  }, { name: file.name, type: file.mimeType, b64: file.buffer.toString('base64') })
  await dropZone(page).dispatchEvent('drop', { dataTransfer })
}

async function expectNoHorizontalScroll(page: Page): Promise<void> {
  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow, 'the page is wider than its viewport').toBeLessThanOrEqual(0)
}

test('J3 upload three files and read the result sheet', async ({ page, request }) => {
  const errors = watchErrors(page)
  const slug = await newProject(request, 'J3 Upload')
  await signIn(page)
  await page.goto(uploadUrl(slug))

  await test.step('1. Upload: one drop zone takes browse, folder and drag', async () => {
    await expect(page.getByRole('heading', { name: /Upload/i })).toBeVisible()
    await expect(dropZone(page)).toBeVisible()
    await expect(page.getByRole('button', { name: /Select Files/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /Select Folder/i })).toBeVisible()
    record.step()
  })

  await test.step('2. A dragged file is accepted, and the pre-flight counts it before the button', async () => {
    await dragIn(page, { name: 'small-drag.png', mimeType: 'image/png', buffer: readFileSync(SMALL) })
    // The dragged file joins the pick: one image, no duplicate, nothing too large.
    await expect(preflight(page), 'the drag was taken as an image').toContainText(/\b1 image\b/i)
    record.step()
  })

  await test.step('3. A refused format names the format and the accepted list, and is not a silent skip', async () => {
    await uploadInput(page).setInputFiles([refusedFile(), jpg(DUP), jpg(ONE)])
    // The refusal line names the extension; the accepted list is stated beside the zone.
    await expect(page.getByText(/1 file ignored \(psd\)/i).first(), 'the refused file is named').toBeVisible()
    await expect(page.getByText(/(JPEG|JPG)[^.]*PNG|PNG[^.]*(JPEG|JPG)/i).first(),
      'the accepted image formats are named').toBeVisible()
    // Two of the three images are new: one.jpg and duplicate.jpg are byte-identical, so one is skipped.
    await expect(preflight(page)).toContainText(/\b2 images\b/i)
    await expect(preflight(page)).toContainText(/\b1 duplicate\b/i)
    await expect(preflight(page)).toContainText(/\b0 too large\b/i)
    record.step()
  })

  await test.step('4. Batch and split: a dated default, and Auto 80 / 10 / 10', async () => {
    const batch = page.getByLabel(/Batch name/i)
    await expect(batch).toBeVisible()
    await expect(batch, 'the batch name defaults to the date').toHaveValue(/\d{4}-\d{2}-\d{2}/)
    await expect(batch, 'the batch name names the shift').toHaveValue(/shift/i)
    await expect(page.getByText(/Auto\s*80\s*\/\s*10\s*\/\s*10/i).first(),
      'the split chip reads Auto 80 / 10 / 10').toBeVisible()
    record.step()
  })

  await test.step('5. Save and Continue: the button is busy in place', async () => {
    // Hold the POST for a moment so the busy state is observable: a three-file chunk otherwise
    // finishes between two polls and the loading state can never be asserted.
    await page.route('**/upload', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 800))
      await route.continue()
    })
    await saveButton(page).click()
    await expect(saveButton(page), 'the button reports its work').toHaveText(/Uploading|Saving|Adding/i)
    record.step()
  })

  await test.step('6. The result sheet reads Added 2 · duplicates 1 · failed 0 and names the skip', async () => {
    await expect(resultSheet(page), 'the sheet counts what happened').toBeVisible({ timeout: 60_000 })
    await expect(resultSheet(page)).toContainText(/Added 2 · duplicates 1 · failed 0/i)
    // Nothing is silently skipped: the sheet names the file that did not go in.
    await expect(page.getByText(/(one|duplicate|small-drag)\.(jpg|png)/i).last(),
      'the skipped duplicate is named').toBeVisible()
    record.step()
  })

  await test.step('7. View Dataset: the new images are there with the reviewer filter cleared', async () => {
    await page.getByRole('button', { name: /View Dataset/i }).click()
    await expect(page.getByRole('heading', { name: /Dataset/i })).toBeVisible()
    // A fresh upload has no labels, so the reviewer default (approved) hides it; clear it.
    await page.getByRole('combobox').first().selectOption('all')
    await expect(page.getByRole('button', { name: /^Open .+ in the editor$/ }), 'the two added images')
      .toHaveCount(2)
    record.step()
  })

  const result = record.done({ steps: 7, timeMs: 90_000 })
  test.info().annotations.push({ type: 'journey-result', description: `J3 ${result.steps} steps, ${result.timeMs} ms` })
  expect(result, JSON.stringify(result)).toMatchObject({ ok: true })
  expect(errors, `console errors: ${errors.join(' | ')}`).toEqual([])
})

test('J3b a URL import refuses a private address in place', async ({ page, request }) => {
  // T-068 gates the URL row behind T-066's key. Until that card lands the key is not even
  // registered, so the switch is attempted and its absence becomes the finding, not a dead test.
  try {
    await setFlags(request, ['task_66'])
  } catch (error) {
    if (!/unknown feature flag/i.test(String(error))) throw error
    test.info().annotations.push({ type: 'note', description: 'task_66 is not a registered flag yet' })
  }
  const slug = await newProject(request, 'J3 Url')
  await signIn(page)
  await page.goto(uploadUrl(slug))

  // The URL row lives on the same page, and it validates the scheme before any request.
  await expect(page.getByRole('button', { name: /Add from URL/i }),
    'the upload page offers a URL row').toBeVisible()
  await page.getByRole('button', { name: /Add from URL/i }).click()
  const field = page.getByRole('textbox', { name: /URL/i })
  await expect(field).toBeVisible()
  await field.fill('ftp://images.example.com/gate.jpg')
  await page.getByRole('button', { name: /^(Import|Add)$/i }).click()
  await expect(page.getByRole('alert').filter({ hasText: /http/i }).first(),
    'a scheme other than http(s) is refused in place').toBeVisible()

  // A public address goes in, and the same sheet shape reports it. The POST is stubbed: CI never
  // fetches a real URL.
  await stubApi(page, '**/uploads/from-url', { body: { uploaded: 1, duplicates: 0, failed: [] }, times: 1 })
  await field.fill('https://images.labeldesk.dev/gate-1.jpg')
  await page.getByRole('button', { name: /^(Import|Add)$/i }).click()
  await expect(resultSheet(page), 'the URL leg reads like the file leg').toBeVisible({ timeout: 30_000 })
  await expect(resultSheet(page)).toContainText(/Added 1 · duplicates 0 · failed 0/i)

  // A private address is refused by the shipped route with a remedy sentence, never silently skipped.
  await page.getByRole('button', { name: /Add from URL/i }).click()
  await page.getByRole('textbox', { name: /URL/i }).fill('http://10.0.0.5/gate.jpg')
  await page.getByRole('button', { name: /^(Import|Add)$/i }).click()
  const refusal = page.getByRole('alert').filter({ hasText: /private|local network|internal/i }).first()
  await expect(refusal, 'the private address is refused in place').toBeVisible({ timeout: 30_000 })
  await expect(refusal, 'the refusal carries a remedy').toContainText(/download|save it|upload the file|ask/i)
})

test('J3c video frames open the extraction dialog', { tag: '@nightly' }, async ({ page, request }) => {
  await setFlags(request, ['task_22'])
  const slug = await newProject(request, 'J3 Video')
  await signIn(page)
  await page.goto(`/${seeded.workspace}/p/${slug}/videos`)

  // Choosing a file opens the dialog; nothing is uploaded until the plan is confirmed.
  await page.locator('input[type=file]').first().setInputFiles({
    name: 'gate.mp4', mimeType: 'video/mp4', buffer: readFileSync(FRAME),
  })
  const dialog = page.getByRole('dialog')
  await expect(dialog, 'choosing a video opens the extraction dialog').toBeVisible({ timeout: 30_000 })

  // Trim, rate and the live plan line: what it will produce, stated before the job.
  await expect(dialog.getByRole('slider'), 'two trim handles').toHaveCount(2)
  await expect(dialog.getByLabel(/fps|interval|every/i).first(), 'the rate is a control').toBeVisible()
  await expect(dialog.getByText(/Every .+ · .+→.+ · .+ frames?/i).first(), 'the plan line states the yield')
    .toBeVisible()

  // Hand-picked frames: the same moment twice adds nothing.
  await dialog.press('m')
  await expect(dialog.getByText(/1 hand-picked/i).first()).toBeVisible()
  await dialog.press('m')
  await expect(dialog.getByText(/1 hand-picked/i).first(), 'a repeated pick adds nothing').toBeVisible()

  // Start extraction: the tray row appears and the frames are counted as they land.
  await dialog.getByRole('button', { name: /Start extraction/i }).click()
  await expect(dialog).toHaveCount(0)
  await expect(page.getByText(/Extracting frames/i).first(), 'the job card appears').toBeVisible({ timeout: 30_000 })
  await expect(page.getByText(/\b3 frames\b/i).first(), 'the job card counts the frames it wrote')
    .toBeVisible({ timeout: 30_000 })
})

test('J3d flag off: the frame leg is named off and the file leg still works', async ({ page, request }) => {
  await setFlags(request, ['task_22'], false)
  const slug = await newProject(request, 'J3 Off')
  await signIn(page)

  // The gated surface says it is off, in its own name: skipped with a reason, not silently missing.
  await page.goto(`/${seeded.workspace}/p/${slug}/videos`)
  const notice = page.getByText(/is not enabled in this workspace/i).first()
  await expect(notice, 'the gated surface says it is off').toBeVisible()
  await expect(notice, 'the reason names the surface it hides').toContainText(/Video/i)

  // The file leg is unaffected by the video flag.
  await page.goto(uploadUrl(slug))
  await expect(dropZone(page)).toBeVisible()
  await uploadInput(page).setInputFiles(SMALL)
  await saveButton(page).click()
  await expect(anySheet(page), 'the file leg still completes').toBeVisible({ timeout: 60_000 })
  await expect(anySheet(page)).toContainText(/failed 0/i)
})

test('J3e at 375 the drop zone and the result sheet stack without horizontal scroll', async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  const slug = await newProject(request, 'J3 Narrow')
  await signIn(page)
  await page.goto(uploadUrl(slug))

  await expect(dropZone(page)).toBeVisible()
  await expectNoHorizontalScroll(page)

  await uploadInput(page).setInputFiles([SMALL, ONE])
  await expect(page.getByText(/new images/i).first(), 'the pick is counted').toBeVisible()
  await expectNoHorizontalScroll(page)
  await saveButton(page).click()
  await expect(anySheet(page)).toBeVisible({ timeout: 60_000 })
  await expectNoHorizontalScroll(page)

  const box = await anySheet(page).boundingBox()
  expect(box, 'the sheet has a box').not.toBeNull()
  expect(box!.x, 'the sheet starts inside the viewport').toBeGreaterThanOrEqual(0)
  expect(box!.x + box!.width, 'the sheet is not wider than the viewport').toBeLessThanOrEqual(376)
})

test('J3f an upload into one workspace is absent from another', async ({ page, request, browser }) => {
  // Workspace A: the seeded demo workspace, through the upload page.
  const slug = await newProject(request, 'J3 Iso')
  await signIn(page)
  await page.goto(uploadUrl(slug))
  await uploadInput(page).setInputFiles([SMALL, ONE])
  await saveButton(page).click()
  await expect(anySheet(page)).toBeVisible({ timeout: 60_000 })

  // Workspace B: a fresh signup, a project of its own, and the same bytes.
  const other = await browser.newContext()
  const b = await other.newPage()
  const bErrors: string[] = []
  b.on('console', (m) => { if (m.type() === 'error') bErrors.push(m.text()) })
  await b.goto('/signup')
  await b.locator('#signup-name').fill('J3 Other Buyer')
  await b.locator('#signup-email').fill(`j3+${runId}@labeldesk.dev`)
  await b.locator('#signup-password').fill('labeldesk-j3-passphrase')
  await b.locator('#signup-workspace').fill(`J3 Other ${runId}`)
  await b.getByRole('button', { name: 'Create account' }).click()
  await expect(b.getByRole('heading', { name: 'Home', exact: true })).toBeVisible({ timeout: 30_000 })
  const end = b.getByRole('button', { name: 'End tour' })
  if (await end.isVisible().catch(() => false)) await end.click()

  await b.getByRole('button', { name: /^New project$/i }).first().click()
  const bDialog = b.getByRole('dialog')
  await expect(bDialog).toBeVisible()
  await bDialog.getByLabel(/Project Name/i).fill(`J3 Other ${runId}`)
  await bDialog.getByRole('button', { name: /Object Detection/i }).click()
  await bDialog.getByRole('button', { name: /Create project/i }).click()
  await expect(bDialog).toHaveCount(0, { timeout: 30_000 })

  // The same bytes that already landed in workspace A are new to B: no duplicate, and A's file is
  // not in B's dataset.
  await uploadInput(b).setInputFiles([SMALL, ONE])
  await saveButton(b).click()
  await expect(anySheet(b), 'B knows nothing of A\'s copies').toBeVisible({ timeout: 60_000 })
  await expect(anySheet(b), 'the same bytes are new to B').toContainText(/duplicates( skipped)? 0/i)
  await expect(anySheet(b)).toContainText(/failed 0/i)
  await b.getByRole('button', { name: /View Dataset/i }).click()
  await b.getByRole('combobox').first().selectOption('all')
  await expect(b.getByRole('button', { name: /^Open .+ in the editor$/ })).toHaveCount(2)

  expect(bErrors, `console errors in the second workspace: ${bErrors.join(' | ')}`).toEqual([])
  await other.close()
})
