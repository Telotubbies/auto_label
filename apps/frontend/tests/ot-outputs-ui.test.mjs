// Task 40 fix round (I1, I2): the per-row switch is the actuator control, so it must say what it
// does in visible text; the screenshot script must also capture the flag-off page, since off is
// the shipped default. Source-checked because the suite has no DOM renderer and no server.
//   node --test tests/ot-outputs-ui.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8')
const row = read('../src/features/project/OtOutputs.tsx')
const shot = read('../scripts/ot-shot.mjs')

test('the row switch shows Enabled/Disabled beside it, like the add form', () => {
  const lines = row.split('\n')
  const at = lines.findIndex((l) => l.includes('label={`Enable ${output.name}`}'))
  assert.ok(at >= 0, 'the row switch must keep its accessible label')
  assert.match(lines.slice(at, at + 3).join('\n'), /\{output\.enabled \? 'Enabled' : 'Disabled'\}/)
})

test('the shot script captures the flag-off page and restores the flag', () => {
  assert.match(shot, /setFlag\(offContext, offHeaders, false\)/, 'a flag-off pass must exist')
  assert.match(shot, /ot-outputs-flag-off\.png/, 'the flag-off capture must be saved')
  assert.match(shot, /finally \{[\s\S]{0,60}setFlag\(offContext, offHeaders, true\)/, 'the flag must be restored')
})
