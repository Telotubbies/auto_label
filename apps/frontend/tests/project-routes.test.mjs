// T-474: the /p/ project prefix, its one path builder and the legacy URL redirects.
// Runs with the built-in Node test runner: node --test tests/project-routes.test.mjs  (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { editorPath, legacyProjectPath, PROJECT_ROUTE_MATCH, projectPath, stageTab } from '../src/lib/routes.ts'
import { RESERVED_WORKSPACE_SEGMENTS } from '../src/lib/nav.ts'

const source = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const routeSrc = source('../src/routes/project/index.tsx') + source('../src/routes/project/LegacyProject.tsx')

test('project path shapes', () => {
  assert.equal(projectPath('w', 'ppe'), '/w/p/ppe')
  assert.equal(projectPath('w', 'ppe', 'annotate'), '/w/p/ppe/annotate')
  assert.equal(stageTab('w', 'ppe', 'dataset', 'versions'), '/w/p/ppe/dataset?tab=versions')
  // The editor keeps the slice in the query, so the same image opens on the same filter.
  assert.equal(editorPath('w', 'ppe', 'img1', '?status=done'), '/w/p/ppe/annotate/img1?status=done')
  assert.equal(editorPath('w', 'ppe', 'img1'), '/w/p/ppe/annotate/img1')
})

test('legacy segments redirect', () => {
  assert.equal(legacyProjectPath('browse'), 'dataset')
  assert.equal(legacyProjectPath('versions'), 'dataset?tab=versions')
  assert.equal(legacyProjectPath('model-insights'), 'train?tab=models')
  assert.equal(legacyProjectPath('streams'), 'deploy?tab=streams')
  assert.equal(legacyProjectPath('index'), '')
  assert.equal(legacyProjectPath(''), '')
  // The redirects that already shipped stay exactly where they were.
  assert.equal(legacyProjectPath('access'), 'settings?tab=access')
  assert.equal(legacyProjectPath('analytics'), 'insights?tab=health')
  // An unknown segment is not guessed at: the shell renders not-found instead.
  assert.equal(legacyProjectPath('nope'), null)
  assert.equal(legacyProjectPath('constructor'), null)
})

test('screens that did not move keep their old URL alive', () => {
  // T-474 moved the prefix only: the shipped nav still links `/:ws/:project/<screen>`.
  for (const screen of ['upload', 'train', 'deploy', 'settings', 'annotate', 'models']) {
    assert.equal(legacyProjectPath(screen), screen)
  }
})

test('a project named p still resolves', () => {
  // The segment after `p/` is the project, the one before it is the prefix.
  assert.equal(projectPath('w', 'p', 'upload'), '/w/p/p/upload')
  assert.equal(RESERVED_WORKSPACE_SEGMENTS.has('p'), true)
})

test('old and new shapes both exist', () => {
  assert.match(routeSrc, /path="p\/:project"/, 'the new prefix has no route')
  assert.match(routeSrc, /path=":project\/\*"/, 'the old project shape has no branch')
  assert.match(routeSrc, /<Navigate[^>]*replace/, 'the old branch must replace, so Back does not bounce')
  // One child list, mounted once: a second copy drifts the first time a page is added.
  assert.match(routeSrc, /const PROJECT_CHILDREN/, 'the child routes must be built once')
})

test('the shell matches the /p/ project route', () => {
  // TopBar builds the breadcrumb from this match; the others hide workspace-only chrome.
  assert.equal(PROJECT_ROUTE_MATCH, '/:ws/p/:project/*')
  for (const file of ['TopBar', 'AppLayout', 'AppSidebar', 'JobTray']) {
    const src = source(`../src/components/shell/${file}.tsx`)
    assert.match(src, /PROJECT_ROUTE_MATCH/, `${file} still matches the pre-T-474 project shape`)
  }
})

test('query string survives the editor redirect', () => {
  // status / batch / review decide which image slice the editor opens on.
  assert.match(routeSrc, /useLocation\(\)\.search/)
  assert.match(routeSrc, /editorPath\(/, 'the old editor URL must build its target through the helper')
})
