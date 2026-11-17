// Parity guard area 3: the editor's shipped route, shell, provenance chip and objects list (T-003).
//   node --test tests/parity-guard-area3.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { ORDER_ACTIONS } from '../src/features/editor/annotationOrder.ts'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const routes = read('../src/routes/project/index.tsx')
const editor = read('../src/features/editor/Editor.tsx')
const panels = read('../src/features/editor/Panels.tsx')
const objects = read('../src/features/editor/ObjectList.tsx')
const board = read('../src/features/project/AnnotateBoard.tsx')
const datasetApi = read('../src/lib/api/dataset.ts')

test('the editor route and its shell regions survive', () => {
  // A board card or a grid tile opens the editor at this path.
  assert.match(routes, /path=":project\/images\/:imageId"/)
  assert.match(routes, /import\('@\/features\/editor\/Editor'\)/)
  // The tool rail: bounding box, polygon, smart polygon, keypoints.
  assert.match(editor, /tools\.map\(/)
  for (const id of ['bbox', 'polygon', 'smart', 'keypoints']) {
    assert.match(editor, new RegExp(`id: '${id}'`), `tool ${id} is off the rail`)
  }
  assert.match(editor, /aria-label=\{label\}/)
  // The header carries previous / next.
  assert.match(editor, /aria-label="Previous"/)
  assert.match(editor, /aria-label="Next"/)
})

test('the panel source chip keeps source and confidence', () => {
  assert.match(panels, /export function SourceChip\(/)
  // VLM boxes carry no calibrated score, and the chip says so instead of inventing one.
  assert.match(panels, /source === 'vlm\+sam3'/)
  assert.match(panels, /no confidence/)
  // Everything else renders the confidence as a percentage.
  assert.match(panels, /Math\.round\(confidence \* 100\)\}%/)
})

test('the objects list keeps hide, lock, delete and the four order actions', () => {
  assert.match(objects, /data-testid="object-hide"/)
  assert.match(objects, /data-testid="object-lock"/)
  assert.match(objects, /aria-pressed=\{isHidden\}/)
  assert.match(objects, /aria-pressed=\{isLocked\}/)
  assert.match(objects, /data-testid="object-delete"/)
  assert.deepEqual(ORDER_ACTIONS, ['front', 'forward', 'backward', 'back'])
  assert.match(objects, /ORDER_ACTIONS\.map\(/)
  assert.match(objects, /canMove\(list, id, action\)/)
})

test('the smart polygon and auto-label entries are still in the editor', () => {
  // Click-to-grow/shrink posts to the smart-polygon assist.
  assert.match(editor, /\/images\/\$\{imageId\}\/smart-polygon/)
  // The board opens the auto-label dialog, whose preview calls the documented route.
  assert.match(board, /<AutoLabelDialog/)
  assert.match(datasetApi, /autolabel\/preview/)
})
