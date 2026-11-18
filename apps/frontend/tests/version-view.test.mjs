import test from 'node:test'
import assert from 'node:assert/strict'
import { f1Score, resizeLabel, preprocessSteps } from '../src/features/project/versionView.ts'

test('f1 is the harmonic mean and undefined without both inputs', () => {
  assert.equal(f1Score(0.5, 0.5), 0.5)
  assert.equal(f1Score(undefined, 0.5), undefined)
  assert.equal(f1Score(0, 0), undefined)
})
test('resize label and preprocessing steps', () => {
  const s = { preprocessing: { resize: { width: 320, height: 320 }, grayscale: true, filter_null: true, contrast: false } }
  assert.equal(resizeLabel(s), '320×320')
  assert.equal(resizeLabel({}), undefined)
  assert.deepEqual(preprocessSteps(s), ['grayscale', 'filter null'])
})
