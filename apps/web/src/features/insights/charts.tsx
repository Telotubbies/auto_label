// Shared chart plumbing for Insights: ECharts core registration, theme-aware colours,
// the ChartCard frame (chart/table toggle + PNG/CSV/JSON export) and small table helpers.
import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import ReactEChartsCore from 'echarts-for-react/lib/core'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, ScatterChart } from 'echarts/charts'
import { DataZoomComponent, GridComponent, LegendComponent, MarkLineComponent, TooltipComponent, VisualMapComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsType } from 'echarts'
import type { EChartsOption } from 'echarts'
import { AlertTriangle, Download } from 'lucide-react'
import { Button, Card, Dropdown } from '@/components/ui'
import { classColor, useThemePrefs, viridis } from '@/lib/theme'
import { cn } from '@/lib/utils'

echarts.use([
  LineChart, BarChart, ScatterChart,
  GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, DataZoomComponent, VisualMapComponent,
  CanvasRenderer,
])

export type ChartOption = EChartsOption
export type ExportRows = (string | number | null)[][]

// ---------- colour -----------------------------------------------------------
// Theme tokens are oklch(), and viridis() returns space-separated rgb(); zrender's parser
// understands neither, so every colour goes through a 1×1 canvas and comes back as rgb().
const colorCache = new Map<string, string>()
let colorCtx: CanvasRenderingContext2D | null | undefined

/** Normalise any CSS colour (oklch, space-separated rgb, hex) to a zrender-safe rgb() string. */
export function toRgb(css: string): string {
  if (!css) return 'rgb(0, 0, 0)'
  const cached = colorCache.get(css)
  if (cached) return cached
  if (typeof document === 'undefined') return css
  if (colorCtx === undefined) colorCtx = document.createElement('canvas').getContext('2d', { willReadFrequently: true })
  if (!colorCtx) return css
  colorCtx.fillStyle = 'rgb(0, 0, 0)'
  colorCtx.fillStyle = css
  colorCtx.fillRect(0, 0, 1, 1)
  const [r, g, b, a] = colorCtx.getImageData(0, 0, 1, 1).data
  const out = a === 255 ? `rgb(${r}, ${g}, ${b})` : `rgba(${r}, ${g}, ${b}, ${(a / 255).toFixed(3)})`
  colorCache.set(css, out)
  return out
}

export interface ChartTheme {
  font: string
  fg: string; muted: string; border: string; card: string; popover: string
  primary: string; success: string; warning: string; destructive: string; info: string
  dark: boolean
  reducedMotion: boolean
}

/** Subscribes to the theme store and to the root attribute/style writes applyTheme() performs. */
export function useChartTheme(): ChartTheme {
  const prefs = useThemePrefs()
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    const root = document.documentElement
    const observer = new MutationObserver(() => setRevision((r) => r + 1))
    observer.observe(root, { attributes: true, attributeFilter: ['class', 'style', 'data-theme'] })
    const scheme = window.matchMedia('(prefers-color-scheme: dark)')
    const onScheme = () => setRevision((r) => r + 1)
    scheme.addEventListener('change', onScheme)
    return () => { observer.disconnect(); scheme.removeEventListener('change', onScheme) }
  }, [])
  return useMemo(() => {
    const css = getComputedStyle(document.documentElement)
    const v = (name: string, fallback: string) => toRgb(css.getPropertyValue(name).trim() || fallback)
    return {
      font: getComputedStyle(document.body).fontFamily || 'sans-serif',
      fg: v('--foreground', 'CanvasText'),
      muted: v('--muted-foreground', 'GrayText'),
      border: v('--border', 'CanvasText'),
      card: v('--card', 'Canvas'),
      popover: v('--popover', 'Canvas'),
      primary: v('--primary', 'CanvasText'),
      success: v('--success', 'CanvasText'),
      warning: v('--warning', 'CanvasText'),
      destructive: v('--destructive', 'CanvasText'),
      info: v('--info', 'CanvasText'),
      dark: document.documentElement.classList.contains('dark'),
      reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    }
  }, [prefs, revision])
}

// ---------- series palettes --------------------------------------------------
/** Run line styles: colour identifies the metric, the dash pattern identifies the run. */
export type RunDash = 'solid' | 'dashed' | 'dotted' | number[]
const RUN_DASHES: RunDash[] = ['solid', 'dashed', 'dotted', [7, 3, 2, 3], [2, 3], [11, 4]]

export function runDash(i: number): RunDash {
  return RUN_DASHES[Math.abs(i) % RUN_DASHES.length]
}

/** SVG dasharray equivalent for the run-picker swatches. */
export function dashCss(i: number): string | undefined {
  const dash = runDash(i)
  if (dash === 'solid') return undefined
  if (dash === 'dashed') return '5 3'
  if (dash === 'dotted') return '1.5 2.5'
  return Array.isArray(dash) ? dash.join(' ') : undefined
}

/** Model colour for compare overlays and run colour for training overlays. */
export function runColor(i: number, total: number, dark = false): string {
  const start = dark ? 0.4 : 0.18
  const span = dark ? 0.55 : 0.62
  const t = total <= 1 ? start + span / 2 : start + (span * i) / (total - 1)
  return toRgb(viridis(t))
}

// Okabe-Ito order chosen so the first four metrics avoid low-contrast yellow and near-black.
const METRIC_ORDER = [0, 1, 2, 6, 5, 4, 3]

/** Metric colour: class palette for quality/other, viridis for loss curves. */
export function metricColor(i: number, total: number, group: 'quality' | 'loss' | 'other', dark = false): string {
  if (group === 'loss') {
    const start = dark ? 0.42 : 0.16
    const span = dark ? 0.5 : 0.56
    const t = total <= 1 ? start + span / 2 : start + (span * i) / (total - 1)
    return toRgb(viridis(t))
  }
  return toRgb(classColor(METRIC_ORDER[Math.abs(i) % METRIC_ORDER.length]))
}

// ---------- option helpers ---------------------------------------------------
export const axisText = (t: ChartTheme) => ({ color: t.muted, fontSize: 10 })
export const axisLine = (t: ChartTheme) => ({ lineStyle: { color: t.border } })
export const splitLine = (t: ChartTheme) => ({ lineStyle: { color: t.border, opacity: 0.55 } })

export function legendBase(t: ChartTheme) {
  return {
    type: 'scroll' as const, top: 0, left: 0, right: 0, itemWidth: 12, itemHeight: 8, itemGap: 10,
    textStyle: { color: t.muted, fontSize: 10 },
    pageTextStyle: { color: t.muted }, pageIconColor: t.muted, pageIconInactiveColor: t.border,
  }
}

export function chartBase(t: ChartTheme, overrides: ChartOption = {}): ChartOption {
  const { tooltip, ...rest } = overrides
  return {
    backgroundColor: 'transparent',
    animation: !t.reducedMotion,
    animationDuration: 320,
    animationEasing: 'cubicOut',
    textStyle: { fontFamily: t.font, color: t.fg, fontSize: 11 },
    tooltip: {
      confine: true,
      backgroundColor: t.popover,
      borderColor: t.border,
      borderWidth: 1,
      textStyle: { color: t.fg, fontSize: 11 },
      extraCssText: 'border-radius:8px;box-shadow:0 6px 24px rgb(0 0 0 / 0.18);',
      ...tooltip,
    },
    ...rest,
  }
}

/** EMA smoothing for training curves (TensorBoard convention: weight of the previous point). */
export function ema(values: number[], weight: number): number[] {
  if (weight <= 0 || values.length < 2) return values
  const out: number[] = [values[0]]
  for (let i = 1; i < values.length; i++) out.push(weight * out[i - 1] + (1 - weight) * values[i])
  return out
}

// ---------- chart component --------------------------------------------------
const ChartSlot = createContext<{ current: EChartsType | null } | null>(null)

export function EChart({ option, ariaLabel, height = 260, className }: {
  option: ChartOption; ariaLabel: string; height?: number; className?: string
}) {
  const slot = useContext(ChartSlot)
  const instance = useRef<EChartsType | null>(null)
  const labelRef = useRef(ariaLabel)
  const observer = useRef<MutationObserver | null>(null)
  labelRef.current = ariaLabel

  const labelCanvases = (dom: HTMLElement) => {
    dom.querySelectorAll('canvas').forEach((canvas) => {
      canvas.setAttribute('role', 'img')
      canvas.setAttribute('aria-label', labelRef.current)
    })
  }

  useEffect(() => {
    if (instance.current) labelCanvases(instance.current.getDom())
  }, [ariaLabel])

  useEffect(() => () => {
    observer.current?.disconnect()
    if (slot && slot.current === instance.current) slot.current = null
  }, [slot])

  return (
    <div className={cn('w-full', className)} style={{ height }}>
      <ReactEChartsCore
        echarts={echarts}
        option={option}
        notMerge
        lazyUpdate
        style={{ height: '100%', width: '100%' }}
        opts={{ renderer: 'canvas' }}
        onChartReady={(chart) => {
          instance.current = chart
          if (slot) slot.current = chart
          const dom = chart.getDom()
          labelCanvases(dom)
          // ECharts can replace its canvas on re-render; keep the accessible name on the current one.
          observer.current?.disconnect()
          observer.current = new MutationObserver(() => labelCanvases(dom))
          observer.current.observe(dom, { childList: true, subtree: true })
        }}
      />
    </div>
  )
}

// ---------- export -----------------------------------------------------------
function saveFile(name: string, data: BlobPart, type: string) {
  const url = URL.createObjectURL(new Blob([data], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}

export function toCsv(rows: ExportRows): string {
  return rows.map((row) => row.map((cell) => {
    const text = cell == null ? '' : String(cell)
    return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
  }).join(',')).join('\r\n')
}

// ---------- ChartCard --------------------------------------------------------
function ViewToggle({ value, onChange, label }: { value: 'chart' | 'table'; onChange: (v: 'chart' | 'table') => void; label: string }) {
  return (
    <div role="group" aria-label={label} className="flex rounded-md border p-0.5">
      {(['chart', 'table'] as const).map((v) => (
        <button key={v} type="button" aria-pressed={value === v} onClick={() => onChange(v)}
          className={cn('min-h-6 cursor-pointer rounded px-2 py-0.5 text-[11px] transition-colors',
            value === v ? 'bg-accent font-medium text-foreground' : 'text-muted-foreground hover:text-foreground')}>
          {v === 'chart' ? 'Chart' : 'Table'}
        </button>
      ))}
    </div>
  )
}

/**
 * Card frame every chart shares: title + description, chart/table toggle, export menu,
 * an sr-only summary, and a real <table> fallback supplied by the caller.
 */
export function ChartCard({ title, description, summary, exportName, csvRows, jsonData, table, actions, className, children }: {
  title: string
  description?: ReactNode
  summary: string
  exportName: string
  csvRows?: ExportRows
  jsonData?: unknown
  table: ReactNode
  actions?: ReactNode
  className?: string
  children: ReactNode
}) {
  const [view, setView] = useState<'chart' | 'table'>('chart')
  const slot = useRef<EChartsType | null>(null)
  const theme = useChartTheme()

  const download = (kind: 'png' | 'csv' | 'json') => {
    if (kind === 'png') {
      const url = slot.current?.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: theme.card })
      if (!url) return
      const a = document.createElement('a')
      a.href = url
      a.download = `${exportName}.png`
      document.body.appendChild(a)
      a.click()
      a.remove()
      return
    }
    if (kind === 'csv' && csvRows?.length) {
      saveFile(`${exportName}.csv`, toCsv(csvRows), 'text/csv;charset=utf-8')
      return
    }
    if (kind === 'json' && jsonData !== undefined) {
      saveFile(`${exportName}.json`, JSON.stringify(jsonData, null, 2), 'application/json')
    }
  }

  const items = [
    ...(view === 'chart' ? [{ label: 'PNG image', onClick: () => download('png') }] : []),
    ...(csvRows?.length ? [{ label: 'CSV data', onClick: () => download('csv') }] : []),
    ...(jsonData !== undefined ? [{ label: 'JSON data', onClick: () => download('json') }] : []),
  ]

  return (
    <Card className={cn('min-w-0 p-4', className)}>
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold">{title}</h3>
          {description ? <p className="mt-0.5 text-xs text-muted-foreground">{description}</p> : null}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {actions}
          <ViewToggle value={view} onChange={setView} label={`${title} view`} />
          <Dropdown align="right" items={items}
            trigger={<Button variant="ghost" size="icon" className="h-8 w-8" aria-label={`Export ${title}`}><Download className="h-4 w-4" /></Button>} />
        </div>
      </div>
      <figure className="mt-3 min-w-0">
        {view === 'chart'
          ? <ChartSlot.Provider value={slot}>{children}</ChartSlot.Provider>
          : <div className="max-h-80 overflow-auto">{table}</div>}
        <figcaption className="sr-only">{summary}</figcaption>
      </figure>
    </Card>
  )
}

// ---------- tables & states --------------------------------------------------
export function DataTable({ caption, head, rows, rowHeader = true }: {
  caption: ReactNode; head: ReactNode[]; rows: ReactNode[][]; rowHeader?: boolean
}) {
  return (
    <table className="w-full min-w-[320px] text-sm">
      <caption className="pb-2 text-left text-xs text-muted-foreground">{caption}</caption>
      <thead>
        <tr className="border-b text-left text-xs text-muted-foreground">
          {head.map((h, i) => (
            <th key={i} scope="col" className={cn('whitespace-nowrap px-2 py-1.5 font-medium', i > 0 && 'text-right')}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, ri) => (
          <tr key={ri} className="border-b last:border-0">
            {row.map((cell, ci) => ci === 0 && rowHeader
              ? <th key={ci} scope="row" className="px-2 py-1.5 text-left font-normal">{cell}</th>
              : <td key={ci} className={cn('px-2 py-1.5 tabular-nums', ci > 0 && 'text-right')}>{cell}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function ChartSkeleton({ height = 260 }: { height?: number }) {
  return (
    <div role="status" aria-live="polite" className="animate-pulse space-y-3">
      <span className="sr-only">Loading chart</span>
      <div className="h-3 w-40 rounded bg-muted" />
      <div className="rounded bg-muted" style={{ height }} />
    </div>
  )
}

export function PageSkeleton() {
  return (
    <div role="status" aria-live="polite" className="space-y-4">
      <span className="sr-only">Loading insights</span>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => <div key={i} className="h-20 animate-pulse rounded-lg border bg-muted/60" />)}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {[0, 1].map((i) => <div key={i} className="h-72 animate-pulse rounded-lg border bg-muted/60" />)}
      </div>
    </div>
  )
}

export function ErrorState({ title = 'Could not load this view', message, onRetry }: {
  title?: string; message?: string; onRetry?: () => void
}) {
  return (
    <Card role="alert" className="flex flex-col items-start gap-3 border-destructive/40 bg-destructive/5 p-4 sm:flex-row sm:items-center">
      <AlertTriangle className="h-5 w-5 shrink-0 text-destructive" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">{title}</p>
        {message ? <p className="mt-0.5 break-words text-xs text-muted-foreground">{message}</p> : null}
      </div>
      {onRetry ? <Button variant="outline" size="sm" onClick={onRetry}>Retry</Button> : null}
    </Card>
  )
}

/** Small colour swatch + label used by legends and tables. */
export function Swatch({ color, label, dashed }: { color: string; label: ReactNode; dashed?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <svg width={14} height={8} aria-hidden="true" className="shrink-0">
        <line x1={0} y1={4} x2={14} y2={4} stroke={color} strokeWidth={2} strokeDasharray={dashed ? '4 2' : undefined} />
      </svg>
      {label}
    </span>
  )
}
