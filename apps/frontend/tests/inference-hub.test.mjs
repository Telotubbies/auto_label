// T-1000: the Inference hub shell — rail visibility, the admin/flag gate and the URL-owned tab.
// Runs with the built-in Node test runner: node --test tests/inference-hub.test.mjs (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { visibleWorkspaceNav } from '../src/lib/nav.ts'
import { INFERENCE_TAB_LABELS, INFERENCE_TABS, tabFrom } from '../src/features/inference/tabs.ts'

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

// T-1005: the calculator panel is the calculator (form, results, assumptions), not a placeholder card.
test('test_calculator_tab_mounts_the_calculator', () => {
  const hub = readFileSync(new URL('../src/features/inference/InferenceHub.tsx', import.meta.url), 'utf8')
  assert.match(hub, /tab === 'calculator' \? <CalculatorTab \/>/, 'the calculator tab renders CalculatorTab')
  assert.match(hub, /import CalculatorTab from '\.\/CalculatorTab'/, 'and imports it from its own module')
  assert.doesNotMatch(hub, /calculator arrives with the sizing card/, 'the placeholder sentence is gone')
})

// T-1007: the engines panel is the engines tab, and the header picker is fed by the host list.
test('test_engines_tab_mounts_the_engines_panel_with_a_real_host_picker', () => {
  const hub = readFileSync(new URL('../src/features/inference/InferenceHub.tsx', import.meta.url), 'utf8')
  assert.match(hub, /<EnginesTab/, 'the engines tab renders EnginesTab')
  assert.match(hub, /import EnginesTab from '\.\/EnginesTab'/, 'and imports it from its own module')
  assert.doesNotMatch(hub, /No engine catalogue yet\./, 'the placeholder sentence is gone')
  assert.match(hub, /inferenceApi\.hosts\(/, 'the picker reads GET /hosts')
})

// T-1012: the models panel is the models tab, fed by the same header host picker.
test('test_models_tab_mounts_the_models_panel', () => {
  const hub = readFileSync(new URL('../src/features/inference/InferenceHub.tsx', import.meta.url), 'utf8')
  assert.match(hub, /<ModelsTab/, 'the models tab renders ModelsTab')
  assert.match(hub, /import ModelsTab from '\.\/ModelsTab'/, 'and imports it from its own module')
  assert.doesNotMatch(hub, /No model catalogue yet\./, 'the placeholder sentence is gone')
})

// T-1015: the segmentation panel is its own module with the project picker, not a placeholder card.
test('test_segmentation_tab_mounts_the_segmentation_panel', () => {
  const hub = readFileSync(new URL('../src/features/inference/InferenceHub.tsx', import.meta.url), 'utf8')
  assert.match(hub, /<SegmentationTab/, 'the segmentation tab renders SegmentationTab')
  assert.match(hub, /import SegmentationTab from '\.\/SegmentationTab'/, 'and imports it from its own module')
  assert.doesNotMatch(hub, /PANEL_EMPTY/, 'the placeholder map is gone')
})

// ---------- T-1021: the UI QA guards ------------------------------------------
// Two guarantees the QA pass can never verify by eye alone, so they are checked here as well as in
// docs/research/inference-hub/ui-qa.md. Source-checked like the other design guards, because the
// suite has no DOM renderer.

const inferenceTree = readdirSync(new URL('../src/features/inference/', import.meta.url), { recursive: true })
  .map((f) => f.replaceAll('\\', '/'))
  .filter((f) => /\.(ts|tsx)$/.test(f))
const inferenceSrc = (rel) => readFileSync(new URL(`../src/features/inference/${rel}`, import.meta.url), 'utf8')

/** The three things the glass system forbids in this tree: a literal colour, an arbitrary size, an inline size. */
const violations = (text) => [
  ...(text.match(/#[0-9a-fA-F]{3,8}\b/g) ?? []),
  ...(text.match(/text-\[[^\]]+\]/g) ?? []),
  ...(text.match(/style=\{\{[^}]*fontSize/g) ?? []),
]

test('test_no_hex_or_arbitrary_font_size_in_the_inference_tree', () => {
  assert.ok(inferenceTree.length >= 15, 'the inference tree was read')
  for (const file of inferenceTree) {
    assert.deepEqual(violations(inferenceSrc(file)), [],
      `features/inference/${file} carries a literal colour, an arbitrary font size or an inline font size; `
      + 'the shipped roles and text-sm / text-xs are the whole scale')
  }
  // A guard that cannot fail is not a guard: the scanner itself has to catch all three.
  assert.deepEqual(
    violations("const c = '#3b6cf6'\n<p className=\"text-[13px]\" style={{ fontSize: 11 }}>x</p>"),
    ['#3b6cf6', 'text-[13px]', 'style={{ fontSize'],
    'the scanner detects a hex literal, an arbitrary size and an inline font size')
})

test('test_every_tab_id_has_copy', () => {
  // One map owns every tab's title (the tab bar is the panel heading). An id without copy, or
  // without its panel module, fails here instead of shipping as a blank tab.
  assert.deepEqual([...INFERENCE_TABS].sort(), Object.keys(INFERENCE_TAB_LABELS).sort(),
    'the copy map lists exactly the tab ids')
  for (const id of INFERENCE_TABS) {
    assert.equal(typeof INFERENCE_TAB_LABELS[id], 'string', `${id} has a label`)
    assert.ok(INFERENCE_TAB_LABELS[id].trim().length > 0, `${id} has copy, not an empty string`)
    const panel = `${id[0].toUpperCase()}${id.slice(1)}Tab.tsx`
    assert.ok(inferenceTree.includes(panel), `${id} has its panel module, ${panel}`)
  }
  const hub = inferenceSrc('InferenceHub.tsx')
  assert.match(hub, /INFERENCE_TAB_LABELS\[id\]/, 'the tab bar and the 375 px select read the map')
  assert.doesNotMatch(hub, /label: '(Engines|Models|Calculator|Segmentation)'/, 'no tab label is inlined in the hub')
  assert.doesNotMatch(hub, /<option key=\{id\} value=\{id\}>[A-Z]/, 'no tab label is inlined in the select')
})
