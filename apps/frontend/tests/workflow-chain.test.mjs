// Chain editing rules for the no-code workflow builder. Runs with the built-in Node test runner:
//   node --test tests/workflow-chain.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { canAddBlock, insertBlock, moveBlock } from '../src/features/project/workflowChain.ts'

const model = { type: 'model', model_ref: 'ultralytics:yolo26n' }
const sink = { type: 'sink', kind: 'response' }
const filter = { type: 'filter', classes: [], min_conf: 0.4 }

test('a new block lands before the sink so the chain stays valid', () => {
  assert.deepEqual(insertBlock([model, sink], filter), [model, filter, sink])
})

test('a new block appends when there is no sink yet', () => {
  assert.deepEqual(insertBlock([model], filter), [model, filter])
})

test('adding a second sink is refused', () => {
  assert.equal(canAddBlock([model, sink], 'sink'), false)
  assert.equal(canAddBlock([model], 'sink'), true)
})

test('the chain stops at the twelve-block limit', () => {
  const full = Array.from({ length: 12 }, () => ({ ...filter }))
  assert.equal(canAddBlock(full, 'filter'), false)
  assert.equal(canAddBlock(full.slice(0, 11), 'filter'), true)
})

test('the sink cannot be moved off the end', () => {
  const blocks = [model, filter, sink]
  assert.deepEqual(moveBlock(blocks, 2, -1), blocks)
})

test('no block can move down past the sink', () => {
  const blocks = [model, filter, sink]
  assert.deepEqual(moveBlock(blocks, 1, 1), blocks)
})

test('other blocks still reorder freely', () => {
  const blocks = [model, filter, sink]
  assert.deepEqual(moveBlock(blocks, 1, -1), [filter, model, sink])
})

test('a move outside the list changes nothing', () => {
  const blocks = [model, filter, sink]
  assert.deepEqual(moveBlock(blocks, 0, -1), blocks)
  assert.deepEqual(moveBlock(blocks, 9, 1), blocks)
})
