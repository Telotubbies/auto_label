// Source contract for area 2's shipped flows (T-002). A later card may re-render these screens, but
// it may not quietly drop the duplicate pre-check, the one-line upload summary, the dataset selection
// bar or rename the board/health entries. Runs with the built-in Node test runner:
//   node --test tests/parity-guard-area2.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8')
const upload = read('../src/features/project/Upload.tsx')
const dataset = read('../src/features/project/Dataset.tsx')
const board = read('../src/features/project/AnnotateBoard.tsx')
const insights = read('../src/features/project/Insights.tsx')

test('test_upload_keeps_the_duplicate_precheck_and_the_summary_line', () => {
  assert.match(upload, /uploads\/check/, 'the browser still asks which hashes already exist')
  assert.match(upload, /\{dups\} duplicates skipped/, 'the drop zone still counts skipped duplicates')
  assert.match(
    upload,
    /Uploaded \{done\.uploaded\} · duplicates skipped \{done\.duplicates\} · failed \{done\.failed\.length\}/,
    'the run still ends in one summary: uploaded, duplicates skipped, failed',
  )
})

test('test_dataset_selection_bar_keeps_split_tag_status_and_the_counted_delete', () => {
  assert.match(dataset, /images\/bulk/, 'the bulk bar still posts to the bulk route')
  for (const action of ['split', 'add_tag', 'status', 'delete']) {
    assert.match(dataset, new RegExp(`bulk\\('${action}'`), `the bar still sends the ${action} action`)
  }
  assert.match(dataset, /\{sel\.size\} selected/, 'the bar still shows how many images are selected')
  assert.match(dataset, /Delete \$\{sel\.size\} images\?/, 'delete still asks with the count')
})

test('test_board_and_health_entries_are_not_renamed', () => {
  const start = board.indexOf('const COLS')
  const cols = board.slice(start, board.indexOf('\n]', start))
  assert.match(cols, /\{ id: 'unassigned', title: 'Unassigned'/)
  assert.match(cols, /\{ id: 'annotating', title: 'Annotating'/)
  assert.match(cols, /\{ id: 'review', title: 'Review'/)
  assert.match(cols, /\{ id: 'done', title: 'Dataset'/)
  const order = ['unassigned', 'annotating', 'review', 'done'].map((id) => cols.indexOf(`id: '${id}'`))
  assert.deepEqual([...order].sort((a, b) => a - b), order, 'the four columns keep their pipeline order')

  assert.match(insights, /\{ id: 'health', label: 'Dataset health' \}/,
    'the health tab keeps its id and label so a later chart card cannot delete it')
})
