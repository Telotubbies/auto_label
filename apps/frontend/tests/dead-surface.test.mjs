// T-054: the frontend exposes only what something calls. Two exports no file imports, four props no
// call site passes, one orphan CSS class, and one project-settings permission query that should be the
// shared hook. Source-checked, like the other parity guards, because the suite has no DOM renderer.
//   node --test tests/dead-surface.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'

const src = (rel) => readFileSync(new URL(`../src/${rel}`, import.meta.url), 'utf8')
/** Every TypeScript source under src/, so a symbol cannot hide in a feature file. */
const sourceTree = readdirSync(new URL('../src/', import.meta.url), { recursive: true })
  .map((f) => f.replaceAll('\\', '/'))
  .filter((f) => /\.(ts|tsx)$/.test(f))
const allSources = sourceTree.map((f) => src(f)).join('\n')

const ui = src('components/ui.tsx')
const widgetModel = src('features/dashboards/widgetModel.ts')
const settings = src('features/project/ProjectSettings.tsx')
const css = src('index.css')

test('test_kebab_and_max_widgets_stay_deleted', () => {
  assert.doesNotMatch(ui, /export function Kebab\b/,
    'Kebab had no caller; a second menu variant invites a second style')
  assert.doesNotMatch(widgetModel, /\bMAX_WIDGETS\b/,
    'the widget cap is enforced by the backend; a client copy only drifts')
  assert.doesNotMatch(allSources, /\bKebab\b/, 'nothing imports Kebab')
  assert.doesNotMatch(allSources, /\bMAX_WIDGETS\b/, 'nothing imports MAX_WIDGETS')
})

test('test_the_orphan_truncate_th_class_stays_deleted', () => {
  assert.doesNotMatch(css, /\.truncate-th\b/, 'no className used the rule')
  assert.doesNotMatch(allSources, /truncate-th/, 'nothing asks for the class')
})

test('test_no_component_passes_the_removed_props', () => {
  assert.doesNotMatch(allSources, /innerClassName/, 'SectionShell takes className only')
  assert.doesNotMatch(allSources, /initialTab/, 'ProjectSettings reads ?tab= only')
})

test('test_project_settings_uses_the_shared_permission_hook', () => {
  assert.match(settings, /import \{ useProjectPermissions \} from '@\/lib\/perms'/)
  assert.match(settings, /useProjectPermissions\(ws, project\.slug\)/)
  assert.doesNotMatch(settings, /api\.permissions/, 'one shared hook, not a second query')
  assert.doesNotMatch(settings, /queryKey: \['permissions'/,
    'the hand-rolled permission query is gone')
  assert.match(settings, /manager = admin \|\| isManager/,
    'a workspace admin still manages every project; otherwise the project role decides')
  assert.match(settings, /if \(!admin && loading\)/,
    'a non-admin sees the loading state until /permissions answers, then the manager decision')
})
