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

test('test_rail_hides_inference_from_the_lean_roles', () => {
  // T-1110 (row 14): a member now sees the hub for the Calculator alone (PLAN §12.5); the roles
  // that work around the build surfaces keep the lean rail.
  const flags = new Set(['task_inference'])
  for (const uiV3 of [true, false]) {
    for (const role of ['labeler', 'billing', 'reviewer', 'annotator']) {
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

// ---------- T-1110: the nine Important findings from the T-1021 QA pass ----------------
// Rows 1-8 and 14 of docs/research/inference-hub/ui-qa.md §4. Source-checked where the fix is
// structural (this suite has no DOM renderer, the house rule the T-1021 guards follow); the
// behaviour a source check cannot prove — no sideways scroll at 375 px, a sheet whose primary
// button is on screen, focus entering the dialog and coming back to its trigger, a real Tab key —
// is asserted in e2e/inference-hub.spec.ts.
const ui = readFileSync(new URL('../src/components/ui.tsx', import.meta.url), 'utf8')

test('test_tabs_are_a_tablist_with_a_selected_tab', () => {
  // Row 4: the bar was a row of buttons with no role and no aria-selected, so a screen reader
  // announced four unrelated buttons and colour was the only signal of the current one.
  assert.match(ui, /role="tablist"/, 'the bar is a tablist')
  assert.match(ui, /role="tab"/, 'each tab is a tab')
  assert.match(ui, /aria-selected=\{active === t\.id\}/, 'the current tab is announced, not just coloured')
  assert.match(ui, /tabIndex=\{active === t\.id \? 0 : -1\}/, 'one tab stop for the whole bar (roving tabindex)')
  for (const key of ['ArrowRight', 'ArrowLeft', 'Home', 'End']) {
    assert.ok(ui.includes(key), `the tablist answers ${key}, as the ARIA tabs pattern requires`)
  }
})

test('test_calculator_columns_can_shrink_below_their_content', () => {
  // Row 1: at 375 px the results table stretched its grid track, so the whole panel scrolled
  // sideways. Both grid children must be allowed to be narrower than their widest child; the
  // table then keeps its own overflow-x-auto instead of widening the page.
  const calc = inferenceSrc('CalculatorTab.tsx')
  assert.match(calc, /<div className="grid gap-4 lg:grid-cols-2">/, 'the two-column calculator grid is unchanged')
  assert.match(calc, /<Card className="min-w-0 space-y-3 p-4 sm:p-6">/, 'the form column may shrink')
  assert.match(calc, /<div className="min-w-0 space-y-4">/, 'the results column may shrink')
  assert.match(calc, /<div className="overflow-x-auto">/, 'the results table keeps its own horizontal scroller')
})

test('test_engine_sheet_keeps_its_footer_on_a_375_viewport', () => {
  // Row 2: the sheet asked for a full viewport height *inside* a dialog that already spends 4rem on
  // margins and a title block, so the acknowledgement and Install fell below the fold. It is now
  // capped inside that chrome, with a scrolling body and a footer that stays put.
  const sheet = inferenceSrc('EngineSheet.tsx')
  assert.doesNotMatch(sheet, /min-h-\[calc\(100dvh-4rem\)\]/, 'the sheet no longer overflows its own dialog')
  assert.match(sheet, /className="flex max-h-\[calc\(100dvh-10rem\)\] flex-col"/,
    'the cap subtracts the dialog chrome the sheet cannot see')
  assert.match(sheet, /className="min-h-0 flex-1[^"]*overflow-y-auto"/, 'the plan body scrolls, not the footer')
  assert.match(sheet, /I understand this installs software on \{host\.host\}/, 'the acknowledgement stays')
})

test('test_hosts_failure_says_so_and_offers_retry', () => {
  // Row 5: a failed /hosts read rendered "No host has reported", which is the empty state and a
  // lie. The picker now names the failure and offers the retry the panel already has.
  const hub = inferenceSrc('InferenceHub.tsx')
  assert.match(hub, /hosts\.isError \? \(/, 'the picker branches on the failed read first')
  assert.match(hub, /Hosts did not load\./, 'the failed read is named as such')
  assert.match(hub, /onClick=\{\(\) => void hosts\.refetch\(\)\}/, 'and the retry is the same refetch the panels use')
  // The empty state can still exist, but only after a read that succeeded.
  assert.ok(hub.indexOf('Hosts did not load.') < hub.indexOf('No host has reported'),
    'the misleading empty state comes after the error branch, never in front of it')
})

test('test_assets_table_keeps_the_model_name_in_view_at_375', () => {
  // Row 7: the assets table was the one table at 375 px without a sticky first column, so the
  // model name scrolled away from the sizes it belongs to.
  const panel = inferenceSrc('AssetsPanel.tsx')
  assert.match(panel, /<th scope="col" className="sticky left-0/, 'the header cell is pinned')
  assert.match(panel, /<td className="sticky left-0 bg-card px-3 py-2\.5 font-medium">/, 'the model cell is pinned')
})

test('test_a_member_reaches_the_calculator_and_nothing_else', () => {
  // Row 14 / PLAN §12.5: any workspace member may open the read-only Calculator, and the other
  // three surfaces stay admin-only. The rail entry exists for a member, and the hub gives that
  // member the Calculator alone: no host picker (it reads the admin-only /hosts) and no tab that
  // would answer 403.
  const flags = new Set(['task_inference'])
  for (const uiV3 of [true, false]) {
    assert.equal(inference(visibleWorkspaceNav('member', false, null, uiV3, flags))?.label, 'Inference',
      `the ${uiV3 ? 'v3' : 'v2'} rail must carry the hub for a member with the flag on`)
  }
  const hub = inferenceSrc('InferenceHub.tsx')
  assert.match(hub, /const staff = role === 'owner' \|\| role === 'admin'/, 'the hub knows which audience it serves')
  assert.match(hub, /enabled: !!ws && staff,/, 'only an admin asks for the admin-only host list')
  assert.match(hub, /const tabs: readonly InferenceTab\[\] = staff \? INFERENCE_TABS : \['calculator'\]/,
    'a member sees the calculator alone')
  assert.match(hub, /const tab = staff \? tabFrom\(params\.toString\(\)\) : 'calculator'/,
    'a member always lands on the calculator, whatever ?tab= says')
  assert.match(hub, /staff && \(/, 'the host picker is admin chrome, so a member does not get it')
})
