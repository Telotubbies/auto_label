// Thai-safe display text (T-473). A Thai combining mark belongs to its base character, so a
// display string is shortened on grapheme boundaries only — never on a UTF-16 code unit, where a
// cut between a base and its mark reads as a different word.
//   node --test tests/thai-text.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { basename, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { excerpt, graphemes, lineCountFor, needsMore } from '../src/lib/text.ts'

// 16 graphemes, 18 code units: "checking the photographs". The mark on ถ is a separate code unit.
const THAI = 'กำลังตรวจสอบภาพถ่าย'

const src = (path) => fileURLToPath(new URL(`../src/${path}`, import.meta.url))

/** Every .ts/.tsx file under a directory, recursively. */
function sources(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = join(dir, e.name)
    return e.isDirectory() ? sources(p) : /\.tsx?$/.test(e.name) ? [p] : []
  })
}

test('test_excerpt_never_splits_a_thai_grapheme', () => {
  const cut = excerpt(THAI, 5)
  assert.equal(cut, graphemes(THAI).slice(0, 5).join(''), 'the result is a prefix of the segmented array')
  assert.equal(graphemes(cut).length, 5, 'five whole graphemes, no more')

  // The 14th grapheme is ถ + MAI EK. A code-unit cut at the same length drops the mark.
  const withMark = excerpt(THAI, 14)
  assert.ok(withMark.endsWith('ถ่'), 'the mark stays on its base')
  const sliced = graphemes(THAI.slice(0, 16))
  assert.equal(sliced.at(-1), 'ถ', 'slice(0, 16) cuts the mark off its base: the defect this rule prevents')
  assert.notEqual(withMark, THAI.slice(0, 16), 'excerpt() is not String.prototype.slice')
})

test('test_excerpt_marks_more', () => {
  const long = 'โครงการตรวจสอบคุณภาพชิ้นงานอุตสาหกรรม'
  assert.equal(excerpt(long, 4), graphemes(long).slice(0, 4).join(''), 'four graphemes')
  assert.equal(needsMore(long, 4), true, 'the rest needs a more affordance')

  const short = 'กล้อง'
  assert.equal(excerpt(short, 4), short, 'a string that fits is returned whole')
  assert.equal(needsMore(short, 4), false, 'nothing to reveal')
})

test('test_an_empty_name_renders_an_em_dash', () => {
  assert.equal(excerpt('', 20), '—', 'never an empty box')
  assert.equal(needsMore('', 20), false)
  assert.equal(lineCountFor('', 240, 14), 0, 'no text, no lines')
})

test('test_no_slice_on_display_strings', () => {
  const DISPLAY = /\b(name|project|class|file|title|label)\b/i
  const hits = []
  for (const dir of ['components/shell', 'features/workspace']) {
    for (const file of sources(src(dir))) {
      readFileSync(file, 'utf8').split('\n').forEach((line, i) => {
        if (/\.slice\(\s*0\s*,/.test(line) && DISPLAY.test(line)) hits.push(`${basename(file)}:${i + 1}: ${line.trim()}`)
      })
    }
  }
  assert.deepEqual(hits, [], 'a display string is shortened through excerpt(), never slice(0, n)')
})

test('test_thai_line_height_is_one_point_six', () => {
  const css = readFileSync(src('index.css'), 'utf8')
  assert.match(css, /:lang\(th\)\s*\{[^}]*line-height:\s*1\.6/, ':lang(th) stays the single source for Thai line-height')
  assert.match(css, /\.clamp-2\s*\{[^}]*display:\s*-webkit-box/, 'the two-line clamp needs the webkit box')
  assert.match(css, /\.clamp-2\s*\{[^}]*(-webkit-)?line-clamp:\s*2/, 'two lines, then the more affordance')
  assert.match(css, /\.clamp-th\s*\{[^}]*(-webkit-)?line-clamp:\s*2/, 'the Thai variant clamps too')
  assert.doesNotMatch(css, /\.clamp-(2|th)\s*\{[^}]*line-height/, 'no clamp class restates the Thai line-height')
})

test('test_latin_numbers_use_tabular_figures', () => {
  // A count that renders beside a name: the project card's image and model totals.
  const home = readFileSync(src('features/workspace/Home.tsx'), 'utf8')
  const countLine = home.split('\n').find((l) => /\{[a-z]+\.images\}/.test(l))
  assert.ok(countLine, 'the project card renders a count beside its name')
  assert.match(countLine, /tabular-nums/, 'counts line up column to column')
})
