// The Compute page's maths: the andon colour of a state, time left, memory share and a job's one-line summary.
import test from 'node:test'
import assert from 'node:assert/strict'
import { STATE_VIEW, fmtLeft, vramShare, jobLine } from '../src/features/compute/computeView.ts'

test('every state has a word, a tone and a shape, so colour is never the only signal', () => {
  for (const s of ['training', 'working', 'idle', 'offline']) {
    const v = STATE_VIEW[s]
    assert.ok(v.word && v.tone && v.shape, s)
  }
  assert.equal(STATE_VIEW.offline.tone, 'destructive')
  assert.equal(STATE_VIEW.idle.tone, 'success')
})

test('time left reads in minutes and hours, and is a dash when unknown', () => {
  assert.equal(fmtLeft(null), '—')
  assert.equal(fmtLeft(45), '45 s')
  assert.equal(fmtLeft(600), '10 min')
  assert.equal(fmtLeft(5400), '1 h 30 min')
})

test('the memory share is a whole percent, capped, and zero with no budget', () => {
  assert.equal(vramShare(2048, 4608), 44)
  assert.equal(vramShare(9000, 4608), 100)
  assert.equal(vramShare(100, 0), 0)
})

test('a training job names its model and epoch; others name their kind and project', () => {
  assert.equal(jobLine({ kind: 'train', name: 'ppe-m', project: 'PPE', progress: 50, epochs: 100, status: 'running' }), 'ppe-m · epoch 50 of 100')
  assert.equal(jobLine({ kind: 'autolabel', name: '', project: 'PPE', progress: 10, epochs: null, status: 'running' }), 'Auto-label · PPE')
  assert.equal(jobLine({ kind: 'train', name: 'ppe-m', project: 'PPE', progress: 0, epochs: 100, status: 'queued' }), 'ppe-m · waiting for a worker')
})
