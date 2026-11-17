// T-1105 — the T-1202 findings V3–V5 on the empty upload page, proven on their own so this card does
// not depend on the new-project dialog (V1/V2 belong to T-1104). The three assertions are copied from
// `journey-project.spec.ts` step 5, unchanged: the size cap is stated, the demo shortcut exists, and
// the batch name and split controls are on the page before any file is picked. Screenshots of the same
// page at 375 px in light and dark mode land in the evidence folder.
import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { expect, test, type APIRequestContext, type Page } from '@playwright/test'
import { seeded, signIn } from './fixtures/harness'

const runId = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
const projectName = `T1105 Empty ${runId}`
const projectSlug = `t1105-empty-${runId}`
const evidence = process.env.T1105_EVIDENCE ?? path.join(import.meta.dirname, '..', 'test-results', 'T-1105')

async function token(request: APIRequestContext): Promise<string | null> {
  const login = await request.post('/api/auth/login', { data: { email: seeded.email, password: seeded.password } })
  return login.ok() ? ((await login.json()) as { token: string }).token : null
}

/** The project is made through the API: the dialog is T-1104's subject, not this card's. */
test.beforeAll(async ({ request }) => {
  const authHeader = { Authorization: `Bearer ${await token(request)}` }
  const created = await request.post(`/api/ws/${seeded.workspace}/projects`, {
    data: { name: projectName, type: 'object-detection' }, headers: authHeader,
  })
  expect(created.ok(), `create project: ${created.status()} ${await created.text()}`).toBe(true)
})

test.afterAll(async ({ request }) => {
  const authHeader = { Authorization: `Bearer ${await token(request)}` }
  await request.delete(`/api/ws/${seeded.workspace}/projects/${projectSlug}`, { headers: authHeader })
})

async function expectNoHorizontalScroll(page: Page): Promise<void> {
  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow, 'the page is wider than its viewport').toBeLessThanOrEqual(0)
}

test('J2 upload empty state: cap, demo set, batch and split before a pick', async ({ page }) => {
  const errors: string[] = []
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()) })
  page.on('pageerror', (error) => errors.push(error.message))

  await signIn(page)
  await page.goto(`/${seeded.workspace}/p/${projectSlug}/upload`)
  await expect(page.getByRole('heading', { name: 'Upload Data' })).toBeVisible()
  await expect(page.getByText(/Drag and drop/i).first()).toBeVisible()

  // V5: the batch name and the split are on the page before any file is picked, defaults unchanged.
  const batch = page.getByLabel(/Batch name/i)
  await expect(batch, 'the batch name is visible on the empty page').toBeVisible()
  await expect(batch).toHaveValue('')
  await expect(batch).toHaveAttribute('placeholder', /uploaded on/i)
  const split = page.getByLabel(/Train \/ Valid \/ Test/i)
  await expect(split, 'the split is visible on the empty page').toBeVisible()
  await expect(split).toHaveValue('auto')

  // V3: the formats, and the size cap read from the endpoint the upload route enforces.
  await expect(page.getByText(/images, folders|\.jpe?g|\.png/i).first()).toBeVisible()
  const cap = page.getByText(/\b\d+\s?(MB|GB|px)\b/i).first()
  await expect(cap, 'the size cap is stated').toBeVisible()

  // V4: the demo shortcut reuses the workspace's existing sample path.
  const demo = page.getByRole('link', { name: /demo set|sample images/i })
    .or(page.getByRole('button', { name: /demo set|sample images/i }))
  await expect(demo, 'the demo set shortcut is offered').toBeVisible()
  await demo.click()
  await expect(page.getByText(/\d+ new images/i), 'the demo images joined this batch').toBeVisible()
  await expect(page.getByRole('button', { name: 'Save and Continue' })).toBeEnabled()

  expect(errors, `console or page errors: ${errors.join(' | ')}`).toEqual([])
})

test('J2 upload empty state at 375 px, light and dark', async ({ page }) => {
  mkdirSync(evidence, { recursive: true })
  await signIn(page)
  await page.setViewportSize({ width: 375, height: 812 })

  // Light (the default is system, and Playwright's browser prefers light).
  await page.emulateMedia({ colorScheme: 'light' })
  await page.goto(`/${seeded.workspace}/p/${projectSlug}/upload`)
  await expect(page.getByRole('heading', { name: 'Upload Data' })).toBeVisible()
  await expect(page.getByLabel(/Batch name/i)).toBeVisible()
  await expect(page.getByText(/\b\d+\s?(MB|GB|px)\b/i).first()).toBeVisible()
  await expectNoHorizontalScroll(page)
  await page.screenshot({ path: path.join(evidence, 'upload-375-light.png'), fullPage: true })

  // Dark: the same page, same controls, same cap.
  await page.emulateMedia({ colorScheme: 'dark' })
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Upload Data' })).toBeVisible()
  await expect(page.getByLabel(/Batch name/i)).toBeVisible()
  await expect(page.getByText(/\b\d+\s?(MB|GB|px)\b/i).first()).toBeVisible()
  await expectNoHorizontalScroll(page)
  await page.screenshot({ path: path.join(evidence, 'upload-375-dark.png'), fullPage: true })
})
