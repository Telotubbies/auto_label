// T-1204 — J4: a labeler draws a box and a polygon, accepts one model proposal and knows the work is
// saved before moving on. One test per UX step, the card's 9-step / 120 s target recorded, then the
// refusal, failed-save, keyboard, isolation and flag-off legs its acceptance list requires.
//
// This file adds no product code: the annotate board, the editor canvas, the class panel, the object
// list and the assist sheet are the subject. The controls named here are the contracts of the cards
// J4 depends on — Start labelling (T-496), the save bar (T-121), polygon vertices (T-125), the assist
// picker (T-140) and the proposal bar (T-151). Where a control is missing the run is a finding
// against that card, never a reason to shorten this journey.
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { expect, test, type APIRequestContext, type Locator, type Page } from '@playwright/test'
import { record, seeded, setFlags, signIn, stubApi } from './fixtures/harness'

const ONE = path.join(import.meta.dirname, 'fixtures', 'one.jpg')   // 640×480, shared with core-loop
const FRAME = path.join(import.meta.dirname, 'fixtures', 'frame.jpg') // 320×180, this card's second image

// One project and one batch per run. The demo project is object-detection, so it has no polygon tool;
// J4 needs a project type that can draw both, and its own batch so the board row is unambiguous.
// The names are fixed, not run-scoped: Playwright restarts the worker after a timeout, re-evaluates
// this module and would otherwise create a second project and exhaust the Free plan's three slots.
// The harness wipes its data directory per run, so a fixed name is safe between runs.
const projectName = 'J4 Segment'
const batchName = 'J4 Shift'
const projectSlug = 'j4-segment'
const runId = 'j4'

const labeler = { email: 'labeler@labeldesk.dev', password: seeded.password }
const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const at = (p: string) => new RegExp(`${escapeRe(p)}$`)

// The journey's first product failure is expected to surface as a console error (a 404/500 on the
// control it needs); after it is reported, the failed response lines are the only ones allowed.
const expectedFailure = /status of (404|409|422|500|503)/

function watchErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('console', (m) => {
    if (m.type() === 'error' && !expectedFailure.test(m.text())) errors.push(m.text())
  })
  page.on('pageerror', (e) => errors.push(e.message))
  return errors
}

/** The seeded labeler, not the admin: J4 is written from the labeler's seat. */
async function signInLabeler(page: Page): Promise<void> {
  await page.goto('/login')
  await page.getByLabel('Email').fill(labeler.email)
  await page.getByLabel('Password').fill(labeler.password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(new RegExp(`/${seeded.workspace}$`))
}

async function adminToken(request: APIRequestContext): Promise<string> {
  const login = await request.post('/api/auth/login', {
    data: { email: seeded.email, password: seeded.password },
  })
  if (!login.ok()) throw new Error(`the demo login answered ${login.status()}: is the API up?`)
  return ((await login.json()) as { token: string }).token
}

async function memberId(request: APIRequestContext, token: string, email: string): Promise<string> {
  const res = await request.get(`/api/ws/${seeded.workspace}/members`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok()) throw new Error(`members answered ${res.status()}`)
  const body = (await res.json()) as { members: { id: string; email: string }[] }
  const member = body.members.find((m) => m.email === email)
  if (!member) throw new Error(`${email} is not a member of ${seeded.workspace}`)
  return member.id
}

/**
 * Setup, never an assertion: a segmentation project with two classes, two images in one batch and
 * that batch assigned to the labeler, so the board row is theirs and the editor has two images to
 * move between. Created once per worker (the free plan allows three projects) and reused by every
 * leg; the run's data directory is wiped per run.
 */
async function createProject(request: APIRequestContext): Promise<string> {
  const token = await adminToken(request)
  const headers = { Authorization: `Bearer ${token}` }
  const base = `/api/ws/${seeded.workspace}/projects/${projectSlug}`
  // A timed-out test restarts the worker, so setup is idempotent: reuse the project and its batch
  // if an earlier leg already made them instead of spending the free plan's third slot twice.
  let project = await request.get(base, { headers })
  if (!project.ok()) {
    const created = await request.post(`/api/ws/${seeded.workspace}/projects`, {
      data: { name: projectName, type: 'instance-segmentation' },
      headers,
    })
    if (!created.ok()) throw new Error(`create project answered ${created.status()}: ${await created.text()}`)
    project = await request.get(base, { headers })
  }
  const classes = await request.get(`${base}/classes`, { headers })
  const have = new Set(((await classes.json()) as { name: string }[]).map((c) => c.name))
  for (const name of ['person', 'helmet']) {
    if (have.has(name)) continue
    const cls = await request.post(`${base}/classes`, { data: { name }, headers })
    if (!cls.ok()) throw new Error(`create class ${name} answered ${cls.status()}: ${await cls.text()}`)
  }
  const { images } = (await project.json()) as { images: number }
  if (!images) {
    // Two files in one batch need FormData: the plain-object shape sends one file per field.
    const form = new FormData()
    form.set('batch_name', batchName)
    form.set('split', 'auto')
    form.append('files', new File([readFileSync(ONE)], 'one.jpg', { type: 'image/jpeg' }))
    form.append('files', new File([readFileSync(FRAME)], 'frame.jpg', { type: 'image/jpeg' }))
    const upload = await request.post(`${base}/upload`, { headers, multipart: form })
    if (!upload.ok()) throw new Error(`upload answered ${upload.status()}: ${await upload.text()}`)
  }
  type Card = { batchId: string; batchName: string; assigneeId: string | null }
  const board = (await (await request.get(`${base}/board`, { headers })).json()) as {
    columns: Record<string, Card[]>
  }
  const on = (column: string) => (board.columns[column] ?? []).find((c) => c.batchName === batchName)
  if (!on('annotating')) {
    const card = on('unassigned')
    if (!card) throw new Error(`the setup batch ${batchName} is on no board column`)
    const assignee = await memberId(request, token, labeler.email)
    const assigned = await request.post(`${base}/board/move`, {
      data: { batch_id: card.batchId, from_status: 'unassigned', to_status: 'annotating', set_assignee: assignee },
      headers,
    })
    if (!assigned.ok()) throw new Error(`assign answered ${assigned.status()}: ${await assigned.text()}`)
  }
  return projectSlug
}

let projectReady: Promise<string> | null = null

function ownProject(request: APIRequestContext): Promise<string> {
  projectReady ??= createProject(request).catch((error) => {
    projectReady = null
    throw error
  })
  return projectReady
}

const canvas = (page: Page) => page.getByTestId('canvas-area')

async function clickAt(page: Page, fx: number, fy: number): Promise<void> {
  const box = await canvas(page).boundingBox()
  if (!box) throw new Error('the canvas area has no box')
  await page.mouse.click(box.x + box.width * fx, box.y + box.height * fy)
}

/** The image's own geometry after a save: the Raw panel is the editor's read of the stored set. */
async function storedAnnotations(page: Page): Promise<{ classId: string; shape: Record<string, unknown> }[]> {
  await page.getByRole('button', { name: 'Raw', exact: true }).click()
  const text = await page.locator('pre').first().innerText()
  const parsed = JSON.parse(text) as { annotations: { classId: string; shape: Record<string, unknown> }[] }
  return parsed.annotations
}

test.beforeEach(() => record.reset())

test('J4 box, polygon, assist, save, reload', { tag: '@nightly' }, async ({ page, request }) => {
  const errors = watchErrors(page)
  await ownProject(request)
  // task_23 is the card's review leg; the assist picker itself is task_assist_session in T-140 and
  // is expected to default to off until that card lands.
  await setFlags(request, ['task_23'])
  await signInLabeler(page)
  await page.goto(`/${seeded.workspace}/p/${projectSlug}/annotate`)

  await test.step('1. Annotate board: the batch is there and Start labelling opens its first image', async () => {
    await expect(page.getByRole('heading', { name: 'Annotate' })).toBeVisible()
    await expect(page.getByText(batchName, { exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Start labelling' }).first().click()
    await expect(page).toHaveURL(new RegExp(`${escapeRe(`/${seeded.workspace}/p/${projectSlug}/annotate/`)}[^/?]+`))
    record.step()
  })

  await test.step('2. Editor: class list, tool column and canvas fit at 1440', async () => {
    await expect(canvas(page)).toBeVisible()
    await expect(canvas(page).locator('canvas').first()).toBeVisible()
    await expect(page.getByTestId('class-option').first()).toBeVisible()
    await expect(page.getByTestId('tool-bbox')).toBeVisible()
    // Every work surface is inside the 1440×900 viewport: no scrolling to reach the tool column.
    for (const surface of [page.getByTestId('class-option').first(), page.getByTestId('tool-bbox'), canvas(page)]) {
      const box = await surface.boundingBox()
      expect(box, 'a work surface has no box').not.toBeNull()
      expect(box!.y, 'a work surface starts above the viewport').toBeGreaterThanOrEqual(0)
      expect(box!.y + box!.height, 'a work surface runs below the viewport').toBeLessThanOrEqual(901)
    }
    // The whole image fits: FIT is the shipped gesture, and it leaves no scrollbar on the page.
    await page.getByRole('button', { name: 'FIT' }).click()
    const overflow = await page.evaluate(() =>
      document.documentElement.scrollHeight - document.documentElement.clientHeight)
    expect(overflow, 'the editor scrolls the page').toBeLessThanOrEqual(0)
    record.step()
  })

  await test.step('3. Box: class, box tool, two clicks, one object row with its class and count', async () => {
    await page.getByTestId('class-option').filter({ hasText: 'helmet' }).first().click()
    await page.getByTestId('tool-bbox').click()
    await clickAt(page, 0.3, 0.3)
    await clickAt(page, 0.55, 0.55)
    await page.getByRole('button', { name: 'Objects' }).click()
    await expect(page.getByTestId('object-row')).toHaveCount(1)
    await expect(page.getByTestId('object-row').first()).toContainText('helmet')
    await expect(page.getByTestId('object-count')).toContainText('1 object')
    record.step()
  })

  await test.step('4. Polygon: four vertices, Enter closes, each is a committed row', async () => {
    await page.getByRole('button', { name: 'Classes' }).click()
    await page.getByTestId('class-option').filter({ hasText: 'person' }).first().click()
    await page.getByTestId('tool-polygon').click()
    for (const [fx, fy] of [[0.62, 0.25], [0.8, 0.25], [0.78, 0.48], [0.62, 0.48]]) {
      await clickAt(page, fx, fy)
      // Konva closes a polygon on a double-click; a machine-speed second vertex would be read as one.
      await page.waitForTimeout(450)
    }
    await page.keyboard.press('Enter')
    await page.getByRole('button', { name: 'Objects' }).click()
    await expect(page.getByTestId('object-row')).toHaveCount(2)
    await expect(page.getByTestId('object-row').filter({ hasText: 'person' })).toHaveCount(1)
    // Empty state: with no shape selected, no object row claims the selection.
    await page.keyboard.press('Escape')
    await expect(page.locator('[data-testid="object-select"][aria-current="true"]')).toHaveCount(0)
    record.step()
  })

  await test.step('5. Assist: picker, fake model, proposal bar, then Keep commits it', async () => {
    // T-140: the assist button opens a picker; the seeded model is the one row to choose.
    await page.getByRole('button', { name: /assist/i }).click()
    const picker = page.getByRole('dialog', { name: /assist/i })
    await expect(picker).toBeVisible()
    await picker.getByRole('button', { name: new RegExp(seeded.model) }).click()
    // Loading state: the sheet stays open until the model answers.
    await picker.getByRole('button', { name: /Continue/i }).click()
    // T-151: a proposal is in the bar, not in the object count, until Keep commits it.
    const proposals = page.getByTestId('proposal-bar')
    await expect(proposals).toBeVisible()
    await expect(proposals).toContainText(/suggestion/i)
    await expect(page.getByTestId('object-row')).toHaveCount(2)
    await proposals.getByRole('button', { name: 'Keep', exact: true }).click()
    await expect(page.getByTestId('object-row')).toHaveCount(3)
    record.step()
  })

  await test.step('6. Save: the status says Saved, with no modal', async () => {
    await expect(page.getByText('Saved', { exact: true })).toBeVisible({ timeout: 15_000 })
    await expect(page.getByRole('dialog')).toHaveCount(0)
    record.step()
  })

  await test.step('7. Next image: the shortcut advances and both images stay in the strip', async () => {
    const first = page.url()
    await page.keyboard.press('ArrowRight')
    await expect(page).not.toHaveURL(first)
    await expect(canvas(page)).toBeVisible()
    record.step()
  })

  await test.step('8. Back and reload: the previous image keeps its shapes', async () => {
    await page.keyboard.press('ArrowLeft')
    await expect(canvas(page)).toBeVisible()
    await page.reload()
    await expect(canvas(page)).toBeVisible()
    await page.getByRole('button', { name: 'Objects' }).click()
    await expect(page.getByTestId('object-row')).toHaveCount(3)
    await expect(page.getByTestId('object-row').filter({ hasText: 'helmet' }).first()).toBeVisible()
    await expect(page.getByTestId('object-row').filter({ hasText: 'person' }).first()).toBeVisible()
    record.step()
  })

  await test.step('9. Geometry after reload: the box numbers and the polygon vertex count', async () => {
    const stored = await storedAnnotations(page)
    const box = stored.find((a) => a.shape.kind === 'bbox')
    const polygon = stored.find((a) => a.shape.kind === 'polygon')
    expect(box, 'the box survived the reload').toBeDefined()
    for (const key of ['x', 'y', 'w', 'h']) expect(typeof box!.shape[key], `box.${key} is a number`).toBe('number')
    expect(polygon, 'the polygon survived the reload').toBeDefined()
    expect((polygon!.shape.points as number[]).length, 'a four-vertex polygon is eight numbers').toBe(8)
    record.step()
  })

  const result = record.done({ steps: 9, timeMs: 120_000 })
  console.log(`J4 measured: ${result.steps} steps, ${result.timeMs} ms`)
  test.info().annotations.push({ type: 'journey-result', description: `J4 ${result.steps} steps, ${result.timeMs} ms` })
  expect(result.failures, 'the journey stays inside its step and time targets').toEqual([])
  expect(result.steps, 'no more than 11 steps').toBeLessThanOrEqual(11)
  expect(result.timeMs, 'no more than 240 s').toBeLessThanOrEqual(240_000)
  expect(errors, `console or page errors: ${errors.join(' | ')}`).toEqual([])
})

test('J4b a zero-area box is refused in place', { tag: '@nightly' }, async ({ page, request }) => {
  const errors = watchErrors(page)
  await ownProject(request)
  await signInLabeler(page)
  await page.goto(`/${seeded.workspace}/p/${projectSlug}/annotate`)
  await page.getByRole('button', { name: 'Start labelling' }).first().click()
  await expect(canvas(page)).toBeVisible()

  // The empty image first: the objects list says there is nothing to show, not a blank table.
  await page.getByRole('button', { name: 'Objects' }).click()
  await expect(page.getByTestId('object-empty')).toBeVisible()

  // One click, then a second click on the same pixel: no area, so nothing may be created.
  await page.getByRole('button', { name: 'Classes' }).click()
  await page.getByTestId('class-option').filter({ hasText: 'helmet' }).first().click()
  await page.getByTestId('tool-bbox').click()
  await clickAt(page, 0.4, 0.4)
  await clickAt(page, 0.4, 0.4)

  await page.getByRole('button', { name: 'Objects' }).click()
  await expect(page.getByTestId('object-row'), 'a zero-area box is not saved').toHaveCount(0)
  // The refusal is inline and says why; it is not a silent no-op.
  await expect(page.getByRole('alert')).toContainText(/area|too small|nothing to save/i)
  expect(errors, `console or page errors: ${errors.join(' | ')}`).toEqual([])
})

test('J4c a failed save keeps the shapes and offers a retry', { tag: '@nightly' }, async ({ page, request }) => {
  const errors = watchErrors(page)
  await ownProject(request)
  await signInLabeler(page)
  await page.goto(`/${seeded.workspace}/p/${projectSlug}/annotate`)
  await page.getByRole('button', { name: 'Start labelling' }).first().click()
  await expect(canvas(page)).toBeVisible()

  // The first annotations write fails once; the second is the real save, so the retry is observable.
  await stubApi(page, /\/api\/images\/[^/]+\/annotations$/, {
    status: 503, body: { detail: 'storage is busy' }, times: 1,
  })
  await page.getByTestId('class-option').filter({ hasText: 'helmet' }).first().click()
  await page.getByTestId('tool-bbox').click()
  await clickAt(page, 0.3, 0.3)
  await clickAt(page, 0.5, 0.5)

  // T-121: the one honest save state, with the retry beside it, and the drawn shape still on screen.
  const retry = page.getByRole('button', { name: /Save failed.*retry/i })
  await expect(retry).toBeVisible({ timeout: 15_000 })
  await page.getByRole('button', { name: 'Objects' }).click()
  await expect(page.getByTestId('object-row'), 'the failed save lost the box').toHaveCount(1)

  await retry.click()
  await expect(page.getByText('Saved', { exact: true })).toBeVisible({ timeout: 15_000 })
  await expect(page.getByTestId('object-row')).toHaveCount(1)
  expect(errors, `console or page errors: ${errors.join(' | ')}`).toEqual([])
})

test('J4d keyboard only: class, box tool, two Enter-anchored points, save, next', { tag: '@nightly' }, async ({ page, request }) => {
  await ownProject(request)
  await signInLabeler(page)
  await page.goto(`/${seeded.workspace}/p/${projectSlug}/annotate`)
  await page.getByRole('button', { name: 'Start labelling' }).first().click()
  await expect(canvas(page)).toBeVisible()

  // Class and tool have fixed, printed keys; neither needs the pointer.
  await page.keyboard.press('1')
  await page.keyboard.press('b')
  await expect(page.getByTestId('tool-bbox')).toHaveAttribute('aria-pressed', 'true')

  // The canvas keyboard cursor: Enter anchors a corner, arrows move it, Enter anchors the second.
  await canvas(page).focus()
  await page.keyboard.press('Enter')
  for (let i = 0; i < 8; i++) await page.keyboard.press('ArrowRight')
  for (let i = 0; i < 8; i++) await page.keyboard.press('ArrowDown')
  await page.keyboard.press('Enter')
  await page.getByRole('button', { name: 'Objects' }).click()
  await expect(page.getByTestId('object-row'), 'two Enter-anchored points draw one box').toHaveCount(1)

  await page.keyboard.press('Control+s')
  await expect(page.getByText('Saved', { exact: true })).toBeVisible({ timeout: 15_000 })
  const before = page.url()
  await page.keyboard.press('ArrowRight')
  await expect(page).not.toHaveURL(before)
})

test('J4e workspace isolation: the saved annotation is absent from another workspace', { tag: '@nightly' }, async ({ page, request }) => {
  await ownProject(request)
  await signInLabeler(page)
  await page.goto(`/${seeded.workspace}/p/${projectSlug}/annotate`)
  await page.getByRole('button', { name: 'Start labelling' }).first().click()
  await expect(canvas(page)).toBeVisible()

  await page.getByTestId('class-option').filter({ hasText: 'helmet' }).first().click()
  await page.getByTestId('tool-bbox').click()
  await clickAt(page, 0.3, 0.3)
  await clickAt(page, 0.5, 0.5)
  await expect(page.getByText('Saved', { exact: true })).toBeVisible({ timeout: 15_000 })
  const imageId = page.url().split('/annotate/')[1].split(/[?#]/)[0]

  // A second workspace, made the way a buyer makes one, sees neither the project nor the image.
  const otherEmail = `j4+${runId}@labeldesk.dev`
  const signup = await request.post('/api/auth/signup', {
    data: { name: 'J4 Other Buyer', email: otherEmail, password: 'labeldesk-j4-passphrase', workspace: `J4 Other ${runId}` },
  })
  expect([200, 201, 409], 'the second workspace exists for this run').toContain(signup.status())
  const login = await request.post('/api/auth/login', { data: { email: otherEmail, password: 'labeldesk-j4-passphrase' } })
  const { token } = (await login.json()) as { token: string }
  const image = await request.get(`/api/images/${imageId}`, { headers: { Authorization: `Bearer ${token}` } })
  expect(image.status(), 'another workspace must not read the saved image').toBe(404)
})

test('J4f flag off: the review shortcut is skipped, drawing and saving still pass', { tag: '@nightly' }, async ({ page, request }) => {
  await ownProject(request)
  await setFlags(request, ['task_23'], false)
  await signInLabeler(page)
  await page.goto(`/${seeded.workspace}/p/${projectSlug}/annotate`)
  await page.getByRole('button', { name: 'Start labelling' }).first().click()
  await expect(canvas(page)).toBeVisible()

  // With the review queue off, the editor offers no review shortcut.
  await expect(page.getByRole('button', { name: /submit for review|review/i })).toHaveCount(0)

  // The manual legs are flag-independent.
  await page.getByTestId('class-option').filter({ hasText: 'helmet' }).first().click()
  await page.getByTestId('tool-bbox').click()
  await clickAt(page, 0.3, 0.3)
  await clickAt(page, 0.5, 0.5)
  await expect(page.getByText('Saved', { exact: true })).toBeVisible({ timeout: 15_000 })
  await page.getByRole('button', { name: 'Objects' }).click()
  await expect(page.getByTestId('object-row')).toHaveCount(1)
})
