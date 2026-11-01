import { useEffect, useMemo, useState } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'
import { ImageOff, Scale } from 'lucide-react'
import { api, fileUrl } from '@/lib/api'
import type { CompareDisagreement, CompareInsights, ModelDetections, ModelEvalDetection, ModelItem } from '@/lib/types'
import { Badge, Card, EmptyState, Modal } from '@/components/ui'
import { cn } from '@/lib/utils'
import {
  ChartCard, DataTable, EChart, ErrorState, PageSkeleton, axisLine, axisText, chartBase, legendBase, runColor,
  splitLine, useChartTheme, type ChartOption, type ChartTheme, type ExportRows,
} from './charts'
import { useCompareInsights } from './useInsights'

const num3 = (v?: number | null) => (v == null || Number.isNaN(v) ? '—' : v.toFixed(3))
const fmtValue = (value: unknown) => Array.isArray(value) ? value.map((v) => Number(v).toFixed(3)).join(', ') : Number(value).toFixed(3)

function defaultCompare(candidates: ModelItem[], modelParam?: string): string[] {
  const anchor = candidates.find((m) => m.id === modelParam) ?? candidates[0]
  if (!anchor) return []
  const peer = candidates.find((m) => m.id !== anchor.id && m.versionId === anchor.versionId && m.task === anchor.task)
  return peer ? [anchor.id, peer.id] : [anchor.id]
}

function classOrder(models: CompareInsights['models']): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const model of models) for (const row of model.per_class) {
    if (!seen.has(row.class)) { seen.add(row.class); out.push(row.class) }
  }
  return out
}

function prOption(data: CompareInsights, theme: ChartTheme): ChartOption {
  const n = data.models.length
  return chartBase(theme, {
    grid: { left: 30, right: 14, top: 36, bottom: 24, containLabel: true },
    legend: legendBase(theme),
    tooltip: { trigger: 'axis', valueFormatter: fmtValue },
    xAxis: {
      type: 'value', min: 0, max: 1, name: 'Recall', nameLocation: 'middle', nameGap: 22, nameTextStyle: axisText(theme),
      axisLabel: { ...axisText(theme), formatter: (v: number) => v.toFixed(1) }, axisLine: axisLine(theme), splitLine: splitLine(theme),
    },
    yAxis: {
      type: 'value', min: 0, max: 1, name: 'Precision', nameLocation: 'middle', nameGap: 34, nameTextStyle: axisText(theme),
      axisLabel: { ...axisText(theme), formatter: (v: number) => v.toFixed(1) }, axisLine: axisLine(theme), splitLine: splitLine(theme),
    },
    series: data.models.map((model, i) => {
      const color = runColor(i, n, theme.dark)
      return {
        type: 'line' as const, name: model.name, showSymbol: false, smooth: true,
        data: [...model.pr_curve].sort((a, b) => a.recall - b.recall).map((p) => [p.recall, p.precision]),
        lineStyle: { width: 2, color }, itemStyle: { color }, emphasis: { focus: 'series' as const },
      }
    }),
  })
}

function apOption(data: CompareInsights, theme: ChartTheme): ChartOption {
  const classes = classOrder(data.models)
  const n = data.models.length
  return chartBase(theme, {
    grid: { left: 8, right: 14, top: 36, bottom: 8, containLabel: true },
    legend: legendBase(theme),
    tooltip: { trigger: 'axis', valueFormatter: fmtValue },
    xAxis: {
      type: 'category', data: classes,
      axisLabel: { ...axisText(theme), interval: classes.length > 12 ? 'auto' : 0, rotate: classes.length > 7 ? 30 : 0, width: 76, overflow: 'truncate' },
      axisTick: { show: false }, axisLine: axisLine(theme),
    },
    yAxis: { type: 'value', min: 0, max: 1, axisLabel: axisText(theme), axisLine: axisLine(theme), splitLine: splitLine(theme) },
    series: data.models.map((model, i) => ({
      type: 'bar' as const, name: model.name, barMaxWidth: 20,
      itemStyle: { color: runColor(i, n, theme.dark) },
      data: classes.map((cls) => model.per_class.find((c) => c.class === cls)?.AP ?? NaN),
    })),
  })
}

function scatterOption(data: CompareInsights, theme: ChartTheme): ChartOption {
  const n = data.models.length
  const pareto = new Set(data.pareto)
  return chartBase(theme, {
    grid: { left: 8, right: 60, top: 36, bottom: 24, containLabel: true },
    legend: legendBase(theme),
    tooltip: {
      trigger: 'item',
      valueFormatter: (value) => Array.isArray(value) ? `${Number(value[0]).toFixed(1)} ms · AP50 ${Number(value[1]).toFixed(3)}` : String(value),
    },
    xAxis: {
      type: 'value', name: 'Latency (ms)', nameLocation: 'middle', nameGap: 22, nameTextStyle: axisText(theme), scale: true,
      axisLabel: { ...axisText(theme), formatter: (v: number) => `${Math.round(v)}` }, axisLine: axisLine(theme), splitLine: splitLine(theme),
    },
    yAxis: {
      type: 'value', min: 0, max: 1,
      axisLabel: { ...axisText(theme), formatter: (v: number) => v.toFixed(1) }, axisLine: axisLine(theme), splitLine: splitLine(theme),
    },
    series: data.models.map((model, i) => {
      const onFront = pareto.has(model.id)
      return {
        type: 'scatter' as const, name: model.name,
        data: [{
          name: model.name,
          value: [model.latency_ms, model.coco.AP50 ?? NaN],
          symbol: onFront ? 'diamond' : 'circle',
          symbolSize: onFront ? 15 : 10,
          itemStyle: { color: runColor(i, n, theme.dark), borderColor: theme.fg, borderWidth: onFront ? 2 : 0 },
        }],
        label: { show: true, formatter: '{b}', position: 'right' as const, color: theme.muted, fontSize: 10 },
        emphasis: { focus: 'series' as const },
      }
    }),
  })
}

function detectionFor(detail: ModelDetections | undefined, file: string): ModelEvalDetection | undefined {
  return detail?.detections?.find((d) => d.file === file)
}

const boxRect = (box: number[], width: number, height: number) => ({
  x: (box[0] / width) * 100,
  y: (box[1] / height) * 100,
  width: (box[2] / width) * 100,
  height: (box[3] / height) * 100,
})

function DisagreementDetail({ entry, models, details }: {
  entry: CompareDisagreement; models: CompareInsights['models']; details: Map<string, ModelDetections>
}) {
  const theme = useChartTheme()
  const n = models.length
  const detections = models.map((m) => detectionFor(details.get(m.id), entry.file))
  const ground = detections.find((d) => !!d)
  const url = entry.url || models.map((m) => details.get(m.id)?.images?.[entry.file]).find(Boolean) || ''

  return (
    <div className="space-y-4">
      {url ? (
        <div className="relative overflow-hidden rounded-md border bg-muted">
          <img src={fileUrl(url)} alt={`Ground truth and predictions for ${entry.file}`} className="block w-full" />
          <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"
            className="pointer-events-none absolute inset-0 h-full w-full">
            {ground?.gt.map((box, i) => {
              const r = boxRect(box.bbox, ground.width, ground.height)
              return <rect key={`gt-${i}`} {...r} fill="none" stroke={theme.muted} strokeWidth={1.5}
                strokeDasharray="2 1.5" vectorEffect="non-scaling-stroke" />
            })}
            {models.map((model, mi) => (detections[mi]?.pred ?? []).map((pred, pi) => {
              const r = boxRect(pred.bbox, detections[mi]!.width, detections[mi]!.height)
              return (
                <rect key={`${model.id}-${pi}`} {...r} fill="none" stroke={runColor(mi, n, theme.dark)} strokeWidth={2}
                  vectorEffect="non-scaling-stroke">
                  <title>{`${model.name}: ${pred.cls} ${pred.conf.toFixed(2)}`}</title>
                </rect>
              )
            }))}
          </svg>
        </div>
      ) : (
        <div className="grid aspect-video place-items-center rounded-md border border-dashed bg-muted px-4 text-center text-sm text-muted-foreground">
          <span className="flex flex-col items-center gap-1"><ImageOff className="h-5 w-5" aria-hidden="true" />Preview unavailable for {entry.file}</span>
        </div>
      )}

      <ul className="grid gap-2 sm:grid-cols-2">
        {models.map((model, i) => {
          const counts = entry.models.find((x) => x.id === model.id)
          const det = detections[i]
          return (
            <li key={model.id} className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-md border px-2.5 py-2 text-xs">
              <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: runColor(i, n, theme.dark) }} aria-hidden="true" />
              <span className="min-w-0 flex-1 truncate font-medium">{model.name}</span>
              <span className="tabular-nums text-success">TP {counts?.tp ?? 0}</span>
              <span className="tabular-nums text-destructive">FP {counts?.fp ?? 0}</span>
              <span className="tabular-nums text-warning">FN {counts?.fn ?? 0}</span>
              <span className="text-muted-foreground">{det ? `${det.pred.length} boxes` : 'no boxes stored'}</span>
            </li>
          )
        })}
      </ul>
      <p className="text-[11px] text-muted-foreground">
        Grey dashed boxes are ground truth. Coloured boxes are each model's stored predictions; hover a box for its class and confidence.
      </p>
    </div>
  )
}

export function CompareTab({ ws, slug, modelParam }: { ws: string; slug: string; modelParam?: string }) {
  const theme = useChartTheme()
  const [picked, setPicked] = useState<string[] | null>(null)
  const [active, setActive] = useState<CompareDisagreement | null>(null)

  const modelsQ = useQuery({ queryKey: ['models', ws, slug], queryFn: () => api.models(ws, slug), staleTime: 30_000 })
  const all = modelsQ.data ?? []
  const candidates = all.filter((m) => !!m.metrics.eval)
  const fallback = useMemo(() => defaultCompare(candidates, modelParam), [modelsQ.data, modelParam])
  const selection = picked ?? fallback
  const selectionKey = selection.join(',')
  const compare = useCompareInsights(ws, slug, selection)

  useEffect(() => { setActive(null) }, [selectionKey])

  const activeFile = active?.file ?? ''
  const detailQueries = useQueries({
    queries: selection.map((id) => ({
      queryKey: ['insights', 'detections', ws, slug, id, activeFile],
      queryFn: () => api.insightsDetections(ws, slug, id, [activeFile]),
      enabled: !!activeFile,
      staleTime: 60_000,
    })),
  })
  const details = useMemo(() => {
    const map = new Map<string, ModelDetections>()
    detailQueries.forEach((q, i) => { if (q.data) map.set(selection[i], q.data) })
    return map
  }, [detailQueries, selection])

  const anchor = candidates.find((m) => m.id === selection[0])
  const reasonFor = (model: ModelItem): string | null => {
    if (model.task === 'classify') return 'Classification eval has no COCO curves'
    if (!anchor) return null
    if (model.task !== anchor.task) return `Different task (${model.task})`
    if (model.versionId !== anchor.versionId) return `Different dataset version (v${model.version ?? '—'})`
    return null
  }

  const toggle = (id: string) => {
    setPicked((prev) => {
      const current = prev ?? fallback
      if (current.includes(id)) return current.length > 2 ? current.filter((x) => x !== id) : current
      if (current.length >= 4) return current
      const next = new Set([...current, id])
      return candidates.filter((m) => next.has(m.id)).map((m) => m.id)
    })
  }

  if (modelsQ.isLoading) return <PageSkeleton />
  if (modelsQ.isError) {
    return <ErrorState title="Models could not be loaded" message={(modelsQ.error as Error).message} onRetry={() => modelsQ.refetch()} />
  }
  if (candidates.length < 2) {
    return (
      <Card className="p-6">
        <EmptyState icon={<Scale className="h-8 w-8 text-muted-foreground/50" />} title="Not enough evaluated models"
          hint="Compare needs at least two models with an evaluation from the same dataset version." />
      </Card>
    )
  }

  const data = compare.data
  const classes = data ? classOrder(data.models) : []
  const loadingDetails = detailQueries.some((q) => q.isLoading)

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-sm font-semibold">Models to compare</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">Pick 2–4 evaluated models from the same dataset version and task. {selection.length} selected.</p>
          </div>
          {data?.cache.hit ? <Badge className="bg-success/15 text-success">server cache hit</Badge> : null}
        </div>
        <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label="Models to compare">
          {candidates.map((model) => {
            const selected = selection.includes(model.id)
            const reason = reasonFor(model)
            const atLimit = !selected && selection.length >= 4
            const blocked = !selected && (!!reason || atLimit)
            return (
              <button key={model.id} type="button" role="checkbox" aria-checked={selected} disabled={blocked}
                title={reason ?? (atLimit ? 'Up to 4 models can be compared' : undefined)}
                onClick={() => toggle(model.id)}
                className={cn('flex min-h-9 cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 text-left text-xs transition-colors',
                  selected ? 'border-primary bg-accent/50 text-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                  blocked && 'cursor-not-allowed opacity-45')}>
                <span className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ background: selected ? runColor(selection.indexOf(model.id), selection.length, theme.dark) : 'var(--muted-foreground)' }} aria-hidden="true" />
                <span className="font-medium">{model.name}</span>
                <span className="tabular-nums">v{model.version ?? '—'} · {model.task}</span>
                {!selected && reason ? <span className="text-[10px] text-warning">{reason}</span> : null}
              </button>
            )
          })}
        </div>
      </Card>

      {selection.length < 2 ? (
        <Card className="p-6"><EmptyState title="Select at least two models" hint="The comparison plots need two or more evaluated models." /></Card>
      ) : compare.isLoading ? (
        <PageSkeleton />
      ) : compare.isError ? (
        <ErrorState title="Comparison failed" message={(compare.error as Error).message} onRetry={() => compare.refetch()} />
      ) : data ? (
        <>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span>{data.models.length} models · dataset v{data.version ?? '—'} · {data.split} split</span>
            <span aria-hidden="true">·</span>
            <span>{data.disagreement.length} disagreement {data.disagreement.length === 1 ? 'image' : 'images'} · counts at confidence {data.threshold.toFixed(2)}</span>
          </div>

          <div className="grid items-start gap-4 lg:grid-cols-2">
            <ChartCard title="Precision–recall" description="Overlaid curves on the same evaluation split; each model keeps its colour across charts."
              summary={`Overlaid precision–recall curves for ${data.models.length} models.`}
              exportName="compare-pr"
              csvRows={[['Model', 'Recall', 'Precision'], ...data.models.flatMap((m) => m.pr_curve.map((p) => [m.name, p.recall, p.precision] as (string | number)[]))]}
              jsonData={data.models.map((m) => ({ id: m.id, name: m.name, pr_curve: m.pr_curve }))}
              table={<DataTable caption="AP, AP50, latency and best F1 per model." head={['Model', 'AP', 'AP50', 'Latency', 'Best F1']}
                rows={data.models.map((m) => [m.name, num3(m.coco.AP), num3(m.coco.AP50), `${m.latency_ms.toFixed(1)} ms`, num3(m.f1_best.f1)])} />}>
              <EChart option={prOption(data, theme)} height={280}
                ariaLabel={`Overlaid precision–recall curves for ${data.models.length} models. A table view compares their summary metrics.`} />
            </ChartCard>

            <ChartCard title="Per-class AP" description="AP for every class, one bar group per model."
              summary={`Per-class AP for ${classes.length} classes across ${data.models.length} models.`}
              exportName="compare-per-class-ap"
              csvRows={[['Class', ...data.models.map((m) => m.name)], ...classes.map((cls) => [cls, ...data.models.map((m) => m.per_class.find((c) => c.class === cls)?.AP ?? '')])]}
              jsonData={data.models.map((m) => ({ id: m.id, name: m.name, per_class: m.per_class }))}
              table={<DataTable caption="Per-class AP by model." head={['Class', ...data.models.map((m) => m.name)]}
                rows={classes.map((cls) => [cls, ...data.models.map((m) => num3(m.per_class.find((c) => c.class === cls)?.AP))])} />}>
              <EChart option={apOption(data, theme)} height={280}
                ariaLabel={`Grouped bar chart of per-class AP for ${data.models.length} models. A table view lists the same values.`} />
            </ChartCard>

            <ChartCard title="Latency vs mAP50" description="Diamond markers with an outline sit on the Pareto front: no other model is both faster and more accurate."
              summary={`Latency versus mAP50 for ${data.models.length} models. Pareto front: ${data.models.filter((m) => data.pareto.includes(m.id)).map((m) => m.name).join(', ') || 'none'}.`}
              exportName="compare-latency-ap"
              csvRows={[['Model', 'Latency (ms)', 'AP50', 'Pareto'], ...data.models.map((m) => [m.name, m.latency_ms, m.coco.AP50, data.pareto.includes(m.id) ? 'yes' : 'no'])]}
              jsonData={{ pareto: data.pareto, models: data.models.map((m) => ({ id: m.id, name: m.name, latency_ms: m.latency_ms, AP50: m.coco.AP50 })) }}
              table={<DataTable caption="Latency, mAP50 and Pareto membership per model." head={['Model', 'Latency', 'mAP50', 'Pareto']}
                rows={data.models.map((m) => [m.name, `${m.latency_ms.toFixed(1)} ms`, num3(m.coco.AP50), data.pareto.includes(m.id) ? 'yes' : 'no'])} />}>
              <EChart option={scatterOption(data, theme)} height={280}
                ariaLabel={`Scatter chart of latency against mAP50 for ${data.models.length} models, with the Pareto front outlined.`} />
            </ChartCard>

            <Card className="min-w-0 p-4 lg:col-span-1">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <h3 className="text-sm font-semibold">Disagreement gallery</h3>
                  <p className="mt-0.5 text-xs text-muted-foreground">Images where the models disagree most. Open one to see ground truth against each model's boxes.</p>
                </div>
                <span className="text-xs tabular-nums text-muted-foreground">{data.disagreement.length} {data.disagreement.length === 1 ? 'image' : 'images'}</span>
              </div>
              {data.disagreement.length ? (
                <ul className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {data.disagreement.map((entry) => (
                    <li key={entry.file}>
                      <button type="button" onClick={() => setActive(entry)}
                        className="group block w-full cursor-pointer overflow-hidden rounded-lg border text-left transition-colors hover:border-primary focus-visible:border-primary">
                        <span className="relative block aspect-video bg-muted">
                          {entry.url
                            ? <img src={fileUrl(entry.url)} alt="" loading="lazy" className="h-full w-full object-cover" />
                            : <span className="grid h-full place-items-center gap-1 px-2 text-center text-[11px] text-muted-foreground"><ImageOff className="h-4 w-4" aria-hidden="true" />Preview unavailable</span>}
                          <span className="absolute right-2 top-2 rounded bg-scrim/70 px-1.5 py-0.5 text-[10px] font-medium tabular-nums text-white">
                            score {entry.score}
                          </span>
                        </span>
                        <span className="block space-y-1 p-2">
                          <span className="block truncate text-[11px] font-medium" title={entry.file}>{entry.file}</span>
                          <span className="flex flex-wrap gap-1">
                            {entry.models.map((row) => {
                              const model = data.models.find((m) => m.id === row.id)
                              const index = data.models.findIndex((m) => m.id === row.id)
                              return (
                                <span key={row.id} className="flex items-center gap-1 rounded border px-1 py-0.5 text-[10px] tabular-nums">
                                  <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: runColor(index, data.models.length, theme.dark) }} aria-hidden="true" />
                                  <span className="max-w-[9ch] truncate" title={model?.name}>{model?.arch ?? row.id}</span>
                                  <span className="text-success">TP {row.tp}</span>
                                  <span className="text-destructive">FP {row.fp}</span>
                                  <span className="text-warning">FN {row.fn}</span>
                                </span>
                              )
                            })}
                          </span>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-sm text-muted-foreground">
                  {data.has_detections
                    ? 'The selected models agree on every stored image.'
                    : 'These evaluations predate per-image detections, so the gallery is unavailable.'}
                </p>
              )}
            </Card>
          </div>

          <Modal open={!!active} onClose={() => setActive(null)} wide title={active?.file}>
            {active ? (
              loadingDetails
                ? <div className="grid h-40 place-items-center text-sm text-muted-foreground">Loading stored detections…</div>
                : <DisagreementDetail entry={active} models={data.models} details={details} />
            ) : null}
          </Modal>
        </>
      ) : null}
    </div>
  )
}
