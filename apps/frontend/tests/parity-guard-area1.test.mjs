// Parity guard, area 1: workspace, projects and first run.
// Pins the HAVE rows 1-F2.1, 1-F3.2, 1-F3.3, 1-F6.1 and 1-F6.2 in the source that renders them.
// Runs with the built-in Node test runner: node --test tests/parity-guard-area1.test.mjs  (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { projectNav } from '../src/lib/nav.ts'

const source = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const homeSrc = source('../src/features/workspace/Home.tsx')
const projectRoutes = source('../src/routes/project/index.tsx')
const boardSrc = source('../src/features/project/AnnotateBoard.tsx')
/** The four board columns, read from the `COLS` literal that renders them. */
const boardColumnIds = [...boardSrc.matchAll(/\{\s*id: '([a-z]+)',\s*title:/g)].map((m) => m[1])

test('the project nav keeps the lifecycle order', () => {
  const labels = projectNav.map((g) => g.label)
  for (const label of ['DATA', 'LABEL', 'MODELS', 'DEPLOY', 'SETTINGS']) {
    assert.ok(labels.includes(label), `1-F3.2: the project sidebar needs a ${label} group`)
  }
  const at = (label) => labels.indexOf(label)
  assert.ok(at('DATA') < at('LABEL'), '1-F3.2: DATA comes before LABEL')
  assert.ok(at('LABEL') < at('MODELS'), '1-F3.2: LABEL comes before MODELS')
  // STUDIO is deliberately not pinned here: the wave-E IA pass (T-470+) may move it into Insights.
  assert.ok(at('MODELS') < at('DEPLOY'), '1-F3.2: MODELS comes before DEPLOY')
  assert.ok(at('DEPLOY') < at('SETTINGS'), '1-F3.2: DEPLOY comes before SETTINGS')
  assert.equal(labels.at(-1), 'SETTINGS', '1-F3.2: SETTINGS is the last project group')
})

test('creating a project lands on upload, and a returning visit lands on browse', () => {
  assert.match(homeSrc, /nav\(projectPath\(ws, p\.slug, 'upload'\)\)/,
    '1-F2.1: Create must navigate straight to the project upload page')
  assert.match(projectRoutes, /<Navigate to="browse" replace \/>/,
    '1-F3.2: opening a project again lands on its dataset, not on a blank index')
})

test('home renders folders then projects, and a designed empty state', () => {
  const foldersAt = homeSrc.indexOf('folders.data?.map(')
  const projectsAt = homeSrc.indexOf('list.map((p) =>')
  assert.ok(foldersAt > -1 && projectsAt > -1, '1-F6.1: Home must render both folders and project cards')
  assert.ok(foldersAt < projectsAt, '1-F6.1: folders render above the project grid')
  assert.ok(homeSrc.includes('No projects yet.'), '1-F6.2: a brand-new workspace gets a designed empty state')
  assert.ok(homeSrc.includes('No projects match.'), '1-F6.2: an empty search or filter says why the grid is bare')
  assert.match(homeSrc, /Create your first project/,
    '1-F6.2: the empty state carries the create action')
})

test('the annotate board keeps four columns in pipeline order', () => {
  assert.deepEqual(boardColumnIds, ['unassigned', 'annotating', 'review', 'done'],
    '1-F3.3: Unassigned / Annotating / Review / Dataset, in that order')
})
