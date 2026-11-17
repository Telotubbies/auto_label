// T-478: the project rail reads top to bottom like the work does — three purpose groups holding
// five numbered stages plus their unnumbered destinations, with counts, state dots and locks.
// Runs with the built-in Node test runner: node --test tests/stage-rail.test.mjs  (from apps/frontend)
//
// The suite has no DOM renderer, so a rendered contract is pinned twice: the manifest is executed
// directly (Node type stripping) and the component's render path is source-checked, like the other
// shell guards in this folder.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { GROUPS, SECONDARY, STAGES, stageCount, stageFacts } from '../src/lib/nav/project/stages.ts'
import { visibleStageGroups } from '../src/lib/nav/visibility.ts'

const source = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const sourceTree = (dir) => readdirSync(new URL(`${dir}/`, import.meta.url), { recursive: true })
  .filter((f) => /\.(ts|tsx)$/.test(f))
  .map((f) => source(`${dir}/${f.replaceAll('\\', '/')}`))
  .join('\n')

const panelSrc = source('../src/components/shell/ProjectPanel.tsx')
const itemSrc = source('../src/components/shell/StageItem.tsx')
const groupSrc = source('../src/components/shell/RailGroup.tsx')
const shellSrc = sourceTree('../src/components/shell')
const layoutSrc = source('../src/features/project/ProjectLayout.tsx')

const perms = (...granted) => {
  const set = new Set(granted)
  return (p) => set.has(p)
}
const MANAGER = perms('project.read', 'project.annotate', 'project.review', 'project.upload', 'project.export',
  'project.classes', 'project.train', 'project.models', 'project.infer', 'project.settings', 'project.streams')
const LABELER = perms('project.read', 'project.annotate', 'project.classes', 'project.infer')

const project = (over = {}) => ({
  slug: 'ppe', images: 40, models: 0, classes: [], statusCounts: {}, ...over,
})
const version = (number) => ({
  id: `v${number}`, number, name: `v${number}`, settings: {}, status: 'ready', stats: {}, created: number,
  job: null, exports: {},
})
const facts = (over = {}, versions = [], jobs = []) => stageFacts({ project: project(over), versions, jobs })
const rowsOf = (groups) => groups.flatMap((g) => g.items)

test('test_stage_dot_always_ships_a_label', () => {
  // The dot is decoration: the row's own text carries the label, the state word and the count, so a
  // screenshot, a high-contrast theme and a screen reader all read the same state. That text is also
  // the accessible name, in reading order (WCAG 2.5.3, T-1107): no aria-label reorders the row.
  assert.match(itemSrc, /aria-hidden/)
  assert.match(itemSrc, /\{row\.label\}/, 'the label is visible text, not an invented name')
  assert.doesNotMatch(itemSrc, /aria-label=\{/, 'no row renames itself over the row the eye reads')
  assert.match(itemSrc, /stageWord\(/, 'the state word comes from the shared vocabulary')
  // The lock keeps its "request access" meaning as a description, never as a rename.
  assert.match(itemSrc, /aria-describedby=\{descId\}/)
  assert.match(itemSrc, /Locked for your role/)
})

test('test_groups_render_in_order_and_are_not_all_caps', () => {
  assert.deepEqual(GROUPS.map((g) => g.label), ['Data', 'Models', 'Deploy'])
  for (const g of GROUPS) {
    const sentence = g.label[0].toUpperCase() + g.label.slice(1).toLowerCase()
    assert.equal(g.label, sentence, `${g.label} must stay sentence case`)
  }
  // The panel renders the manifest's groups in manifest order, with the rows inside their group.
  assert.match(panelSrc, /groups\.map\(/)
  assert.match(panelSrc, /<RailGroup key=\{g\.id\}/)
  assert.match(panelSrc, /g\.items\.map\(/)
  assert.match(groupSrc, /\{label\}/)
})

test('test_collapsing_keeps_the_rows_mounted', () => {
  // A collapsed group hides its list; the destinations stay in the DOM behind the header button,
  // and the header keeps a summary so collapsing never hides an alert.
  assert.match(groupSrc, /aria-expanded=\{expanded\}/)
  assert.match(groupSrc, /aria-controls=\{listId\}/)
  assert.match(groupSrc, /<ul id=\{listId\} hidden=\{!expanded\}/)
  assert.match(groupSrc, /summary/)
  assert.match(groupSrc, /\{children\}/, 'the rows are children of the hidden list, not filtered out')
})

test('test_the_active_group_cannot_collapse_shut', () => {
  assert.match(groupSrc, /const expanded = open \|\| holdsActive/,
    'a group holding the current route is always open')
  assert.match(panelSrc, /holdsActive=\{/, 'the panel tells the group where the current page is')
  assert.match(panelSrc, /activeId/, 'one row is active, and its group stays open')
})

test('test_locked_stage_is_dimmed_not_hidden', () => {
  const rows = rowsOf(visibleStageGroups(LABELER, 'labeler'))
  // Every numbered stage survives for a labeler: the two they cannot act on are dimmed, not dropped.
  for (const id of STAGES.map((s) => s.id)) {
    assert.ok(rows.some((r) => r.id === id), `${id} must still render for a labeler`)
  }
  assert.deepEqual(rows.filter((r) => r.locked).map((r) => r.id), ['train', 'deploy'])
  assert.deepEqual(rowsOf(visibleStageGroups(MANAGER, 'manager')).filter((r) => r.locked), [])

  assert.match(itemSrc, /aria-disabled="true"/, 'a locked row is announced, focusable, never a dead link')
  assert.match(itemSrc, /setAsk\(true\)/, 'clicking it opens the request-access sheet')
  assert.match(itemSrc, /opacity-/, 'a locked row is dimmed')
  assert.match(itemSrc, /<Modal open=\{ask\}/, 'the sheet is a sheet, not a silent redirect')
})

test('test_numbering_is_visible_and_ordered', () => {
  const numbered = rowsOf(visibleStageGroups(MANAGER, 'manager')).filter((r) => r.number !== undefined)
  assert.deepEqual(numbered.map((r) => [r.number, r.label]), [
    [1, 'Upload'], [2, 'Annotate'], [3, 'Dataset'], [4, 'Train'], [5, 'Deploy'],
  ])
  // Only the five stages are numbered; the secondary row above the rule never is.
  assert.deepEqual(SECONDARY.filter((i) => 'number' in i), [])
  assert.match(itemSrc, /\{row\.number\}/)
})

test('test_counts_use_tabular_figures', () => {
  // A count that changes while the member works must not shift the pill sideways.
  assert.match(itemSrc, /tabular-nums/)
  assert.match(itemSrc, /stageCount\(/)
})

test('test_no_train_button_in_the_chrome', () => {
  assert.doesNotMatch(shellSrc, /Train Model/, 'the global Train button left the chrome')
  // The v3 rail renders no portal at all; the v2 buttons exist only for a workspace with the flag off.
  assert.match(layoutSrc, /\{!uiV3 && slot && createPortal\(/)
})

// --- the card's acceptance states above the UX flow ----------------------------------------------
test('test_unknown_numbers_never_render_as_zero', () => {
  // While the facts load, each row keeps its height with a skeleton count; a failed call offers a
  // Retry and still paints the rail — never a fake zero.
  assert.match(itemSrc, /animate-pulse/)
  assert.match(itemSrc, /\bpending\s*\?/, 'a number the API has not answered for yet renders as a skeleton')
  assert.match(panelSrc, /Retry/)
  assert.match(panelSrc, /onClick=\{retry\}/)
  const unknown = stageFacts({ project: project({ statusCounts: undefined }) })
  assert.equal(stageCount(unknown, 'annotate'), null)
  assert.equal(stageCount(unknown, 'dataset'), null)
  assert.equal(stageCount(unknown, 'train'), null)
  // A project with no deployment record shows a dash, not a zero it made up.
  assert.equal(stageCount(facts({ statusCounts: { done: 24 } }, [version(1)]), 'deploy'), null)
})

test('test_the_compact_strip_renders_the_same_groups', () => {
  // Below 1024 px the panel collapses to the strip, which reads the same model: one builder, so a
  // role never sees a different IA by width.
  assert.match(layoutSrc, /useProjectRail\(project\)/)
  assert.match(layoutSrc, /rail\.groups\.map\(/)
  assert.match(layoutSrc, /<StageItem row=\{row\}/, 'the strip renders the same numbered rows')
  assert.match(layoutSrc, /rail\.activeId/)
})

test('test_flag_off_keeps_the_v2_panel', () => {
  assert.match(panelSrc, /useFlag\('task_470'\)/, 'the rail reads the ui_v3 flag')
  assert.match(panelSrc, /projectNavGroups\(/, 'flag off renders the shipped grouped panel')
  assert.match(panelSrc, /visibleStageGroups\(/, 'flag on renders the stage manifest')
})
