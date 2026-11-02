/** Pure presentation rules for the dashboard builder.
 *
 * The API returns uniform `{key, group, value}` rows from one aggregation engine. Everything here turns
 * those rows into chart options and export tables without touching the DOM, so the rules are unit-tested
 * with Node's test runner. Colours arrive as callbacks so this module never hard-codes a palette.
 */

export type WidgetSource = 'dataset' | 'version' | 'model' | 'streams'
export type ChartKind = 'bar' | 'line' | 'scatter' | 'heatmap' | 'pie' | 'donut' | 'table' | 'kpi'

export interface WidgetFilters { [key: string]: string | number | undefined }

export interface WidgetSpec {
  id: string
  title: string
  source: WidgetSource
  measure: string
  dimension: string
  dimension2: string | null
  chart: ChartKind
  filters: WidgetFilters
  w: number
}

export interface WidgetRow { key: string; group: string | null; value: number }

export interface WidgetData {
  source: WidgetSource
  measure: string
  dimension: string
  dimension2: string | null
  unit: string
  rows: WidgetRow[]
  total: number
  filters: WidgetFilters
}

export interface WidgetTheme { fg: string; muted: string; border: string; primary: string }

export type WidgetOption = Record<string, unknown>

export const WIDGET_SIZES = [3, 4, 6, 12] as const
export const MAX_WIDGETS = 24

export const MEASURES: Record<WidgetSource, string[]> = {
  dataset: ['annotations', 'images'],
  version: ['annotations', 'images'],
  model: ['ap'],
  streams: ['events', 'dwell_seconds'],
}

export const DIMENSIONS: Record<WidgetSource, string[]> = {
  dataset: ['class', 'split', 'source', 'batch', 'tag', 'none'],
  version: ['class', 'split', 'source', 'batch', 'tag', 'none'],
  model: ['class', 'none'],
  streams: ['day', 'hour', 'rule', 'zone', 'class', 'stream', 'none'],
}

export const CHARTS: ChartKind[] = ['bar', 'line', 'scatter', 'heatmap', 'pie', 'donut', 'table', 'kpi']

const SPLITS = ['train', 'valid', 'test']
const TIME_DIMENSIONS = new Set(['day', 'hour'])

const groupLabel = (group: string | null) => group ?? 'Total'

/** Display order for a dimension's members: splits follow their canonical order, everything else sorts. */
export function groupOrder(groups: (string | null)[]): (string | null)[] {
  const unique = [...new Set(groups)]
  const named = unique.filter((g): g is string => g !== null)
  if (named.length && named.every((g) => SPLITS.includes(g))) {
    return SPLITS.filter((s) => named.includes(s))
  }
  return unique.sort((a, b) => String(a ?? '').localeCompare(String(b ?? '')))
}

interface Pivot {
  keys: string[]
  groups: (string | null)[]
  valueOf: (key: string, group: string | null) => number
  has: (key: string, group: string | null) => boolean
}

/** Rows to a category × group matrix; time dimensions stay chronological, other dimensions rank by value. */
export function pivotRows(data: WidgetData, dimension: string): Pivot {
  const totals = new Map<string, number>()
  const cells = new Map<string, number>()
  const groups: (string | null)[] = []
  for (const row of data.rows) {
    totals.set(row.key, (totals.get(row.key) ?? 0) + row.value)
    const cell = `${row.key}\u0000${row.group ?? ''}`
    cells.set(cell, (cells.get(cell) ?? 0) + row.value)
    if (!groups.includes(row.group)) groups.push(row.group)
  }
  const keys = [...totals.keys()]
  if (TIME_DIMENSIONS.has(dimension)) {
    keys.sort((a, b) => a.localeCompare(b))
  } else if (dimension === 'split') {
    keys.sort((a, b) => SPLITS.indexOf(a) - SPLITS.indexOf(b))
  } else {
    keys.sort((a, b) => (totals.get(b) ?? 0) - (totals.get(a) ?? 0) || a.localeCompare(b))
  }
  const ordered = groups.length ? groupOrder(groups) : [null]
  const key = (key: string, group: string | null) => `${key}\u0000${group ?? ''}`
  return {
    keys,
    groups: ordered,
    valueOf: (k, g) => cells.get(key(k, g)) ?? 0,
    has: (k, g) => cells.has(key(k, g)),
  }
}

const axis = (theme: WidgetTheme) => ({
  axisLabel: { color: theme.muted, fontSize: 10, hideOverlap: true },
  axisLine: { lineStyle: { color: theme.border } },
  splitLine: { lineStyle: { color: theme.border, opacity: 0.55 } },
})

function tooltip(theme: WidgetTheme, trigger: 'axis' | 'item') {
  return {
    trigger,
    confine: true,
    backgroundColor: theme.primary,
    borderColor: theme.border,
    borderWidth: 1,
    textStyle: { color: theme.fg, fontSize: 11 },
  }
}

/** ECharts option for a widget, excluding the frame theme that the card applies. */
export function buildWidgetOption(
  spec: WidgetSpec,
  data: WidgetData,
  theme: WidgetTheme,
  colorAt: (i: number) => string,
  heatColors?: string[],
): WidgetOption {
  const pivot = pivotRows(data, spec.dimension)
  const chart = spec.chart
  // A class breakdown keeps one colour per class, matching the class palette used elsewhere.
  const classKeys = spec.dimension === 'class' ? [...pivot.keys].sort((a, b) => a.localeCompare(b)) : []
  const colorForKey = (key: string, fallback: number) =>
    spec.dimension === 'class' ? colorAt(Math.max(0, classKeys.indexOf(key))) : colorAt(fallback)

  if (chart === 'table' || chart === 'kpi') return { series: [] }

  if (chart === 'pie' || chart === 'donut') {
    const slices = pivot.keys.map((key, i) => ({
      name: key,
      value: data.rows.filter((r) => r.key === key).reduce((n, r) => n + r.value, 0),
      itemStyle: { color: colorForKey(key, i) },
    }))
    return {
      tooltip: tooltip(theme, 'item'),
      legend: { type: 'scroll', bottom: 0, textStyle: { color: theme.muted, fontSize: 10 } },
      series: [{
        type: 'pie',
        radius: chart === 'donut' ? ['42%', '64%'] : ['0%', '64%'],
        center: ['50%', '46%'],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: theme.primary, borderWidth: 1 },
        label: { color: theme.fg, fontSize: 10 },
        data: slices,
      }],
    }
  }

  if (chart === 'heatmap') {
    const max = Math.max(0, ...data.rows.map((r) => r.value))
    const cells: [number, number, number][] = []
    pivot.groups.forEach((group, y) => {
      pivot.keys.forEach((key, x) => {
        cells.push([x, y, pivot.valueOf(key, group)])
      })
    })
    return {
      tooltip: tooltip(theme, 'item'),
      grid: { left: 8, right: 16, top: 20, bottom: 42, containLabel: true },
      xAxis: { type: 'category', data: pivot.keys, ...axis(theme), splitArea: { show: false } },
      yAxis: { type: 'category', data: pivot.groups.map(groupLabel), ...axis(theme), splitArea: { show: false } },
      // Narrow cards need angled column labels; at desktop width they read horizontally.
      media: [{
        query: { maxWidth: 640 },
        option: {
          grid: { bottom: 78 },
          xAxis: { axisLabel: { rotate: 45, interval: 0, width: 90, overflow: 'truncate' } },
        },
      }],
      visualMap: {
        min: 0,
        max: max || 1,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: 0,
        itemHeight: 70,
        textStyle: { color: theme.muted, fontSize: 10 },
        inRange: { color: heatColors?.length ? heatColors : [colorAt(0), colorAt(1)] },
      },
      series: [{ type: 'heatmap', data: cells, emphasis: { itemStyle: { borderColor: theme.fg, borderWidth: 1 } } }],
    }
  }

  const series = pivot.groups.map((group, gi) => {
    const values = pivot.keys.map((key) => pivot.valueOf(key, group))
    const color = colorAt(gi)
    const name = groupLabel(group)
    if (chart === 'line') {
      return {
        type: 'line', name, data: values, showSymbol: pivot.keys.length <= 31, symbolSize: 3,
        lineStyle: { width: 1.8, color }, itemStyle: { color }, emphasis: { focus: 'series' },
      }
    }
    if (chart === 'scatter') {
      return {
        type: 'scatter', name, symbolSize: 8,
        itemStyle: { color, opacity: 0.75 },
        data: values.map((value, x) => [x, value]),
      }
    }
    if (pivot.groups.length === 1 && spec.dimension === 'class') {
      return {
        type: 'bar', name, barMaxWidth: 34, itemStyle: { borderRadius: [3, 3, 0, 0] },
        data: pivot.keys.map((key) => ({
          value: pivot.valueOf(key, group),
          itemStyle: { color: colorForKey(key, gi) },
        })),
      }
    }
    return {
      type: 'bar', name, barMaxWidth: 34,
      itemStyle: { color, borderRadius: [3, 3, 0, 0] },
      data: values,
    }
  })

  return {
    tooltip: tooltip(theme, chart === 'scatter' ? 'item' : 'axis'),
    legend: pivot.groups.length > 1
      ? { type: 'scroll', top: 0, left: 0, right: 0, textStyle: { color: theme.muted, fontSize: 10 } }
      : undefined,
    grid: { left: 8, right: 16, top: pivot.groups.length > 1 ? 30 : 20, bottom: 36, containLabel: true },
    xAxis: {
      type: 'category',
      data: pivot.keys,
      ...axis(theme),
      axisLabel: { ...axis(theme).axisLabel, interval: 0, rotate: pivot.keys.length > 8 ? 28 : 0, width: 110, overflow: 'truncate' },
    },
    yAxis: { type: 'value', ...axis(theme) },
    series,
  }
}

/** Table/CSV rows in the order the chart displays them. */
export function widgetCsv(spec: WidgetSpec, data: WidgetData): (string | number | null)[][] {
  const pivot = pivotRows(data, spec.dimension)
  const rows: (string | number | null)[][] = [['Key', 'Group', 'Value', 'Unit']]
  for (const key of pivot.keys) {
    for (const group of pivot.groups) {
      if (!pivot.has(key, group)) continue
      rows.push([key, group ?? '', pivot.valueOf(key, group), data.unit])
    }
  }
  return rows
}

/** One CSV for every widget on a dashboard. */
export function dashboardCsv(items: { title: string; data: WidgetData }[]): (string | number | null)[][] {
  const rows: (string | number | null)[][] = [['Widget', 'Key', 'Group', 'Value', 'Unit']]
  for (const item of items) {
    const spec = { dimension: item.data.dimension } as WidgetSpec
    for (const row of widgetCsv(spec, item.data).slice(1)) {
      rows.push([item.title, ...row])
    }
  }
  return rows
}

/** A new widget starts on a measure/dimension pair the chosen source actually supports. */
export function defaultWidget(source: WidgetSource): WidgetSpec {
  const base: WidgetSpec = {
    id: '',
    title: '',
    source,
    measure: MEASURES[source][0],
    dimension: DIMENSIONS[source][0],
    dimension2: null,
    chart: 'bar',
    filters: {},
    w: 6,
  }
  if (source === 'version') base.filters = { version: '' }
  if (source === 'model') base.filters = { model: '' }
  if (source === 'streams') base.dimension = 'rule'
  return base
}

/** Client-side guard mirroring the API validation, so the editor explains a bad widget before saving. */
export function validateWidgetDraft(spec: WidgetSpec): string[] {
  const errors: string[] = []
  if (!spec.title.trim()) errors.push('Give the widget a title.')
  if (!MEASURES[spec.source]?.includes(spec.measure)) {
    errors.push(`${spec.source} does not support the "${spec.measure}" measure.`)
  }
  if (!DIMENSIONS[spec.source]?.includes(spec.dimension)) {
    errors.push(`${spec.source} does not support the "${spec.dimension}" dimension.`)
  }
  if (spec.dimension2) {
    if (!DIMENSIONS[spec.source]?.includes(spec.dimension2)) {
      errors.push(`The second dimension "${spec.dimension2}" does not belong to ${spec.source}.`)
    } else if (spec.dimension2 === spec.dimension) {
      errors.push('The second heatmap dimension must differ from the first.')
    }
  }
  if (spec.chart === 'heatmap' && !spec.dimension2) {
    errors.push('A heatmap needs a second dimension.')
  }
  if (spec.chart === 'kpi' && spec.dimension !== 'none') {
    errors.push('A KPI shows one total; choose the total dimension.')
  }
  if (!CHARTS.includes(spec.chart)) errors.push('Choose a supported chart type.')
  if (spec.source === 'version' && !spec.filters.version) {
    errors.push('Choose a version for the version source.')
  }
  if (spec.source === 'model' && !spec.filters.model) {
    errors.push('Choose a model for the model source.')
  }
  return errors
}

/** Reorder a widget in place by one slot; both ends clamp and the input array is never mutated. */
export function moveWidget<T>(widgets: T[], index: number, delta: number): T[] {
  const target = Math.min(widgets.length - 1, Math.max(0, index + delta))
  if (target === index) return [...widgets]
  const next = [...widgets]
  const [item] = next.splice(index, 1)
  next.splice(target, 0, item)
  return next
}

/** Drop empty filter values; the API treats absent and empty the same, but a stable key matters for caching. */
export function cleanFilters(filters: WidgetFilters): WidgetFilters {
  return Object.fromEntries(
    Object.entries(filters).filter(([, value]) => value !== '' && value !== undefined),
  )
}
