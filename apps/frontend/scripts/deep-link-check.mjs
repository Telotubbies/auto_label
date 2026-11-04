// Anonymous deep-link check: a logged-out project URL must bounce to /login with ?next= and return there
// after signing in with the seeded demo account.
//   node scripts/deep-link-check.mjs [baseUrl]
import assert from 'node:assert/strict'
import { chromium } from 'playwright'

const base = process.argv[2] ?? 'http://localhost:5180'
const deep = '/labeldesk-demo/ppe-detection/browse'
const email = process.env.LD_DEMO_EMAIL ?? 'demo@labeldesk.dev'
const password = process.env.LD_DEMO_PW ?? 'demo1234'

const browser = await chromium.launch()
const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage()
const failed = []
try {
  await page.goto(base + deep, { waitUntil: 'domcontentloaded' })
  await page.waitForURL(/\/login\?next=/, { timeout: 10_000 })
  const loginUrl = new URL(page.url())
  assert.equal(loginUrl.pathname, '/login', `expected /login, got ${loginUrl.pathname}`)
  assert.equal(loginUrl.searchParams.get('next'), deep, 'next param lost the original path')

  await page.getByPlaceholder('Email').fill(email)
  await page.getByPlaceholder('Password').fill(password)
  await page.getByRole('button', { name: 'Sign In' }).click()
  await page.waitForURL(base + deep, { timeout: 20_000 })

  console.log(JSON.stringify({ deep, landedOn: page.url(), ok: true }, null, 2))
} catch (e) {
  failed.push(String(e))
  console.log(JSON.stringify({ deep, landedOn: page.url(), ok: false, error: String(e).split('\n')[0] }, null, 2))
} finally {
  await browser.close()
}
if (failed.length) process.exit(1)
