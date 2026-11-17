// T-1104 O1 — the first-run tour must never sit above an open modal or take its clicks. The
// T-1202 observation: at 375 px a fresh visit renders `#home-tour` (fixed, z-[150]) over the
// new-project dialog (z-[100]) and Playwright's click on `Create Project` was intercepted for two
// minutes. These two tests are that finding: a pointer click and a keyboard Enter, both at 375 px,
// both on a first visit with the tour still on.
import { expect, test, type APIRequestContext, type Page } from '@playwright/test'
import { record, seeded, setFlags, signIn } from './fixtures/harness'

const runId = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
const at = (path: string) => new RegExp(`${path}$`)

// One name per test: a trashed project keeps its address (the create route says so rather than
// storing `<slug>-2`), so a second test may not reuse the first one's name after cleanup.
const pointerName = `J2 Tour Gate Pointer ${runId}`
const pointerSlug = `j2-tour-gate-pointer-${runId}`
const keysName = `J2 Tour Gate Keys ${runId}`
const keysSlug = `j2-tour-gate-keys-${runId}`

const dialog = (page: Page) => page.getByRole('dialog')
const tour = (page: Page) => page.locator('#home-tour')
const newProject = (page: Page) => page.getByRole('button', { name: /^New project$/i })
const nameField = (page: Page) => dialog(page).getByLabel(/Project Name/i)
const createButton = (page: Page) => dialog(page).getByRole('button', { name: /Create project/i })

/** The label a keyboard user would read: an input's wrapping label, a button's text. */
async function focusedLabel(page: Page): Promise<string> {
  return page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null
    return ((el?.closest('label')?.textContent ?? el?.textContent ?? '').replace(/\s+/g, ' ').trim())
  })
}

async function demoToken(request: APIRequestContext): Promise<string | null> {
  const login = await request.post('/api/auth/login', { data: { email: seeded.email, password: seeded.password } })
  return login.ok() ? ((await login.json()) as { token: string }).token : null
}

// The demo workspace is on the three-project Free plan. Only this run's own projects are trashed,
// through the shipped (reversible) delete route.
test.afterEach(async ({ request }) => {
  const token = await demoToken(request)
  if (!token) return
  const headers = { Authorization: `Bearer ${token}` }
  const list = await request.get(`/api/ws/${seeded.workspace}/projects`, { headers })
  if (!list.ok()) return
  for (const p of (await list.json()) as { slug: string }[]) {
    if (p.slug.startsWith('j2-tour-gate-') && p.slug.endsWith(runId)) {
      await request.delete(`/api/ws/${seeded.workspace}/projects/${p.slug}`, { headers })
    }
  }
})

test.beforeEach(() => record.reset())

test('a fresh visit at 375 px: the tour is not over the dialog and its primary receives the click', async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await setFlags(request, ['task_470'])
  await signIn(page)

  // A first visit, so the coach mark is up before the dialog opens.
  await expect(tour(page), 'a first visit shows the tour').toBeVisible()
  await newProject(page).first().click()
  await expect(dialog(page)).toBeVisible()

  // The coach mark is out of the way: no second floating surface over the task.
  await expect(tour(page), 'the tour is not rendered over an open modal').toHaveCount(0)

  // Cancel keeps the tour for the next step rather than silently ending it.
  await dialog(page).getByRole('button', { name: 'Cancel' }).click()
  await expect(dialog(page)).toHaveCount(0)
  await expect(tour(page), 'the tour comes back when the dialog closes').toBeVisible()

  await newProject(page).first().click()
  await expect(dialog(page)).toBeVisible()
  await nameField(page).fill(pointerName)
  // A short timeout on purpose: an intercepted click fails as intercepted, not as a slow wait.
  await createButton(page).click({ timeout: 5_000 })

  await expect(dialog(page)).toHaveCount(0, { timeout: 30_000 })
  await expect(page).toHaveURL(at(`/${seeded.workspace}/p/${pointerSlug}/upload`))
})

test('keyboard only at 375 px: Tab reaches the dialog primary with the tour on', async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await setFlags(request, ['task_470'])
  await signIn(page)
  await expect(tour(page)).toBeVisible()

  // Open the dialog without ending the tour: the card's primary has to stay reachable.
  await newProject(page).first().focus()
  await page.keyboard.press('Enter')
  await expect(dialog(page)).toBeVisible()
  await expect(tour(page)).toHaveCount(0)

  await expect.poll(() => focusedLabel(page)).toContain('Project Name')
  await nameField(page).fill(keysName)

  let reached = false
  for (let i = 0; i < 20 && !reached; i++) {
    await page.keyboard.press('Tab')
    reached = /Create project/i.test(await focusedLabel(page))
  }
  expect(reached, 'Tab reaches Create project inside the dialog').toBe(true)

  await page.keyboard.press('Enter')
  await expect(dialog(page)).toHaveCount(0, { timeout: 30_000 })
  await expect(page).toHaveURL(at(`/${seeded.workspace}/p/${keysSlug}/upload`))
})
