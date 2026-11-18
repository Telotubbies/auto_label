import test from 'node:test'
import assert from 'node:assert/strict'
import { sortCards } from '../src/features/project/boardSort.ts'

const c = (batchName, created, images) => ({ batchName, created, images })
const cards = [c('b', 2, 5), c('a', 3, 1), c('c', 1, 9)]

test('sorts by newest, name and image count without mutating', () => {
  assert.deepEqual(sortCards(cards, 'newest').map((x) => x.batchName), ['a', 'b', 'c'])
  assert.deepEqual(sortCards(cards, 'name').map((x) => x.batchName), ['a', 'b', 'c'])
  assert.deepEqual(sortCards(cards, 'images').map((x) => x.batchName), ['c', 'b', 'a'])
  assert.deepEqual(cards.map((x) => x.batchName), ['b', 'a', 'c'])
})
