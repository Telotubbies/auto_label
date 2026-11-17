// Parity guard, area 5: model table, train entry and evaluation panel.
// Pins the HAVE rows 5-F5.1, 5-F5.16, 5-F5.38, 5-F5.23, 5-F5.18 and 5-F5.44 in the source that
// renders them, so a train/registry/eval card cannot drop a column, a metric key or an affordance.
// Runs with the built-in Node test runner: node --test tests/parity-guard-area5.test.mjs  (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8')
const models = read('../src/features/project/Models.tsx')
const evalPanel = read('../src/features/evaluation/EvalPanel.tsx')
const train = read('../src/features/project/Train.tsx')

/** The body of one top-level component, so a key found elsewhere cannot satisfy the guard. */
function component(src, name, next) {
  const start = src.indexOf(`function ${name}`)
  const end = next ? src.indexOf(next, start) : src.length
  assert.ok(start >= 0 && end > start, `expected the ${name} component`)
  return src.slice(start, end)
}

test('test_model_table_keeps_the_version_latency_and_licence_columns', () => {
  const leaderboard = component(models, 'LeaderboardTab', 'function Charts')

  assert.match(leaderboard, />Version<\/th>/, '5-F5.1: the model table needs its Version column')
  assert.match(leaderboard, /\{r\.version == null \? '—' : `v\$\{r\.version\}`\}/,
    '5-F5.1: the Version cell prints the version number')
  assert.match(leaderboard, /r\.latency_ms/, '5-F5.38: the row carries a latency cell')
  assert.match(leaderboard, /Latency<\/th>/, '5-F5.38: the latency cell is labelled')

  assert.match(models, /Licence: \{m\.license\}/, '5-F5.38: each model shows its licence')

  const charts = component(models, 'Charts', 'export default function Models')
  for (const key of ['metrics/mAP50', 'metrics/mAP50-95', 'metrics/precision', 'metrics/recall']) {
    assert.ok(charts.includes(key), `5-F5.16: the training graphs read ${key}`)
  }
})

test('test_evaluation_panel_keeps_the_threshold_slider_and_the_gt_vs_prediction_labels', () => {
  assert.match(evalPanel, /type="range"/, '5-F5.23: the threshold control is a slider')
  assert.match(evalPanel, /aria-label="Confidence threshold"/,
    '5-F5.23: the slider is announced as the confidence threshold')

  assert.match(evalPanel, /label="Ground truth"/, '5-F5.23: the ground-truth panel survives')
  assert.match(evalPanel, /label="Prediction"/, '5-F5.23: the prediction panel survives')
  assert.doesNotMatch(evalPanel, /label="(Truth|Pred)"/,
    '5-F5.23: the panels keep their full names rather than an abbreviated label')

  assert.match(evalPanel, /ev\.confusion\.labels/, '5-F5.23: the labels come from the stored matrix')
  assert.match(evalPanel, /ev\.confusion\.matrix/, '5-F5.23: the counts come from the stored matrix')
  assert.match(evalPanel, /ev\.confusion\.images/, '5-F5.23: the cell drill-down reads its images')
  assert.match(evalPanel, /ev\.detections/, '5-F5.23: the slider re-derives from the per-image detections')
})

test('test_train_keeps_the_resume_and_family_reason_affordances', () => {
  assert.match(train, /resume_from: resume_from \|\| null/,
    '5-F5.18: Start sends the chosen checkpoint as resume_from')
  assert.match(train, /const resumable = .*m\.status === 'ready'/,
    '5-F5.18: only ready models can be continued from')

  const family = train.slice(train.indexOf('export default function Train'))
  assert.match(family, /disabled=\{!x\.available\}/, '5-F5.44: a blocked family is a disabled option')
  assert.match(family, /\{!x\.available && <div[^>]*>\{x\.reason\}<\/div>\}/,
    '5-F5.44: a blocked family still prints the reason it cannot run')
})
