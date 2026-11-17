// T-1200 — the e2e harness's own arithmetic: step counting, the journey target and flag errors.
// Runs with the built-in Node test runner: node --test tests/e2e-harness.test.mjs (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { JourneyRecord, setFlags } from '../e2e/fixtures/harness.ts'

test('test_record_counts_one_step_per_action', () => {
  const ticks = [0, 100, 300, 600]          // the first read is the constructor's start
  const record = new JourneyRecord(() => ticks.shift())

  record.step()
  record.step()
  record.step()

  assert.equal(record.steps, 3)
  // Each step owns the delta since the previous one, so the total is their sum, not the wall clock.
  assert.equal(record.timeMs, 600)
  assert.equal(record.done({ steps: 3, timeMs: 600 }).ok, true)
})

test('test_record_fails_on_a_missing_target', () => {
  const ticks = [0, 30, 45, 60]
  const slow = new JourneyRecord(() => ticks.shift())
  slow.step()
  slow.step()
  slow.step()

  const overSteps = slow.done({ steps: 2, timeMs: 60 })
  assert.equal(overSteps.ok, false)
  assert.match(overSteps.failures.join(' '), /steps 3 over the 2 target/)

  const overTime = slow.done({ steps: 3, timeMs: 40 })
  assert.equal(overTime.ok, false)
  assert.match(overTime.failures.join(' '), /time 60 ms over the 40 ms target/)
})

test('test_setFlags_names_an_unknown_key', async () => {
  const calls = []
  const request = {
    post: async (url) => {
      calls.push({ url })
      return { ok: () => true, status: () => 200, json: async () => ({ token: 'e2e-token' }) }
    },
    put: async (url, options) => {
      calls.push({ url, options })
      return { ok: () => false, status: () => 404, text: async () => '{"detail":"unknown feature flag"}' }
    },
  }

  await assert.rejects(() => setFlags(request, ['task_470']), /task_470.*404/s)

  assert.deepEqual(calls.map((c) => c.url), ['/api/auth/login', '/api/ws/labeldesk-demo/flags/task_470'])
  assert.deepEqual(calls[1].options.data, { enabled: true })
  assert.equal(calls[1].options.headers.Authorization, 'Bearer e2e-token')

  // A flag-off leg asks for nothing, so the stub must not be reached at all.
  const empty = {
    post: async () => { throw new Error('a disabled surface must not log in') },
    put: async () => { throw new Error('a disabled surface must not call the API') },
  }
  await setFlags(empty, [])
})
