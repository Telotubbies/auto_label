// Tour placement rules (T-525): the card keeps to the corner opposite its target, and a step only
// scrolls when the target is not already in view.
//   node --test tests/tour-placement.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { cornerBox, placeCard, scrollBlock } from '../src/features/workspace/tourPlacement.ts'

const VIEW = { width: 1440, height: 900 }

test('test_card_goes_opposite_a_right_hand_target', () => {
  // A target on the right of the page puts the card at a left corner.
  const corner = placeCard({ x: 1000, y: 200, width: 300, height: 200 }, VIEW)
  assert.equal(corner, 'bottom-left')
})

test('test_card_goes_opposite_a_low_target', () => {
  // A target near the bottom of the page puts the card at a top corner.
  const corner = placeCard({ x: 100, y: 700, width: 600, height: 180 }, VIEW)
  assert.equal(corner, 'top-right')
})

test('test_card_never_shares_a_corner_with_the_target', () => {
  // Deterministic LCG so a failure is reproducible; sections are at most 40% of the viewport,
  // which is the largest thing the tour ever rings.
  let seed = 525
  const rand = () => (seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296
  for (let i = 0; i < 200; i++) {
    const width = 80 + rand() * (VIEW.width * 0.4 - 80)
    const height = 80 + rand() * (VIEW.height * 0.4 - 80)
    const target = {
      x: rand() * (VIEW.width - width),
      y: rand() * (VIEW.height - height),
      width,
      height,
    }
    const corner = placeCard(target, VIEW)
    const box = cornerBox(corner, VIEW)
    const overlaps = box.x < target.x + target.width && target.x < box.x + box.width
      && box.y < target.y + target.height && target.y < box.y + box.height
    assert.equal(overlaps, false, `${corner} over ${JSON.stringify(target)}`)
  }
})

test('test_target_already_in_view_does_not_scroll', () => {
  // Fully visible: the tour leaves the page alone.
  assert.equal(scrollBlock({ x: 100, y: 100, width: 300, height: 200 }, VIEW), 'none')
  // Any edge outside the viewport asks for one nearest-aligned scroll.
  assert.equal(scrollBlock({ x: 100, y: 850, width: 300, height: 200 }, VIEW), 'nearest')
  assert.equal(scrollBlock({ x: -20, y: 100, width: 300, height: 200 }, VIEW), 'nearest')
})
