// Regression test for I10 residual round 2: Dataset, Editor, Versions and the workspace Privacy
// page still gated on the workspace rank, although the API enforces the effective project role.
// A workspace member who is a project reviewer must see review/upload controls; a billing user
// (workspace rank 2) must not; a project manager who is a workspace member must see manager
// actions. These files are source-checked because the suite has no DOM renderer.
//
//   node --test tests/project-screen-permissions.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8')
const dataset = read('../src/features/project/Dataset.tsx')
const editor = read('../src/features/editor/Editor.tsx')
const versions = read('../src/features/project/Versions.tsx')
const privacy = read('../src/features/governance/Privacy.tsx')
const streams = read('../src/features/streams/Streams.tsx')
const streamDetail = read('../src/features/streams/StreamDetail.tsx')

function lineWith(src, needle) {
  const line = src.split('\n').find((l) => l.includes(needle))
  assert.ok(line, `expected a line containing ${JSON.stringify(needle)}`)
  return line
}

test('Dataset resolves the effective project role instead of the workspace rank', () => {
  assert.match(dataset, /useProjectPermissions\(ws, project\.slug\)/)
  assert.doesNotMatch(dataset, /useApp\(\(s\) => s\.can\)/)
})

test('Dataset gates review actions on project.review and upload on project.upload', () => {
  assert.match(lineWith(dataset, 'Auto Label</Button>'), /can\('project\.review'\)/)
  assert.match(lineWith(dataset, '{sel.size > 0 &&'), /can\('project\.review'\)/)
  assert.match(lineWith(dataset, 'Upload images'), /can\('project\.upload'\)/)
})

test('Dataset default status filter follows project.review, not the workspace rank', () => {
  assert.match(lineWith(dataset, "status: sp.get('status')"), /can\('project\.review'\)/)
})

test('Editor approves and rejects with project.review', () => {
  assert.match(editor, /useProjectPermissions\(ws, project\)/)
  assert.doesNotMatch(editor, /can\('reviewer'\)/)
  assert.match(lineWith(editor, "{can('project.review') && <>"), /can\('project\.review'\)/)
  assert.match(editor, /Approve<\/Button>/)
  assert.match(editor, /Reject<\/Button>/)
})

test('Editor loads the label-assist model list only with project.infer', () => {
  assert.match(lineWith(editor, "queryKey: ['models', ws, project]"), /can\('project\.infer'\)/)
})

test('Versions gates Train on project.train and delete on isManager', () => {
  assert.match(versions, /useProjectPermissions\(ws, project\.slug\)/)
  assert.doesNotMatch(versions, /can\('admin'\)/)
  assert.match(lineWith(versions, 'Train a model'), /can\('project\.train'\)/)
  assert.match(lineWith(versions, 'Delete this version?'), /\bisManager\b/)
})

test('The workspace Privacy page edits each project with that project\'s role', () => {
  assert.match(privacy, /useProjectPermissions\(ws, project\.slug\)/)
  assert.match(lineWith(privacy, "const canEdit"), /can\('project\.privacy'\)/)
  assert.doesNotMatch(privacy, /canEdit=\{canEdit\}/)
})

test('Streams manages cameras with the effective project manager role', () => {
  assert.match(streams, /useProjectPermissions\(ws, project\)/)
  assert.doesNotMatch(streams, /useApp\(\(s\) => s\.can\)/)
  assert.match(lineWith(streams, 'const admin'), /\bisManager\b/)
})

test('StreamDetail reviews with project.review and manages with isManager', () => {
  assert.match(streamDetail, /useProjectPermissions\(ws, project\)/)
  assert.doesNotMatch(streamDetail, /can\('reviewer'\)/)
  assert.doesNotMatch(streamDetail, /can\('admin'\)/)
  assert.match(lineWith(streamDetail, "canReview ="), /can\('project\.review'\)/)
  assert.match(lineWith(streamDetail, 'const admin'), /\bisManager\b/)
})
