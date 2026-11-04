// Task G5: annotation stack order and viewport culling — pure rules for the editor.
//   node --test tests/editor-g5.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { canMove, moveAnnotation, orderIndexOf, ORDER_ACTIONS } from '../src/features/editor/annotationOrder.ts'
import { CULL_MARGIN_PX, cullAnnotations, intersects, shapeBounds, viewportBounds } from '../src/features/editor/culling.ts'

const ids = (list) => list.map((a) => a.id)
const list = () => [{ id: 'a' }, { id: 'b' }, { id: 'c' }]

test('the four order actions move one item and leave every other id in place', () => {
  assert.deepEqual(ids(moveAnnotation(list(), 'b', 'forward')), ['a', 'c', 'b'])
  assert.deepEqual(ids(moveAnnotation(list(), 'b', 'backward')), ['b', 'a', 'c'])
  assert.deepEqual(ids(moveAnnotation(list(), 'a', 'front')), ['b', 'c', 'a'])
  assert.deepEqual(ids(moveAnnotation(list(), 'c', 'back')), ['c', 'a', 'b'])
})

test('moving to an end is idempotent and never reorders the neighbours', () => {
  assert.deepEqual(ids(moveAnnotation(list(), 'c', 'front')), ['a', 'b', 'c'])
  assert.deepEqual(ids(moveAnnotation(list(), 'a', 'back')), ['a', 'b', 'c'])
  // A no-op returns the same array reference so the editor cannot mark the image dirty.
  const current = list()
  assert.equal(moveAnnotation(current, 'c', 'forward'), current)
  assert.equal(moveAnnotation(current, 'a', 'backward'), current)
  assert.equal(moveAnnotation(current, 'c', 'front'), current)
  assert.equal(moveAnnotation(current, 'a', 'back'), current)
  assert.equal(moveAnnotation(current, 'ghost', 'forward'), current)
  // A real move returns a new array; the input is never mutated.
  const moved = moveAnnotation(current, 'a', 'front')
  assert.notEqual(moved, current)
  assert.deepEqual(ids(current), ['a', 'b', 'c'])
})

test('order guards tell the UI when a button must be disabled', () => {
  const current = list()
  assert.equal(canMove(current, 'b', 'forward'), true)
  assert.equal(canMove(current, 'c', 'forward'), false)
  assert.equal(canMove(current, 'a', 'backward'), false)
  assert.equal(canMove(current, 'a', 'front'), true)
  assert.equal(canMove(current, 'c', 'front'), false)
  assert.equal(canMove(current, 'c', 'back'), true)
  assert.equal(canMove(current, 'a', 'back'), false)
  assert.equal(canMove(current, 'b', 'front'), true)
  assert.equal(canMove(current, 'ghost', 'front'), false)
  assert.deepEqual(ORDER_ACTIONS, ['front', 'forward', 'backward', 'back'])
})

test('the visible order index is 1-based from the back of the stack', () => {
  assert.equal(orderIndexOf(list(), 'a'), 1)
  assert.equal(orderIndexOf(list(), 'c'), 3)
  assert.equal(orderIndexOf(list(), 'ghost'), null)
})

test('array order survives the JSON round-trip the save endpoint performs', () => {
  const moved = moveAnnotation(list(), 'a', 'front')
  const saved = JSON.parse(JSON.stringify(moved))
  assert.deepEqual(ids(saved), ['b', 'c', 'a'])
  // Relabelling maps over the array, so it cannot reorder the stack.
  const relabelled = saved.map((a) => (a.id === 'b' ? { ...a, classId: 'helmet' } : a))
  assert.deepEqual(ids(relabelled), ['b', 'c', 'a'])
})

const bbox = (id, x, y, w = 0.1, h = 0.1) => ({ id, classId: 'c', shape: { kind: 'bbox', x, y, w, h } })
const W = 1000
const H = 500

test('shape bounds are stage pixels for every annotation kind that is drawn', () => {
  assert.deepEqual(shapeBounds({ kind: 'bbox', x: 0.1, y: 0.2, w: 0.2, h: 0.1 }, W, H),
    { minX: 100, minY: 100, maxX: 300, maxY: 150 })

  assert.deepEqual(shapeBounds({ kind: 'polygon', points: [0.1, 0.2, 0.4, 0.3, 0.2, 0.8] }, W, H),
    { minX: 100, minY: 100, maxX: 400, maxY: 400 })

  // Unrotated oriented box.
  assert.deepEqual(shapeBounds({ kind: 'obb', cx: 0.5, cy: 0.5, w: 0.2, h: 0.2, angle: 0 }, W, H),
    { minX: 400, minY: 200, maxX: 600, maxY: 300 })

  // Rotated 90°: the stage-pixel extents swap because w/h are normalised per axis.
  const quarter = shapeBounds({ kind: 'obb', cx: 0.5, cy: 0.5, w: 0.2, h: 0.2, angle: Math.PI / 2 }, W, H)
  assert.ok(Math.abs(quarter.minX - 450) < 1e-9 && Math.abs(quarter.maxX - 550) < 1e-9, JSON.stringify(quarter))
  assert.ok(Math.abs(quarter.minY - 150) < 1e-9 && Math.abs(quarter.maxY - 350) < 1e-9, JSON.stringify(quarter))

  assert.deepEqual(shapeBounds({ kind: 'keypoints', points: [0.1, 0.2, 2, 0.5, 0.6, 1] }, W, H),
    { minX: 100, minY: 100, maxX: 500, maxY: 300 })

  // Image-label annotations are never canvas nodes.
  assert.equal(shapeBounds({ kind: 'class' }, W, H), null)
})

test('the viewport is the visible stage rectangle with a screen-space margin', () => {
  const plain = viewportBounds({ width: 800, height: 600, scale: 1, x: -100, y: -50 }, 0)
  assert.deepEqual(plain, { minX: 100, minY: 50, maxX: 900, maxY: 650 })

  // At 2× the stage-space margin halves: 96 screen px become 48 stage px.
  const zoomed = viewportBounds({ width: 800, height: 600, scale: 2, x: -100, y: -50 }, CULL_MARGIN_PX)
  assert.deepEqual(zoomed, { minX: 2, minY: -23, maxX: 498, maxY: 373 })
  assert.ok(intersects({ minX: 0, minY: 0, maxX: 10, maxY: 10 }, zoomed), 'a shape touching the margin is visible')
  assert.ok(!intersects({ minX: 500, minY: 0, maxX: 600, maxY: 10 }, zoomed), 'a shape past the margin is culled')
})

test('culling keeps only nodes inside the viewport, plus the selected annotation', () => {
  const anns = [
    bbox('inside', 0.1, 0.1, 0.2, 0.2),      // 100..300 x, 50..150 y
    bbox('outside', 0.8, 0.8, 0.1, 0.1),     // 800..900 x, 400..450 y
    bbox('edge', 0.49, 0.49, 0.04, 0.04),    // straddles the viewport edge
    { id: 'label', classId: 'c', shape: { kind: 'class' } },
  ]
  const viewport = { minX: 0, minY: 0, maxX: 500, maxY: 500 }
  const view = { width: W, height: H }
  assert.deepEqual(ids(cullAnnotations(anns, viewport, view)), ['inside', 'edge'])
  // The Transformer target is mounted even when it is off screen.
  assert.deepEqual(ids(cullAnnotations(anns, viewport, { ...view, always: 'outside' })), ['inside', 'outside', 'edge'])
  // Image-label annotations have no node at all, selected or not.
  assert.deepEqual(ids(cullAnnotations(anns, viewport, { ...view, always: 'label' })), ['inside', 'edge'])
})

test('a 1,000-shape scan stays far below an interaction frame', () => {
  const anns = Array.from({ length: 1000 }, (_, i) => {
    const x = (i % 40) / 40
    const y = Math.floor(i / 40) / 25
    return bbox(`a${i}`, x, y, 0.02, 0.03)
  })
  const viewport = { minX: 200, minY: 100, maxX: 450, maxY: 300 }
  const started = performance.now()
  let visible = []
  for (let i = 0; i < 200; i++) visible = cullAnnotations(anns, viewport, { width: W, height: H })
  const perPass = (performance.now() - started) / 200
  assert.ok(visible.length > 0 && visible.length < 1000, `culling must narrow the set, got ${visible.length}`)
  // Generous ceiling: the honest number is printed for the report. An R-tree is only warranted
  // when one pass costs more than a frame; this asserts we are orders of magnitude away.
  assert.ok(perPass < 16, `one cull pass took ${perPass.toFixed(3)} ms`)
  console.log(`  cull 1,000 shapes: ${perPass.toFixed(4)} ms/pass, ${visible.length} visible`)
})
