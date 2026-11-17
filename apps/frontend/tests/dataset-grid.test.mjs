// The dataset grid at 375 px and the count above it (T-520, UI audit A8/A9). The grid slice and
// the CSS breakpoints come from one helper so the virtualiser can never fold five items into a
// two-column row, and the subtitle names the project total instead of passing a filtered count off
// as the whole dataset.
//   node --test tests/dataset-grid.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { colsForWidth, rowHeightForWidth } from '../src/features/project/datasetGrid.ts'
import { countLine } from '../src/features/project/datasetCopy.ts'

const dataset = readFileSync(new URL('../src/features/project/Dataset.tsx', import.meta.url), 'utf8')

// Tailwind's sm / lg / xl default breakpoints, which the row element's classes use.
const CLASS_FOR_COLS = { 2: 'grid-cols-2', 3: 'sm:grid-cols-3', 4: 'lg:grid-cols-4', 5: 'xl:grid-cols-5' }

test('test_columns_follow_the_width', () => {
  assert.equal(colsForWidth(375), 2)
  assert.equal(colsForWidth(768), 3)
  assert.equal(colsForWidth(1024), 4)
  assert.equal(colsForWidth(1440), 5)
})

test('test_row_height_grows_as_columns_shrink', () => {
  const phone = rowHeightForWidth(375)
  const desktop = rowHeightForWidth(1440)
  assert.ok(phone > desktop, `a 375 px tile keeps a usable image height (${phone} > ${desktop})`)
  assert.ok(rowHeightForWidth(768) >= desktop, 'a tablet row is never shorter than a desktop row')
})

test('test_count_names_the_total_when_a_filter_is_on', () => {
  assert.equal(countLine(24, 40), '24 of 40 images match')
})

test('test_count_is_a_plain_total_without_a_filter', () => {
  assert.equal(countLine(40, 40), '40 images')
})

test('test_grid_class_set_matches_the_helper', () => {
  for (const [width, cls] of [[375, 'grid-cols-2'], [768, 'sm:grid-cols-3'], [1024, 'lg:grid-cols-4'], [1440, 'xl:grid-cols-5']]) {
    assert.equal(CLASS_FOR_COLS[colsForWidth(width)], cls, `the helper and the class agree at ${width}`)
    assert.ok(dataset.includes(cls), `Dataset.tsx renders ${cls}`)
  }
  assert.doesNotMatch(dataset, /(?<!:)grid-cols-5/, 'the row no longer pins five columns at every width')
  assert.match(dataset, /colsForWidth\(/, 'the virtualiser slices the columns the helper returns')
  assert.match(dataset, /rowHeightForWidth\(/, 'the virtualiser estimates rows with the helper')
})
