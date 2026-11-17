// The Playground model list groups its rows by family, so the vendor prints once per group.
//   node --test tests/model-groups.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { groupModels } from '../src/features/playground/modelGroups.ts'

const model = (family, variant, name) => ({ ref: `${family}:${variant}`, family, variant, name })
const registry = [
  model('ultralytics', 'yolo26n', 'YOLO26 N'),
  model('ultralytics', 'yolo26n-seg', 'YOLO26 N Seg'),
  model('ultralytics', 'yolo26s', 'YOLO26 S'),
  model('sam3', 'sam3.1', 'SAM 3.1'),
  model('vlm', 'qwen2.5-vl-7b', 'Qwen2.5-VL 7B'),
]

test('test_groups_keep_registry_order — the first model of the input is the first row of the first group', () => {
  const groups = groupModels(registry)
  assert.equal(groups[0].items[0].ref, registry[0].ref)
})

test('test_every_model_appears_exactly_once — the flattened groups equal the input length, no duplicates', () => {
  const rows = groupModels(registry).flatMap((group) => group.items)
  assert.equal(rows.length, registry.length)
  assert.equal(new Set(rows.map((m) => m.ref)).size, registry.length)
  assert.deepEqual(rows.map((m) => m.ref), registry.map((m) => m.ref))
})

test('test_empty_registry_renders_no_group — an empty list returns no groups, so no empty heading', () => {
  assert.deepEqual(groupModels([]), [])
})

test('test_group_label_is_the_family — each group carries the family string the row used to repeat', () => {
  const groups = groupModels(registry)
  assert.deepEqual(groups.map((group) => group.family), ['ultralytics', 'sam3', 'vlm'])
  assert.deepEqual(groups.map((group) => group.items.length), [3, 1, 1])
})
