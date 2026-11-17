// T-1000: the Inference hub shell — rail visibility, the admin/flag gate and the URL-owned tab.
// Runs with the built-in Node test runner: node --test tests/inference-hub.test.mjs (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { visibleWorkspaceNav } from '../src/lib/nav.ts'
import { tabFrom } from '../src/features/inference/tabs.ts'

const flat = (groups) => groups.flatMap((g) => g.items)
const inference = (groups) => flat(groups).find((i) => i.to === 'inference')

test('test_rail_shows_inference_for_admin_with_the_flag', () => {
  const flags = new Set(['task_inference'])
  for (const uiV3 of [true, false]) {
    assert.equal(inference(visibleWorkspaceNav('admin', false, null, uiV3, flags))?.label, 'Inference',
      `the ${uiV3 ? 'v3' : 'v2'} rail must carry the hub for an admin with the flag on`)
  }
  // The owner is the same audience as the admin, and the entry is workspace-level.
  assert.ok(inference(visibleWorkspaceNav('owner', false, null, true, flags)))
})

test('test_rail_hides_inference_without_the_flag', () => {
  for (const uiV3 of [true, false]) {
    assert.equal(inference(visibleWorkspaceNav('admin', false, null, uiV3, new Set())), undefined,
      `the ${uiV3 ? 'v3' : 'v2'} rail must hide the hub while the flag is off`)
  }
})

test('test_rail_hides_inference_from_a_member', () => {
  const flags = new Set(['task_inference'])
  for (const uiV3 of [true, false]) {
    for (const role of ['member', 'labeler', 'billing', 'reviewer', 'annotator']) {
      assert.equal(inference(visibleWorkspaceNav(role, false, null, uiV3, flags)), undefined,
        `${role} must never see the hub, even with the flag on`)
    }
  }
})

test('test_tab_defaults_to_engines_and_survives_a_reload', () => {
  assert.equal(tabFrom(''), 'engines')
  assert.equal(tabFrom('?tab=models'), 'models')
  assert.equal(tabFrom('?tab=calculator'), 'calculator')
  assert.equal(tabFrom('?tab=segmentation'), 'segmentation')
  assert.equal(tabFrom('?tab=not-a-tab'), 'engines')
  assert.equal(tabFrom('?other=1'), 'engines')
})
