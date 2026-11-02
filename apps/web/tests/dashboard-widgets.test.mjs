// Pure rules behind the dashboard builder. Runs with Node's test runner:
//   node --test tests/dashboard-widgets.test.mjs   (from apps/web)
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  buildWidgetOption,
  dashboardCsv,
  defaultWidget,
  groupOrder,
  moveWidget,
  pivotRows,
  validateWidgetDraft,
  widgetCsv,
} from '../src/features/dashboards/widgetModel.ts'

const spec = (over = {}) => ({
  id: 'w1',
  title: 'Annotations per class',
  source: 'dataset',
  measure: 'annotations',
  dimension: 'class',
  dimension2: null,
  chart: 'bar',
  filters: {},
  w: 6,
  ...over,
})

const data = (rows, over = {}) => ({
  source: 'dataset',
  measure: 'annotations',
  dimension: 'class',
  dimension2: null,
  unit: 'annotations',
  rows,
  total: rows.reduce((n, r) => n + r.value, 0),
  filters: {},
  ...over,
})

const theme = {
  fg: 'rgb(1, 1, 1)', muted: 'rgb(2, 2, 2)', border: 'rgb(3, 3, 3)',
  primary: 'rgb(4, 4, 4)', popover: 'rgb(9, 9, 9)',
}
const colorAt = (i) => `rgb(${10 + i}, 20, 30)`

const row = (key, value, group = null) => ({ key, group, value })

test('pivotRows orders categories by value, largest first, and keeps ties alphabetical', () => {
  const pivot = pivotRows(data([row('person', 3), row('car', 5), row('bus', 3)]), 'class')
  assert.deepEqual(pivot.keys, ['car', 'bus', 'person'])
  assert.deepEqual(pivot.groups, [null])
  assert.equal(pivot.valueOf('person', null), 3)
})

test('pivotRows keeps day and hour keys in chronological order', () => {
  const pivot = pivotRows(data([row('2026-11-02', 1), row('2026-10-31', 4)], { dimension: 'day' }), 'day')
  assert.deepEqual(pivot.keys, ['2026-10-31', '2026-11-02'])
  const hourly = pivotRows(data([row('09', 1), row('08', 4)], { dimension: 'hour' }), 'hour')
  assert.deepEqual(hourly.keys, ['08', '09'])
})

test('groupOrder uses train, valid, test for splits and alphabetical elsewhere', () => {
  assert.deepEqual(groupOrder(['test', 'train', 'valid']), ['train', 'valid', 'test'])
  assert.deepEqual(groupOrder(['yolo', 'sam3', 'human']), ['human', 'sam3', 'yolo'])
})

test('a bar widget yields one series per group with keys in pivot order', () => {
  const option = buildWidgetOption(spec(), data([
    row('person', 3, 'train'), row('person', 1, 'test'), row('car', 2, 'train'),
  ]), theme, colorAt)
  assert.equal(option.xAxis.data.length, 2)
  assert.deepEqual(option.xAxis.data, ['person', 'car'])
  assert.deepEqual(option.series.map((s) => s.name), ['train', 'test'])
  assert.deepEqual(option.series.map((s) => s.data), [[3, 2], [1, 0]])
  assert.equal(option.series[0].itemStyle.color, 'rgb(10, 20, 30)')
})

test('a single-series class bar gives each class its palette colour', () => {
  const option = buildWidgetOption(spec(), data([row('person', 3), row('car', 5)]), theme, colorAt)
  assert.deepEqual(option.series[0].data, [
    { value: 5, itemStyle: { color: 'rgb(10, 20, 30)' } },   // car sorts first
    { value: 3, itemStyle: { color: 'rgb(11, 20, 30)' } },   // person
  ])
})

test('a heatmap widget yields x/y triples with a zero cell for every pair', () => {  const option = buildWidgetOption(spec({ chart: 'heatmap', dimension2: 'split' }), data([
    row('person', 3, 'train'), row('car', 2, 'test'),
  ], { dimension2: 'split' }), theme, colorAt)
  assert.deepEqual(option.xAxis.data, ['person', 'car'])
  assert.deepEqual(option.yAxis.data, ['train', 'test'])
  assert.equal(option.series[0].type, 'heatmap')
  assert.deepEqual(option.series[0].data, [
    [0, 0, 3], [1, 0, 0], [0, 1, 0], [1, 1, 2],
  ])
  assert.ok(option.visualMap)
})

test('a donut is a pie with an inner radius, and a line plots categories in order', () => {
  const donut = buildWidgetOption(spec({ chart: 'donut' }), data([row('person', 3)]), theme, colorAt)
  assert.equal(donut.series[0].type, 'pie')
  assert.notEqual(donut.series[0].radius[0], '0%')
  const line = buildWidgetOption(
    spec({ chart: 'line', dimension: 'day' }),
    data([row('2026-11-02', 1), row('2026-10-31', 4)], { dimension: 'day' }),
    theme,
    colorAt,
  )
  assert.equal(line.series[0].type, 'line')
  assert.deepEqual(line.xAxis.data, ['2026-10-31', '2026-11-02'])
  assert.deepEqual(line.series[0].data, [4, 1])
})

test('widget tooltips pair the popover surface with foreground text', () => {
  for (const chart of ['bar', 'pie', 'heatmap']) {
    const data2 = chart === 'heatmap' ? { dimension2: 'split' } : {}
    const option = buildWidgetOption(
      spec({ chart, dimension2: chart === 'heatmap' ? 'split' : null }),
      data([row('person', 3, chart === 'heatmap' ? 'train' : null)], data2),
      theme,
      colorAt,
    )
    assert.equal(option.tooltip.backgroundColor, theme.popover, chart)
    assert.equal(option.tooltip.textStyle.color, theme.fg, chart)
  }
})

test('widgetCsv always emits key, group, value rows in displayed order', () => {
  const rows = widgetCsv(spec(), data([row('person', 3), row('car', 5)]))
  assert.deepEqual(rows, [
    ['Key', 'Group', 'Value', 'Unit'],
    ['car', '', 5, 'annotations'],
    ['person', '', 3, 'annotations'],
  ])
  const combined = dashboardCsv([
    { title: 'By class', data: data([row('person', 3)]) },
    { title: 'By split', data: data([row('train', 7)], { dimension: 'split' }) },
  ])
  assert.deepEqual(combined[0], ['Widget', 'Key', 'Group', 'Value', 'Unit'])
  assert.deepEqual(combined.slice(1), [
    ['By class', 'person', '', 3, 'annotations'],
    ['By split', 'train', '', 7, 'annotations'],
  ])
})

test('defaultWidget picks a measure and dimension the source supports', () => {
  assert.deepEqual(
    { measure: defaultWidget('dataset').measure, dimension: defaultWidget('dataset').dimension, chart: defaultWidget('dataset').chart },
    { measure: 'annotations', dimension: 'class', chart: 'bar' },
  )
  assert.deepEqual(
    { measure: defaultWidget('model').measure, dimension: defaultWidget('model').dimension },
    { measure: 'ap', dimension: 'class' },
  )
  assert.deepEqual(
    { measure: defaultWidget('streams').measure, dimension: defaultWidget('streams').dimension },
    { measure: 'events', dimension: 'rule' },
  )
  assert.equal(defaultWidget('version').filters.version, '')
})

test('validateWidgetDraft catches the cases the API would reject', () => {
  assert.deepEqual(validateWidgetDraft(spec()), [])
  assert.match(validateWidgetDraft(spec({ title: ' ' }))[0], /title/i)
  assert.match(validateWidgetDraft(spec({ chart: 'heatmap', dimension2: null }))[0], /second dimension/i)
  assert.match(
    validateWidgetDraft(spec({ source: 'model', measure: 'ap', filters: { model: 'm' }, chart: 'heatmap', dimension2: 'split' }))[0],
    /second dimension/i,
  )
  assert.match(
    validateWidgetDraft(spec({ chart: 'kpi' }))[0],
    /KPI/i,
  )
  assert.match(
    validateWidgetDraft(spec({ source: 'model', measure: 'ap', filters: {} }))[0],
    /model/i,
  )
  assert.match(
    validateWidgetDraft(spec({ source: 'version', filters: {} }))[0],
    /version/i,
  )
  assert.match(validateWidgetDraft(spec({ source: 'dataset', measure: 'ap' }))[0], /measure/i)
})

test('moveWidget reorders without mutating and clamps at both ends', () => {
  const list = [spec({ id: 'a' }), spec({ id: 'b' }), spec({ id: 'c' })]
  assert.deepEqual(moveWidget(list, 2, -1).map((w) => w.id), ['a', 'c', 'b'])
  assert.deepEqual(moveWidget(list, 0, -1).map((w) => w.id), ['a', 'b', 'c'])
  assert.deepEqual(moveWidget(list, 2, 1).map((w) => w.id), ['a', 'b', 'c'])
  assert.deepEqual(list.map((w) => w.id), ['a', 'b', 'c'])
})
