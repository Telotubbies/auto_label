// Stage tabs (T-479): Versions, Health and Streams open inside their stage, never as siblings.
// Runs with the built-in Node test runner: node --test tests/stage-tabs.test.mjs  (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { LEGACY_TAB_PATHS, resolveTab, STAGE_TABS, tabHref, tabsFor } from '../src/lib/nav/project/stages.ts'

const source = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const tabsSrc = source('../src/components/shell/StageTabs.tsx')
const datasetStageSrc = source('../src/features/project/DatasetStage.tsx')
const deployStageSrc = source('../src/features/project/DeployStage.tsx')
const projectRoutes = source('../src/routes/project/index.tsx')
const dataRoutes = source('../src/routes/project/data.routes.tsx')
const deployRoutes = source('../src/routes/project/deploy.routes.tsx')
const modelRoutes = source('../src/routes/project/models.routes.tsx')

const perms = (...granted) => {
  const set = new Set(granted)
  return (p) => set.has(p)
}
const ids = (tabs) => tabs.map((t) => t.id)

test('test_tab_defaults_and_round_trip', () => {
  assert.equal(resolveTab('dataset', ''), 'images')
  assert.equal(resolveTab('dataset', null), 'images')
  assert.equal(resolveTab('dataset', 'versions'), 'versions')
  // An unknown tab falls back to the first one and says nothing.
  assert.equal(resolveTab('dataset', 'report'), 'images')
  assert.equal(tabHref('dataset', 'versions'), '?tab=versions')
  assert.equal(resolveTab('deploy', undefined), 'test')
  assert.equal(tabHref('deploy', 'streams'), '?tab=streams')
})

test('test_legacy_paths_map_to_tabs', () => {
  assert.deepEqual(LEGACY_TAB_PATHS, {
    versions: 'dataset?tab=versions',
    streams: 'deploy?tab=streams',
    'model-insights': 'models',
  })
  // The siblings stay reachable as redirects, so an old link lands on the same screen.
  assert.match(dataRoutes, /to="\.\.\/dataset\?tab=versions"/, 'versions must redirect into the dataset tab')
  assert.match(deployRoutes, /to="\.\.\/deploy\?tab=streams"/, 'streams must redirect into the deploy tab')
  assert.match(dataRoutes, /to="\.\.\/models"/, 'model-insights must redirect to models')
})

test('test_a_stage_without_tabs_renders_none', () => {
  assert.deepEqual(tabsFor('train'), [])
  assert.deepEqual(tabsFor('models'), [])
  // Train mounts the page directly: a one-item tablist is noise.
  assert.match(modelRoutes, /path="train" element=\{<PermGate perm="project\.train"><Train \/><\/PermGate>\}/)
  assert.equal(/StageTabs/.test(modelRoutes), false, 'Train must not host a tab row')
  assert.equal(datasetStageSrc.includes('train'), false)
})

test('test_a_role_without_the_permission_loses_the_tab', () => {
  const labeler = perms('project.read', 'project.annotate', 'project.classes', 'project.infer')
  assert.deepEqual(ids(tabsFor('dataset', labeler)), ['images'])
  const exporter = perms('project.read', 'project.export')
  assert.deepEqual(ids(tabsFor('dataset', exporter)), ['images', 'versions'])
  const reviewer = perms('project.read', 'project.review')
  assert.deepEqual(ids(tabsFor('dataset', reviewer)), ['images', 'health'])
  // Deploy collapses without project.models; Streams needs its own permission and flag.
  assert.deepEqual(ids(tabsFor('deploy', labeler)), [])
  assert.deepEqual(ids(tabsFor('deploy', perms('project.models'))), ['test'])
  assert.deepEqual(ids(tabsFor('deploy', perms('project.models', 'project.streams'))), ['test'])
  assert.deepEqual(
    ids(tabsFor('deploy', perms('project.models', 'project.streams'), new Set(['task_10b']))),
    ['test', 'streams'],
  )
})

test('test_tab_row_is_a_real_tablist', () => {
  assert.match(tabsSrc, /role="tablist"/)
  assert.match(tabsSrc, /role="tab"/)
  assert.match(tabsSrc, /aria-selected/)
  assert.match(tabsSrc, /ArrowLeft/)
  assert.match(tabsSrc, /ArrowRight/)
  assert.match(tabsSrc, /replace: true/, 'a tab change replaces the history entry')
  assert.match(tabsSrc, /tabIndex=\{/, 'roving tabindex')
  assert.match(tabsSrc, /\.focus\(\)/, 'focus stays on the active tab after a change')
  assert.match(tabsSrc, /role="tabpanel"/)
})

test('test_no_child_page_is_edited', () => {
  // The hosts compose the existing pages; they never copy their internals.
  assert.match(datasetStageSrc, /import Dataset from '\.\/Dataset'/)
  assert.match(datasetStageSrc, /lazy\(\(\) => import\('\.\/DatasetHealth'\)\.then/)
  assert.match(datasetStageSrc, /lazy\(\(\) => import\('\.\/Versions'\)\)/)
  assert.match(deployStageSrc, /lazy\(\(\) => import\('\.\/Deploy'\)\)/)
  assert.match(deployStageSrc, /lazy\(\(\) => import\('@\/features\/streams\/Streams'\)\)/)
  for (const host of [datasetStageSrc, deployStageSrc]) {
    assert.equal(/api\.|useQuery|PageHeader/.test(host), false, 'a host must not reimplement a child page')
  }
  // Each host keeps the gate its sibling route had.
  assert.match(datasetStageSrc, /<PermGate perm="project\.export"><Versions \/><\/PermGate>/)
  assert.match(datasetStageSrc, /<PermGate perm="project\.review"><DatasetHealth \/><\/PermGate>/)
  assert.match(deployStageSrc, /<PermGate perm="project\.models"><Deploy \/><\/PermGate>/)
  assert.match(deployStageSrc, /<PermGate perm="project\.streams"><Streams \/><\/PermGate>/)
  // Dataset and Deploy are the only tab-hosted stages.
  assert.deepEqual(Object.keys(STAGE_TABS).sort(), ['dataset', 'deploy'])
  assert.match(projectRoutes, /<DatasetStage \/>/)
  assert.match(deployRoutes, /<DeployStage \/>/)
})
