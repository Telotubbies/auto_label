import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import ReactEChartsCore from 'echarts-for-react/lib/core'
import * as echarts from 'echarts/core'
import type { EChartsOption } from 'echarts'
import { BarChart, HeatmapChart, LineChart, PieChart, ScatterChart } from 'echarts/charts'
import { AriaComponent, AxisPointerComponent, BrushComponent, GridComponent, LegendComponent, ToolboxComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart3, Download, Table2 } from 'lucide-react'
import { Button, Card } from '@/components/ui'
import { toRgb, useChartTheme, type ChartTheme } from '@/features/insights/charts'

// The project-insight pages import these two from here; both are the shared helpers, not copies.
export { toRgb as cssColor, useChartTheme }

// Only the series and components Insights uses, so the lazy route does not ship all of ECharts.
echarts.use([
  BarChart, HeatmapChart, LineChart, PieChart, ScatterChart,
  AriaComponent, AxisPointerComponent, BrushComponent, GridComponent, LegendComponent, ToolboxComponent, TooltipComponent,
  CanvasRenderer,
])

export const tooltipStyle = (t: ChartTheme) => ({
  backgroundColor: t.card, borderColor: t.border, borderWidth: 1, textStyle: { color: t.fg, fontSize: 12 },
})

/** Shared axis chrome; spreads into xAxis / yAxis. */
export const axisChrome = (t: ChartTheme) => ({
  axisLine: { lineStyle: { color: t.border } },
  axisTick: { lineStyle: { color: t.border } },
  axisLabel: { color: t.muted, fontSize: 11 },
  splitLine: { lineStyle: { color: t.border, opacity: 0.45 } },
})

export interface ChartTable {
  caption: string
  columns: string[]
  rows: (string | number)[][]
}

/**
 * Panels build plain option objects; ECharts' inferred unions reject widened string literals
 * such as `type: 'bar'`, so the option stays loosely typed until it crosses the library edge.
 */
export type ChartOption = Record<string, unknown>

export function PanelError({ error }: { error: Error }) {
  return (
    <p role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
      {error.message}
    </p>
  )
}

/** Fixed-height placeholder so a slow aggregate never shifts the layout. */
export function ChartSkeleton({ height = 280 }: { height?: number }) {
  return (
    <Card className="p-4" aria-hidden="true">
      <div className="skeleton h-4 w-40" />
      <div className="skeleton mt-2 h-3 w-64 max-w-full" />
      <div className="skeleton mt-4 w-full" style={{ height }} />
    </Card>
  )
}

function csvCell(value: string | number): string {
  const text = String(value)
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

function downloadCsv(title: string, table: ChartTable): void {
  const body = [table.columns, ...table.rows].map((row) => row.map(csvCell).join(',')).join('\r\n')
  const name = `${title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'chart'}.csv`
  const url = URL.createObjectURL(new Blob([`\uFEFF${body}`], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function DataTable({ table }: { table: ChartTable }) {
  return (
    <table className="w-full text-left text-xs">
      <caption className="px-2 py-1.5 text-left text-[11px] text-muted-foreground">{table.caption}</caption>
      <thead className="sticky top-0 bg-card">
        <tr className="border-b">
          {table.columns.map((c) => <th key={c} scope="col" className="whitespace-nowrap px-2 py-1.5 font-medium text-muted-foreground">{c}</th>)}
        </tr>
      </thead>
      <tbody>
        {table.rows.map((row, i) => (
          <tr key={i} className="border-b last:border-0">
            {row.map((cell, j) => j === 0
              ? <th key={j} scope="row" className="whitespace-nowrap px-2 py-1 text-left font-normal">{cell}</th>
              : <td key={j} className="whitespace-nowrap px-2 py-1 text-right tabular-nums">{cell}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function ChartCard({ title, desc, ariaLabel, option, table, height = 280, actions, footnote, empty, onEvents }: {
  title: string
  desc?: string
  ariaLabel: string
  option: ChartOption
  table: ChartTable
  height?: number
  actions?: ReactNode
  footnote?: ReactNode
  /** Rendered inside the plot area when there is nothing to plot. */
  empty?: ReactNode
  onEvents?: Record<string, (params: unknown) => void>
}) {
  const [view, setView] = useState<'chart' | 'table'>('chart')
  const t = useChartTheme()
  const plot = useRef<HTMLDivElement>(null)
  const chartApi = useRef<{ resize: () => void } | null>(null)
  const tableMode = view === 'table'

  // echarts-for-react only listens to window resize; a Card that narrows (mobile, sidebar
  // collapse) leaves a 0-width canvas without an explicit resize.
  useEffect(() => {
    const el = plot.current
    if (!el || tableMode) return
    const ro = new ResizeObserver(() => chartApi.current?.resize())
    ro.observe(el)
    return () => ro.disconnect()
  }, [tableMode])

  const opt = useMemo<ChartOption>(() => ({
    ...option,
    backgroundColor: 'transparent',
    animation: option.animation === false ? false : !t.reducedMotion,
    textStyle: { ...((option.textStyle ?? {}) as Record<string, unknown>), fontFamily: t.font, color: t.fg },
    aria: { enabled: true, description: ariaLabel },
  }), [option, ariaLabel, t.reducedMotion, t.font, t.fg])
  return (
    <Card className="flex min-w-0 flex-col p-4">
      <div className="flex flex-wrap items-start justify-between gap-x-2 gap-y-1.5">
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold">{title}</h3>
          {desc && <p className="mt-0.5 text-xs text-muted-foreground">{desc}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {actions}
          <Button variant="ghost" size="sm" onClick={() => downloadCsv(title, table)}
            aria-label={`Download ${title} as CSV`} title="Download CSV">
            <Download className="h-3.5 w-3.5" aria-hidden="true" /> CSV
          </Button>
          <Button variant="outline" size="sm" onClick={() => setView(tableMode ? 'chart' : 'table')}
            aria-label={tableMode ? 'Show chart view' : 'Show the same numbers as a table'}
            title={tableMode ? 'Show the chart' : 'Show the same numbers as a table'}>
            {tableMode ? <BarChart3 className="h-3.5 w-3.5" aria-hidden="true" /> : <Table2 className="h-3.5 w-3.5" aria-hidden="true" />}
            {tableMode ? 'Chart' : 'Table'}
          </Button>
        </div>
      </div>
      <div className="mt-3" style={{ height }}>
        {tableMode ? (
          <div className="h-full overflow-auto rounded-md border">
            <DataTable table={table} />
          </div>
        ) : empty ? (
          <div className="flex h-full items-center justify-center rounded-md border border-dashed px-4 text-center text-sm text-muted-foreground">{empty}</div>
        ) : (
          <div ref={plot} tabIndex={0} role="img" aria-label={ariaLabel} className="h-full w-full rounded-md">
            <ReactEChartsCore echarts={echarts} option={opt as unknown as EChartsOption} notMerge lazyUpdate
              opts={{ renderer: 'canvas' }} onEvents={onEvents}
              onChartReady={(chart: { resize: () => void }) => { chartApi.current = chart; chart.resize() }}
              style={{ height: '100%', width: '100%' }} />
          </div>
        )}
      </div>
      {footnote && <p className="mt-2 text-xs text-muted-foreground">{footnote}</p>}
    </Card>
  )
}
