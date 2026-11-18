// The Stat tile is a data card on dense pages (Admin, Dataset health, Overview, Versions diff).
// Rules (impeccable craft floor + VISUAL-OVERRIDE): solid surface, no coloured side stripe, numerals
// align (tabular-nums), the label/value pair is a description list so a reader hears "Images, 480",
// and a status colour never stands alone: a tone is a dot beside a label that already names it.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const ui = source('../src/components/ui.tsx')
const versions = source('../src/features/project/insights/VersionsOps.tsx')

/** The text of `export function Stat` up to the next top-level export. */
const stat = ui.slice(ui.indexOf('export function Stat('), ui.indexOf('export function StatusPill('))

test('the Stat tile has no coloured side stripe', () => {
  assert.doesNotMatch(stat, /border-l-/, 'a >1px coloured side border is the stripe the design floor refuses')
})

test('the Stat value uses tabular numerals and a quiet surface', () => {
  assert.match(stat, /tabular-nums/, 'counts and sizes must line up across tiles')
  assert.match(stat, /shadow-none/, 'a static tile does not float: the border carries the edge')
})

test('the Stat label and value are a description list', () => {
  assert.match(stat, /<dl>/)
  assert.match(stat, /<dt[ >]/)
  assert.match(stat, /<dd[ >]/)
})

test('a tone is a decorative dot, never the only carrier of meaning', () => {
  assert.match(stat, /tone\?:/, 'Stat takes an optional tone')
  assert.match(stat, /aria-hidden/, 'the dot is decoration: the label already names the meaning')
})

test('the versions diff tiles use Stat with a tone instead of hand-built striped cards', () => {
  assert.doesNotMatch(versions, /border-l-4/)
  for (const [label, tone] of [['Added in target', 'primary'], ['Removed', 'destructive'], ['Split moves', 'warning']]) {
    assert.match(versions, new RegExp(`<Stat label="${label}"[^>]*tone="${tone}"`), `${label} keeps its ${tone} tone`)
  }
})
