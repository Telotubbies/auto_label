// Regression test for I10 residual: a project reviewer (explicit ProjectMember role="reviewer")
// was shown manager-only controls whose API routes answer 403. The API requires:
//   POST   /train                -> admin   (project.train is manager-only)
//   POST   /models/{id}/export   -> admin
//   DELETE /models/{id}          -> admin
//   PUT/POST deployment + rollback -> admin
//   POST   /jobs/{id}/cancel     -> reviewer (project.review also includes reviewers)
// so the UI must gate each control on the same capability the server enforces.
//
//   node --test tests/models-permissions.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8')
const models = read('../src/features/project/Models.tsx')
const workspace = read('../src/features/workspace/WorkspacePages.tsx')

/** The last `chars` characters before `needle` — i.e. the gate guarding that control. */
function gateBefore(src, needle, chars = 240) {
  const i = src.indexOf(needle)
  assert.ok(i >= 0, `expected to find ${JSON.stringify(needle)}`)
  return src.slice(Math.max(0, i - chars), i)
}

function lineWith(src, needle) {
  const line = src.split('\n').find((l) => l.includes(needle))
  assert.ok(line, `expected a line containing ${JSON.stringify(needle)}`)
  return line
}

test('Models.tsx no longer treats project.models as permission to manage models', () => {
  assert.doesNotMatch(models, /can\('project\.models'\)/)
  assert.doesNotMatch(models, /canManage/)
})

test('the Train controls are gated on project.train', () => {
  for (const label of ['Train new model', 'Train your first model']) {
    assert.match(lineWith(models, label), /can\('project\.train'\)/, `${label} must use project.train`)
  }
})

test('Export TensorRT is gated on isManager', () => {
  assert.match(gateBefore(models, 'exportEngine}>'), /\bisManager\b/)
})

test('Delete model is gated on isManager', () => {
  assert.match(gateBefore(models, 'aria-label="Delete model"'), /\bisManager\b/)
})

test('Stop stays available to reviewers rather than becoming manager-only', () => {
  const stop = lineWith(models, '/cancel')
  assert.match(stop, /can\('project\.review'\)/)
  assert.doesNotMatch(stop, /isManager/)
})

test('AliasCard gates deploy and rollback on isManager, not a permission string', () => {
  const start = workspace.indexOf('function AliasCard')
  const end = workspace.indexOf('function DriftStrip')
  assert.ok(start >= 0 && end > start, 'expected the AliasCard component')
  const aliasCard = workspace.slice(start, end)

  assert.doesNotMatch(aliasCard, /canManage/)
  assert.doesNotMatch(aliasCard, /can\('project\.models'\)/)
  assert.match(aliasCard, /const \{ isManager \} = useProjectPermissions\(ws, project\.slug\)/)

  assert.match(lineWith(aliasCard, 'deploy.mutate(modelId)'), /\bisManager\b/)
  assert.match(aliasCard, /alias\?\.previous_model_id && isManager &&/)
})

test('DriftStrip keeps its reviewer gate untouched', () => {
  const drift = workspace.slice(workspace.indexOf('function DriftStrip'))
  assert.match(drift, /can\('project\.review'\)/)
})
