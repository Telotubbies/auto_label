// T-481: the job tray is a workspace panel behind the top-bar icon.
//   node --test tests/job-tray.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { activeCount, cancelPath, etaLabel, jobPath, resultLine } from '../src/lib/jobs.ts'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8')
const panel = read('../src/components/shell/JobTray.tsx')
const button = read('../src/components/shell/JobButton.tsx')
const jobsSrc = read('../src/lib/jobs.ts')
const coreSrc = read('../src/lib/api/core.ts')
const flagsApi = read('../../backend/app/services/flags.py')

const job = (o = {}) => ({
  id: 'j-1', kind: 'train', status: 'queued', progress: 0, params: {}, result: {}, error: '',
  created: 1_000_000, started: null, finished: null, ...o,
})

test('test_active_count_ignores_finished_jobs', () => {
  const jobs = [
    job({ id: 'q', status: 'queued' }),
    job({ id: 'r', status: 'running' }),
    job({ id: 'c', status: 'cancelling' }),
    job({ id: 'd', status: 'done' }),
    job({ id: 'f', status: 'failed' }),
    job({ id: 'x', status: 'cancelled' }),
  ]
  assert.equal(activeCount(jobs), 3)
  assert.equal(activeCount([]), 0)
})

test('test_eta_label_uses_progress_and_elapsed', () => {
  const started = 1_000_000
  // 62 % after four minutes: about 2.5 minutes remain, read as ~2 min.
  assert.equal(etaLabel(job({ status: 'running', progress: 62, started }), started + 4 * 60), '~2 min left')
  // Under 5 % complete there is not enough signal to promise a time.
  assert.equal(etaLabel(job({ status: 'running', progress: 3, started }), started + 4 * 60), 'estimating')
  // A queued job has not started; it must not invent a countdown.
  assert.equal(etaLabel(job({ status: 'queued', progress: 0 }), started), 'estimating')
})

test('test_result_line_separates_project_with_a_middle_dot', () => {
  assert.equal(resultLine(job({ kind: 'train', project_name: 'Helmets' })), 'Training \u00B7 Helmets')
  assert.equal(resultLine(job({ kind: 'version', project_name: 'PPE' })), 'Version \u00B7 PPE')
  // A project-less job still reads as one line.
  assert.equal(resultLine(job({ kind: 'health', project_name: undefined })), 'Health check')
  // U+00B7 is written as an escape, and the file carries no mojibake.
  assert.ok(jobsSrc.includes('\\u00B7'), 'the separator is U+00B7')
  assert.ok(!/[ÃÂ]|\uFFFD/.test(jobsSrc), 'no corrupted bytes in jobs.ts')
})

test('test_cancel_uses_the_jobs_own_project', () => {
  const j = job({ id: 'j-9', project: 'ppe' })
  assert.equal(cancelPath('acme', j), '/ws/acme/projects/ppe/jobs/j-9/cancel')
  // The Retry link likewise resolves from the job, not the route the panel was opened on.
  assert.equal(jobPath('acme', job({ kind: 'train', project: 'helmets' })), '/acme/helmets/models')
  assert.equal(jobPath('acme', job({ kind: 'autolabel', project: 'helmets' })), '/acme/helmets/annotate')
})

test('test_panel_is_a_labelled_dialog', () => {
  assert.match(panel, /role="dialog"/)
  assert.match(panel, /aria-modal="false"/)
  assert.match(panel, /aria-live="polite"/)
  // A Tab trap keeps focus inside, and Escape hands it back to the trigger.
  assert.match(panel, /FOCUSABLE/)
  assert.match(panel, /e\.key === 'Escape'/)
  assert.match(panel, /focus\(\)/)
  assert.match(button, /aria-expanded=\{open\}/)
  assert.match(button, /aria-controls="job-panel"/)
})

test('test_panel_has_empty_loading_and_error_states', () => {
  assert.match(panel, /Nothing is running\. Uploads, versions, training and exports appear here\./)
  // Three skeleton rows while the first workspace list loads.
  assert.match(panel, /\[0, 1, 2\]\.map/)
  assert.match(panel, /aria-busy="true"/)
  assert.match(panel, /Could not load jobs . retry/)
  // The failure line and the retry action keep the panel open: no redirect.
  assert.doesNotMatch(panel, /<Navigate/)
})

test('test_panel_reads_the_workspace_job_list', () => {
  assert.match(coreSrc, /jobsList: \(ws: string\) => get<Job\[\]>\(`\/ws\/\$\{ws\}\/jobs`\)/)
  assert.match(panel, /api\.jobsList\(ws\)/)
  assert.match(button, /useFlag\('task_470'\)/)
})

test('test_flag_off_keeps_the_floating_tray', () => {
  assert.match(flagsApi, /"task_470":/)
  assert.match(panel, /fixed bottom-4 right-4/)
  assert.match(panel, /useFlag\('task_470'\)/)
  // The icon is flag-on only.
  assert.match(button, /if \(!on\) return null/)
})
