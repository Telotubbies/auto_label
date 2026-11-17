/**
 * T-1020 — the four Inference surfaces and the labeler denial, on a mocked worker.
 *
 * Only the inference routes are stubbed (`**\/api\/ws\/*\/inference\/**`), so sign-in, the project
 * list and the model registry stay real: the segmentation handoff is proved against the real
 * registry, not against a fixture. Nothing here starts an engine, downloads a weight, needs an
 * HF token or touches a GPU; every reply comes from `fixtures/inference.json`.
 */
import { expect, test, type Page, type Request } from '@playwright/test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { apiLog, seeded, setFlags } from './fixtures/harness'

test.use({ screenshot: 'only-on-failure' })

const WS = seeded.workspace
const INFERENCE = '**/api/ws/*/inference/**'
const fixtures = JSON.parse(
  readFileSync(path.join(import.meta.dirname, 'fixtures', 'inference.json'), 'utf8'),
)

type Reply = { status?: number; body: unknown }
/** Return a reply to override one route, or null to fall through to the fixture's default. */
type Hook = (tail: string, req: Request) => Reply | null

const json = (body: unknown, status = 200): Reply => ({ status, body })

/** The route's last segment path: `jobs/job-1`, `models/plan`, `engines/install`, `hosts`. */
const tailOf = (url: string) => {
  const at = new URL(url).pathname.indexOf('/inference/')
  return new URL(url).pathname.slice(at + '/inference/'.length)
}

function defaultReply(tail: string, req: Request): Reply {
  if (tail === 'hosts') return json(fixtures.hosts)
  if (tail === 'catalog') return json(fixtures.catalog)
  if (tail === 'estimate') return json(fixtures.estimate)
  if (tail === 'engines') return json(fixtures.engines)
  if (tail === 'engines/plan') return json(fixtures.enginePlan)
  if (tail === 'engines/install') return json({ job: fixtures.installQueued })
  if (tail === 'jobs') return json([])
  if (tail.startsWith('jobs/')) return json(fixtures.installDone)
  if (tail === 'models') return json(fixtures.models)
  if (tail === 'models/plan') {
    const body = JSON.parse(req.postData() ?? '{}')
    if (body.id === 'llama-3.1-8b') return json(fixtures.gatedPlan)
    if (body.variant === 'bf16') return json(fixtures.shortfallPlan)
    return json(fixtures.modelPlan)
  }
  if (tail === 'models/download') return json({ job: fixtures.downloadQueued })
  if (tail === 'segmentation') return json(fixtures.segmentation)
  return json({ detail: 'not found' }, 404)
}

/** Answer every inference call from the fixture; a hook may serve a state machine instead. */
async function stubInference(page: Page, hook?: Hook): Promise<void> {
  await page.route(INFERENCE, async (route) => {
    const req = route.request()
    const tail = tailOf(req.url())
    const reply = hook?.(tail, req) ?? defaultReply(tail, req)
    await route.fulfill({
      status: reply.status ?? 200,
      contentType: 'application/json',
      body: JSON.stringify(reply.body),
    })
  })
}

/** The demo admin signs in through the real form; a dead API fails naming its log, not a timeout. */
async function signInAs(page: Page, email: string): Promise<void> {
  await page.goto('/login')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(seeded.password)
  const answered = page.waitForResponse((r) => r.url().includes('/api/auth/login'))
  await page.getByRole('button', { name: 'Sign in' }).click()
  const response = await answered
  if (!response.ok()) {
    throw new Error(`signInAs: /api/auth/login answered ${response.status()}. Log: ${apiLog}`)
  }
  await page.waitForURL(new RegExp(`/${WS}$`))
}

/** The hub's host picker is loaded before its panel answers, so wait for the heading first. */
async function openHub(page: Page, tab: string): Promise<void> {
  await page.goto(`/${WS}/inference?tab=${tab}`)
  await expect(page.getByRole('heading', { name: 'Inference' })).toBeVisible()
}

/** The row whose engine checkbox is named `Select <engine>`, not a substring of another name. */
const engineRow = (page: Page, name: string) =>
  page.getByRole('row').filter({ has: page.getByRole('checkbox', { name: `Select ${name}` }) })

test('test_calculator_fits_and_states_its_assumptions', async ({ page, request }) => {
  await setFlags(request, ['task_inference'])
  const bodies: Record<string, any>[] = []
  await stubInference(page, (tail, req) => {
    if (tail !== 'estimate') return null
    bodies.push(JSON.parse(req.postData() ?? '{}'))
    return json(fixtures.estimate)
  })
  await signInAs(page, seeded.email)
  await page.getByRole('link', { name: 'Inference' }).click()
  await expect(page.getByRole('heading', { name: 'Inference' })).toBeVisible()
  await page.getByRole('tab', { name: 'Calculator' }).click()

  await page.getByLabel('Model source').selectOption('qwen2.5-vl-7b')
  await page.getByLabel('Card').selectOption('rtx4090')
  await expect(page.getByLabel('Precision')).toHaveValue('bf16')
  await expect(page.getByLabel('Context (tokens)')).toHaveValue('8192')
  await page.getByLabel('Batch').fill('4')

  await expect(page.getByText('Fits', { exact: true })).toBeVisible()
  await expect(page.getByText(/676–1014 tok\/s/)).toBeVisible()

  await page.getByText('Assumptions', { exact: true }).click()
  await expect(page.getByText('Estimate, not a benchmark.')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Transformer Math 101' })).toBeVisible()

  expect(bodies.at(-1)).toMatchObject({
    quant: 'bf16', context: 8192, batch: 4, tensor_parallel: 1,
    gpu: { preset: 'rtx4090' }, model: { params_b: 7.6 },
  })
})

test('test_blocked_engine_cannot_be_selected', async ({ page, request }) => {
  await setFlags(request, ['task_inference'])
  await stubInference(page)
  await signInAs(page, seeded.email)
  await openHub(page, 'engines')

  const trt = engineRow(page, 'TensorRT-LLM')
  await expect(trt.getByRole('checkbox', { name: 'Select TensorRT-LLM' })).toBeDisabled()
  await expect(trt.getByText('Blocked', { exact: true })).toBeVisible()
  await expect(trt).toContainText('Driver 535.54 or newer is required; the host reports 525.60.')
})

test('test_install_plan_needs_the_acknowledgement', async ({ page, request }) => {
  await setFlags(request, ['task_inference'])
  let posted = false
  let polls = 0
  let finished = false
  await stubInference(page, (tail) => {
    if (tail === 'engines/install') {
      posted = true
      return json({ job: fixtures.installQueued })
    }
    if (tail === 'jobs') {
      if (!posted) return json([])
      polls += 1
      // Three polled states: queued, then the phase the worker is on, then it leaves the list.
      if (polls === 1) return json([fixtures.installQueued])
      if (polls === 2) return json([fixtures.installRunning])
      return json([])
    }
    if (tail === `jobs/${fixtures.installDone.id}`) {
      finished = true
      return json(fixtures.installDone)
    }
    if (tail === 'engines' && finished) return json(fixtures.enginesAfterInstall)
    return null
  })
  await signInAs(page, seeded.email)
  await openHub(page, 'engines')
  await expect(page.getByLabel('Host')).toHaveValue('host-gpu-demo')

  await page.getByRole('checkbox', { name: 'Select vLLM' }).check()
  await page.getByRole('button', { name: 'Review install plan' }).click()

  const sheet = page.getByRole('dialog')
  await expect(sheet).toContainText('uv pip install --python .venv/bin/python vllm==0.6.6')
  await expect(sheet).toContainText('Total download')
  await expect(sheet).toContainText('Disk after')

  const install = sheet.getByRole('button', { name: 'Install' })
  await expect(install).toBeDisabled()
  await sheet.getByRole('checkbox').check()
  await expect(install).toBeEnabled()
  await install.click()

  await expect(page.getByText('Install queued on gpu-demo.', { exact: true })).toBeVisible()
  await expect(page.getByText('Installing vLLM.', { exact: true })).toBeVisible()
  await expect(page.getByText('Installed on gpu-demo.', { exact: true })).toBeVisible()
  await expect(engineRow(page, 'vLLM').getByText('Installed 0.6.6')).toBeVisible()
})

test('test_a_busy_host_409_renders_inline', async ({ page, request }) => {
  await setFlags(request, ['task_inference'])
  await stubInference(page, (tail) => {
    if (tail === 'engines/plan') return json(fixtures.sglangPlan)
    if (tail === 'engines/install') {
      return {
        status: 409,
        body: { detail: { error: 'An engine job is already running on this host.', job_id: fixtures.busyJob.id } },
      }
    }
    if (tail === 'jobs') return json([fixtures.busyJob])
    return null
  })
  await signInAs(page, seeded.email)
  await openHub(page, 'engines')

  await page.getByRole('checkbox', { name: 'Select SGLang' }).check()
  await page.getByRole('button', { name: 'Review install plan' }).click()

  const sheet = page.getByRole('dialog')
  await sheet.getByRole('checkbox').check()
  await sheet.getByRole('button', { name: 'Install' }).click()

  await expect(sheet.getByRole('alert'))
    .toContainText('An engine job is already running on this host, or the plan is out of date.')
  await sheet.getByRole('button', { name: 'View job' }).click()
  await expect(sheet).toBeHidden()
  await expect(page.getByText('Installing vLLM.', { exact: true })).toBeVisible()
})

test('test_model_download_shows_the_disk_after', async ({ page, request }) => {
  await setFlags(request, ['task_inference'])
  let downloading = false
  let polls = 0
  let finished = false
  await stubInference(page, (tail) => {
    if (tail === 'models/download') {
      downloading = true
      return json({ job: fixtures.downloadQueued })
    }
    if (tail === 'jobs') {
      if (!downloading) return json([])
      polls += 1
      return json(polls <= 2 ? [fixtures.downloadRunning] : [])
    }
    if (tail === `jobs/${fixtures.downloadDone.id}`) {
      finished = true
      return json(fixtures.downloadDone)
    }
    if (tail === 'models' && finished) return json(fixtures.modelsAfterDownload)
    if (tail === 'hosts' && finished) return json(fixtures.hostsAfterDownload)
    return null
  })
  await signInAs(page, seeded.email)
  await openHub(page, 'models')

  const bar = page.getByRole('progressbar', { name: 'Free disk on gpu-demo' })
  await expect(page.getByText('28 GB free of 80 GB')).toBeVisible()
  await expect(bar).toHaveAttribute('aria-valuenow', '35')

  await page.getByLabel('Fits this host').check()
  const qwen = page.getByRole('row').filter({ hasText: 'Qwen2.5-VL 7B' })

  // A plan that cannot fit states the shortfall and offers no Download button.
  await qwen.getByRole('button', { name: 'BF16', exact: true }).click()
  await qwen.getByRole('button', { name: 'Download' }).click()
  const tooBig = page.getByRole('dialog')
  await expect(tooBig.getByRole('alert')).toHaveText('Needs 41.0 GB, host has 28.0 GB free.')
  await expect(tooBig.getByRole('button', { name: 'Download' })).toHaveCount(0)
  await tooBig.getByRole('button', { name: 'Close' }).click()

  await qwen.getByRole('button', { name: 'AWQ', exact: true }).click()
  await qwen.getByRole('button', { name: 'Download' }).click()

  const sheet = page.getByRole('dialog')
  await expect(sheet).toContainText('Disk after')
  await expect(sheet).toContainText('22.5 GB')
  await sheet.getByRole('button', { name: 'Download' }).click()

  await expect(qwen.getByText('Downloading 43%')).toBeVisible()
  await expect(qwen.getByText('Installed', { exact: true })).toBeVisible()

  await expect(page.getByText('23 GB free of 80 GB')).toBeVisible()
  await expect(bar).toHaveAttribute('aria-valuenow', '28')
  const assets = page.getByRole('region', { name: 'Installed models' })
  await expect(assets).toContainText('Qwen2.5-VL 7B')
  await expect(assets).toContainText('AWQ')
  await expect(assets).toContainText('5.5 GB')
})

test('test_gated_model_without_a_token_is_disabled', async ({ page, request }) => {
  await setFlags(request, ['task_inference'])
  await stubInference(page)
  await signInAs(page, seeded.email)
  await openHub(page, 'models')

  const llama = page.getByRole('row').filter({ hasText: 'Llama 3.1 8B' })
  await expect(llama.getByText('Gated', { exact: true })).toBeVisible()
  await llama.getByRole('button', { name: 'Download' }).click()

  const sheet = page.getByRole('dialog')
  await expect(sheet.getByRole('alert')).toContainText('HF_TOKEN')
  await expect(sheet.getByRole('button', { name: 'Download' })).toHaveCount(0)

  await sheet.getByRole('button', { name: 'Close' }).click()
  await page.getByLabel('Installed').check()
  await expect(page.getByText('No model matches these filters.')).toBeVisible()
  await page.getByRole('button', { name: 'Clear filters' }).first().click()
  await expect(llama).toBeVisible()
})

test('test_segmentation_handoff_preselects_the_model', async ({ page, request }) => {
  await setFlags(request, ['task_inference'])
  await stubInference(page)
  await signInAs(page, seeded.email)
  await openHub(page, 'segmentation')

  await page.getByLabel('Project', { exact: true }).selectOption({ label: seeded.projectName })
  const sam = page.getByRole('listitem').filter({ hasText: 'SAM 3.1' })
  await expect(sam.getByText('Ready', { exact: true })).toBeVisible()
  await sam.getByRole('button', { name: 'Use SAM 3.1 for auto-label' }).click()

  await expect(page).toHaveURL(new RegExp(`/${WS}/p/${seeded.project}/dataset$`))
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  // The real registry answers this select; the handoff must land on a ref it really lists.
  await expect(dialog.getByLabel('Model')).toHaveValue('sam3:sam3.1')
  await expect(page).not.toHaveURL(/autolabel/)
})

test('test_labeler_has_no_rail_entry_and_direct_url_redirects', async ({ page, request }) => {
  await setFlags(request, ['task_inference'])
  await signInAs(page, 'labeler@labeldesk.dev')

  await expect(page.getByRole('link', { name: 'Inference' })).toHaveCount(0)
  await page.goto(`/${WS}/inference`)
  await expect(page).toHaveURL(new RegExp(`/${WS}$`))
  await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Inference' })).toHaveCount(0)
})

// ---------------------------------------------------------------------------------------------
// T-1110: the nine Important findings from the T-1021 UI QA pass, proved in the browser where the
// finding was a measurement. `e2e` runs at 1440 x 900 unless a test sets its own viewport.
// ---------------------------------------------------------------------------------------------

test('test_the_tab_bar_is_a_tablist', async ({ page, request }) => {
  // Row 4: the bar announced four buttons and marked the current one by colour alone.
  await setFlags(request, ['task_inference'])
  await stubInference(page)
  await signInAs(page, seeded.email)
  await openHub(page, 'engines')

  await expect(page.getByRole('tablist')).toBeVisible()
  const engines = page.getByRole('tab', { name: 'Engines' })
  await expect(engines).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByRole('tab', { name: 'Models' })).toHaveAttribute('aria-selected', 'false')

  // One tab stop for the bar; the arrows move between tabs (ARIA tabs pattern).
  await engines.press('ArrowRight')
  await expect(page.getByRole('tab', { name: 'Models' })).toHaveAttribute('aria-selected', 'true')
  await expect(page).toHaveURL(/tab=models/)
})

test('test_hosts_failure_says_so_and_retries', async ({ page, request }) => {
  // Row 5: a failed /hosts read used to say "No host has reported".
  await setFlags(request, ['task_inference'])
  let down = true
  await stubInference(page, (tail) => (tail === 'hosts' && down ? { status: 500, body: { detail: 'boom' } } : null))
  await signInAs(page, seeded.email)
  await openHub(page, 'engines')

  await expect(page.getByText('Hosts did not load.')).toBeVisible()
  await expect(page.getByLabel('Host', { exact: true })).toHaveCount(0)

  down = false
  await page.getByRole('button', { name: 'Retry' }).first().click()
  await expect(page.getByLabel('Host', { exact: true })).toHaveValue('host-gpu-demo')
  await expect(page.getByText('Hosts did not load.')).toHaveCount(0)
})

test('test_install_sheet_fits_a_375_viewport_and_traps_focus', async ({ page, request }) => {
  // Rows 2 and 3: the sheet was taller than a 375 px viewport, so Install sat below the fold; and
  // focus stayed on the page behind it, walked out of the dialog after four stops and was never
  // given back.
  await page.setViewportSize({ width: 375, height: 812 })
  await setFlags(request, ['task_inference'])
  await stubInference(page)
  await signInAs(page, seeded.email)
  await openHub(page, 'engines')

  await page.getByRole('checkbox', { name: 'Select vLLM' }).check()
  const trigger = page.getByRole('button', { name: 'Review install plan' })
  await trigger.click()

  const sheet = page.getByRole('dialog')
  await expect(sheet).toBeVisible()
  const install = sheet.getByRole('button', { name: 'Install' })
  await expect(install).toBeVisible()
  // The whole primary button and the acknowledgement are inside the 812 px viewport, not merely
  // touching its edge: the finding was that Install sat below the fold.
  for (const locator of [install, sheet.getByRole('checkbox')]) {
    const box = await locator.boundingBox()
    expect(box).not.toBeNull()
    expect(box!.y + box!.height).toBeLessThanOrEqual(812)
  }

  // Focus enters the dialog, and Tab from the last control comes back to the first (Close).
  await expect(sheet).toBeFocused()
  await sheet.getByRole('button', { name: 'Cancel' }).focus()
  await page.keyboard.press('Tab')
  await expect(sheet.getByRole('button', { name: 'Close' })).toBeFocused()

  // Escape closes it and focus returns to the control that opened it.
  await page.keyboard.press('Escape')
  await expect(sheet).toHaveCount(0)
  await expect(trigger).toBeFocused()
})

test('test_calculator_does_not_scroll_sideways_at_375', async ({ page, request }) => {
  // Row 1: the results table stretched its grid track, so the whole panel scrolled 50 px sideways
  // once an estimate was shown. Measured on the scroller the page actually uses.
  await page.setViewportSize({ width: 375, height: 812 })
  await setFlags(request, ['task_inference'])
  await stubInference(page)
  await signInAs(page, seeded.email)
  await openHub(page, 'calculator')

  await page.getByLabel('Model source').selectOption('qwen2.5-vl-7b')
  await page.getByRole('button', { name: 'Show estimate' }).click()
  await expect(page.getByText('Fits', { exact: true })).toBeVisible()

  const measured = await page.evaluate(() => {
    const main = document.querySelector('main')
    const root = document.scrollingElement ?? document.documentElement
    return {
      document: root.scrollWidth,
      viewport: window.innerWidth,
      main: main ? [main.scrollWidth, main.clientWidth] : null,
    }
  })
  expect(measured.document).toBeLessThanOrEqual(measured.viewport)
  if (measured.main) expect(measured.main[0]).toBeLessThanOrEqual(measured.main[1])
})
