// T-1200 — the shared e2e harness. One import gives a spec sign-in, feature flags, the seeded ids,
// step counting, axe and API stubs, so a journey file is intent instead of setup.
import path from 'node:path'
import { tmpdir } from 'node:os'
import type { APIRequestContext, Page } from '@playwright/test'

/** Where playwright.config.ts sends the API's output; a failed sign-in names it. */
export const apiLog = path.join(process.env.TMP || tmpdir(), 'labeldesk-e2e-api.log')

/** The demo seed by slug and name: row ids are generated per run, so a spec navigates by these. */
export const seeded = {
  workspace: 'labeldesk-demo',
  project: 'ppe-detection',
  projectName: 'PPE Detection',
  version: 'Demo v1',
  model: 'PPE Detector YOLO26n',
  stream: 'Gate camera',
  classes: ['person', 'helmet', 'closed footwear', 'harness'],
  email: 'demo@labeldesk.dev',
  password: 'demo1234',
} as const

/** Sign the demo admin in through the real form; a dead API fails naming its log, not a timeout. */
export async function signIn(page: Page): Promise<void> {
  await page.goto('/login')
  await page.getByLabel('Email').fill(seeded.email)
  await page.getByLabel('Password').fill(seeded.password)
  const answered = page.waitForResponse((r) => r.url().includes('/api/auth/login'))
  await page.getByRole('button', { name: 'Sign in' }).click()
  const response = await answered
  if (!response.ok()) {
    throw new Error(`signIn: /api/auth/login answered ${response.status()}. Is the API up? Log: ${apiLog}`)
  }
  await page.waitForURL(new RegExp(`/${seeded.workspace}$`))
}

/** Turn a card's flags on (or off) for the demo workspace before the first navigation. */
export async function setFlags(request: APIRequestContext, keys: readonly string[], enabled = true): Promise<void> {
  if (!keys.length) return                                  // a flag-off leg asks for nothing
  const login = await request.post('/api/auth/login', {
    data: { email: seeded.email, password: seeded.password },
  })
  if (!login.ok()) {
    throw new Error(`setFlags: the demo login answered ${login.status()}. Is the API up? Log: ${apiLog}`)
  }
  const { token } = (await login.json()) as { token: string }
  for (const key of keys) {
    const response = await request.put(`/api/ws/${seeded.workspace}/flags/${key}`, {
      data: { enabled }, headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok()) {
      throw new Error(`setFlags: flag "${key}" answered ${response.status()}: ${await response.text()}`)
    }
  }
}

export type JourneyTarget = { steps: number; timeMs: number }
export type JourneyResult = { ok: boolean; steps: number; timeMs: number; failures: string[] }

/** Step and time accounting for one journey: each step owns the time since the previous one. */
export class JourneyRecord {
  private readonly now: () => number
  private deltas: number[] = []
  private last = 0
  steps = 0

  constructor(now: () => number = () => Date.now()) {
    this.now = now
    this.reset()
  }

  reset(): void {
    this.steps = 0
    this.deltas = []
    this.last = this.now()
  }

  step(): void {
    const at = this.now()
    this.deltas.push(at - this.last)
    this.last = at
    this.steps += 1
  }

  get timeMs(): number {
    return this.deltas.reduce((sum, ms) => sum + ms, 0)
  }

  /** Compare against the card's target; returns the failure so a spec can report both numbers. */
  done(target: JourneyTarget): JourneyResult {
    const failures: string[] = []
    if (this.steps > target.steps) failures.push(`steps ${this.steps} over the ${target.steps} target`)
    if (this.timeMs > target.timeMs) failures.push(`time ${this.timeMs} ms over the ${target.timeMs} ms target`)
    return { ok: failures.length === 0, steps: this.steps, timeMs: this.timeMs, failures }
  }
}

/** The running journey of a spec; call `reset()` between two tests in one file. */
export const record = new JourneyRecord()

export type StubReply = { status?: number; body?: unknown; delayMs?: number; times?: number }

/**
 * Answer a route without the backend: an empty list, a 503, or a slow reply for the loading state.
 * `times` lets one failure pass and the real route take over, which is how a retry is proven.
 */
export async function stubApi(page: Page, url: string | RegExp, reply: StubReply = {}): Promise<void> {
  let served = 0
  await page.route(url, async (route) => {
    if (reply.times !== undefined && served >= reply.times) return route.fallback()
    served += 1
    if (reply.delayMs) await new Promise((resolve) => setTimeout(resolve, reply.delayMs))
    await route.fulfill({
      status: reply.status ?? 200,
      contentType: 'application/json',
      body: JSON.stringify(reply.body ?? {}),
    })
  })
}

export type AxeViolation = { id: string; impact?: string | null; help: string; nodes: unknown[] }

/** Run axe on the current page (or one region); the audit specs grade what comes back. */
export async function axe(page: Page, selector?: string): Promise<AxeViolation[]> {
  const { default: AxeBuilder } = await import('@axe-core/playwright')   // lazy: node tests stay light
  let builder = new AxeBuilder({ page })
  if (selector) builder = builder.include(selector)
  const { violations } = await builder.analyze()
  return violations
}
