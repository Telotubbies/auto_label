// T-475: every internal project link goes through `projectPath`, so a route prefix change is one file.
// Runs with the built-in Node test runner: node --test tests/link-paths.test.mjs  (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { backPath } from '../src/lib/routes.ts'
import { projectNav } from '../src/lib/nav.ts'
import { onboardingSteps } from '../src/features/workspace/dashboardRules.ts'

/** A hand-built project URL: the template opens with the workspace and a project slug straight after. */
const HAND_BUILT = '`/${ws}/${'

function sourceFiles(dir) {
  return readdirSync(new URL(`${dir}/`, import.meta.url), { recursive: true })
    .map((f) => f.replaceAll('\\', '/'))
    .filter((f) => /\.(ts|tsx)$/.test(f))
}

test('no hand-built project paths', () => {
  const dirs = ['../src/features', '../src/components']
  const files = dirs.flatMap((d) => sourceFiles(d).map((f) => `${d}/${f}`))
  // A broken glob would pass this test silently, so prove the tree was read.
  assert.ok(files.length > 50, `only ${files.length} source files found under src/features and src/components`)
  const offenders = files.filter((f) => readFileSync(new URL(f, import.meta.url), 'utf8').includes(HAND_BUILT))
  assert.deepEqual(offenders, [],
    `hand-built project URLs found; build them with projectPath() in lib/routes.ts:\n${offenders.join('\n')}`)
})

test('dashboard steps use the helper', () => {
  const steps = onboardingSteps({
    ws: 'acme', projects: 1, images: 0, annotations: 0, models: 0, deployments: 0, teammates: 0,
    canInvite: false, canCreateProject: true, canUpload: true, canTrain: false, canAnnotate: true,
    firstProject: 'ppe',
  })
  assert.equal(steps.find((s) => s.key === 'images').to, '/acme/p/ppe/upload')
  assert.equal(steps.find((s) => s.key === 'labels').to, '/acme/p/ppe/annotate')
})

test('editor back link matches mode', () => {
  assert.equal(backPath('acme', 'ppe', { review: true }), '/acme/p/ppe/annotate')
  assert.equal(backPath('acme', 'ppe', { review: false }), '/acme/p/ppe/dataset')
})

test('nav entries stay relative', () => {
  const items = projectNav.flatMap((g) => g.items)
  assert.ok(items.some((i) => i.to === 'upload'), 'the DATA group lost its upload entry')
  assert.deepEqual(items.filter((i) => i.to.startsWith('/')).map((i) => i.to), [],
    'nav entries must stay relative: one child list serves both mounted branches')
})
