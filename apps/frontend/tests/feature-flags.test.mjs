// I13 regression: feature flags must gate the surfaces they name, in the nav and in the router.
//   node --test tests/feature-flags.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { projectNav, visibleProjectNav } from '../src/lib/nav.ts'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8')

// Routes and their guards live in `src/routes/`, one file per feature; read the whole tree.
const readRoutes = () => readdirSync(new URL('../src/routes/', import.meta.url), { recursive: true })
  .map((f) => f.replaceAll('\\', '/'))
  .filter((f) => /\.(ts|tsx)$/.test(f))
  .map((f) => read(`../src/routes/${f}`))
  .join('\n')

const MANAGER = (p) => [
  'project.read', 'project.annotate', 'project.review', 'project.upload', 'project.export',
  'project.classes', 'project.train', 'project.models', 'project.infer', 'project.settings',
  'project.streams',
].includes(p)

const targets = (groups) => groups.flatMap((g) => g.items.map((i) => i.to))

test('the gated surfaces declare a flag', () => {
  const flags = Object.fromEntries(projectNav.flatMap((g) => g.items).map((i) => [i.to, i.flag]))
  assert.equal(flags.streams, 'task_10b')
  assert.equal(flags.qa, 'task_23')
  assert.equal(flags.lineage, 'task_20c')
  assert.equal(flags.dashboards, 'task_20c')
  assert.equal(flags['stream-analytics'], 'task_20c')
})

test('surfaces whose flag is off disappear from the project nav', () => {
  const off = targets(visibleProjectNav(MANAGER, 'manager', new Set()))
  for (const to of ['streams', 'qa', 'lineage', 'dashboards', 'stream-analytics']) {
    assert.ok(!off.includes(to), `${to} must be hidden while its flag is off`)
  }
  assert.ok(off.includes('browse'), 'ungated surfaces must stay visible')
})

test('turning a surface flag on restores exactly that surface', () => {
  const on = targets(visibleProjectNav(MANAGER, 'manager', new Set(['task_10b'])))
  assert.ok(on.includes('streams'))
  assert.ok(!on.includes('qa'))
})

test('the route registry gates every flagged route with the workspace flag', () => {
  const routes = readRoutes()
  assert.match(routes, /function FlagGate/)
  for (const flag of ['task_10b', 'task_20c', 'task_22', 'task_23']) {
    assert.match(routes, new RegExp(`<FlagGate flag="${flag}"`), `${flag} must wrap its routes`)  }
})
