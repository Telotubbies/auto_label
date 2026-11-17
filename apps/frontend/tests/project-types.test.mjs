// T-017 — the New project grid names eight types and words each by what you get, not by model family.
// Pins the catalogue Home.tsx and ProjectPanel.tsx read; the server half lives in
// apps/backend/tests/test_project_types.py.
//   node --test tests/project-types.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { availableTypes, PROJECT_TYPES, typeLabel } from '../src/features/project/projectTypes.ts'

// A buyer picks by outcome; a model family is an implementation detail and trips the no-competitor rule.
const MODEL_FAMILY = /YOLO|SAM|CLIP|DETR|Roboflow/i

test('test_catalogue_has_eight_outcome_sentences', () => {
  assert.equal(PROJECT_TYPES.length, 8, 'the grid carries the eight types, in order')
  for (const t of PROJECT_TYPES) {
    assert.equal(t.chips.length, 2, `${t.id} carries two capability chips`)
    assert.match(t.outcome, /\.$/, `${t.id} is one outcome sentence`)
    for (const text of [t.label, t.outcome, ...t.chips]) {
      assert.doesNotMatch(text, MODEL_FAMILY, `${t.id} names a model family: ${text}`)
    }
    assert.equal(typeLabel(t.id), t.label, `${t.id} labels resolve from the catalogue`)
  }
  assert.equal(typeLabel('obb'), 'obb', 'an unknown id falls back to itself')
})

test('test_available_types_hides_anomaly_without_its_flag', () => {
  const seven = availableTypes(new Set(['task_a1_types']))
  assert.equal(seven.length, 7)
  assert.ok(!seven.some((t) => t.id === 'anomaly-detection'), 'anomaly needs task_29')
  assert.equal(seven.at(-1).id, 'action-recognition')

  const eight = availableTypes(new Set(['task_a1_types', 'task_29']))
  assert.equal(eight.length, 8)
  assert.equal(eight.at(-1).id, 'anomaly-detection', 'anomaly stays last')
})

test('test_flag_off_returns_the_original_five', () => {
  // Exactly the set Home.tsx carries today, anomaly included when its own flag is on.
  assert.deepEqual(availableTypes(new Set(['task_29'])).map((t) => t.id), [
    'object-detection', 'instance-segmentation', 'classification', 'keypoint-detection', 'anomaly-detection',
  ])
  // And exactly today's render when task_29 is off too.
  assert.deepEqual(availableTypes(new Set()).map((t) => t.id), [
    'object-detection', 'instance-segmentation', 'classification', 'keypoint-detection',
  ])
})
