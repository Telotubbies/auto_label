// A flag-gated surface says it is off instead of bouncing to the dataset (UI audit A10, T-521).
//   node --test tests/flag-gate.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { flagDecision, flagSurfaceLabel } from '../src/lib/flagGate.ts'
import { projectNav } from '../src/lib/nav.ts'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8')
const notice = read('../src/components/NotEnabled.tsx')
const guards = read('../src/routes/guards.tsx')
const flagsApi = read('../../backend/app/services/flags.py')

const on = (...enabled) => ({ loading: false, enabled, flag: 'task_10b' })

test('test_loading_flag_is_not_a_decision', () => {
  assert.equal(flagDecision({ loading: true, enabled: [], flag: 'task_10b' }), 'loading')
  // Even a cached hit that already names the key waits: the first paint is the flags request.
  assert.equal(flagDecision({ loading: true, enabled: ['task_10b'], flag: 'task_10b' }), 'loading')
})

test('test_enabled_flag_renders_the_surface', () => {
  assert.equal(flagDecision(on('task_10b')), 'render')
  assert.equal(flagDecision(on('task_23', 'task_10b')), 'render')
})

test('test_missing_flag_is_off_not_a_redirect', () => {
  assert.equal(flagDecision(on()), 'off')
  assert.equal(flagDecision(on('task_23', 'task_31')), 'off')
})

test('test_unknown_flag_is_off', () => {
  // The API never reports a key outside services/flags.py FLAGS (enabled_keys filters on it),
  // so a key that is not in the registry can only ever read as off on this side too.
  assert.doesNotMatch(flagsApi, /task_9999/)
  assert.equal(flagDecision({ loading: false, enabled: [], flag: 'task_9999' }), 'off')
})

test('test_notice_names_the_surface', () => {
  // The heading comes from the nav registry the sidebar renders, so the two cannot disagree.
  assert.equal(flagSurfaceLabel('/acme/ppe/streams'), 'Streams')
  assert.equal(flagSurfaceLabel('/acme/ppe/streams/cam-1'), 'Streams')
  assert.equal(flagSurfaceLabel('/acme/ppe/qa'), 'Review & Quality')
  const labels = projectNav.flatMap((g) => g.items).filter((i) => i.flag)
  for (const item of labels) {
    assert.equal(flagSurfaceLabel(`/acme/ppe/${item.to}`), item.label)
  }

  // The notice is the shipped EmptyState, with the given label in the sentence and both actions.
  assert.match(notice, /<EmptyState/)
  assert.match(notice, /title=\{`\$\{label\} is not enabled in this workspace\.`\}/)
  assert.match(notice, /An administrator turns it on in Workspace settings\./)
  assert.match(notice, /Back to Dataset/)
  assert.match(notice, /Open workspace settings/)
  // Navigation renders as a link, not a click handler: the two actions are two <Link>s.
  assert.equal((notice.match(/<Link to=/g) ?? []).length, 2)
})

test('flag gates render in place; role gates still redirect', () => {
  const body = (name) => {
    const start = guards.indexOf(`export function ${name}(`)
    const next = guards.indexOf('\nexport function', start + 1)
    return guards.slice(start, next === -1 ? undefined : next)
  }
  // A deep link keeps the user's intent: the surface's own route renders the notice, no Navigate.
  const flagGate = body('FlagGate')
  assert.match(flagGate, /<NotEnabled/)
  assert.doesNotMatch(flagGate, /<Navigate/)
  assert.match(flagGate, /flagDecision\(/)
  // The role gates are a different question and keep their redirect.
  for (const gate of ['Gate', 'PermGate', 'SuperAdminGate']) {
    assert.match(body(gate), /<Navigate/, `${gate} must still redirect`)
  }
})
