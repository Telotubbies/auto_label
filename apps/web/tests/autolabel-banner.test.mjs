// The Autolabel banner renders for every labeler, including lean job payloads that strip params.
//   node --test tests/autolabel-banner.test.mjs   (from apps/web)
import test from 'node:test'
import assert from 'node:assert/strict'
import { autolabelLabel } from '../src/features/project/autolabelLabel.ts'

test('a lean job with no params still names a model', () => {
  assert.equal(autolabelLabel(undefined), 'model')
})

test('the SAM method is named when no model ref is set', () => {
  assert.equal(autolabelLabel({ method: 'sam' }), 'SAM 3.1')
})

test('a model ref wins over the method label', () => {
  assert.equal(autolabelLabel({ method: 'sam', model_ref: 'yolo26n.pt' }), 'yolo26n.pt')
})

test('a non-SAM method without a ref falls back to model', () => {
  assert.equal(autolabelLabel({ method: 'vlm' }), 'model')
})
