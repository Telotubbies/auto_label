// Selection rules for the Compare tab picker. Runs with the built-in Node test runner:
//   node --test tests/compare-selection.test.mjs   (from apps/web)
import test from 'node:test'
import assert from 'node:assert/strict'
import { defaultCompare, toggleSelection } from '../src/features/insights/modelSelection.ts'

const model = (id, versionId, task = 'detect') => ({ id, versionId, task })

test('an isolated anchor falls back to the first version with two evaluated models', () => {
  // Newest first: v2 holds a single evaluated run, v1 holds two.
  const candidates = [model('newest', 'v2'), model('older-a', 'v1'), model('older-b', 'v1')]
  assert.deepEqual(defaultCompare(candidates), ['older-a', 'older-b'])
})

test('an isolated ?model= anchor does not strand the picker', () => {
  const candidates = [model('newest', 'v2'), model('older-a', 'v1'), model('older-b', 'v1')]
  assert.deepEqual(defaultCompare(candidates, 'newest'), ['older-a', 'older-b'])
})

test('a requested anchor keeps its place when it has a peer', () => {
  const candidates = [model('newest', 'v2'), model('older-a', 'v1'), model('older-b', 'v1')]
  assert.deepEqual(defaultCompare(candidates, 'older-b'), ['older-b', 'older-a'])
})

test('one model per version selects the single model so it can be cleared', () => {
  const candidates = [model('solo-a', 'v1'), model('solo-b', 'v2')]
  assert.deepEqual(defaultCompare(candidates), ['solo-a'])
})

test('deselecting the last selected model reaches the empty state', () => {
  const candidates = [model('solo-a', 'v1'), model('solo-b', 'v2')]
  assert.deepEqual(toggleSelection(candidates, ['solo-a'], 'solo-a'), [])
})

test('adding a model keeps candidate order and respects the four-model cap', () => {
  const candidates = ['a', 'b', 'c', 'd', 'e'].map((id) => model(id, 'v1'))
  assert.deepEqual(toggleSelection(candidates, ['b', 'a'], 'c'), ['a', 'b', 'c'])
  assert.deepEqual(toggleSelection(candidates, ['a', 'b', 'c', 'd'], 'e'), ['a', 'b', 'c', 'd'])
})
