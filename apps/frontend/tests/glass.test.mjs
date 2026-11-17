// T-472: the glass contract. The card pins the look the app already ships — 16/20 px blur, 58/62 % chrome tint,
// 80/84 % overlay tint, 92 % fallback — and widens the reduced-transparency fallback so a later chrome class
// cannot ship a surface that only works with blur. Source-checked like the other parity guards, because the
// suite has no DOM renderer.
//   node --test tests/glass.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const src = (rel) => readFileSync(new URL(`../src/${rel}`, import.meta.url), 'utf8')
const css = src('index.css')
const ui = src('components/ui.tsx')

/** The body of the first rule with this exact selector, up to its first closing brace (these rules do not nest). */
const rule = (selector) => {
  const start = css.indexOf(`${selector} {`)
  assert.notEqual(start, -1, `${selector} rule exists in index.css`)
  const open = css.indexOf('{', start)
  return css.slice(open, css.indexOf('}', open))
}

/** The balanced block starting at `from`; an at-rule nests rules, so count braces. */
const block = (from) => {
  const open = css.indexOf('{', from)
  assert.notEqual(open, -1, 'the rule has a body')
  let depth = 0
  for (let i = open; i < css.length; i++) {
    if (css[i] === '{') depth++
    else if (css[i] === '}' && --depth === 0) {
      return { head: css.slice(from, open), body: css.slice(open + 1, i) }
    }
  }
  throw new Error(`unclosed block at ${from}`)
}

/** Every class that can carry .glass, so both fallbacks must name all three. */
const GLASS_CLASSES = ['.glass', '.glass-overlay', '.glass-sidebar']

test('test_blur_and_saturation_literals', () => {
  assert.match(css, /@supports \(\(-webkit-backdrop-filter: blur\(1px\)\) or \(backdrop-filter: blur\(1px\)\)\)/,
    'blur is gated on the browser supporting it')
  for (const px of [16, 20]) {
    for (const property of ['-webkit-backdrop-filter', 'backdrop-filter']) {
      assert.match(css, new RegExp(`(?:^|[\\s;{])${property}: blur\\(${px}px\\) saturate\\(180%\\)`, 'm'),
        `${property} blurs at ${px}px with saturate(180%)`)
    }
  }
})

test('test_fill_percentages_are_the_shipped_ones', () => {
  assert.match(rule('.glass'), /--glass-tint: color-mix\(in oklab, var\(--popover\) 58%, transparent\)/,
    'chrome tints at 58% in light mode')
  assert.match(rule('.dark .glass'), /--glass-tint: color-mix\(in oklab, var\(--popover\) 62%, transparent\)/,
    'chrome tints at 62% in dark mode')
  assert.match(rule('.glass-overlay'), /--glass-tint: color-mix\(in oklab, var\(--popover\) 80%, transparent\)/,
    'overlays tint at 80% in light mode')
  assert.match(rule('.dark .glass-overlay'), /--glass-tint: color-mix\(in oklab, var\(--popover\) 84%, transparent\)/,
    'overlays tint at 84% in dark mode')
  assert.match(rule('.glass'), /--glass-solid: color-mix\(in oklab, var\(--popover\) 92%, var\(--foreground\)\)/,
    'the no-blur fallback is a 92% fill')
})

test('test_fallback_covers_every_glass_class', () => {
  const media = block(css.indexOf('@media (prefers-reduced-transparency: reduce)'))
  const inner = [...media.body.matchAll(/([^{}]+)\{([^}]*)\}/g)].map((m) => ({ head: m[1].trim(), body: m[2] }))
  const reduced = inner.find((r) => r.head.split(',').map((s) => s.trim()).includes('.glass'))
  assert.ok(reduced, 'the media query has a rule for .glass')

  // The toggle rule is one grouped selector list; every class in it receives the same declarations.
  const toggle = block(css.indexOf('html[data-reduce-transparency] .glass'))
  const selectors = toggle.head.split(',').map((s) => s.trim())

  for (const cls of GLASS_CLASSES) {
    assert.ok(reduced.head.split(',').map((s) => s.trim()).includes(cls),
      `prefers-reduced-transparency covers ${cls}`)
    assert.ok(selectors.includes(`html[data-reduce-transparency] ${cls}`),
      `the Settings toggle covers ${cls}`)
    for (const body of [reduced.body, toggle.body]) {
      assert.match(body, /background-image: none/, `${cls} drops the sheen`)
      assert.match(body, /-webkit-backdrop-filter: none/, `${cls} drops the prefixed blur`)
      assert.match(body, /(?:^|[;\s])backdrop-filter: none/, `${cls} drops the blur`)
    }
  }
})

test('test_blur_never_animates', () => {
  const starts = [...css.matchAll(/@keyframes/g)].map((m) => m.index)
  assert.ok(starts.length > 0, 'the motion layer still defines keyframes')
  for (const at of starts) assert.doesNotMatch(block(at).body, /blur\(/, 'no keyframe animates blur')
  for (const m of css.matchAll(/transition(?:-property)?\s*:[^;}]*/g)) {
    assert.doesNotMatch(m[0], /backdrop-filter/, 'no transition lists backdrop-filter')
  }
})

test('test_glass_is_chrome_only', () => {
  const card = ui.slice(ui.indexOf('export function Card'), ui.indexOf('export function Switch'))
  assert.match(card, /bg-card/, 'Card is still the solid content surface')
  assert.doesNotMatch(card, /glass/i, 'Card never applies .glass')
  assert.match(rule('.canvas-well'), /background:/, 'the canvas well still paints a surface')
  assert.doesNotMatch(rule('.canvas-well'), /glass/i, 'the canvas well never applies .glass')
})
