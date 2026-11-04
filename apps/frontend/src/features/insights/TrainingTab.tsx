import { useMemo, useState } from 'react'
import { ChartLine } from 'lucide-react'
import { Card, EmptyState, Switch } from '@/components/ui'
import type { TrainingMetricKey, TrainingRun } from '@/lib/types'
import { cn } from '@/lib/utils'
import {
  ChartCard, ChartSkeleton, DataTable, EChart, ErrorState, PageSkeleton, axisLine, axisText, chartBase, dashCss, ema,
  legendBase, metricColor, runDash, splitLine, useChartTheme, type ChartOption, type ChartTheme, type ExportRows,
} from './charts'
import { useTrainingInsights } from './useInsights'

const GROUPS = [
  { id: 'quality', title: 'Quality metrics', description: 'Validation quality per epoch. A 0–1 axis unless log scale is on.' },
  { id: 'loss', title: 'Loss', description: 'Training and validation loss per epoch. The y-axis follows the data range.' },
  { id: 'other', title: 'Other metrics', description: 'Every other logged metric, on an automatic axis.' },
] as const

type Group = (typeof GROUPS)[number]['id']

const MAX_RUNS = 6

function defaultSelection(runs: TrainingRun[], modelParam?: string): string[] {
  if (!runs.length) return []
  const index = modelParam ? runs.findIndex((r) => r.id === modelParam) : -1
  if (index >= 0) {
    const peer = runs[index + 1] ?? runs[index - 1]
    return peer ? [runs[index].id, peer.id] : [runs[index].id]
  }
  return runs.slice(0, 2).map((r) => r.id)
}

/** Points for one run/metric after EMA smoothing, optionally dropping non-positive values for log axes. */
function seriesPoints(run: TrainingRun, key: string, smooth: number, log: boolean): [number, number][] {
  const raw: [number, number][] = []
  run.history.forEach((h, i) => {
    const epoch = Number(h.epoch ?? i + 1)
    const value = h[key]
    if (Number.isFinite(epoch) && typeof value === 'number' && Number.isFinite(value)) raw.push([epoch, value])
  })
  const kept = log ? raw.filter(([, v]) => v > 0) : raw
  const values = ema(kept.map(([, v]) => v), smooth)
  return kept.map(([epoch], i) => [epoch, values[i]])
}

const fmtAxis = (v: number) => {
  const abs = Math.abs(v)
  if (abs >= 1000) return `${(v / 1000).toFixed(1)}k`
  if (abs > 0 && abs < 0.01) return v.toExponential(1)
  return String(Number(v.toFixed(3)))
}

function buildOption(group: Group, runs: TrainingRun[], keys: TrainingMetricKey[], theme: ChartTheme, smooth: number, log: boolean): ChartOption {
  const quality = group === 'quality'
  const series = runs.flatMap((run, runIndex) => keys.map((key, keyIndex) => {
    const color = metricColor(keyIndex, keys.length, group, theme.dark)
    return {
      type: 'line' as const,
      name: `${run.name} · ${key.label}`,
      data: seriesPoints(run, key.key, smooth, log),
      showSymbol: false,
      symbolSize: 3,
      smooth: false,
      lineStyle: { width: 1.8, color, type: runDash(runIndex) },
      itemStyle: { color },
      emphasis: { focus: 'series' as const },
    }
  }))

  const yType: 'value' | 'log' = log ? 'log' : 'value'
  return chartBase(theme, {
    grid: { left: 8, right: 16, top: 36, bottom: 8, containLabel: true },
    legend: legendBase(theme),
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value) => Array.isArray(value) ? value.map((v) => Number(v).toFixed(3)).join(', ') : Number(value).toFixed(3),
    },
    xAxis: {
      type: 'value',
      min: 1,
      minInterval: 1,
      axisLabel: { ...axisText(theme), formatter: (v: number) => String(Math.round(v)) },
      axisLine: axisLine(theme),
      splitLine: splitLine(theme),
    },
    yAxis: {
      type: yType,
      min: !log && quality ? 0 : undefined,
      max: quality ? 1 : undefined,
      scale: !quality,
      axisLabel: { ...axisText(theme), formatter: (v: number) => fmtAxis(v) },
      axisLine: axisLine(theme),
      splitLine: splitLine(theme),
    },
    series,
  })
}

export function TrainingTab({ ws, slug, modelParam }: { ws: string; slug: string; modelParam?: string }) {
  const theme = useChartTheme()
  const catalogue = useTrainingInsights(ws, slug)
  const [picked, setPicked] = useState<string[] | null>(null)
  const [smooth, setSmooth] = useState(0)
  const [log, setLog] = useState(false)

  const allRuns = catalogue.data?.runs ?? []
  const catalogueKeys = catalogue.data?.keys ?? []
  const fallback = useMemo(() => defaultSelection(catalogue.data?.runs ?? [], modelParam), [catalogue.data, modelParam])
  const selection = picked ?? fallback
  const query = useTrainingInsights(ws, slug, selection, selection.length > 0)
  const keys = query.data?.keys ?? catalogueKeys

  const toggle = (id: string) => {
    setPicked((prev) => {
      const current = prev ?? fallback
      if (current.includes(id)) return current.length > 1 ? current.filter((x) => x !== id) : current
      if (current.length >= MAX_RUNS) return current
      const next = new Set([...current, id])
      return allRuns.filter((r) => next.has(r.id)).map((r) => r.id)
    })
  }

  if (catalogue.isLoading) return <PageSkeleton />
  if (catalogue.isError) {
    return <ErrorState title="Training history could not be loaded" message={(catalogue.error as Error).message} onRetry={() => catalogue.refetch()} />
  }
  if (!allRuns.length) {
    return (
      <Card className="p-6">
        <EmptyState icon={<ChartLine className="h-8 w-8 text-muted-foreground/50" />} title="No training history yet"
          hint="Curves appear here once a training run has logged at least one epoch." />
      </Card>
    )
  }

  const epochs = Math.max(0, ...(query.data?.runs ?? allRuns.filter((r) => selection.includes(r.id))).map((r) => r.epochs || r.history.length))
  const groups = GROUPS.filter((g) => keys.some((k) => k.group === g.id))

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
          <div className="min-w-0">
            <h2 className="text-sm font-semibold">Training runs</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Pick 1–6 runs to overlay. {selection.length} selected · {epochs} epochs logged.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <label htmlFor="ema-smoothing" className="flex min-h-6 items-center gap-2 text-xs">
              <span className="text-muted-foreground">Smoothing</span>
              <input id="ema-smoothing" type="range" min={0} max={0.9} step={0.05} value={smooth}
                aria-valuetext={smooth.toFixed(2)} onChange={(e) => setSmooth(Number(e.target.value))}
                className="h-1.5 w-24 cursor-pointer accent-[var(--primary)] sm:w-32" />
              <span className="w-8 tabular-nums">{smooth.toFixed(2)}</span>
            </label>
            <div className="flex min-h-6 items-center gap-2 text-xs">
              <span className="text-muted-foreground">Log scale</span>
              <Switch checked={log} onChange={setLog} label="Logarithmic y-axis" />
            </div>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label="Training runs to compare">
          {allRuns.map((run) => {
            const selected = selection.includes(run.id)
            const inChart = query.data?.runs.findIndex((r) => r.id === run.id) ?? -1
            const index = selected ? (inChart >= 0 ? inChart : selection.indexOf(run.id)) : allRuns.indexOf(run)
            const atLimit = !selected && selection.length >= MAX_RUNS
            return (
              <button key={run.id} type="button" role="checkbox" aria-checked={selected} disabled={atLimit}
                title={atLimit ? `Up to ${MAX_RUNS} runs can be overlaid` : undefined}
                onClick={() => toggle(run.id)}
                className={cn('flex min-h-9 cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 text-left text-xs transition-colors',
                  selected ? 'border-primary bg-accent/50 text-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                  atLimit && 'cursor-not-allowed opacity-45')}>
                <svg width={18} height={8} aria-hidden="true" className="shrink-0">
                  <line x1={0} y1={4} x2={18} y2={4} stroke="currentColor" strokeWidth={2} strokeDasharray={dashCss(index)} />
                </svg>
                <span className="font-medium">{run.name}</span>
                <span className="tabular-nums">v{run.version ?? '—'} · {run.task} · {run.epochs} ep</span>
              </button>
            )
          })}
        </div>
      </Card>

      {query.isLoading ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {[0, 1].map((i) => <Card key={i} className="p-4"><ChartSkeleton height={240} /></Card>)}
        </div>
      ) : query.isError ? (
        <ErrorState title="Training curves could not be loaded" message={(query.error as Error).message} onRetry={() => query.refetch()} />
      ) : !groups.length ? (
        <Card className="p-6">
          <EmptyState title="No metrics logged" hint="This run recorded epochs but no numeric metrics." />
        </Card>
      ) : (
        <div className="grid items-start gap-4 lg:grid-cols-2">
          {groups.map((group) => {
            const groupKeys = keys.filter((k) => k.group === group.id)
            const runs = query.data?.runs ?? []
            const option = buildOption(group.id, runs, groupKeys, theme, smooth, log)
            const csvRows: ExportRows = [['Epoch', 'Run', 'Metric', 'Value']]
            for (const run of runs) {
              for (const key of groupKeys) {
                for (const [epoch, value] of seriesPoints(run, key.key, smooth, log)) {
                  csvRows.push([epoch, run.name, key.label, Number(value.toFixed(6))])
                }
              }
            }
            return (
              <ChartCard key={group.id} title={group.title} description={group.description}
                summary={`${group.title} over ${epochs} epochs for ${runs.length} ${runs.length === 1 ? 'run' : 'runs'}: ${groupKeys.map((k) => k.label).join(', ')}.`}
                exportName={`training-${group.id}`} csvRows={csvRows}
                jsonData={{ smoothing: smooth, logScale: log, keys: groupKeys, runs: runs.map((r) => ({ id: r.id, name: r.name, version: r.version, epochs: r.epochs, history: r.history })) }}
                table={<DataTable caption={`${group.title} per epoch (EMA ${smooth.toFixed(2)}).`} head={['Epoch', 'Run', 'Metric', 'Value']} rows={csvRows.slice(1)} />}>
                <EChart option={option} height={260}
                  ariaLabel={`${group.title} line chart for ${runs.map((r) => r.name).join(', ')}. A table view lists the same values.`} />
              </ChartCard>
            )
          })}
        </div>
      )}
    </div>
  )
}
