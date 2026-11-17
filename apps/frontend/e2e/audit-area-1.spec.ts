// T-1214 — audit area 1: the entry, the workspace home and the project overview. Read-only: this
// file changes no product code. It measures the first hour seven ways — axe on every route in light
// and dark, keyboard-only entry, three breakpoints, the six forced states and the first-run tour —
// and writes the evidence the report `docs/qa/audits/area-1.md` names. A finding's fix card keeps
// this spec as its regression test; the assertions encode the target, never the current defect.
//
// Tagged `@nightly`: 60 screenshots and 18 axe passes are too slow for the 10-minute smoke set.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { expect, test, type APIRequestContext, type BoundingBox, type Page } from '@playwright/test'
import { axe, seeded, setFlags, signIn, stubApi, type AxeViolation } from './fixtures/harness'

const evidence = process.env.LD_AUDIT_EVIDENCE || path.join(process.env.TMP || __dirname, 'labeldesk-audit-area-1')
mkdirSync(evidence, { recursive: true })

// One account per run: the seed is not reset between specs and only this file reads it.
const runId = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
const password = 'labeldesk-area1-passphrase'

const MODES = ['light', 'dark'] as const
type Mode = (typeof MODES)[number]
const WIDTHS = [375, 768, 1440] as const

const size = (width: number) => width === 375
  ? { width: 375, height: 812 }
  : width === 768 ? { width: 768, height: 1024 } : { width: 1440, height: 900 }

const home = `/${seeded.workspace}`
const overview = `/${seeded.workspace}/p/${seeded.project}`

// ---------------------------------------------------------------------------------------------
// Evidence: every screenshot and axe result lands here, named the same way the report names it.
// ---------------------------------------------------------------------------------------------

const shots: string[] = []

/** The manifests merge with what is on disk, so running one test alone never truncates the record. */
function mergeList<T>(file: string, rows: T[], same: (a: T, b: T) => boolean): void {
  let prior: T[] = []
  try { prior = JSON.parse(readFileSync(file, 'utf8')) as T[] } catch { /* first write */ }
  writeFileSync(file, JSON.stringify([...prior.filter((p) => !rows.some((r) => same(p, r))), ...rows], null, 2))
}

function flushShots(): void {
  mergeList(path.join(evidence, 'screenshots.json'), shots, (a, b) => a === b)
}

/** Theme is a media preference the app already reads; reduced motion keeps a screenshot still. */
async function useTheme(page: Page, mode: Mode): Promise<void> {
  await page.emulateMedia({ colorScheme: mode, reducedMotion: 'reduce' })
  await expect(page.locator('html')).toHaveAttribute('data-theme', mode)
}

async function capture(page: Page, screen: string, width: number, mode: Mode): Promise<string> {
  const file = path.join(evidence, `area1-${screen}-${width}-${mode}.png`)
  await page.screenshot({ path: file, fullPage: true })
  shots.push(path.basename(file))
  return file
}

type AxeRow = {
  screen: string; mode: Mode; width: number
  critical: number; serious: number; moderate: number; minor: number
  violations: AxeViolation[]
}

const axeRows: AxeRow[] = []

/** Run axe, write its raw output, and count by impact so the report can name every item. */
async function grade(page: Page, screen: string, width: number, mode: Mode): Promise<AxeRow> {
  const violations = await axe(page)
  const row: AxeRow = { screen, mode, width, critical: 0, serious: 0, moderate: 0, minor: 0, violations }
  for (const v of violations) {
    const impact = v.impact ?? 'minor'
    if (impact === 'critical' || impact === 'serious' || impact === 'moderate' || impact === 'minor') row[impact] += 1
  }
  writeFileSync(path.join(evidence, `axe-${screen}-${width}-${mode}.json`), JSON.stringify(violations, null, 2))
  axeRows.push(row)
  return row
}

// ---------------------------------------------------------------------------------------------
// The routes of area 1, and the one primary each screen owns.
// ---------------------------------------------------------------------------------------------

type Screen = { key: string; path: string; ready: (page: Page) => Promise<void> }

const signedOut: Screen[] = [
  { key: 'landing', path: '/', ready: async (p) => { await expect(p.locator('#hero-title')).toBeVisible() } },
  { key: 'login', path: '/login', ready: async (p) => { await expect(p.getByRole('heading', { name: 'Sign in', exact: true })).toBeVisible() } },
  { key: 'signup', path: '/signup', ready: async (p) => { await expect(p.getByRole('heading', { name: 'Create your account' })).toBeVisible() } },
  { key: 'forgot', path: '/forgot', ready: async (p) => { await expect(p.getByRole('heading', { name: 'Reset your password' })).toBeVisible() } },
  { key: 'reset', path: '/reset/area-1-audit-token', ready: async (p) => { await expect(p.getByRole('heading', { name: 'Choose a new password' })).toBeVisible() } },
  { key: 'verify', path: '/verify/area-1-audit-token', ready: async (p) => { await expect(p.getByRole('heading', { name: /This link won/ })).toBeVisible() } },
]

const signedIn: Screen[] = [
  { key: 'home', path: home, ready: async (p) => {
    await expect(p.getByRole('heading', { name: 'Home', exact: true })).toBeVisible()
    // The settled screen, not its skeleton: the loading state is graded where it is forced.
    await expect(p.getByRole('heading', { name: 'At a glance', exact: true })).toBeVisible()
  } },
  { key: 'overview', path: overview, ready: async (p) => { await expect(p.getByRole('list', { name: 'Project pipeline' }).getByRole('heading')).toHaveCount(5) } },
]

/** The first action a buyer needs on the screen: present, and inside the viewport at 375. */
function primary(page: Page, key: string) {
  switch (key) {
    case 'landing': return page.getByRole('link', { name: 'Start free' }).first()
    case 'login': return page.getByRole('button', { name: 'Sign in' })
    case 'signup': return page.getByRole('button', { name: 'Create account' })
    case 'forgot': return page.getByRole('button', { name: 'Send reset link' })
    case 'reset': return page.getByRole('button', { name: 'Update password' })
    case 'verify': return page.getByRole('link', { name: /^(Sign in|Open LabelDesk)$/ })
    case 'home': return page.getByRole('button', { name: /^New project$/i })
    case 'overview': return page.getByRole('button', {
      name: /^(Upload \d+ images|Label \d+ images|Review \d+ labels|Create a version|Open dataset|Train on v\d+|Test the model|Start labelling)$/,
    })
    // First run ships two create actions today (checklist + empty state); the audit records that,
    // and measures the first one so the reachability check is not ambiguous.
    case 'first-run': return page.getByRole('button', { name: /^(Create|Create your first project)$/ }).first()
    default: throw new Error(`no primary for ${key}`)
  }
}

async function expectNoHorizontalScroll(page: Page, where: string): Promise<void> {
  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow, `${where}: the document is wider than its viewport`).toBeLessThanOrEqual(0)
}

async function expectInsideViewport(page: Page, where: string, locator: ReturnType<Page['locator']>): Promise<void> {
  const box = await locator.boundingBox()
  expect(box, `${where}: the primary has no box`).not.toBeNull()
  const width = page.viewportSize()!.width
  expect(box!.x, `${where}: the primary is clipped on the left`).toBeGreaterThanOrEqual(0)
  expect(box!.x + box!.width, `${where}: the primary is clipped on the right`).toBeLessThanOrEqual(width + 1)
}

// ---------------------------------------------------------------------------------------------
// Keyboard helpers: what Tab landed on, whether its ring is painted, and a bounded Tab walk.
// ---------------------------------------------------------------------------------------------

type FocusInfo = { tag: string; label: string; ring: boolean; outline: string }

async function focusInfo(page: Page): Promise<FocusInfo> {
  return page.evaluate(() => {
    const el = document.activeElement as (HTMLElement & { labels?: NodeListOf<HTMLLabelElement> }) | null
    // A `TextField` renders `<label for>` next to its input, so `labels` is the honest name source
    // there; a `Field` wraps its control, which `closest` covers.
    const label = el?.labels?.[0]?.textContent ?? el?.closest('label')?.textContent ?? el?.getAttribute('aria-label') ?? el?.textContent ?? ''
    return {
      tag: el?.tagName.toLowerCase() ?? '',
      label: label.replace(/\s+/g, ' ').trim(),
      ring: !!el && el.matches(':focus-visible'),
      outline: el ? getComputedStyle(el).outlineWidth : '0px',
    }
  })
}

async function expectPaintedFocus(page: Page, pattern: RegExp): Promise<FocusInfo> {
  await expect.poll(async () => (await focusInfo(page)).label, { timeout: 5_000 }).toMatch(pattern)
  const seen = await focusInfo(page)
  expect(seen.ring, `"${seen.label}" matches :focus-visible`).toBe(true)
  expect(seen.outline, `"${seen.label}" paints a focus ring`).not.toBe('0px')
  return seen
}

/** Tab until the focused control's label matches, then report every stop on the way. */
async function tabTo(page: Page, pattern: RegExp, limit = 90): Promise<string[]> {
  const seen: string[] = []
  for (let i = 0; i < limit; i++) {
    await page.keyboard.press('Tab')
    const now = await focusInfo(page)
    seen.push(now.label)
    if (pattern.test(now.label)) {
      expect(now.ring, `"${now.label}" matches :focus-visible`).toBe(true)
      expect(now.outline, `"${now.label}" paints a focus ring`).not.toBe('0px')
      return seen
    }
  }
  throw new Error(`Tab never reached ${pattern}; passed ${seen.join(' | ')}`)
}

/** The page has stopped scrolling: the tour must not move it on the first step. */
async function settledScroll(page: Page): Promise<number> {
  let last = -1
  for (let i = 0; i < 25; i++) {
    const y = await page.evaluate(() => window.scrollY)
    if (y === last) return y
    last = y
    await page.waitForTimeout(120)
  }
  return last
}

function overlaps(a: BoundingBox, b: BoundingBox): boolean {
  return a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height
}

// ---------------------------------------------------------------------------------------------
// A brand-new person, for the first-run screen: the seed has projects and cannot show it.
// ---------------------------------------------------------------------------------------------

function flushAxe(): void {
  mergeList(path.join(evidence, 'axe-summary.json'), axeRows,
    (a, b) => a.screen === b.screen && a.mode === b.mode && a.width === b.width)
}

/**
 * Turn `task_470` on for a workspace through the shipped flag API: a new workspace starts with
 * every flag off, and this audit reads the v3 frame.
 */
async function enableV3(request: APIRequestContext, slug: string, email: string): Promise<void> {
  const login = await request.post('/api/auth/login', { data: { email, password } })
  expect(login.ok(), `${email}: can sign in`).toBe(true)
  const { token } = (await login.json()) as { token: string }
  const flag = await request.put(`/api/ws/${slug}/flags/task_470`, {
    data: { enabled: true }, headers: { Authorization: `Bearer ${token}` },
  })
  expect(flag.ok(), `${slug}: task_470 is on`).toBe(true)
}

/**
 * Sign up a new account in a fresh browser context, then turn `task_470` on for its workspace.
 */
async function signUpFresh(page: Page, request: APIRequestContext, label: string): Promise<string> {
  const tag = label.replace(/\s+/g, '-').toLowerCase()
  const email = `area1+${tag}+${runId}@labeldesk.dev`
  await page.goto('/signup')
  await page.locator('#signup-name').fill(`Area 1 ${label}`)
  await page.locator('#signup-email').fill(email)
  await page.locator('#signup-password').fill(password)
  await page.getByLabel('Workspace name').fill(`Area 1 ${label} ${runId}`)
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page.getByRole('heading', { name: 'Home', exact: true })).toBeVisible({ timeout: 30_000 })

  const slug = new URL(page.url()).pathname.replace(/^\//, '')
  await enableV3(request, slug, email)
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Home', exact: true })).toBeVisible()
  return slug
}

async function endTour(page: Page): Promise<void> {
  const end = page.getByRole('button', { name: 'End tour' })
  // The tour paints after the dashboard's first query; wait for it before deciding it is absent.
  await end.waitFor({ state: 'visible', timeout: 4_000 }).catch(() => {})
  if (await end.count()) {
    await end.click()
    await expect(page.locator('#home-tour')).toHaveCount(0)
  }
}

test.describe.configure({ timeout: 300_000 })

// ---------------------------------------------------------------------------------------------
// 1. axe: every route, light and dark, at 1440.
// ---------------------------------------------------------------------------------------------

test('area 1 axe: every route, light and dark', async ({ page, request, browser }) => {
  test.setTimeout(600_000)
  // `task_470` is the v3 frame: the overview is the project index and the rail is the five stages.
  await setFlags(request, ['task_470'])

  for (const mode of MODES) {
    await page.setViewportSize(size(1440))
    await page.goto('/')
    await useTheme(page, mode)
    for (const screen of signedOut) {
      await page.goto(screen.path)
      await screen.ready(page)
      await useTheme(page, mode)
      await grade(page, screen.key, 1440, mode)
      await capture(page, screen.key, 1440, mode)
    }
  }

  // Signed in: the workspace home and the project overview. The first home visit shows the tour.
  await signIn(page)
  for (const mode of MODES) {
    await page.setViewportSize(size(1440))
    await useTheme(page, mode)
    for (const screen of signedIn) {
      await page.goto(screen.path)
      await screen.ready(page)
      await useTheme(page, mode)
      await grade(page, screen.key, 1440, mode)
      await endTour(page)
      await capture(page, screen.key, 1440, mode)
      if (screen.key === 'overview') {
        // The board's five cards share the column left by two rails and the 360 px aside.
        const widths = await page.getByRole('list', { name: 'Project pipeline' }).getByRole('listitem')
          .evaluateAll((items) => items.map((item) => Math.round(item.getBoundingClientRect().width)))
        writeFileSync(path.join(evidence, 'overview-board-widths.json'), JSON.stringify({
          viewport: 1440, mode, available: await page.getByRole('list', { name: 'Project pipeline' })
            .evaluate((el) => Math.round(el.getBoundingClientRect().width)), cards: widths,
        }, null, 2))
      }
    }
  }

  // First run: a brand-new workspace, so home has no projects and the tour is up.
  for (const mode of MODES) {
    const fresh = await browser.newContext({ viewport: size(1440) })
    const freshPage = await fresh.newPage()
    await freshPage.emulateMedia({ colorScheme: mode, reducedMotion: 'reduce' })
    await signUpFresh(freshPage, request, `axe ${mode}`)
    await useTheme(freshPage, mode)
    await expect(freshPage.getByRole('heading', { name: 'Getting started' })).toBeVisible()
    await grade(freshPage, 'first-run', 1440, mode)
    await capture(freshPage, 'first-run', 1440, mode)
    await fresh.close()
  }

  flushAxe()
  flushShots()

  const blocking = axeRows.filter((r) => r.critical + r.serious > 0)
  expect(
    blocking.map((r) => `${r.screen} ${r.mode}: critical ${r.critical}, serious ${r.serious} — ${r.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious').map((v) => v.id).join(', ')}`),
    'zero critical and zero serious violations on every route',
  ).toEqual([])

  const totals = (impact: 'moderate' | 'minor') => axeRows.reduce((n, r) => n + r[impact], 0)
  test.info().annotations.push({
    type: 'area-1-axe',
    description: `critical 0, serious 0, moderate ${totals('moderate')}, minor ${totals('minor')} across ${axeRows.length} passes`,
  })
})

// ---------------------------------------------------------------------------------------------
// 2. Keyboard only: landing → sign up → home → project overview.
// ---------------------------------------------------------------------------------------------

test('area 1 keyboard: landing → sign up → home → overview', async ({ page, request }) => {
  test.setTimeout(600_000)
  await setFlags(request, ['task_470'])
  await page.setViewportSize(size(1440))

  await test.step('1. Landing: the first stops follow reading order, and the one primary ends them', async () => {
    await page.goto('/')
    await expect(page.locator('#hero-title')).toBeVisible()
    // The brand link's text includes the aria-hidden "L" tile, so it is matched by its tail.
    const order: RegExp[] = [/^Skip to content$/, /LabelDesk$/, /^Product$/, /^Models$/, /^Pricing$/, /^Docs$/, /^Log in$/, /^Start free$/]
    for (const label of order) {
      await page.keyboard.press('Tab')
      await expectPaintedFocus(page, label)
    }
    // The last stop is the primary, so Enter takes the keyboard user to the sign-up form.
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/\/signup$/)
    await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
    await page.locator('#signup-name').waitFor()
    await page.waitForLoadState('load')
  })

  await test.step('2. Sign up: every field in reading order, the submit keeps its ring', async () => {
    // The form autofocuses the name field; if that ever stops, Tab still lands on it first.
    for (let i = 0; i < 3 && !/^Full name/.test((await focusInfo(page)).label); i++) await page.keyboard.press('Tab')
    await expectPaintedFocus(page, /^Full name/)
    const fields: [string, RegExp, string][] = [
      ['#signup-name', /^Work email$/, 'Area 1 Keyboard'],
      ['#signup-email', /^Password/, `area1+kb+${runId}@labeldesk.dev`],
      ['#signup-password', /^Workspace name$/, password],
      ['#signup-workspace', /^Create account$/, `Area 1 Keyboard ${runId}`],
    ]
    for (const [selector, next, value] of fields) {
      await page.locator(selector).fill(value)
      await page.keyboard.press('Tab')
      await expectPaintedFocus(page, next)
    }
    await page.keyboard.press('Enter')
    await expect(page.getByRole('heading', { name: 'Home', exact: true })).toBeVisible({ timeout: 30_000 })
    // Setup, not a step: a new workspace starts with `task_470` off, and the audit reads the v3 frame.
    const slug = new URL(page.url()).pathname.replace(/^\//, '')
    await enableV3(request, slug, `area1+kb+${runId}@labeldesk.dev`)
    await page.reload()
    await expect(page.getByRole('heading', { name: 'Home', exact: true })).toBeVisible()
  })

  await test.step('3. First run: the tour never covers its target and step 1 never scrolls', async () => {
    const tour = page.locator('#home-tour')
    await expect(tour).toBeVisible()
    await expect(page.getByText(/Step 1 of 5/)).toBeVisible()
    expect(await settledScroll(page), 'step 1 does not scroll the page').toBe(0)

    const targets = ['home-stats', 'home-tasks', 'home-checklist', 'home-activity', 'home-projects']
    for (let i = 0; i < targets.length; i++) {
      const target = page.locator(`[data-tour="${targets[i]}"]`)
      await expect(target).toHaveCount(1)
      const scrolled = await settledScroll(page)
      const card = await tour.boundingBox()
      const ring = await target.boundingBox()
      expect(card, `step ${i + 1}: the card has a box`).not.toBeNull()
      expect(ring, `step ${i + 1}: the target has a box`).not.toBeNull()
      expect(
        overlaps(card!, ring!),
        `step ${i + 1}: the tour card covers the section it rings (card ${JSON.stringify(card)}, target ${JSON.stringify(ring)}, scrollY ${scrolled})`,
      ).toBe(false)

      await tabTo(page, /^(Next|Done)$/)
      await page.keyboard.press('Enter')
      if (i < targets.length - 1) await expect(page.getByText(new RegExp(`Step ${i + 2} of 5`))).toBeVisible()
    }
    await expect(tour).toHaveCount(0)
  })

  await test.step('4. Empty workspace: the checklist offers a create action, reachable by Tab', async () => {
    await expect(page.getByRole('heading', { name: 'Getting started' })).toBeVisible()
    await expect(page.getByText(/^0 of \d+ done$/)).toBeVisible()
    await expect(page.getByText('No projects yet.')).toBeVisible()
    await tabTo(page, /^Create$/)
    await page.keyboard.press('Enter')
    await expect(page.getByRole('dialog')).toBeVisible()
  })

  await test.step('5. Create a project without a pointer, and open its overview', async () => {
    const name = `Area 1 Keys ${runId}`
    await expectPaintedFocus(page, /Project Name/)
    await page.keyboard.type(name)
    await tabTo(page, /^Create Project$/i)
    await page.keyboard.press('Enter')
    await expect(page.getByRole('dialog')).toHaveCount(0, { timeout: 30_000 })
    await expect(page).toHaveURL(new RegExp(`/p/area-1-keys-${runId}/upload$`))

    await tabTo(page, new RegExp(name))
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(new RegExp(`/p/area-1-keys-${runId}$`))
    const pipeline = page.getByRole('list', { name: 'Project pipeline' })
    await expect(pipeline.getByRole('heading')).toHaveCount(5)
    const next = primary(page, 'overview')
    await expect(next).toBeVisible()
    await expectInsideViewport(page, 'overview primary', next)
  })
})

// ---------------------------------------------------------------------------------------------
// 3. Responsive: 375 and 768, light and dark; 1440 was captured by the axe pass.
// ---------------------------------------------------------------------------------------------

test('area 1 responsive: 375, 768, 1440', async ({ page, request }) => {
  test.setTimeout(600_000)
  await setFlags(request, ['task_470'])
  const checkedAt1440: string[] = []

  // Signed out first: the app swaps its whole route table once a session exists.
  for (const width of WIDTHS) {
    await page.setViewportSize(size(width))
    await page.goto('/')
    for (const mode of MODES) {
      await useTheme(page, mode)
      for (const screen of signedOut) {
        await page.goto(screen.path)
        await screen.ready(page)
        await expectNoHorizontalScroll(page, `${screen.key} ${width} ${mode}`)
        await expectInsideViewport(page, `${screen.key} ${width} ${mode}`, primary(page, screen.key))
        if (width === 1440) checkedAt1440.push(`${screen.key} ${mode}`)
        else await capture(page, screen.key, width, mode)
      }
    }
  }

  await signIn(page)
  for (const width of WIDTHS) {
    await page.setViewportSize(size(width))
    for (const mode of MODES) {
      await useTheme(page, mode)
      for (const screen of signedIn) {
        await page.goto(screen.path)
        await screen.ready(page)
        await endTour(page)
        await expectNoHorizontalScroll(page, `${screen.key} ${width} ${mode}`)
        await expectInsideViewport(page, `${screen.key} ${width} ${mode}`, primary(page, screen.key))
        if (width === 1440) checkedAt1440.push(`${screen.key} ${mode}`)
        else await capture(page, screen.key, width, mode)
      }
    }
  }

  writeFileSync(path.join(evidence, 'responsive-1440.json'), JSON.stringify(checkedAt1440, null, 2))
  flushShots()
})

// ---------------------------------------------------------------------------------------------
// 4. States: empty workspace, no match, loading, error — each forced, never hoped for.
// ---------------------------------------------------------------------------------------------

test('area 1 states: empty workspace, no-match, loading, error', async ({ page, request, browser }) => {
  test.setTimeout(600_000)
  await setFlags(request, ['task_470'])
  const copy = { firstRun: '', queue: '', noMatch: '' }
  const actions: Record<'firstRun' | 'queue' | 'noMatch', string[]> = { firstRun: [], queue: [], noMatch: [] }
  let loadingAxe: AxeRow | null = null
  // Evidence is written as each state is reached, so a red assertion below never costs the record.
  const flush = () => {
    writeFileSync(path.join(evidence, 'empty-state-copy.json'), JSON.stringify(copy, null, 2))
    writeFileSync(path.join(evidence, 'empty-state-actions.json'), JSON.stringify(actions, null, 2))
    flushAxe()
    flushShots()
  }

  await test.step('1. First run: a designed empty workspace with one next step', async () => {
    for (const width of WIDTHS) {
      for (const mode of MODES) {
        const fresh = await browser.newContext({ viewport: size(width) })
        const freshPage = await fresh.newPage()
        await freshPage.emulateMedia({ colorScheme: mode, reducedMotion: 'reduce' })
        await signUpFresh(freshPage, request, `state ${width} ${mode}`)
        await useTheme(freshPage, mode)

        await expect(freshPage.getByRole('button', { name: 'End tour' })).toBeVisible()
        await expect(freshPage.getByRole('heading', { name: 'Getting started' })).toBeVisible()
        await expect(freshPage.getByText(/^0 of \d+ done$/)).toBeVisible()
        await expect(freshPage.getByText('No projects yet.')).toBeVisible()
        copy.firstRun = (await freshPage.getByText('No projects yet.').locator('..').textContent()) ?? ''
        actions.firstRun = (await freshPage.getByRole('button', { name: /^(Create|Create your first project)$/ }).allInnerTexts())
          .map((s) => s.replace(/\s+/g, ' ').trim())
        await capture(freshPage, 'first-run', width, mode)
        await expectNoHorizontalScroll(freshPage, `first-run ${width} ${mode}`)
        await expectInsideViewport(freshPage, `first-run ${width} ${mode}`, primary(freshPage, 'first-run'))
        await fresh.close()
      }
    }
  })

  await test.step('2. Workspace home: the empty queue and the no-match state are different sentences', async () => {
    await page.setViewportSize(size(1440))
    await page.goto('/')
    await useTheme(page, 'light')
    await signIn(page)
    await endTour(page)
    await expect(page.getByText('Work waiting for you')).toBeVisible()

    await page.getByPlaceholder('Search projects').fill('zzz no project matches this')
    await expect(page.getByText('No projects match.')).toBeVisible()
    await expect(page.getByText('No projects yet.')).toHaveCount(0)
    copy.noMatch = (await page.getByText('No projects match.').locator('..').textContent()) ?? ''
    actions.noMatch = (await page.getByText('No projects match.').locator('..').locator('button, a').allInnerTexts())
      .map((s) => s.replace(/\s+/g, ' ').trim())
    // The shell scrolls inside a div, so the message is brought into the viewport for the shot.
    await page.getByText('No projects match.').scrollIntoViewIfNeeded()
    await capture(page, 'home-no-match', 1440, 'light')
    await page.getByPlaceholder('Search projects').fill('')

    // The empty queue belongs to a workspace with nothing waiting: a fresh one.
    const fresh = await browser.newContext({ viewport: size(1440) })
    const freshPage = await fresh.newPage()
    await freshPage.emulateMedia({ colorScheme: 'light', reducedMotion: 'reduce' })
    await signUpFresh(freshPage, request, 'queue')
    await endTour(freshPage)
    await expect(freshPage.getByText("You're all caught up.")).toBeVisible()
    copy.queue = (await freshPage.getByText("You're all caught up.").locator('..').textContent()) ?? ''
    actions.queue = (await freshPage.getByText("You're all caught up.").locator('..').locator('button, a').allInnerTexts())
      .map((s) => s.replace(/\s+/g, ' ').trim())
    await fresh.close()
    flush()
  })

  await test.step('3. Loading: a skeleton in the page’s own shape, then the real dashboard', async () => {
    await page.goto(home)
    await endTour(page)
    // One delayed response is enough: the skeleton is the only thing on screen while it runs.
    await page.route(/\/api\/ws\/[^/]+\/home$/, async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 1_200))
      await route.continue()
    }, { times: 1 })
    await page.reload()
    const skeleton = page.getByLabel('Loading workspace dashboard')
    await expect(skeleton).toBeVisible()
    await expect(skeleton).toHaveAttribute('aria-busy', 'true')
    await capture(page, 'home-loading', 1440, 'light')
    // The skeleton is a state of a core journey, so it is graded like a screen. The verdict is
    // asserted after the error state, so one red finding never costs the other evidence.
    loadingAxe = await grade(page, 'home-loading', 1440, 'light')
    flush()
    await expect(page.getByRole('heading', { name: 'At a glance', exact: true })).toBeVisible({ timeout: 15_000 })
  })

  await test.step('4. Error: what failed, a retry, and the same screen once the API answers', async () => {
    // Two 503s: the query's own retry fails too, so the error card is reached honestly.
    await stubApi(page, /\/api\/ws\/[^/]+\/home$/, { status: 503, body: { detail: 'audit: forced failure' }, times: 2 })
    await page.reload()
    const alert = page.getByRole('alert').filter({ hasText: 'Could not load the workspace dashboard' })
    await expect(alert).toBeVisible({ timeout: 15_000 })
    await expect(alert.getByRole('button', { name: 'Try again' })).toBeVisible()
    await capture(page, 'home-error', 1440, 'light')
    await alert.getByRole('button', { name: 'Try again' }).click()
    await expect(page.getByRole('heading', { name: 'At a glance', exact: true })).toBeVisible({ timeout: 15_000 })
    await expect(alert).toHaveCount(0)
  })

  flush()

  // The three empty states say three different things, and none is the other's sentence.
  expect(new Set([copy.firstRun, copy.queue, copy.noMatch]).size, 'first run, empty queue and no match read differently').toBe(3)
  expect(
    (loadingAxe?.critical ?? 0) + (loadingAxe?.serious ?? 0),
    `the loading skeleton has ${loadingAxe?.critical} critical and ${loadingAxe?.serious} serious violations: ${(loadingAxe?.violations ?? []).filter((v) => v.impact === 'critical' || v.impact === 'serious').map((v) => v.id).join(', ')}`,
  ).toBe(0)
})
