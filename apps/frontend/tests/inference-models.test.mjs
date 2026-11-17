// T-1012: the Models tab's pure rules — filters that combine, the variant the row starts on, the
// state the job outranks, and the copy a block carries.
// node --test tests/inference-models.test.mjs (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  NO_FILTERS, blockCopy, defaultVariant, filterModels, gib, rowState,
} from '../src/features/inference/modelRows.ts'

const GIB = 1024 ** 3
const variant = (over = {}) => ({
  id: 'bf16', quant: 'BF16', format: 'safetensors', engine: 'vllm', bytes: 16 * GIB,
  vram_gb: 18.4, fits: null, fit_verdict: null, assumed_context: 4096, installed: false, blocked: [],
  ...over,
})
const model = (over = {}) => ({
  id: 'qwen2.5-vl-7b', name: 'Qwen2.5-VL 7B Instruct', family: 'Qwen2.5-VL',
  params_b: 8.3, installed: false, fits: null, blocked: [],
  licence: { name: 'Apache-2.0', url: 'https://example.invalid/LICENSE', gated: false, non_commercial: false },
  variants: [variant()],
  ...over,
})
const ids = (rows) => rows.map((row) => row.id)

test('test_default_variant_is_the_smallest_that_fits', () => {
  // Three variants, two fit: the row starts on the smaller of the two, not the smallest overall.
  const three = model({
    fits: true,
    variants: [
      variant({ id: 'awq', bytes: 6 * GIB, fits: true }),
      variant({ id: 'bf16', bytes: 16 * GIB, fits: true }),
      variant({ id: 'fp8', bytes: 9 * GIB, fits: false }),
    ],
  })
  assert.equal(defaultVariant(three).id, 'awq')

  // Nothing fits: the smallest variant still opens, and it says it does not fit.
  const none = model({
    fits: false,
    variants: [
      variant({ id: 'fp8', bytes: 9 * GIB, fits: false }),
      variant({ id: 'bf16', bytes: 16 * GIB, fits: false }),
    ],
  })
  const picked = defaultVariant(none)
  assert.equal(picked.id, 'fp8')
  assert.equal(picked.fits, false)
  // Unknown (the host reported no GPU) is not a fit: only an explicit true counts as one.
  const unknown = model({
    variants: [variant({ id: 'awq', bytes: 6 * GIB, fits: null }),
      variant({ id: 'bf16', bytes: 16 * GIB, fits: null })],
  })
  assert.equal(defaultVariant(unknown).id, 'awq')
})

test('test_filters_combine', () => {
  const rows = [
    model({ id: 'qwen-7b', family: 'Qwen2.5-VL', installed: true, fits: true }),
    model({ id: 'qwen-27b', family: 'Qwen2.5-VL', installed: false, fits: true, params_b: 27.43 }),
    model({ id: 'llama-8b', family: 'Llama 3.1', installed: true, fits: false, params_b: 8.03 }),
    model({ id: 'gemma-27b', family: 'Gemma 3', installed: false, fits: false, params_b: 27.43 }),
  ]
  // Family + Fits + Installed is an intersection, not a union.
  assert.deepEqual(ids(filterModels(rows, { ...NO_FILTERS, family: 'Qwen2.5-VL', fits: true, installed: true })),
    ['qwen-7b'])
  assert.deepEqual(ids(filterModels(rows, { ...NO_FILTERS, family: 'Qwen2.5-VL', fits: true })), ['qwen-7b', 'qwen-27b'])
  assert.deepEqual(ids(filterModels(rows, { ...NO_FILTERS, band: 'mid' })), ['qwen-27b', 'gemma-27b'])
  assert.deepEqual(ids(filterModels(rows, { ...NO_FILTERS, quant: 'AWQ' })), [])
  // Clear filters restores every row, in catalogue order.
  assert.deepEqual(ids(filterModels(rows, NO_FILTERS)), ['qwen-7b', 'qwen-27b', 'llama-8b', 'gemma-27b'])
  // Filtering never rewrites the catalogue rows.
  const frozen = JSON.stringify(rows)
  filterModels(rows, { ...NO_FILTERS, fits: true })
  assert.equal(JSON.stringify(rows), frozen)
})

test('test_row_state_prefers_the_job_over_the_catalogue', () => {
  const waiting = model({ installed: false })
  const running = rowState(waiting, { status: 'running', progress: 43 })
  assert.equal(running.label, 'Downloading 43%')
  assert.notEqual(running.label, 'Not installed')
  assert.equal(running.state, 'downloading')
  assert.deepEqual(running.actions, [], 'a running download offers no second action')

  // Queued is its own state; a finished job gives the catalogue its say again.
  assert.equal(rowState(waiting, { status: 'queued', progress: 0 }).label, 'Queued')
  assert.equal(rowState(waiting, { status: 'failed', progress: 12 }).label, 'Not installed')
  assert.equal(rowState(model({ installed: true }), { status: 'done', progress: 100 }).label, 'Installed')
})

test('test_block_copy_names_the_numbers', () => {
  const plan = (over = {}) => ({
    total_bytes: 41 * GIB, disk_free_gb: 812, token_present: true,
    gate: { gated: false, licence: 'Apache-2.0', url: 'https://example.invalid/LICENSE', non_commercial: false },
    blocked: [],
    ...over,
  })
  // Disk: the sentence carries both numbers, and the 20% the download must leave alone.
  const disk = blockCopy(plan({ disk_free_gb: 28 }))
  assert.equal(disk.block, 'Needs 41.0 GB, host has 28.0 GB free.')
  assert.equal(disk.note, null)

  // Gated without a token on the host.
  const gated = blockCopy(plan({ token_present: false,
    gate: { gated: true, licence: 'Llama 3.1 Community License', url: 'https://example.invalid/L', non_commercial: false } }))
  assert.match(gated.block, /HF_TOKEN/)

  // Non-commercial is a badge sentence, not a block: the row stays downloadable.
  const nc = blockCopy(plan({
    gate: { gated: false, licence: 'CC BY-NC 4.0', url: 'https://example.invalid/NC', non_commercial: true } }))
  assert.equal(nc.block, null)
  assert.match(nc.note, /Non-commercial licence/)

  // A plan with nothing against it shows no block and no note.
  assert.deepEqual(blockCopy(plan()), { block: null, note: null })
})

test('test_installed_row_has_no_download_action', () => {
  const state = rowState(model({ installed: true, variants: [variant({ installed: true })] }))
  assert.equal(state.state, 'installed')
  assert.deepEqual(state.actions.map((action) => action.label), ['Manage on host'])
  assert.equal(state.actions.some((action) => action.kind === 'download'), false)
})

test('test_bytes_render_in_gb_with_one_decimal', () => {
  assert.equal(gib(41_000_000_000), '38.2 GB')
  assert.equal(gib(0), '0.0 GB')
  assert.equal(gib(2.1e12), '1955.8 GB')
  assert.doesNotMatch(gib(2.1e12), /e\+/, 'never scientific notation')
})
