import { useCallback, useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, Loader2, MousePointer2, RotateCw } from 'lucide-react'
import { api } from '@/lib/api'
import { classColor } from '@/lib/theme'
import type { InsightEmbedding, InsightEmbeddingPoint, InsightSummary } from '@/lib/types'
import { Badge, Button, Card, Progress, Select, toast } from '@/components/ui'
import { axisChrome, ChartCard, cssColor, tooltipStyle, useChartTheme } from './Chart'

const fmt = (n: number) => n.toLocaleString()
const TABLE_CAP = 2000
const OPEN_CAP = 1000
const SPLIT_INDEX: Record<string, number> = { train: 4, valid: 2, test: 5 }
const NO_CLASS = 'No class'

type ColorBy = 'split' | 'class' | 'source' | 'error'

const COLOR_OPTIONS: { id: ColorBy; label: string }[] = [
  { id: 'split', label: 'Split' },
  { id: 'class', label: 'Class' },
  { id: 'source', label: 'Label source' },
  { id: 'error', label: 'Error' },
]

export function Embeddings({ ws, slug, summary, embedding }: {
  ws: string
  slug: string
  summary: InsightSummary
  embedding: InsightEmbedding
}) {
  const t = useChartTheme()
  const nav = useNavigate()
  const qc = useQueryClient()
  const [colorBy, setColorBy] = useState<ColorBy>('split')
  const [selected, setSelected] = useState<number[]>([])
  const job = embedding.job
  const running = !!job && (job.status === 'queued' || job.status === 'running')
  const run = useMutation({
    mutationFn: () => api.insights.scanEmbedding(ws, slug),
    onSuccess: () => { toast.ok('Embedding scan queued'); setSelected([]); qc.invalidateQueries({ queryKey: ['insights'] }) },
    onError: (e) => toast.err(e as Error),
  })

  const points = embedding.points
  const classIndex = useMemo(() => {
    const m = new Map<string, number>(summary.classes.map((c, i) => [c.name, i]))
    for (const p of points) {
      const name = p.class ?? NO_CLASS
      if (!m.has(name)) m.set(name, m.size)
    }
    return m
  }, [summary.classes, points])
  const sourceIndex = useMemo(() => {
    const m = new Map<string, number>()
    for (const p of points) if (!m.has(p.source)) m.set(p.source, m.size)
    return m
  }, [points])

  const colorFor = useCallback((p: InsightEmbeddingPoint) => {
    if (colorBy === 'split') return cssColor(classColor(SPLIT_INDEX[p.split] ?? 0))
    if (colorBy === 'class') return cssColor(classColor(classIndex.get(p.class ?? NO_CLASS) ?? 0))
    if (colorBy === 'source') return cssColor(classColor(sourceIndex.get(p.source) ?? 0))
    return cssColor(classColor(p.error ? 5 : 2))
  }, [colorBy, classIndex, sourceIndex])

  const labelFor = useCallback((p: InsightEmbeddingPoint) => {
    if (colorBy === 'split') return p.split
    if (colorBy === 'class') return p.class ?? NO_CLASS
    if (colorBy === 'source') return p.source
    return p.error ? 'Flagged' : 'No error'
  }, [colorBy])

  // One series per colour category: ECharts' large scatter draw is single-colour per series.
  const groups = useMemo(() => {
    const map = new Map<string, { label: string; color: string; indices: number[] }>()
    points.forEach((p, i) => {
      const label = labelFor(p)
      const group = map.get(label)
      if (group) group.indices.push(i)
      else map.set(label, { label, color: colorFor(p), indices: [i] })
    })
    return [...map.values()]
  }, [points, labelFor, colorFor])

  const legend = useMemo(() => {
    if (colorBy === 'split') {
      return ['train', 'valid', 'test'].map((name) => ({
        label: name, color: cssColor(classColor(SPLIT_INDEX[name])),
        count: points.filter((p) => p.split === name).length,
      }))
    }
    if (colorBy === 'class') {
      return [...classIndex.entries()].map(([label, i]) => ({
        label, color: cssColor(classColor(i)), count: points.filter((p) => (p.class ?? NO_CLASS) === label).length,
      }))
    }
    if (colorBy === 'source') {
      return [...sourceIndex.entries()].map(([label, i]) => ({ label, color: cssColor(classColor(i)), count: points.filter((p) => p.source === label).length }))
    }
    return [
      { label: 'No error', color: cssColor(classColor(2)), count: points.filter((p) => !p.error).length },
      { label: 'Flagged', color: cssColor(classColor(5)), count: points.filter((p) => p.error).length },
    ]
  }, [colorBy, classIndex, sourceIndex, points])

  // Stable identity keeps ECharts from re-setting the option while a brush is being drawn.
  const option = useMemo(() => {
    const series = groups.map((group) => ({
      name: group.label, type: 'scatter', symbolSize: 6, largeThreshold: 2000,
      itemStyle: { color: group.color, opacity: 0.75 },
      emphasis: { focus: 'series' },
      data: group.indices.map((i) => {
        const p = points[i]
        return { value: [p.x, p.y] as [number, number], name: p.name, split: p.split, klass: p.class, source: p.source, error: p.error }
      }),
    }))
    return {
      animation: false,
      grid: { left: 8, right: 20, top: 34, bottom: 40, containLabel: true },
      tooltip: {
        ...tooltipStyle(t),
        formatter: (raw: unknown) => {
          const d = (raw as { data?: { name?: string; split?: string; klass?: string | null; source?: string; error?: boolean | string | null } }).data
          if (!d) return ''
          const flag = d.error ? `<br/><span style="color:${t.warning}">flagged: ${d.error === true ? 'yes' : d.error}</span>` : ''
          return `${d.name ?? 'Image'}<br/>${d.klass ?? NO_CLASS} · ${d.split ?? ''} · ${d.source ?? ''}${flag}`
        },
      },
      toolbox: {
        right: 4, top: 0, itemSize: 14,
        iconStyle: { borderColor: t.muted },
        feature: { brush: { type: ['polygon', 'rect', 'clear'], title: { polygon: 'Lasso select', rect: 'Box select', clear: 'Clear selection' } } },
      },
      brush: {
        brushType: 'polygon', brushMode: 'single', transformable: false,
        throttleType: 'debounce', throttleDelay: 150, xAxisIndex: 0,
      },
      xAxis: { type: 'value', name: `${embedding.projection.toUpperCase()} 1`, nameLocation: 'middle', nameGap: 26, nameTextStyle: { color: t.muted, fontSize: 11 }, ...axisChrome(t), scale: true },
      yAxis: { type: 'value', name: `${embedding.projection.toUpperCase()} 2`, nameTextStyle: { color: t.muted, fontSize: 11 }, ...axisChrome(t), scale: true },
      series,
    }
  }, [points, groups, embedding.projection, t])

  const onBrush = useCallback((params: unknown) => {
    const selectedSeries = (params as { batch?: { selected?: { seriesIndex?: number; dataIndex?: number[] }[] }[] }).batch?.[0]?.selected ?? []
    const indices: number[] = []
    for (const hit of selectedSeries) {
      const group = groups[hit.seriesIndex ?? -1]
      if (!group) continue
      for (const dataIndex of hit.dataIndex ?? []) {
        const pointIndex = group.indices[dataIndex]
        if (pointIndex !== undefined) indices.push(pointIndex)
      }
    }
    setSelected(indices)
  }, [groups])

  const events = useMemo(() => ({ brushSelected: onBrush }), [onBrush])

  const selectedPoints = selected.map((i) => points[i]).filter((p): p is InsightEmbeddingPoint => !!p)
  const openInDataset = () => {
    const ids = selectedPoints.slice(0, OPEN_CAP).map((p) => p.image_id)
    if (selectedPoints.length > OPEN_CAP) toast.ok(`Opening the first ${fmt(OPEN_CAP)} of ${fmt(selectedPoints.length)} selected images`)
    const params = new URLSearchParams({ ids: ids.join(','), status: 'all' })
    nav(`/${ws}/${slug}/browse?${params.toString()}`)
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Embedding map</h2>
        <p className="mt-0.5 text-sm text-muted-foreground">Similar images cluster together. Lasso a cluster to open exactly those images in the dataset.</p>
      </div>
      <Card className="flex flex-wrap items-center gap-x-4 gap-y-2 p-3">
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
            Map state
            <Badge className="uppercase">{embedding.projection}</Badge>
            {running && <span className="text-xs font-normal text-muted-foreground">{Math.round(job?.progress ?? 0)}%</span>}
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Activate the lasso in the chart toolbar, draw around a cluster, then open the selection in the dataset.
          </p>
        </div>
        <Badge>{fmt(points.length)} images</Badge>
        <Button variant="outline" size="sm" onClick={() => run.mutate()} disabled={run.isPending || running}
          title={running ? 'An embedding scan is already running' : undefined}>
          {running || run.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : <RotateCw className="h-3.5 w-3.5" aria-hidden="true" />}
          {running ? 'Embedding…' : 'Re-embed'}
        </Button>
      </Card>

      {running && (
        <div role="status" className="rounded-lg border px-4 py-3 text-sm">
          <div className="flex items-center gap-2"><span className="font-medium">{job?.status === 'queued' ? 'Embedding queued' : 'Embedding images…'}</span><span className="ml-auto text-xs tabular-nums text-muted-foreground">{Math.round(job?.progress ?? 0)}%</span></div>
          <Progress className="mt-2" value={job?.progress ?? 0} />
          <p className="mt-2 text-xs text-muted-foreground">This page refreshes automatically when the map is ready.</p>
        </div>
      )}
      {job?.status === 'failed' && !running && (
        <p role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-2.5 text-sm text-destructive">
          The last embedding scan failed: {job.error || 'unknown error'}
        </p>
      )}
      {embedding.stale && !running && (
        <div role="status" className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border border-warning/40 bg-warning/10 px-4 py-2.5 text-sm">
          <AlertTriangle className="h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
          <p className="min-w-0 flex-1">Images changed since this map was built — re-embed for current positions.</p>
        </div>
      )}

      <ChartCard
        title="Embedding scatter"
        desc="Similar images sit close together. Colour by split, class, label source or error flag."
        ariaLabel={`Embedding scatter of ${fmt(points.length)} images, coloured by ${COLOR_OPTIONS.find((o) => o.id === colorBy)?.label.toLowerCase()}.`}
        option={option}
        height={440}
        onEvents={events}
        actions={(
          <Select value={colorBy} onChange={(e) => setColorBy(e.target.value as ColorBy)} aria-label="Colour embedding points by" className="h-8 text-xs">
            {COLOR_OPTIONS.map((o) => <option key={o.id} value={o.id}>Colour: {o.label}</option>)}
          </Select>
        )}
        table={{
          caption: `Embedding coordinates.${points.length > TABLE_CAP ? ` Showing the first ${fmt(TABLE_CAP)} of ${fmt(points.length)}.` : ''}`,
          columns: ['Image', 'Split', 'Class', 'Source', 'Error', 'X', 'Y'],
          rows: points.slice(0, TABLE_CAP).map((p) => [p.name, p.split, p.class ?? NO_CLASS, p.source, p.error ? 'yes' : '', p.x.toFixed(2), p.y.toFixed(2)]),
        }}
        empty={points.length ? undefined : 'No embedding map yet — run the scan to project images with UMAP.'}
        footnote={points.length ? 'Brushing uses the polygon tool in the chart toolbar; the lasso stays active until you clear it.' : undefined}
      />

      <Card className="flex flex-wrap items-center gap-2 p-3 text-sm">
        <MousePointer2 className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <span className="min-w-0 flex-1">
          <b className="tabular-nums">{fmt(selectedPoints.length)}</b> selected
          {selectedPoints.length > OPEN_CAP && <span className="text-muted-foreground"> · only the first {fmt(OPEN_CAP)} open</span>}
        </span>
        <Button size="sm" onClick={openInDataset} disabled={!selectedPoints.length}>
          Open {selectedPoints.length > OPEN_CAP ? fmt(OPEN_CAP) : fmt(selectedPoints.length)} selected in dataset
        </Button>
      </Card>

      <Card className="p-3">
        <h3 className="text-xs font-semibold text-muted-foreground">Legend · {COLOR_OPTIONS.find((o) => o.id === colorBy)?.label}</h3>
        <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1.5 text-xs">
          {legend.map((l) => (
            <li key={l.label} className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: l.color }} aria-hidden="true" />
              <span className="capitalize">{l.label}</span>
              <span className="tabular-nums text-muted-foreground">{fmt(l.count)}</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}
