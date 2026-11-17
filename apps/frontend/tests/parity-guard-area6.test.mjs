// Parity guard, area 6: deploy threshold, workflow block fields and the zone/line editor.
// Pins the HAVE rows 6-F6.9, 6-F6.22 and 6-F6.43 in the source that renders them, so a deploy-hub,
// workflow-canvas or streams card cannot drop the confidence contract, a block's required field or
// the normalised geometry the server validates.
// Runs with the built-in Node test runner: node --test tests/parity-guard-area6.test.mjs  (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8')
const deploy = read('../src/features/project/Deploy.tsx')
const blocks = read('../src/features/project/WorkflowBlocks.tsx')
const zones = read('../src/features/streams/ZoneEditor.tsx')

test('test_deploy_keeps_the_confidence_slider_and_reruns_the_preview', () => {
  assert.match(deploy, /label=\{`Confidence \$\{conf\}%`\}/,
    '6-F6.9: the slider is labelled with the live percentage')
  assert.match(deploy, /type="range"/, '6-F6.9: the confidence control is a slider')
  assert.match(deploy, /onMouseUp=\{\(\) => run\(\)\}/,
    '6-F6.9: releasing the slider re-runs the preview at the new confidence')
  assert.match(deploy, /onKeyUp=\{\(\) => run\(\)\}/,
    '6-F6.9: arrow keys re-run the preview too, so keyboard users see the same result')

  assert.match(deploy, /fd\.append\('confidence', String\(c \/ 100\)\)/,
    '6-F6.9: the 1-99 slider is posted as a 0-1 form field')
  assert.match(deploy, /\/models\/\$\{mid\}\/predict/,
    '6-F6.9: the preview calls the model it selected')

  for (const label of ['cURL', 'Python', 'JavaScript', 'Image URL']) {
    assert.ok(deploy.includes(`label: '${label}'`), `6-F6.9: the ${label} snippet tab survives`)
  }

  assert.match(deploy, /No trained model to deploy yet\./,
    '6-F6.9: the empty state still says what to do first')
  assert.match(deploy, /Running inference…/, '6-F6.9: a run still says it is running')
})

test('test_zone_editor_keeps_polygon_and_line_drawing_and_sends_normalised_points', () => {
  assert.match(zones, /clamp01\(\(e\.clientX - r\.left\) \/ r\.width\), clamp01\(\(e\.clientY - r\.top\) \/ r\.height\)/,
    '6-F6.43: every drawn point is clamped into 0-1 space')
  assert.match(zones, /Math\.round\(n \* 10000\) \/ 10000/,
    '6-F6.43: points are rounded, not left as float noise')

  assert.match(zones, /if \(draft\.length < 6\) return/, '6-F6.43: a zone needs three x/y pairs')
  assert.match(zones, /points: draft\.map\(round4\)/,
    '6-F6.43: the finished polygon is saved as a flat points list')

  assert.match(zones, /const line = \[lineDraft\[0\], lineDraft\[1\], x, y\]\.map\(round4\)/,
    '6-F6.43: a line is exactly [x1, y1, x2, y2] of normalised points')
  assert.match(zones, /onLine\?\.\(line\)/, '6-F6.43: the drawn line reaches the rule that asked for it')
  assert.match(zones, /\{rule\.class\} · \{rule\.direction\}/,
    '6-F6.43: an existing line rule still shows its class and direction')

  assert.match(zones, /api\.updateStream\(ws, project, stream\.id, \{ zones \}\)/,
    '6-F6.43: the edited zones are saved through the streams route')
  assert.match(zones, /disabled=\{usedBy > 0\}/,
    '6-F6.43: a zone a rule points at cannot be deleted from the editor')
})

test('test_workflow_block_fields_stay_per_type', () => {
  const start = blocks.indexOf('export function newBlock')
  const end = blocks.indexOf('function classesText', start)
  assert.ok(start >= 0 && end > start, '6-F6.22: expected the newBlock factory')
  const factory = blocks.slice(start, end)
  const line = (type) => factory.split('\n').find((l) => l.includes(`case '${type}':`)) ?? ''

  for (const type of ['model', 'filter', 'crop', 'ocr', 'rule', 'sink']) {
    assert.notEqual(line(type), '', `6-F6.22: newBlock still builds a ${type} block`)
  }
  assert.match(line('model'), /model_ref: modelRef/, '6-F6.22: a model block needs its ref')
  assert.match(line('filter'), /min_conf:/, '6-F6.22: a filter block needs its confidence floor')
  assert.match(line('crop'), /expand:/, '6-F6.22: a crop block needs its padding')
  assert.match(line('ocr'), /model_ref: modelRef/, '6-F6.22: an OCR block needs its ref')
  assert.match(line('ocr'), /prompt:/, '6-F6.22: an OCR block needs its prompt')
  for (const field of [/kind: 'count'/, /class: ''/, /k: 1/, /op: '>='/]) {
    assert.match(line('rule'), field, `6-F6.22: a count rule needs ${field}`)
  }
  assert.match(line('sink'), /kind: 'response'/, '6-F6.22: a sink block needs its output kind')
})
