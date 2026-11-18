// Models > Search: find a trained model by name, architecture, class or status, best score first.
import test from 'node:test'
import assert from 'node:assert/strict'
import { searchModels, headlineScore, tabFromParams } from '../src/features/project/modelFinder.ts'

const model = (id, over = {}) => ({ id, name: id, arch: 'yolo26s-seg', variant: 'yolo26s-seg', task: 'segment', status: 'ready',
  classes: ['person', 'helmet'], metrics: { map50: 0.5 }, ...over })
const list = [
  model('ppe-s', { metrics: { map50: 0.6 } }),
  model('ppe-m', { arch: 'yolo26m-seg', variant: 'yolo26m-seg', metrics: { map50: 0.74 } }),
  model('cls-a', { task: 'classify', arch: 'yolo26n-cls', classes: ['cat'], metrics: { accuracy_top1: 0.9 } }),
  model('ppe-fail', { status: 'failed', metrics: {} }),
  model('ppe-run', { status: 'training', metrics: {} }),
]
const ids = (r) => r.map((m) => m.id)

test('with no filter every model is listed, best score first, unscored last', () => {
  assert.deepEqual(ids(searchModels(list, {})), ['cls-a', 'ppe-m', 'ppe-s', 'ppe-fail', 'ppe-run'])
})

test('the text matches name, architecture and class names, ignoring case', () => {
  assert.deepEqual(ids(searchModels(list, { q: 'HELMET' })), ['ppe-m', 'ppe-s', 'ppe-fail', 'ppe-run'])
  assert.deepEqual(ids(searchModels(list, { q: '26m' })), ['ppe-m'])
  assert.deepEqual(ids(searchModels(list, { q: 'cat' })), ['cls-a'])
})

test('status and task narrow the list', () => {
  assert.deepEqual(ids(searchModels(list, { status: 'failed' })), ['ppe-fail'])
  assert.deepEqual(ids(searchModels(list, { task: 'classify' })), ['cls-a'])
  assert.deepEqual(ids(searchModels(list, { task: 'segment', status: 'ready', q: 'ppe' })), ['ppe-m', 'ppe-s'])
})

test('the headline is top-1 for a classifier and mAP50 otherwise, null when absent', () => {
  assert.equal(headlineScore(list[2]), 0.9)
  assert.equal(headlineScore(list[0]), 0.6)
  assert.equal(headlineScore(list[3]), null)
})

test('the tab comes from the URL and an unknown one falls back to evaluation', () => {
  assert.equal(tabFromParams(new URLSearchParams('tab=search')), 'search')
  assert.equal(tabFromParams(new URLSearchParams('tab=leaderboard&model=x')), 'leaderboard')
  assert.equal(tabFromParams(new URLSearchParams('tab=nonsense')), 'evaluation')
  assert.equal(tabFromParams(new URLSearchParams('')), 'evaluation')
})
