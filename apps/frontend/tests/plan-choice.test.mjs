// T-011: the creation form offers Free / Pro / Enterprise from the plan limits, never a price,
// and the choice travels with the creation request so the workspace really starts on it.
//   node --test tests/plan-choice.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8')

test('test_default_chip_is_free', () => {
  const picker = read('../src/features/onboarding/PlanPicker.tsx')
  const form = read('../src/features/onboarding/WorkspaceForm.tsx')
  assert.match(picker, /export const DEFAULT_PLAN = 'free'/, 'Free is the default tier')
  assert.match(picker, /value \|\| DEFAULT_PLAN/, 'an untouched picker selects the default')
  assert.match(picker, /type="radio"/, 'the chips are one radio group, so arrow keys work')
  assert.match(picker, /checked=\{selected === p\.id\}/, 'the selected chip is the checked radio')
  assert.match(form, /<PlanPicker/, 'the picker sits in the workspace form')
})

test('test_chip_copy_uses_limits_not_prices', () => {
  const picker = read('../src/features/onboarding/PlanPicker.tsx')
  assert.doesNotMatch(picker, /[$฿]/, 'the picker prints no price of any currency')
  assert.match(picker, /p\.projects/, 'the limit line reads the project count from the API')
  assert.match(picker, /p\.credits/, 'the limit line reads the credit allowance from the API')
  assert.match(picker, /·/, 'one line, one separator')
  assert.doesNotMatch(picker, /card number|stripe|checkout/i, 'no card field, no provider')
})

test('test_the_choice_travels_with_creation_and_lands_as_a_note', () => {
  const auth = read('../src/features/auth/Auth.tsx')
  const settings = read('../src/features/settings/Settings.tsx')
  const home = read('../src/features/workspace/Home.tsx')
  assert.match(auth, /plan: plan \|\| 'free'/, 'signup sends the chosen tier')
  assert.match(settings, /plan: plan \|\| 'free'/, 'first run sends the chosen tier')
  assert.match(auth + settings, /startedPlan/, 'the landing carries the tier it started on')
  assert.match(home, /Started on /, 'the landing note names the tier')
  assert.match(home, /Settings → Plan & Usage\./, 'the note says where to change it')
})
