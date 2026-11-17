// Parity guard area 4 (source contract, no render):
//   4-F4.9 / 4-F4.10 / 4-F4.11  five-step wizard, step 1 count, step 2 total gate
//   4-F4.2 / 4-F4.36            version detail counts, settings summary, the three export states
//   4-F4.44                     the Dataset health tab the area-4 report links to
//
//   node --test tests/parity-guard-area4.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8')
const versions = read('../src/features/project/Versions.tsx')
const insights = read('../src/features/project/Insights.tsx')

function lineWith(src, needle) {
  const line = src.split('\n').find((l) => l.includes(needle))
  assert.ok(line, `expected a line containing ${JSON.stringify(needle)}`)
  return line
}

test('test_version_wizard_keeps_five_steps_and_the_total_gate', () => {
  const steps = [...lineWith(versions, 'const steps =').matchAll(/'([^']+)'/g)].map((m) => m[1])
  assert.deepEqual(steps, ['Source', 'Train/Test Split', 'Preprocessing', 'Augmentation', 'Create'])
  assert.equal(steps.length, 5)

  // every step is reachable from the strip, not only the next one
  assert.match(lineWith(versions, '{steps.map('), /onClick=\{\(\) => setStep\(i\)\}/)

  // 4-F4.10: step 1 states what enters the version
  assert.match(versions, /approved images will be frozen/)

  // 4-F4.11: step 2 validates the total inline and the Create action stays disabled until it is 100
  assert.match(versions, /Percentages must add to 100\./)
  const create = lineWith(versions, 'Create Version')
  assert.match(create, /split\.train \+ split\.valid \+ split\.test !== 100/)
  assert.match(create, /disabled=/)
})

test('test_version_detail_keeps_counts_settings_and_the_export_states', () => {
  // 4-F4.2: total plus the three split counts
  assert.match(versions, /Total images/)
  const splitKeys = lineWith(versions, "(['train', 'valid', 'test'] as const).map")
  for (const key of ['train', 'valid', 'test']) assert.match(splitKeys, new RegExp(`'${key}'`))

  // the frozen recipe summary
  assert.match(versions, /Preprocessing: /)
  assert.match(versions, /Augmentation: /)

  // 4-F4.36: done, in-progress and not-started export states
  assert.match(versions, /Download zip/)
  assert.match(versions, /Exporting…/)
  assert.match(versions, />Export<\/Button>/)
})

test('test_the_analytics_tab_keeps_its_health_entry', () => {
  // 4-F4.44: area-4 report links point at ?tab=health; the tab id and its label must not drift
  assert.match(insights, /\{\s*id: 'health', label: 'Dataset health'\s*\}/)
})
