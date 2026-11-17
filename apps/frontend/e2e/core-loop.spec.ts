import { expect, test } from '@playwright/test'
import path from 'node:path'

const WS = 'labeldesk-demo'
const PR = 'ppe-detection'
const FIXTURE = path.join(import.meta.dirname, 'fixtures', 'one.jpg')
const VERSION = 'T-008 core loop'

test('core loop: sign in → project → upload → annotate → version → train entry → deploy', async ({ page }) => {
  const consoleErrors: string[] = []
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()) })
  page.on('pageerror', (e) => consoleErrors.push(e.message))

  await test.step('1. Sign in', async () => {
    await page.goto('/')
    await page.getByRole('link', { name: 'Log in' }).first().click()
    await expect(page).toHaveURL(/\/login$/)

    await page.getByLabel('Email').fill('demo@labeldesk.dev')
    await page.getByLabel('Password').fill('wrong-password')
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page.getByRole('alert')).toContainText(/invalid email or password/i)
    await expect(page).toHaveURL(/\/login$/)
    // The rejected POST is the one expected 401 line; every later step must be clean.
    consoleErrors.length = 0

    await page.getByLabel('Password').fill('demo1234')
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page).toHaveURL(new RegExp(`/${WS}$`))
    await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible()
  })

  await test.step('2. Open project', async () => {
    await page.locator('[data-tour="home-projects"]').getByRole('link', { name: /PPE Detection/ }).first().click()
    await expect(page).toHaveURL(new RegExp(`/${WS}/${PR}/browse$`))
    await expect(page.getByRole('heading', { name: 'Dataset' })).toBeVisible()
    await expect(page.getByRole('navigation', { name: 'Breadcrumb' }).getByRole('link', { name: 'PPE Detection' })).toBeVisible()
  })

  await test.step('3. Upload', async () => {
    await page.getByRole('link', { name: 'Upload' }).click()
    await expect(page.getByRole('heading', { name: 'Upload Data' })).toBeVisible()
    await page.locator('input[type=file]').first().setInputFiles(FIXTURE)
    await page.getByRole('button', { name: 'Save and Continue' }).click()
    await expect(page.getByText(/Uploaded 1 .* failed 0/)).toBeVisible({ timeout: 30_000 })
    await page.getByRole('button', { name: 'View Dataset' }).click()
    await expect(page.getByRole('heading', { name: 'Dataset' })).toBeVisible()
    // A fresh upload has no labels yet, so the reviewer default (approved images) hides it.
    await page.getByRole('combobox').first().selectOption('all')
    await page.getByPlaceholder('Search filename').fill('one.jpg')
    await expect(page.getByRole('button', { name: 'Open one.jpg in the editor' })).toBeVisible()
  })

  await test.step('4. Annotate', async () => {
    await page.getByRole('button', { name: 'Open one.jpg in the editor' }).click()
    await expect(page.getByRole('heading', { name: 'one.jpg' })).toBeVisible()
    const area = page.getByTestId('canvas-area')
    await area.waitFor({ state: 'visible' })
    await area.locator('canvas').first().waitFor({ state: 'visible' })

    await page.getByRole('button', { name: 'Classes' }).click()
    await page.getByTestId('class-option').filter({ hasText: 'helmet' }).first().click()
    await page.getByTestId('tool-bbox').click()

    const saved = page.waitForResponse(
      (r) => r.request().method() === 'PUT' && /\/api\/images\/[^/]+\/annotations$/.test(new URL(r.url()).pathname),
      { timeout: 15_000 },
    )
    const box = await area.boundingBox()
    if (!box) throw new Error('editor canvas has no box')
    await page.mouse.click(box.x + box.width * 0.35, box.y + box.height * 0.35)
    await page.mouse.click(box.x + box.width * 0.6, box.y + box.height * 0.6)

    await page.getByRole('button', { name: 'Objects' }).click()
    await expect(page.getByTestId('object-row')).toHaveCount(1)
    await expect(page.getByTestId('object-row').first()).toContainText('helmet')
    expect((await saved).ok()).toBe(true)

    await page.reload()
    await page.getByTestId('canvas-area').waitFor({ state: 'visible' })
    await page.getByRole('button', { name: 'Objects' }).click()
    await expect(page.getByTestId('object-row')).toHaveCount(1)
    await expect(page.getByTestId('object-row').first()).toContainText('helmet')
  })

  await test.step('5. Version', async () => {
    await page.goto(`/${WS}/${PR}/browse`)
    await expect(page.getByRole('heading', { name: 'Dataset' })).toBeVisible()
    await page.getByRole('link', { name: 'Versions' }).click()
    await expect(page.getByRole('heading', { name: 'Versions' })).toBeVisible()

    await page.getByRole('button', { name: 'Generate New Version' }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    for (let step = 0; step < 4; step++) await page.getByRole('button', { name: 'Continue' }).click()
    await page.getByLabel('Version name (optional)').fill(VERSION)
    await page.getByRole('button', { name: 'Create Version' }).click()
    await expect(page.getByRole('button', { name: new RegExp(VERSION) })).toBeVisible()
  })

  await test.step('6. Train entry', async () => {
    await page.getByRole('link', { name: 'Train' }).click()
    await expect(page.getByRole('heading', { name: 'Train a Model' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Start Training' })).toBeVisible()
  })

  await test.step('7. Deploy page', async () => {
    await page.getByRole('link', { name: 'Deploy & Test', exact: true }).click()
    // The demo model is seeded from the ML checkout; without it the page shows its empty state.
    await expect(page.getByRole('heading', { name: 'Deploy & Test' })
      .or(page.getByText('No trained model to deploy yet.'))).toBeVisible()
  })

  expect(consoleErrors, `console errors: ${consoleErrors.join(' | ')}`).toEqual([])
})
