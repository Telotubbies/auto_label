// A link from the Inference Hub preselects an auto-label model, once.
//   node --test tests/autolabel-prefill.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { autolabelParam, pickInitialRef } from '../src/features/project/autolabelLabel.ts'

const item = (ref, available = true) => ({ ref, available })
const ITEMS = [item('sam3:sam3.1'), item('vlm:qwen3-vl'), item('sam3:off', false)]

test('a ref present in the registry is selected', () => {
  assert.equal(pickInitialRef('sam3:sam3.1', ITEMS), 'sam3:sam3.1')
})

test('an unknown ref falls back to the default and the notice shows', () => {
  const raw = autolabelParam(new URLSearchParams('autolabel=sam3%3Aretired'))
  assert.equal(pickInitialRef(raw, ITEMS), null) // the caller keeps the default
  assert.equal(!!raw && pickInitialRef(raw, ITEMS) === null, true) // the one-line notice condition
})

test('an unavailable ref is still selected so the reason line explains it', () => {
  assert.equal(pickInitialRef('sam3:off', ITEMS), 'sam3:off')
})

test('the parameter is decoded once, and blank values are ignored', () => {
  assert.equal(autolabelParam(new URLSearchParams('autolabel=sam3%3Asam3.1')), 'sam3:sam3.1')
  assert.equal(autolabelParam(new URLSearchParams('autolabel=')), null)
  assert.equal(autolabelParam(new URLSearchParams('autolabel=%20%20')), null)
})

test('no parameter keeps today’s behaviour', () => {
  assert.equal(pickInitialRef(null, ITEMS), null)
  assert.equal(autolabelParam(new URLSearchParams('q=helmet')), null)
})
