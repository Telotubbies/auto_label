// T-1013: the host assets panel's pure rules — the disk needle, the size order, the removal copy and
// the two empty states that must never read the same. node --test tests/inference-assets.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  LOW_DISK, diskPct, emptyCopy, engineLine, installedModels, lowDisk, removeCopy, sortBySize,
} from '../src/features/inference/assets.ts'

test('test_disk_percentage_and_low_disk_threshold', () => {
  assert.equal(diskPct({ models_free_gb: 812, models_total_gb: 1863 }), 44)
  // Under 10% is the warning state; exactly 10% is not (the bar is share free, not share used).
  assert.equal(lowDisk({ models_free_gb: 9, models_total_gb: 100 }), true)
  assert.equal(lowDisk({ models_free_gb: 10, models_total_gb: 100 }), false)
  // T-1110 (row 6): PLAN §9 alerts on "< 10 GB or < 10%" — the share alone labelled a 1.8 TB
  // disk with 28 GB free as low while 28 GB is a lot of room on an 80 GB disk.
  assert.equal(lowDisk({ models_free_gb: 28, models_total_gb: 1800 }), true)
  assert.equal(lowDisk({ models_free_gb: 28, models_total_gb: 280 }), false)
  assert.equal(lowDisk({ models_free_gb: 9.9, models_total_gb: 5000 }), true)
  assert.equal(lowDisk({ models_free_gb: 8, models_total_gb: 50 }), true)   // 16% free, but under 10 GB
  assert.equal(lowDisk({ models_free_gb: 500, models_total_gb: 1863 }), false)
  // A host that reported no disk has no needle and no warning: the panel says nothing rather than guess.
  assert.equal(diskPct(null), null)
  assert.equal(diskPct({ models_free_gb: 812 }), null)
  assert.equal(lowDisk(undefined), false)
})

test('test_low_disk_remedy_names_what_v1_offers', () => {
  // T-1110 (row 8): the remedy named LD_MODELS_MAX_GB, which owner decision §12.4 removed
  // ("No GB cap setting in v1"), and the backticks rendered as literal characters. v1's remedy is
  // removing a model from the panel this sentence lives in.
  assert.match(LOW_DISK, /Under 10 GB or 10% free/, 'the rule the alert applies is stated')
  assert.match(LOW_DISK, /Remove a model/, 'the remedy is the one v1 has')
  assert.doesNotMatch(LOW_DISK, /LD_|`/, 'no setting that v1 does not ship, and no literal markup')
})

test('test_installed_models_are_sorted_by_size_desc', () => {
  const inventory = {
    models: [
      { id: 'small', variant: 'q4_k_m', bytes: 2_000_000_000 },
      { id: 'big', variant: 'q8_0', bytes: 8_000_000_000 },
      { id: 'mid', variant: 'awq', bytes: 4_400_000_000 },
    ],
  }
  const frozen = JSON.stringify(inventory)
  assert.deepEqual(installedModels(inventory).map((model) => model.id), ['big', 'mid', 'small'])
  // Largest first is the point of the panel; the host's own report is not reordered in place.
  assert.deepEqual(sortBySize(inventory.models).map((model) => model.id), ['big', 'mid', 'small'])
  assert.equal(JSON.stringify(inventory), frozen)
})

test('test_remove_copy_names_model_variant_host_and_bytes', () => {
  const copy = removeCopy({
    id: 'qwen2.5-vl-7b', name: 'Qwen2.5-VL-7B', variant: 'AWQ', bytes: 4_700_000_000, host: 'gpu-1',
  })
  for (const part of ['Qwen2.5-VL-7B', 'AWQ', 'gpu-1', '4.4 GB']) {
    assert.equal(copy.includes(part), true, `the confirm must name ${part}`)
  }
  assert.equal(copy, 'Remove Qwen2.5-VL-7B (AWQ) from gpu-1? This frees 4.4 GB.')
})

test('test_empty_inventory_is_distinct_from_nothing_installed', () => {
  // Null is "the host has not said"; an empty list is a fact the host reported.
  assert.match(emptyCopy(null), /has not reported/)
  assert.match(emptyCopy({ models: [] }), /Nothing installed yet\./)
  assert.equal(emptyCopy({ models: [{ id: 'qwen3-4b', bytes: 1 }] }), null)
})

test('test_engine_line_lists_only_installed_engines', () => {
  const inventory = {
    engines: [
      { id: 'vllm', version: '0.6.3', ok: true },
      { id: 'llamacpp', version: 'b3900', ok: false },
      { id: 'ollama', version: '0.5.1', ok: true },
    ],
  }
  assert.equal(engineLine(inventory), 'vLLM 0.6.3 · Ollama 0.5.1')
  assert.equal(engineLine({ engines: [] }), '')
  assert.equal(engineLine(null), '')
})
