// Heatmap overlay rules for the anomaly station page. Runs with the built-in Node test runner:
//   node --test tests/anomaly-view.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { cellOpacity, heatColor, hotCells } from '../src/features/project/anomalyView.ts'

test('cells well below the station threshold stay invisible', () => {
  // A 2x2 map with one quiet cell, one just above the noise floor and one hot cell.
  const values = [
    [0.1, 0.8],
    [2.0, 3.5],
  ]
  const cells = hotCells(values, 1.0)
  assert.deepEqual(cells.map((c) => `${c.row},${c.col}`), ['0,1', '1,0', '1,1'])
})

test('a zero threshold never divides by zero and keeps every cell visible', () => {
  const cells = hotCells([[0.5]], 0)
  assert.equal(cells.length, 1)
  assert.ok(cells[0].opacity > 0 && cells[0].opacity <= 1)
})

test('opacity grows with the score and is capped', () => {
  const low = cellOpacity(1.0, 1.0)
  const mid = cellOpacity(2.0, 1.0)
  const high = cellOpacity(500.0, 1.0)
  assert.ok(low > 0 && low < mid)
  assert.ok(mid <= high)
  assert.ok(high <= 0.9)
  assert.equal(cellOpacity(0.1, 1.0), 0)
})

test('heat colour is a valid rgb string that changes across the scale', () => {
  const cold = heatColor(0, 1)
  const warm = heatColor(1, 1)
  const hot = heatColor(4, 1)
  for (const c of [cold, warm, hot]) assert.match(c, /^rgb\(\d{1,3} \d{1,3} \d{1,3}\)$/)
  assert.notEqual(warm, cold)
  assert.notEqual(hot, warm)
})
