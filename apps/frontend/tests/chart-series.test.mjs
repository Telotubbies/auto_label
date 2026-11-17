// T-523 (UI audit A6/A7): a chart with no series says so instead of drawing empty axes, an
// all-zero metered period is not a flat zero line, and every legend key reads at 12 px in the
// foreground token with colours from the shipped class palette.
//   node --test tests/chart-series.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { registerHooks } from 'node:module'

// lib/theme.ts imports @material/material-color-utilities, whose published ESM uses extensionless
// internal paths Node cannot resolve. Stub only that colour engine so the real classColor() and the
// real chartSeries.ts load; no code under test is mocked.
const stub = 'data:text/javascript,' + encodeURIComponent(
  'export const Hct=0, MaterialDynamicColors=0, SchemeExpressive=0, SchemeTonalSpot=0, SchemeVibrant=0, TonalPalette=0, argbFromHex=0')
registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === '@material/material-color-utilities') return { url: stub, shortCircuit: true }
    return nextResolve(specifier, context)
  },
})

const { seriesColor, legendProps, hasSeries } = await import('../src/lib/chartSeries.ts')
const { classColor } = await import('../src/lib/theme.ts')

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8')
const emptyUrl = new URL('../src/components/charts/SeriesEmpty.tsx', import.meta.url)
const models = read('../src/features/project/Models.tsx')
const settings = read('../src/features/settings/Settings.tsx')

test('test_empty_series_renders_a_sentence_not_axes', () => {
  assert.ok(existsSync(emptyUrl), 'SeriesEmpty.tsx exists')
  const empty = readFileSync(emptyUrl, 'utf8')
  assert.doesNotMatch(empty, /<svg|from 'recharts'|ResponsiveContainer/, 'it draws no axes or chart')
  assert.match(empty, /\{title\}/, 'it renders the sentence it is given')
  assert.match(empty, /height/, 'it keeps the height of the chart it replaces')
  assert.match(models, /No loss recorded for this run\./, 'the Loss card says what is missing')
  assert.match(models, /loss\.length/, 'the Loss card branches on the series it actually has')
})

test('test_series_colour_comes_from_the_palette', () => {
  const values = Array.from({ length: 8 }, (_, i) => seriesColor(i))
  assert.equal(new Set(values).size, 8, 'eight series get eight distinct colours')
  values.forEach((colour, i) => assert.equal(colour, classColor(i), `series ${i} is the shipped palette colour`))
  assert.doesNotMatch(models, /#[0-9a-f]{6}/i, 'Models.tsx writes no colour literal of its own')
})

test('test_legend_style_is_shared', () => {
  const key = legendProps.formatter('mAP50')
  assert.equal(key.type, 'span', 'a legend key is a span')
  assert.match(key.props.className, /(^|\s)text-xs(\s|$)/, 'keys are text-xs')
  assert.match(key.props.className, /(^|\s)text-foreground(\s|$)/, 'keys use the foreground token')
  for (const [name, src] of [['Models', models], ['Settings', settings]]) {
    assert.match(src, /\.\.\.legendProps/, `${name} spreads the one shared legend object`)
    assert.doesNotMatch(src, /wrapperStyle=\{\{ fontSize: 11 \}/, `${name} no longer sets an 11 px legend`)
  }
})

test('test_zero_usage_is_not_a_flat_line', () => {
  assert.equal(hasSeries([0, 0, 0]), false, 'a period of zeros has no series')
  assert.equal(hasSeries([0, 1, 0]), true, 'one non-zero day is a series')
  assert.match(settings, /No metered usage in this period\./, 'the metered card names the empty period')
  assert.match(settings, /hasSeries\(/, 'the metered branch asks the shared helper')
  assert.match(settings, /<SeriesEmpty/, 'the metered card renders the empty component, not a flat line')
})
