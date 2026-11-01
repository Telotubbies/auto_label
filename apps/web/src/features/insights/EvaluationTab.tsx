import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ScanSearch } from 'lucide-react'
import { api } from '@/lib/api'
import type { EvalInsights, EvalSliceDimension, F1Point, ModelItem } from '@/lib/types'
import { Card, EmptyState, Select } from '@/components/ui'
import { classColor, viridis } from '@/lib/theme'
import { EvalPanel } from '@/features/evaluation/EvalPanel'
import {
  ChartCard, DataTable, EChart, ErrorState, PageSkeleton, Swatch, axisLine, axisText, chartBase, legendBase,
  splitLine, toRgb, useChartTheme, type ChartOption, type ChartTheme, type ExportRows,
} from './charts'
import { useModelInsights } from './useInsights'

// Same formatter as Models.tsx, kept local so this lazy route never pulls the Models page chunk in.
const pct = (v?: number | null) => (v == null ? '—' : `${(v * 100).toFixed(1)}%`)
const num3 = (v?: number | null) => (v == null || Number.isNaN(v) ? '—' : v.toFixed(3))
const fmtValue = (value: unknown) => Array.isArray(value) ? value.map((v) => Number(v).toFixed(3)).join(', ') : Number(value).toFixed(3)

function nearestF1(curve: F1Point[], conf: number): F1Point | null {
  let best: F1Point | null = null
  for (const point of curve) {
    if (!best || Math.abs(point.conf - conf) < Math.abs(best.conf - conf)) best = point
  }
  return best
}

function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="min-w-0 bg-card px-3 py-2.5">
      <dt className="text-[10px] leading-tight text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-lg font-semibold tracking-tight tabular-nums">{value}</dd>
      {sub ? <dd className="text-[10px] text-muted-foreground">{sub}</dd> : null}
    </div>
  )
}

function perClassOption(ev: EvalInsights, theme: ChartTheme): ChartOption {
  const colors = ev.per_class.map((_, i) => toRgb(classColor(i)))
  return chartBase(theme, {
    grid: { left: 8, right: 12, top: 20, bottom: 8, containLabel: true },
    tooltip: { trigger: 'axis', valueFormatter: fmtValue },
    xAxis: {
      type: 'category',
      data: ev.per_class.map((c) => c.class),
      axisLabel: { ...axisText(theme), interval: ev.per_class.length > 12 ? 'auto' : 0, rotate: ev.per_class.length > 7 ? 30 : 0, width: 76, overflow: 'truncate' },
      axisTick: { show: false },
      axisLine: axisLine(theme),
    },
    yAxis: { type: 'value', min: 0, max: 1, axisLabel: axisText(theme), axisLine: axisLine(theme), splitLine: splitLine(theme) },
    series: [
      { name: 'AP', type: 'bar', barMaxWidth: 22, itemStyle: { color: theme.primary }, data: ev.per_class.map((c, i) => ({ value: c.AP, itemStyle: { color: colors[i] } })) },
      { name: 'AP50', type: 'bar', barMaxWidth: 22, itemStyle: { color: theme.muted }, data: ev.per_class.map((c, i) => ({ value: c.AP50, itemStyle: { color: colors[i], opacity: 0.55 } })) },
    ],
  })
}

function prOption(ev: EvalInsights, theme: ChartTheme): ChartOption {
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
    series: ev.per_class_pr.map((c, i) => {
      const color = toRgb(classColor(i))
      return {
        type: 'line' as const, name: c.class, showSymbol: false, smooth: true,
        data: [...c.points].sort((a, b) => a.recall - b.recall).map((p) => [p.recall, p.precision]),
        lineStyle: { width: 1.6, color }, itemStyle: { color }, emphasis: { focus: 'series' as const },
      }
    }),
  })
}

function f1Option(ev: EvalInsights, theme: ChartTheme): ChartOption {
  const series = [
    { key: 'precision' as const, label: 'Precision', color: theme.info },
    { key: 'recall' as const, label: 'Recall', color: theme.warning },
    { key: 'f1' as const, label: 'F1', color: theme.fg },
  ]
  return chartBase(theme, {
    grid: { left: 8, right: 14, top: 36, bottom: 24, containLabel: true },
    legend: legendBase(theme),
    tooltip: { trigger: 'axis', valueFormatter: fmtValue },
    xAxis: {
      type: 'value', min: 0, max: 1, name: 'Confidence', nameLocation: 'middle', nameGap: 22, nameTextStyle: axisText(theme),
      axisLabel: { ...axisText(theme), formatter: (v: number) => v.toFixed(2) }, axisLine: axisLine(theme), splitLine: splitLine(theme),
    },
    yAxis: {
      type: 'value', min: 0, max: 1, axisLabel: axisText(theme), axisLine: axisLine(theme), splitLine: splitLine(theme),
    },
    series: series.map((s) => ({
      type: 'line' as const, name: s.label, showSymbol: false,
      data: ev.f1_curve.map((p) => [p.conf, p[s.key]]),
      lineStyle: { width: 1.8, color: s.color }, itemStyle: { color: s.color },
      ...(s.key === 'f1' ? {
        markLine: {
          symbol: 'none', silent: true,
          label: { formatter: `Best F1 ${ev.f1_best.conf.toFixed(2)}`, position: 'insideEndTop' as const, rotate: 0, color: theme.fg, fontSize: 10 },
          lineStyle: { color: theme.warning, type: 'dashed' as const, width: 1 },
          data: [{ xAxis: ev.f1_best.conf }],
        },
      } : {}),
    })),
  })
}

function calibrationOption(ev: EvalInsights, theme: ChartTheme): ChartOption {
  const bins = ev.calibration.bins
  return chartBase(theme, {
    grid: { left: 8, right: 14, top: 16, bottom: 8, containLabel: true },
    tooltip: { trigger: 'axis', valueFormatter: fmtValue },
    xAxis: {
      type: 'category', data: bins.map((b) => b.bin), axisLabel: { ...axisText(theme), interval: 0 },
      axisTick: { show: false }, axisLine: axisLine(theme),
    },
    yAxis: { type: 'value', min: 0, max: 1, axisLabel: axisText(theme), axisLine: axisLine(theme), splitLine: splitLine(theme) },
    series: [
      {
        name: 'Observed accuracy', type: 'bar', barMaxWidth: 26,
        data: bins.map((b) => ({ value: b.accuracy, itemStyle: { color: toRgb(viridis(0.25 + 0.65 * Math.min(1, Math.max(0, b.conf)))) } })),
      },
      {
        name: 'Perfect calibration', type: 'line', showSymbol: true, symbolSize: 4,
        data: bins.map((b, i) => [i, b.conf]),
        lineStyle: { width: 1.2, type: 'dashed', color: theme.muted }, itemStyle: { color: theme.muted },
      },
    ],
  })
}

function sliceOption(rows: EvalInsights['slices'], theme: ChartTheme): ChartOption {
  const colors = rows.map((_, i) => toRgb(classColor(i)))
  return chartBase(theme, {
    grid: { left: 8, right: 14, top: 20, bottom: 8, containLabel: true },
    tooltip: { trigger: 'axis', valueFormatter: fmtValue },
    xAxis: {
      type: 'category', data: rows.map((r) => r.value), axisLabel: { ...axisText(theme), interval: 0, rotate: rows.length > 7 ? 30 : 0, width: 84, overflow: 'truncate' },
      axisTick: { show: false }, axisLine: axisLine(theme),
    },
    yAxis: { type: 'value', min: 0, max: 1, axisLabel: axisText(theme), axisLine: axisLine(theme), splitLine: splitLine(theme) },
    series: [
      { name: 'AP50', type: 'bar', barMaxWidth: 24, itemStyle: { color: theme.primary }, data: rows.map((r, i) => ({ value: r.AP50, itemStyle: { color: colors[i] } })) },
      { name: 'AP', type: 'bar', barMaxWidth: 24, itemStyle: { color: theme.muted }, data: rows.map((r, i) => ({ value: r.AP, itemStyle: { color: colors[i], opacity: 0.55 } })) },
    ],
  })
}

const SLICE_DIMENSIONS: EvalSliceDimension[] = ['size', 'tag', 'batch', 'split', 'brightness', 'source']

export function EvaluationTab({ ws, slug, modelParam }: { ws: string; slug: string; modelParam?: string }) {
  const theme = useChartTheme()
  const [chosen, setChosen] = useState<string | null>(modelParam ?? null)
  const [dimension, setDimension] = useState<EvalSliceDimension | null>(null)
  useEffect(() => { if (modelParam) setChosen(modelParam) }, [modelParam])

  const models = useQuery({ queryKey: ['models', ws, slug], queryFn: () => api.models(ws, slug), staleTime: 30_000 })
  const list: ModelItem[] = models.data ?? []
  const effective = chosen ?? list.find((m) => m.metrics.eval)?.id ?? list[0]?.id
  const detail = useModelInsights(ws, slug, effective)

  const ev = detail.data?.eval ?? null
  const model = detail.data?.model
  const presentDims = new Set<EvalSliceDimension>(ev?.slices.map((s) => s.dimension) ?? [])
  const activeDim: EvalSliceDimension = dimension ?? SLICE_DIMENSIONS.find((d) => presentDims.has(d)) ?? 'size'
  const sliceRows = ev ? ev.slices.filter((s) => s.dimension === activeDim) : []

  if (models.isLoading) return <PageSkeleton />
  if (models.isError) {
    return <ErrorState title="Models could not be loaded" message={(models.error as Error).message} onRetry={() => models.refetch()} />
  }
  if (!list.length) {
    return (
      <Card className="p-6">
        <EmptyState icon={<ScanSearch className="h-8 w-8 text-muted-foreground/50" />} title="No models yet"
          hint="Train a model first; its evaluation report appears here." />
      </Card>
    )
  }

  const selector = (
    <label className="flex items-center gap-2 text-xs">
      <span className="shrink-0 text-muted-foreground">Model</span>
      <Select value={effective ?? ''} onChange={(e) => setChosen(e.target.value)} aria-label="Model to evaluate" className="max-w-[260px]">
        {list.map((m) => (
          <option key={m.id} value={m.id}>
            {m.name} · v{m.version ?? '—'} · {m.task}{m.metrics.eval ? '' : ' (no eval)'}
          </option>
        ))}
      </Select>
    </label>
  )

  if (detail.isLoading) {
    return <div className="space-y-4">{selector}<PageSkeleton /></div>
  }
  if (detail.isError) {
    return <div className="space-y-4">{selector}<ErrorState title="Evaluation could not be loaded" message={(detail.error as Error).message} onRetry={() => detail.refetch()} /></div>
  }

  const mask = (ev?.iou ?? (model?.task === 'segment' ? 'segm' : 'bbox')) === 'segm'
  const usable = !!ev && model?.task !== 'classify' && !/not evaluated|skipped/i.test(ev.note) && Object.keys(ev.coco).length > 0
  const best = ev ? nearestF1(ev.f1_curve, ev.f1_best.conf) : null

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-base font-semibold">{model?.name}</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {model?.arch} · v{model?.version ?? '—'} · {model?.classes.length ?? 0} classes
            {ev ? ` · ${ev.split} split · ${ev.split_images.toLocaleString()} images` : ''}
          </p>
        </div>
        {selector}
      </div>

      {!ev ? (
        <Card className="p-6">
          <EmptyState icon={<ScanSearch className="h-8 w-8 text-muted-foreground/50" />} title="No evaluation for this model"
            hint={detail.data?.reason ?? 'Evaluation runs after training. Refresh once the job finishes.'} />
        </Card>
      ) : !usable ? (
        <Card className="p-4 text-sm text-muted-foreground">{ev.note || 'COCO evaluation is not available for this model.'}</Card>
      ) : (
        <>
          <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border bg-border sm:grid-cols-3 lg:grid-cols-6">
            <Kpi label={mask ? 'Mask AP50' : 'Box AP50'} value={pct(ev.coco.AP50)} />
            <Kpi label={mask ? 'Mask AP50-95' : 'Box AP50-95'} value={pct(ev.coco.AP)} />
            <Kpi label="Precision @ chosen threshold" value={pct(best?.precision)} sub={`threshold ${ev.f1_best.conf.toFixed(2)}`} />
            <Kpi label="Recall @ chosen threshold" value={pct(best?.recall)} sub={`F1 ${best?.f1.toFixed(3) ?? '—'}`} />
            <Kpi label="Latency" value={`${ev.latency_ms.toFixed(1)} ms`} sub="per image" />
            <Kpi label="Calibration ECE" value={ev.calibration.ece.toFixed(3)} sub={`Brier ${ev.calibration.brier.toFixed(3)}`} />
          </dl>

          <p className="text-[11px] text-muted-foreground">
            Derived charts (per-class PR, F1 sweep, calibration, slices) use the stored detail sample:
            {' '}{ev.sample_images.toLocaleString()} of {ev.split_images.toLocaleString()} images, top 100 predictions per image.
            {mask ? ' Box IoU is used because masks are not stored per detection.' : ''}
          </p>

          <div className="grid items-start gap-4 lg:grid-cols-2">
            <ChartCard title="Per-class AP" description="Grouped bars: AP (left) and AP50 (right) per class; colour identifies the class."
              summary={`Per-class AP for ${ev.per_class.length} classes, AP then AP50 per class. Best AP ${num3(ev.per_class.length ? Math.max(...ev.per_class.map((c) => c.AP)) : null)}.`}
              exportName="evaluation-per-class-ap"
              csvRows={[['Class', 'AP', 'AP50'], ...ev.per_class.map((c) => [c.class, c.AP, c.AP50])]}
              jsonData={ev.per_class}
              table={<DataTable caption="Per-class AP and AP50." head={['Class', 'AP', 'AP50']}
                rows={ev.per_class.map((c, i) => [<Swatch key={c.class} color={toRgb(classColor(i))} label={c.class} />, num3(c.AP), num3(c.AP50)])} />}>
              <EChart option={perClassOption(ev, theme)} height={260}
                ariaLabel={`Grouped bar chart of AP and AP50 for ${ev.per_class.length} classes. A table view lists the same values.`} />
            </ChartCard>

            <ChartCard title="Per-class precision–recall" description="One curve per class; toggle classes in the legend. Hover for exact values."
              summary={`Precision–recall curves for ${ev.per_class_pr.length} classes across the confidence sweep.`}
              exportName="evaluation-per-class-pr"
              csvRows={[['Class', 'Recall', 'Precision'], ...ev.per_class_pr.flatMap((c) => c.points.map((p) => [c.class, p.recall, p.precision] as (string | number)[]))]}
              jsonData={ev.per_class_pr}
              table={<DataTable caption="Every point on each per-class precision–recall curve." head={['Class', 'Recall', 'Precision']}
                rows={ev.per_class_pr.flatMap((c, i) => c.points.map((p) => [
                  <Swatch key={`${c.class}-${p.recall}`} color={toRgb(classColor(i))} label={c.class} />,
                  num3(p.recall), num3(p.precision)]))} />}>
              <EChart option={prOption(ev, theme)} height={280}
                ariaLabel={`Precision–recall curves for ${ev.per_class_pr.length} classes. A table view summarises each class.`} />
            </ChartCard>

            <ChartCard title="F1 vs confidence" description={`Precision, recall and F1 on the detail sample. The dashed line marks the chosen threshold, ${ev.f1_best.conf.toFixed(2)}.`}
              summary={`F1 peaks at ${ev.f1_best.f1.toFixed(3)} with confidence ${ev.f1_best.conf.toFixed(2)}.`}
              exportName="evaluation-f1-confidence"
              csvRows={[['Confidence', 'Precision', 'Recall', 'F1'], ...ev.f1_curve.map((p) => [p.conf, p.precision, p.recall, p.f1])]}
              jsonData={{ f1_best: ev.f1_best, f1_curve: ev.f1_curve }}
              table={<DataTable caption="Precision, recall and F1 at each confidence step." head={['Confidence', 'Precision', 'Recall', 'F1']}
                rows={ev.f1_curve.map((p) => [p.conf.toFixed(2), num3(p.precision), num3(p.recall), num3(p.f1)])} />}>
              <EChart option={f1Option(ev, theme)} height={260}
                ariaLabel={`Line chart of precision, recall and F1 against confidence, with the best threshold at ${ev.f1_best.conf.toFixed(2)}.`} />
            </ChartCard>

            <ChartCard title="Calibration" description={`Observed accuracy per confidence bin on the detail sample. ECE ${ev.calibration.ece.toFixed(3)} · Brier ${ev.calibration.brier.toFixed(3)}.`}
              summary={`Reliability diagram with ${ev.calibration.bins.length} confidence bins; expected calibration error ${ev.calibration.ece.toFixed(3)} and Brier score ${ev.calibration.brier.toFixed(3)}.`}
              exportName="evaluation-calibration"
              csvRows={[['Bin', 'Confidence', 'Accuracy', 'Count'], ...ev.calibration.bins.map((b) => [b.bin, b.conf, b.accuracy, b.count])]}
              jsonData={ev.calibration}
              table={<DataTable caption="Confidence bins with observed accuracy and image counts." head={['Bin', 'Confidence', 'Accuracy', 'Count']}
                rows={ev.calibration.bins.map((b) => [b.bin, b.conf.toFixed(2), num3(b.accuracy), b.count])} />}>
              <EChart option={calibrationOption(ev, theme)} height={260}
                ariaLabel={`Reliability diagram: observed accuracy for ${ev.calibration.bins.length} confidence bins against the diagonal.`} />
            </ChartCard>
          </div>

          <ChartCard title="Slice metrics" description={`AP (left) and AP50 (right) per slice value from the detail sample; the top eight values per dimension by image count are shown.`}
            summary={`AP and AP50 across ${sliceRows.length} ${activeDim ?? ''} slices.`}
            exportName={`evaluation-slices-${activeDim ?? 'all'}`}
            csvRows={[['Dimension', 'Value', 'Images', 'Instances', 'AP', 'AP50'], ...sliceRows.map((s) => [s.dimension, s.value, s.images, s.instances, s.AP, s.AP50])]}
            jsonData={{ dimension: activeDim, slices: sliceRows }}
            actions={
              <label className="flex items-center gap-1 text-[11px] text-muted-foreground">
                Slice
                <Select value={activeDim} onChange={(e) => setDimension(e.target.value as EvalSliceDimension)} aria-label="Slice dimension" className="h-8 text-xs">
                  {SLICE_DIMENSIONS.map((d) => <option key={d} value={d}>{presentDims.has(d) ? d : `${d} (no data)`}</option>)}
                </Select>
              </label>
            }
            table={<DataTable caption={`Slice metrics by ${activeDim ?? 'dimension'}.`} head={['Value', 'Images', 'Instances', 'AP', 'AP50']}
              rows={sliceRows.map((s) => [s.value, s.images, s.instances, num3(s.AP), num3(s.AP50)])} />}>
            {sliceRows.length
              ? <EChart option={sliceOption(sliceRows, theme)} height={260}
                  ariaLabel={`Grouped bar chart of AP and AP50 for ${sliceRows.length} ${activeDim ?? ''} slices. A table view lists the same values.`} />
              : <div className="grid h-60 place-items-center rounded-md border border-dashed text-sm text-muted-foreground">No slices for this dimension.</div>}
          </ChartCard>

          <section aria-labelledby="detailed-evaluation" className="space-y-3 pt-2">
            <div>
              <h2 id="detailed-evaluation" className="text-lg font-semibold tracking-tight">Detailed evaluation</h2>
              <p className="mt-0.5 text-sm text-muted-foreground">COCO metrics, the interactive confusion matrix, TIDE and the worst images.</p>
            </div>
            <EvalPanel key={model?.id} ev={ev} images={detail.data?.images} task={model!.task} />
          </section>
        </>
      )}
    </div>
  )
}
