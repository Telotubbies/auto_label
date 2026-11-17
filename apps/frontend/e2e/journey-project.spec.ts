// T-1202 — J2: a buyer with one task in mind picks a project type in words they recognise, names
// the project, and lands where the work starts. Five deliberate actions, one step each, against the
// card's 5-step / 45 s target. J2b proves a duplicate name is refused in place; the rest of the
// acceptance list (375 px, keyboard only, workspace isolation, `task_470` off) is one test each.
//
// This file adds no product code: the dialog and the three screens around it are the subject.
import { expect, test, type APIRequestContext, type Page } from '@playwright/test'
import { record, seeded, setFlags, signIn } from './fixtures/harness'

// One name per run. The seed is not reset between runs, and J2b needs a name only it owns.
const runId = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
const projectName = `J2 Gate Check ${runId}`
// The address the server derives from the name (`slugify`: lower case, non-alphanumerics to dashes).
const projectSlug = `j2-gate-check-${runId}`
const address = `/${seeded.workspace}/p/${projectSlug}`

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const at = (path: string) => new RegExp(`${escapeRe(path)}$`)

// The duplicate create is the flow's one expected refusal; Chromium logs a failed response as a
// console error, so that line is allowed. Any other console or page error fails the test.
const expectedRefusal = /status of (409|422)/

function watchErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error' && !expectedRefusal.test(message.text())) errors.push(message.text())
  })
  page.on('pageerror', (error) => errors.push(error.message))
  return errors
}

async function expectNoHorizontalScroll(page: Page): Promise<void> {
  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow, 'the page is wider than its viewport').toBeLessThanOrEqual(0)
}

/** The primary must sit inside the viewport, not only exist: a clipped button is the 375 px defect. */
async function expectInsideViewport(page: Page, locator: ReturnType<Page['locator']>): Promise<void> {
  const box = await locator.boundingBox()
  expect(box, 'the primary has no box').not.toBeNull()
  const width = page.viewportSize()!.width
  expect(box!.x, 'the primary is clipped on the left').toBeGreaterThanOrEqual(0)
  expect(box!.x + box!.width, 'the primary is clipped on the right').toBeLessThanOrEqual(width + 1)
}

type FocusInfo = { tag: string; label: string; ring: boolean; outline: string }

/** What Tab landed on: an input is named by its wrapping label, a button by its text. */
async function focusInfo(page: Page): Promise<FocusInfo> {
  return page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null
    const label = el?.closest('label')?.textContent ?? el?.textContent ?? ''
    return {
      tag: el?.tagName.toLowerCase() ?? '',
      label: label.replace(/\s+/g, ' ').trim(),
      ring: !!el && el.matches(':focus-visible'),
      outline: el ? getComputedStyle(el).outlineWidth : '0px',
    }
  })
}

const dialog = (page: Page) => page.getByRole('dialog')
const nameField = (page: Page) => dialog(page).getByLabel(/Project Name/i)

/** The one primary on the workspace home: two would mean the eye has no anchor. */
const newProject = (page: Page) => page.getByRole('button', { name: /^New project$/i })
const uploadPrimary = (page: Page) => page.getByRole('button', { name: /^Upload (\d+ )?images$/ })

/**
 * The first-run tour is per person and per workspace, so a fresh browser sees it on the home page.
 * It is a first-run gate, not a step of this journey (J1 owns its content); it is dismissed here.
 */
async function dismissTour(page: Page): Promise<void> {
  const end = page.getByRole('button', { name: 'End tour' })
  const shown = await end.waitFor({ state: 'visible', timeout: 4_000 }).then(() => true, () => false)
  if (!shown) return
  await end.click()
  await expect(page.locator('#home-tour')).toHaveCount(0)
}

async function openNewProject(page: Page): Promise<void> {
  await newProject(page).first().click()
  await expect(dialog(page)).toBeVisible()
}

/** A type card is chosen by the words a buyer recognises, never by a model family name. */
async function chooseType(page: Page, label: RegExp): Promise<void> {
  await dialog(page).getByRole('button', { name: label }).click()
}

async function submit(page: Page): Promise<void> {
  await dialog(page).getByRole('button', { name: /Create project/i }).click()
}

/** The five pipeline rows, in order, with the title each heads and the count each prints. */
async function stageRows(page: Page): Promise<{ title: string; count: string }[]> {
  return page.getByRole('list', { name: 'Project pipeline' }).getByRole('listitem').evaluateAll((items) =>
    items.map((item) => {
      const title = (item.querySelector('h2')?.textContent ?? '').replace(/\s+/g, ' ').trim()
      // The count is the last numeric span in the card; the number badge is numeric too, so read back.
      const count = [...item.querySelectorAll('span')].reverse()
        .map((s) => (s.textContent ?? '').trim())
        .find((t) => /^(\d+|—)$/.test(t)) ?? ''
      return { title, count }
    }))
}

async function demoToken(request: APIRequestContext): Promise<string | null> {
  const login = await request.post('/api/auth/login', { data: { email: seeded.email, password: seeded.password } })
  if (!login.ok()) return null
  return ((await login.json()) as { token: string }).token
}

// The demo workspace is on the three-project free plan. Every project this file created is moved to
// the trash with the shipped delete action, which is reversible (the trash can restore it); nothing
// this run did not create is touched.
test.afterEach(async ({ request }) => {
  const token = await demoToken(request)
  if (!token) return
  const headers = { Authorization: `Bearer ${token}` }
  const list = await request.get(`/api/ws/${seeded.workspace}/projects`, { headers })
  if (!list.ok()) return
  for (const p of (await list.json()) as { slug: string }[]) {
    if (p.slug.startsWith('j2-') && p.slug.includes(runId)) {
      await request.delete(`/api/ws/${seeded.workspace}/projects/${p.slug}`, { headers })
    }
  }
})

test.beforeEach(() => record.reset())

test('J2 create a project and land on upload', async ({ page, request }) => {
  const errors = watchErrors(page)
  await setFlags(request, ['task_470'])
  await signIn(page)
  await dismissTour(page)

  await test.step('1. Workspace home: New project is the one primary', async () => {
    await expect(page.getByRole('heading', { name: 'Home', exact: true })).toBeVisible()
    await expect(newProject(page), 'one primary, not two').toHaveCount(1)
    await expect(newProject(page)).toBeVisible()
    record.step()
  })

  await test.step('2. New project: pick object detection, name it, read the address before submit', async () => {
    await openNewProject(page)
    const card = dialog(page).getByRole('button', { name: /Object Detection/i })
    await expect(card).toBeVisible()
    // The card sells the outcome, not the model family behind it.
    await expect(card).toContainText(/objects|boxes/i)
    await expect(card).not.toContainText(/yolo|detr|sam|model/i)
    await chooseType(page, /Object Detection/i)

    await nameField(page).fill(projectName)
    // The address the name will take is stated before the create is sent.
    await expect(dialog(page)).toContainText(address)
    record.step()
  })

  await test.step('3. Create: busy in place, then the dialog closes on the project', async () => {
    // Hold the create for a moment so the busy state is observable, then let the real request run.
    await page.route('**/api/ws/*/projects', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 500))
      await route.continue()
    }, { times: 1 })
    const create = dialog(page).getByRole('button', { name: /Create project/i })
    const idle = await create.boundingBox()
    await create.click()
    // No page-wide spinner: the dialog keeps its box and its heading while the request is in flight.
    await expect(create).toBeDisabled()
    const busy = await create.boundingBox()
    expect(busy, 'the dialog keeps its box while busy').not.toBeNull()
    expect(Math.abs(busy!.width - idle!.width)).toBeLessThanOrEqual(1)
    await expect(dialog(page).getByRole('heading', { name: /create your project/i })).toBeVisible()

    await expect(dialog(page)).toHaveCount(0, { timeout: 30_000 })
    // The dialog closes onto the new project's upload screen, where the work starts.
    await expect(page).toHaveURL(at(`${address}/upload`))
    record.step()
  })

  await test.step('4. Project overview: five stages, zero counts, one primary', async () => {
    // The project panel names the project; its link is the way to the overview.
    await page.getByRole('link', { name: projectName }).first().click()
    await expect(page).toHaveURL(at(address))
    const pipeline = page.getByRole('list', { name: 'Project pipeline' })
    // Five cards while loading, five headings once the counts have arrived.
    await expect(pipeline.getByRole('heading')).toHaveCount(5)
    const rows = await stageRows(page)
    expect(rows.map((r) => r.title)).toEqual(['Upload', 'Annotate', 'Dataset', 'Train', 'Deploy'])
    // A fresh project shows zeros, not blanks: an empty count would read as "still loading".
    for (const row of rows) expect(row.count, `${row.title} prints a count`).toBe('0')

    await expect(uploadPrimary(page), 'one primary: Upload images').toHaveCount(1)
    await expect(uploadPrimary(page)).toBeVisible()
    record.step()
  })

  await test.step('5. Upload: the drag zone, the batch default and the split choice', async () => {
    await uploadPrimary(page).click()
    await expect(page).toHaveURL(at(`${address}/upload`))
    await expect(page.getByRole('heading', { name: 'Upload Data' })).toBeVisible()
    await expect(page.getByText(/Drag and drop/i).first()).toBeVisible()

    const batch = page.getByLabel(/Batch name/i)
    await expect(batch).toBeVisible()
    const placeholder = await batch.getAttribute('placeholder')
    expect(batch.inputValue() || placeholder || '', 'the batch name has a default').toMatch(/uploaded on/i)

    const split = page.getByLabel(/Train \/ Valid \/ Test/i)
    await expect(split).toBeVisible()
    await expect(split).toHaveValue('auto')

    // Empty state, before any file is picked: the formats, the size cap and the demo-set shortcut.
    await expect(page.getByText(/images, folders|\.jpe?g|\.png/i).first()).toBeVisible()
    await expect(page.getByText(/\b\d+\s?(MB|GB|px)\b/i).first(), 'the size cap is stated').toBeVisible()
    await expect(page.getByRole('link', { name: /demo set|sample images/i })
      .or(page.getByRole('button', { name: /demo set|sample images/i }))).toBeVisible()
    record.step()
  })

  const result = record.done({ steps: 5, timeMs: 45_000 })
  console.log(`J2 measured: ${result.steps} steps, ${result.timeMs} ms`)
  test.info().annotations.push({ type: 'journey-result', description: `J2 ${result.steps} steps, ${result.timeMs} ms` })
  expect(result.failures, 'the journey stays inside its step and time targets').toEqual([])
  expect(result.steps, 'no more than 7 steps').toBeLessThanOrEqual(7)
  expect(result.timeMs, 'no more than 90 s').toBeLessThanOrEqual(90_000)
  expect(errors, `console or page errors: ${errors.join(' | ')}`).toEqual([])
})

test('J2b duplicate name is refused in place', async ({ page, request }) => {
  const errors = watchErrors(page)
  await setFlags(request, ['task_470'])
  await signIn(page)
  await dismissTour(page)

  const dupName = `J2 Duplicate ${runId}`
  const dupSlug = `j2-duplicate-${runId}`

  // The first project: the dialog is still the subject, so it is created the same way.
  await openNewProject(page)
  await chooseType(page, /Object Detection/i)
  await nameField(page).fill(dupName)
  await submit(page)
  await expect(dialog(page)).toHaveCount(0, { timeout: 30_000 })

  // The same name again: the error is inline, names the address, and the typed name survives.
  await page.goto(`/${seeded.workspace}`)
  await openNewProject(page)
  await chooseType(page, /Object Detection/i)
  await nameField(page).fill(dupName)
  await submit(page)

  const alert = dialog(page).getByRole('alert')
  await expect(alert, 'the error is inline in the dialog').toBeVisible()
  await expect(alert).toContainText(`/${seeded.workspace}/p/${dupSlug}`)
  await expect(alert, 'a free address is suggested').toContainText(new RegExp(`${escapeRe(dupSlug)}-\\d`))
  await expect(dialog(page), 'the dialog stays open').toBeVisible()
  await expect(nameField(page), 'the typed name is kept').toHaveValue(dupName)

  expect(errors, `console or page errors: ${errors.join(' | ')}`).toEqual([])
})

test('J2c the same flow at 375 px keeps its primary in view', async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await setFlags(request, ['task_470'])
  await signIn(page)
  await dismissTour(page)

  // Home.
  await expectNoHorizontalScroll(page)
  await expectInsideViewport(page, newProject(page).first())

  // The dialog: the name field, the type cards and the submit.
  await openNewProject(page)
  await expectNoHorizontalScroll(page)
  await expectInsideViewport(page, nameField(page))
  await chooseType(page, /Object Detection/i)
  await nameField(page).fill(`J2 Narrow ${runId}`)
  const create = dialog(page).getByRole('button', { name: /Create project/i })
  await expectInsideViewport(page, create)
  await create.click()
  await expect(dialog(page)).toHaveCount(0, { timeout: 30_000 })

  // The overview and the upload page are measured at their own routes: the landing is J2's check.
  await page.goto(`/${seeded.workspace}/p/j2-narrow-${runId}`)
  await expectNoHorizontalScroll(page)
  await expectInsideViewport(page, uploadPrimary(page))
  await uploadPrimary(page).click()
  await expect(page.getByRole('heading', { name: 'Upload Data' })).toBeVisible()
  await expectNoHorizontalScroll(page)
})

test('J2d keyboard only: type card, name and submit in reading order', async ({ page, request }) => {
  await setFlags(request, ['task_470'])
  await signIn(page)
  await dismissTour(page)

  // Reach the primary without a pointer: it is the first action a keyboard user needs.
  let reached = false
  for (let i = 0; i < 40 && !reached; i++) {
    await page.keyboard.press('Tab')
    reached = /^New Project$/i.test((await focusInfo(page)).label)
  }
  expect(reached, 'Tab reaches the New project button').toBe(true)
  const onButton = await focusInfo(page)
  expect(onButton.ring, 'the focused primary paints a ring').toBe(true)
  expect(onButton.outline, 'the focus ring has a visible outline').not.toBe('0px')
  await page.keyboard.press('Enter')
  await expect(dialog(page)).toBeVisible()

  // The dialog opens on the name field; Tab then meets the type card and the submit in reading order.
  await expect.poll(async () => (await focusInfo(page)).label).toContain('Project Name')
  await nameField(page).fill(`J2 Keys ${runId}`)

  const seen: string[] = []
  for (let i = 0; i < 20; i++) {
    await page.keyboard.press('Tab')
    const now = await focusInfo(page)
    seen.push(now.label)
    if (/Create project/i.test(now.label)) break
  }
  const typeAt = seen.findIndex((t) => /Object Detection/i.test(t))
  const submitAt = seen.findIndex((t) => /Create project/i.test(t))
  expect(typeAt, 'the type card is reachable by Tab').toBeGreaterThanOrEqual(0)
  expect(submitAt, 'the submit is reachable by Tab').toBeGreaterThan(typeAt)

  await page.keyboard.press('Enter')
  await expect(dialog(page)).toHaveCount(0, { timeout: 30_000 })
  await expect(page).toHaveURL(new RegExp(escapeRe(`/${seeded.workspace}/p/j2-keys-${runId}`)))
})

test('J2e the project is created in the seeded workspace and in no other', async ({ page, request, browser }) => {
  await setFlags(request, ['task_470'])
  await signIn(page)
  await dismissTour(page)

  await openNewProject(page)
  await chooseType(page, /Object Detection/i)
  await nameField(page).fill(projectName)
  await submit(page)
  await expect(dialog(page)).toHaveCount(0, { timeout: 30_000 })

  // Reload: the project is the shipped record, not client state, and its counts are still zero.
  await page.goto(address)
  await page.reload()
  await expect(page.getByRole('heading', { name: projectName })).toBeVisible()
  await expect(page.getByRole('list', { name: 'Project pipeline' }).getByRole('heading')).toHaveCount(5)
  const rows = await stageRows(page)
  expect(rows).toHaveLength(5)
  for (const row of rows) expect(row.count).toBe('0')

  // A second workspace: a buyer who signed up elsewhere sees none of it.
  const other = await browser.newContext()
  const otherPage = await other.newPage()
  await otherPage.goto('/signup')
  await otherPage.locator('#signup-name').fill('J2 Other Buyer')
  await otherPage.locator('#signup-email').fill(`j2+${runId}@labeldesk.dev`)
  await otherPage.locator('#signup-password').fill('labeldesk-j2-passphrase')
  await otherPage.locator('#signup-workspace').fill(`J2 Other ${runId}`)
  await otherPage.getByRole('button', { name: 'Create account' }).click()
  await expect(otherPage.getByRole('heading', { name: 'Home', exact: true })).toBeVisible({ timeout: 30_000 })
  await otherPage.getByRole('button', { name: 'End tour' }).click()
  await expect(otherPage.getByRole('heading', { name: 'Getting started' })).toBeVisible()
  await expect(otherPage.getByText(projectName)).toHaveCount(0)
  await other.close()
})

test('J2f flag off: the project index is the dataset grid, and create still completes', async ({ page, request }) => {
  await setFlags(request, ['task_470'], false)
  await signIn(page)
  await dismissTour(page)

  await openNewProject(page)
  await chooseType(page, /Object Detection/i)
  await nameField(page).fill(`J2 Flagless ${runId}`)
  await submit(page)
  await expect(dialog(page)).toHaveCount(0, { timeout: 30_000 })

  // The index falls back to the v2 grid, not the overview.
  await page.goto(`/${seeded.workspace}/p/j2-flagless-${runId}`)
  await expect(page).toHaveURL(at(`/${seeded.workspace}/p/j2-flagless-${runId}/browse`))
  await expect(page.getByRole('heading', { name: 'Dataset' })).toBeVisible()
})
