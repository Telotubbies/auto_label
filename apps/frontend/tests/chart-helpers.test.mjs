// One theme reader and one colour normaliser for every chart (T-059). The five project-insight
// pages keep their colours, so this pins where the colour code lives, not how it looks.
//   node --test tests/chart-helpers.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8')
const chart = read('../src/features/project/insights/Chart.tsx')
const charts = read('../src/features/insights/charts.tsx')

const SRC = fileURLToPath(new URL('../src/', import.meta.url))

function tsxFiles(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = join(dir, entry.name)
    if (entry.isDirectory()) return tsxFiles(full)
    return entry.name.endsWith('.tsx') ? [full] : []
  })
}

test('test_one_theme_reader', () => {
  for (const local of [/function cssColor/, /function useChartTheme/, /interface ChartTheme/, /type ChartTheme\s*=/]) {
    assert.doesNotMatch(chart, local, `${local} still lives in Chart.tsx; the one reader is insights/charts.tsx`)
  }
  const shared = [...chart.matchAll(/(?:import|export)\s*\{([^}]*)\}\s*from\s*'@\/features\/insights\/charts'/gs)]
    .flatMap((m) => m[1].split(',').map((name) => name.trim().replace(/^type\s+/, '')))
    .filter(Boolean)
  for (const name of ['toRgb', 'useChartTheme', 'ChartTheme']) {
    assert.ok(shared.includes(name), `Chart.tsx takes ${name} from @/features/insights/charts`)
  }
  // The project-insight pages import cssColor and useChartTheme from ./Chart, so the shared helpers
  // answer to those names as aliases. A second copy is what this test exists to prevent.
  assert.match(chart, /export\s*\{\s*toRgb as cssColor, useChartTheme\s*\}/,
    'cssColor and useChartTheme are the shared helpers under their old names')
})

test('test_no_component_passes_the_removed_props', () => {
  const hits = tsxFiles(SRC).filter((file) => /rowHeader=|dashed=/.test(readFileSync(file, 'utf8')))
  assert.deepEqual(hits, [], 'no component passes DataTable.rowHeader or Swatch.dashed')
  assert.doesNotMatch(charts, /rowHeader/, 'DataTable no longer takes a rowHeader prop')
  const swatch = charts.match(/function Swatch\(\{([^}]*)\}/)
  assert.ok(swatch, 'Swatch is still exported from insights/charts.tsx')
  assert.doesNotMatch(swatch[1], /dashed/, 'Swatch no longer takes a dashed prop')
})

test('test_both_chart_files_agree_on_the_token_names', () => {
  const declared = charts.match(/export interface ChartTheme \{([\s\S]*?)\n\}/)
  assert.ok(declared, 'insights/charts.tsx declares the one ChartTheme')
  const fields = new Set([...declared[1].matchAll(/([A-Za-z_]\w*)\??:/g)].map((m) => m[1]))
  for (const name of ['font', 'fg', 'muted', 'border', 'card', 'primary', 'success', 'warning', 'info', 'destructive']) {
    assert.ok(fields.has(name), `ChartTheme declares ${name}`)
  }
  const used = [...new Set([...chart.matchAll(/\bt\.([A-Za-z_]\w*)/g)].map((m) => m[1]))]
  assert.ok(used.length > 0, 'Chart.tsx still reads chart theme tokens')
  for (const name of used) {
    assert.ok(fields.has(name), `Chart.tsx reads t.${name}, which the shared ChartTheme must declare`)
  }
})
