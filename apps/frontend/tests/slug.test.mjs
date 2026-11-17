// T-1104 V1 — the new-project dialog shows the address a name will take before submit, so the
// browser needs the API's own slug rule (`apps/backend/app/routers/projects.py:slugify`).
// The same five names are asserted against the server's rule in
// `apps/backend/tests/test_project_address.py`: if either side changes, one of the two goes red.
//   node --test tests/slug.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { projectSlug } from '../src/lib/slug.ts'

/** [name the buyer types, address segment the API stores] */
const CASES = [
  ['Hardhat Detection', 'hardhat-detection'],
  ['PPE — ตรวจสอบ หมวกกันน็อค!', 'ppe'],
  ['ซอย 5 (ทดสอบ)', '5'],
  ['  Lots   of   SPACE  ', 'lots-of-space'],
  ['Settings', 'settings-project'],
]

for (const [name, expected] of CASES) {
  test(`the preview matches the API slug rule for ${JSON.stringify(name)}`, () => {
    assert.equal(projectSlug(name), expected)
  })
}

test('an all-punctuation name still gets the API default', () => {
  assert.equal(projectSlug('!!!'), 'project')
  assert.equal(projectSlug(''), 'project')
})

test('the preview stops where the API stops: 80 characters', () => {
  assert.equal(projectSlug('a'.repeat(120)), 'a'.repeat(80))
})
