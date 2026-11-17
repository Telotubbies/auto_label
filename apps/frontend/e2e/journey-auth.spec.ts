// T-1201 — J1: a buyer signs up, verifies, signs out, survives a wrong password, signs in and
// recovers. Every assertion is about the shipped auth surface; this file adds no product code.
import { expect, test, type Page, type Route } from '@playwright/test'
import { record, seeded, setFlags } from './fixtures/harness'

// One account per run. The seed is not reset between specs, so a fixed address would collide on the
// second run and the suite would report a false duplicate-email failure.
const runId = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
const email = `j1+${runId}@labeldesk.dev`
const password = 'labeldesk-j1-passphrase'
const workspaceName = `J1 ${runId} workspace`

// The two rejections below are the flow's own negative cases; Chromium logs each HTTP failure as a
// console error, so only those two lines are allowed. Any other console or page error fails the test.
const expectedRejection = /status of (401|409)/

function watchErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error' && !expectedRejection.test(message.text())) errors.push(message.text())
  })
  page.on('pageerror', (error) => errors.push(error.message))
  return errors
}

async function expectNoHorizontalScroll(page: Page): Promise<void> {
  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow, 'the page is wider than its viewport').toBeLessThanOrEqual(0)
}

type FocusInfo = { id: string; text: string; ring: boolean; outline: string }

async function focusInfo(page: Page): Promise<FocusInfo> {
  return page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null
    return {
      id: el?.id ?? '',
      text: (el?.textContent ?? '').replace(/\s+/g, ' ').trim(),
      ring: !!el && el.matches(':focus-visible'),
      outline: el ? getComputedStyle(el).outlineWidth : '0px',
    }
  })
}

/** Assert what Tab landed on, and that the focus ring is actually painted. */
async function expectFocus(page: Page, expected: { id?: string; text?: string }): Promise<void> {
  await expect.poll(async () => {
    const seen = await focusInfo(page)
    return expected.id !== undefined ? seen.id : seen.text
  }).toBe(expected.id ?? expected.text)
  const seen = await focusInfo(page)
  expect(seen.ring, 'the focused control matches :focus-visible').toBe(true)
  expect(seen.outline, 'the focus ring has a visible outline').not.toBe('0px')
}

async function signOut(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Account menu' }).click()
  await page.getByRole('button', { name: 'Sign Out' }).click()
  await expect(page).toHaveURL(/\/login(\?|$)/)
}

test.beforeEach(() => record.reset())

test('J1 sign up → verify → sign in → wrong password', async ({ page, request }) => {
  const errors = watchErrors(page)
  // The auth surface has no flag: the flag-off leg is the empty set, and the fresh workspace starts
  // with no flags on, so every page below is reached exactly as a buyer with everything off sees it.
  await setFlags(request, [])

  await test.step('1. Landing: Start free opens Create account, Log in opens the login page', async () => {
    await page.goto('/')
    const startFree = page.getByRole('link', { name: 'Start free' }).first()
    await expect(startFree).toHaveAttribute('href', '/signup')
    await startFree.click()
    await expect(page).toHaveURL(/\/signup$/)
    await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
    await page.goBack()

    const logIn = page.getByRole('link', { name: 'Log in' }).first()
    await expect(logIn).toHaveAttribute('href', '/login')
    await logIn.click()
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByRole('heading', { name: 'Sign in', exact: true })).toBeVisible()
    await page.goBack()

    // 375: both forms fit without a sideways scroll.
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/signup')
    await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
    await expectNoHorizontalScroll(page)
    await page.goto('/login')
    await expect(page.getByRole('heading', { name: 'Sign in', exact: true })).toBeVisible()
    await expectNoHorizontalScroll(page)
    await page.setViewportSize({ width: 1440, height: 900 })

    // Keyboard only: every field, the submit and the footer link, in DOM order, with a visible ring.
    await page.goto('/signup')
    await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
    await expectFocus(page, { id: 'signup-name' })
    await page.keyboard.press('Tab'); await expectFocus(page, { id: 'signup-email' })
    await page.keyboard.press('Tab'); await expectFocus(page, { id: 'signup-password' })
    await page.keyboard.press('Tab'); await expectFocus(page, { id: 'signup-workspace' })
    await page.keyboard.press('Tab'); await expectFocus(page, { text: 'Create account' })
    await page.keyboard.press('Tab'); await expectFocus(page, { text: 'Sign in' })

    await page.goto('/login')
    await expect(page.getByRole('heading', { name: 'Sign in', exact: true })).toBeVisible()
    await expectFocus(page, { id: 'login-email' })
    await page.keyboard.press('Tab'); await expectFocus(page, { id: 'login-password' })
    await page.keyboard.press('Tab'); await expectFocus(page, { text: 'Forgot password?' })
    await page.keyboard.press('Tab'); await expectFocus(page, { text: 'Sign in' })
    await page.keyboard.press('Tab'); await expectFocus(page, { text: 'Create an account' })

    record.step()
  })

  await test.step('2. Create account: empty fields, a busy submit that keeps its width, duplicate email inline', async () => {
    await page.goto('/signup')
    await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
    for (const id of ['signup-name', 'signup-email', 'signup-password', 'signup-workspace']) {
      await expect(page.locator(`#${id}`)).toHaveValue('')
    }

    // A duplicate email is the honest error case: delay the request so the busy state can be measured,
    // then let the real 409 through and read the inline message the buyer gets.
    const slowSignup = async (route: Route) => {
      await new Promise((resolve) => setTimeout(resolve, 700))
      await route.continue()
    }
    await page.route('**/api/auth/signup', slowSignup)

    await page.locator('#signup-name').fill('J1 Buyer')
    await page.locator('#signup-email').fill(seeded.email)
    await page.locator('#signup-password').fill(password)
    await page.locator('#signup-workspace').fill(workspaceName)

    const submit = page.getByRole('button', { name: 'Create account' })
    const idle = await submit.boundingBox()
    expect(idle).not.toBeNull()
    await submit.click()
    await expect(submit).toHaveAttribute('aria-busy', 'true')
    const busy = await submit.boundingBox()
    expect(busy, 'the submit button keeps its box while busy').not.toBeNull()
    expect(Math.abs(busy!.width - idle!.width)).toBeLessThanOrEqual(1)

    await expect(page.locator('form').getByRole('alert')).toHaveCount(1)
    await expect(page.locator('form').getByRole('alert')).toContainText(/already exists/i)
    await expect(page.locator('#signup-email')).toHaveValue(seeded.email)
    await expect(page).toHaveURL(/\/signup$/)
    await page.unroute('**/api/auth/signup', slowSignup)

    // The same form, the buyer's own address.
    await page.locator('#signup-name').fill('J1 Buyer')
    await page.locator('#signup-email').fill(email)
    await page.locator('#signup-password').fill(password)
    await page.locator('#signup-workspace').fill(workspaceName)
    await page.getByRole('button', { name: 'Create account' }).click()

    await expect(page.getByRole('heading', { name: 'Home', exact: true })).toBeVisible({ timeout: 30_000 })
    record.step()
  })

  await test.step('3. Workspace home: its own empty workspace, with one next step', async () => {
    const slug = new URL(page.url()).pathname.replace(/^\//, '')
    expect(slug).toMatch(/^[a-z0-9-]+$/)
    expect(slug).not.toBe(seeded.workspace)

    // A brand-new person gets the designed first-run state: the tour, then the checklist whose only
    // actionable step is "Create a project".
    await expect(page.getByRole('button', { name: 'End tour' })).toBeVisible()
    await page.getByRole('button', { name: 'End tour' }).click()
    await expect(page.getByRole('heading', { name: 'Getting started' })).toBeVisible()
    await expect(page.getByText(/0 of \d+ done/)).toBeVisible()
    await expect(page.getByRole('button', { name: 'Create', exact: true })).toHaveCount(1)
    await expect(page.getByText('No projects yet.')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Create your first project' })).toBeVisible()
    record.step()
  })

  let slug = ''
  await test.step('4. Dev inbox: the verification mail, and its link says the address is verified', async () => {
    slug = new URL(page.url()).pathname.replace(/^\//, '')
    await page.goto('/__mail')
    await expect(page.getByRole('heading', { name: 'Dev mail' })).toBeVisible()
    const letter = page.locator('article').filter({ hasText: email })
    await expect(letter).toHaveCount(1)
    // The dev inbox is shared by every spec in a run; the line above already proves exactly one mail for this address.
    await expect(letter).toContainText('Verify your LabelDesk email')

    const href = await letter.getByRole('link').first().getAttribute('href')
    expect(href, 'the mail carries a verification link').toContain('/verify/')
    // The link is absolute against the API's PUBLIC_URL; the app runs on a chosen port here, so the
    // same link is opened on its path, without minting a token or calling the route by hand.
    await page.goto(new URL(href!).pathname)
    await expect(page.getByRole('heading', { name: 'Email verified' })).toBeVisible()
    await expect(page.getByText(email)).toBeVisible()

    await page.getByRole('link', { name: 'Open LabelDesk' }).click()
    await expect(page).toHaveURL(new RegExp(`/${slug}$`))
    await expect(page.getByRole('heading', { name: 'Home', exact: true })).toBeVisible()
    record.step()
  })

  await test.step('5. Sign out', async () => {
    await signOut(page)
    await expect(page.getByRole('heading', { name: 'Sign in', exact: true })).toBeVisible()
    record.step()
  })

  await test.step('6. Sign in: a wrong password costs one retry and keeps the email', async () => {
    await page.getByLabel('Email').fill(email)
    await page.getByLabel('Password').fill('not-the-password')
    await page.getByRole('button', { name: 'Sign in' }).click()

    await expect(page.locator('form').getByRole('alert')).toHaveCount(1)
    await expect(page.locator('form').getByRole('alert')).toContainText(/invalid email or password/i)
    await expect(page.locator('#login-email')).toHaveValue(email)
    await expect(page).toHaveURL(/\/login(\?|$)/)
    record.step()
  })

  await test.step('7. The right password lands on the workspace', async () => {
    await page.getByLabel('Password').fill(password)
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page).toHaveURL(new RegExp(`/${slug}$`))
    await expect(page.getByRole('heading', { name: 'Home', exact: true })).toBeVisible()
    record.step()
  })

  await test.step('8. Forgot password: one conditional sentence, never whether the account exists', async () => {
    await signOut(page)
    await page.goto('/forgot')
    await expect(page.getByRole('heading', { name: 'Reset your password' })).toBeVisible()
    await page.getByLabel('Email').fill(email)
    await page.getByRole('button', { name: 'Send reset link' }).click()

    await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible()
    await expect(page.getByText(/If an account exists for/)).toBeVisible()
    await expect(page.getByText(email)).toBeVisible()
    await expect(page.getByText(/no account|not found|does not exist/i)).toHaveCount(0)
    record.step()
  })

  const result = record.done({ steps: 8, timeMs: 120_000 })
  console.log(`J1 measured: ${result.steps} steps, ${result.timeMs} ms`)
  test.info().annotations.push({ type: 'journey-result', description: `J1 ${result.steps} steps, ${result.timeMs} ms` })
  expect(result.failures, 'the journey stays inside its step and time targets').toEqual([])
  expect(result.steps, 'no more than 10 steps').toBeLessThanOrEqual(10)
  expect(result.timeMs, 'no more than 240 s').toBeLessThanOrEqual(240_000)
  expect(errors, `console or page errors: ${errors.join(' | ')}`).toEqual([])
})

test('J1b unknown email never leaks existence', async ({ page }) => {
  const errors = watchErrors(page)
  const unknown = `j1+unknown+${runId}@labeldesk.dev`

  await page.goto('/forgot')
  await expect(page.getByRole('heading', { name: 'Reset your password' })).toBeVisible()
  await page.getByLabel('Email').fill(unknown)
  await page.getByRole('button', { name: 'Send reset link' }).click()

  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible()
  await expect(page.getByText(/If an account exists for/)).toBeVisible()
  await expect(page.getByText(unknown)).toBeVisible()
  await expect(page.getByText(/no account|not found|does not exist/i)).toHaveCount(0)
  expect(errors, `console or page errors: ${errors.join(' | ')}`).toEqual([])
})
