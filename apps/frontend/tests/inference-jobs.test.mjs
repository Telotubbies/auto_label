// T-1009: the job card's pure rules — one sentence per status, which statuses stop the poller,
// the log the sheet may render, and the confirm before anything stops.
// node --test tests/inference-jobs.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  cancelCopy, isTerminal, jobCopy, visibleLog,
} from '../src/features/inference/engineRows.ts'

const job = (over = {}) => ({
  id: 'j1', kind: 'engine_apply', status: 'running', progress: 40,
  phase: 'installing vllm', log: [], error: '', host: 'gpu-1', action: 'install',
  result: { engines: [] }, created: 1, finished: null, ...over,
})

test('test_job_copy_maps_every_status_to_a_sentence', () => {
  for (const status of ['queued', 'running', 'cancelling', 'done', 'failed']) {
    const text = jobCopy(job({ status }))
    assert.equal(typeof text, 'string')
    assert.ok(text.trim().length > 1, `${status} has a sentence`)
    assert.match(text, /^[A-Z]/, `${status} starts like a sentence`)
  }

  const failed = jobCopy(job({ status: 'failed', error: 'No space left on device.' }))
  assert.match(failed, /Install failed/)
  assert.match(failed, /No space left on device\./)
  // A worker that failed without a reason still produces a sentence, never an empty tail.
  assert.match(jobCopy(job({ status: 'failed', error: '' })), /Install failed: \S/)

  assert.equal(jobCopy(job({ status: 'cancelling' })), 'Cancelling…')
  assert.match(jobCopy(job({ status: 'done' })), /Installed on gpu-1/)
  assert.match(jobCopy(job({ status: 'running' })), /Installing vllm/)
})

test('test_terminal_statuses_stop_polling', () => {
  for (const status of ['done', 'failed', 'cancelled']) {
    assert.equal(isTerminal(job({ status })), true, `${status} is terminal`)
  }
  // A cancelling job is still on the wire: the worker has not acknowledged it yet.
  for (const status of ['queued', 'running', 'cancelling']) {
    assert.equal(isTerminal(job({ status })), false, `${status} keeps polling`)
  }
})

test('test_log_is_rendered_newest_last_and_capped', () => {
  const lines = Array.from({ length: 250 }, (_, i) => `line ${i + 1}`)
  const shown = visibleLog(job({ log: lines }))
  assert.equal(shown.length, 200)
  assert.equal(shown[0], 'line 51')          // the oldest of the last 200
  assert.equal(shown[199], 'line 250')       // newest last
  assert.deepEqual(visibleLog(job({ log: ['only one'] })), ['only one'])
  assert.deepEqual(visibleLog(job({ log: undefined })), [])
})

test('test_cancel_needs_a_confirm', () => {
  const text = cancelCopy('gpu-1')
  assert.equal(text, 'Stop this install on gpu-1? The half-built environment is removed.')
  assert.match(text, /gpu-1/)
  assert.match(text, /environment is removed/)
})

test('test_a_pull_job_says_pull_not_install', () => {
  assert.equal(jobCopy(job({ status: 'queued', action: 'pull', phase: '' })),
    'Pull queued on gpu-1.')
  assert.equal(jobCopy(job({ status: 'running', action: 'pull', phase: 'pulling qwen3-4b' })),
    'Pulling qwen3-4b.')
  assert.equal(jobCopy(job({ status: 'done', action: 'pull' })), 'Model pulled on gpu-1.')
  assert.match(jobCopy(job({ status: 'failed', action: 'pull', error: 'x' })), /^Pull failed: x/)
  assert.equal(cancelCopy('gpu-1', 'pull'),
    'Stop this pull on gpu-1? The partial model is removed.')
})
