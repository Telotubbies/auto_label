import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Loader2, RotateCw } from 'lucide-react'
import { api } from '@/lib/api'
import { classColor, viridis } from '@/lib/theme'
import type { InsightGeometry, InsightImageStats, InsightSummary } from '@/lib/types'
import { Badge, Button, Card, Progress, Select, toast } from '@/components/ui'
import { axisChrome, ChartCard, cssColor, tooltipStyle, useChartTheme } from './Chart'

const fmt = (n: number) => n.toLocaleString()
const TABLE_CAP = 3000

const AREA_BUCKETS = [
  { key: 'small', label: 'Small', hint: '< 32² px' },
  { key: 'medium', label: 'Medium', hint: '32²–96² px' },
  { key: 'large', label: 'Large', hint: '≥ 96² px' },
] as const

function histOption(rows: { bin: number | string; count: number }[], label: string, color: string, t: ReturnType<typeof useChartTheme>) {
  return {
    grid: { left: 8, right: 16, top: 28, bottom: 42, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...tooltipStyle(t) },
    xAxis: { type: 'category', data: rows.map((r) => String(r.bin)), name: label, nameLocation: 'middle', nameGap: 26, nameTextStyle: { color: t.muted, fontSize: 11 }, ...axisChrome(t) },
    yAxis: { type: 'value', ...axisChrome(t) },
    series: [{ type: 'bar', barMaxWidth: 28, itemStyle: { color, borderRadius: [2, 2, 0, 0] }, data: rows.map((r) => r.count) }],
  }
}

export function DataQuality({ ws, slug, summary, geometry, stats }: {
  ws: string
  slug: string
  summary: InsightSummary
  geometry: InsightGeometry
  stats: InsightImageStats
}) {
  const t = useChartTheme()
  const qc = useQueryClient()
  const [centreClass, setCentreClass] = useState('')
  const job = stats.job
  const running = !!job && (job.status === 'queued' || job.status === 'running')
  const run = useMutation({
    mutationFn: () => api.insights.scanImageStats(ws, slug),
    onSuccess: () => { toast.ok('Image scan queued'); qc.invalidateQueries({ queryKey: ['insights'] }) },
    onError: (e) => toast.err(e as Error),
  })

  const classes = summary.classes
  const classIndex = new Map(classes.map((c, i) => [c.name, i]))
  // The API sends normalised boxes; scale them to the analysed training size for readable pixels.
  const px = geometry.imgsz || 640
  const points = geometry.box_scatter.filter((p) => p.w > 0 && p.h > 0)
  const boxData = points.map((p) => {
    // log axes cannot plot zero, so sub-pixel boxes clamp to 1
    const w = Math.max(1, Math.round(p.w * px))
    const h = Math.max(1, Math.round(p.h * px))
    return {
      value: [w, h] as [number, number],
      itemStyle: { color: cssColor(classColor(classIndex.get(p.class) ?? 0)) },
      name: p.class,
      split: p.split,
    }
  })
  const boxTable = points.slice(0, TABLE_CAP)

  const classLegend = classes.length ? (
    <span className="flex max-h-16 flex-wrap gap-x-3 gap-y-1 overflow-y-auto">
      {classes.map((c, i) => (
        <span key={c.id} className="inline-flex items-center gap-1">
          <span className="h-2 w-2 rounded-full" style={{ background: cssColor(classColor(i)) }} aria-hidden="true" />{c.name}
        </span>
      ))}
    </span>
  ) : null

  const areaData = AREA_BUCKETS.map((b) => ({ label: b.label, hint: b.hint, count: geometry.area_buckets[b.key] }))
  const areaOption = {
    grid: { left: 8, right: 16, top: 32, bottom: 34, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...tooltipStyle(t) },
    xAxis: { type: 'category', data: areaData.map((d) => d.label), ...axisChrome(t) },
    yAxis: { type: 'value', ...axisChrome(t) },
    series: [{
      type: 'bar', barMaxWidth: 64,
      itemStyle: { color: t.primary, borderRadius: [3, 3, 0, 0] },
      label: { show: true, position: 'top', color: t.muted, fontSize: 10 },
      data: areaData.map((d) => d.count),
    }],
  }

  const aspectRows = geometry.aspect
  const aspectOption = {
    grid: { left: 8, right: 16, top: 24, bottom: 34, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...tooltipStyle(t) },
    xAxis: { type: 'category', data: aspectRows.map((r) => r.bucket), ...axisChrome(t), axisLabel: { ...axisChrome(t).axisLabel, interval: 0, rotate: 25, overflow: 'truncate', width: 80 } },
    yAxis: { type: 'value', ...axisChrome(t) },
    series: [{ type: 'bar', barMaxWidth: 40, itemStyle: { color: cssColor(classColor(1)), borderRadius: [2, 2, 0, 0] }, data: aspectRows.map((r) => r.count) }],
  }

  const cells = new Array<number>(100).fill(0)
  let cellMax = 1
  if (centreClass) {
    const row = geometry.centres.find((c) => c.class === centreClass)
    for (let i = 0; i < 100; i++) { cells[i] = row?.cells[i] ?? 0; cellMax = Math.max(cellMax, cells[i]) }
  } else {
    for (const row of geometry.centres) for (let i = 0; i < 100; i++) { cells[i] += row.cells[i] ?? 0; cellMax = Math.max(cellMax, cells[i]) }
  }
  const centreData = cells.map((value, i) => ({
    value: [(i % 10) + 1, Math.floor(i / 10) + 1, value],
    itemStyle: { color: value ? cssColor(viridis(value / cellMax)) : 'transparent', borderColor: t.card, borderWidth: 1 },
  }))
  const centreOption = {
    grid: { left: 8, right: 16, top: 12, bottom: 40, containLabel: true },
    tooltip: {
      ...tooltipStyle(t),
      formatter: (p: unknown) => {
        const v = (p as { value?: [number, number, number] }).value
        return v ? `Row ${v[1]}, column ${v[0]}: ${fmt(v[2])} objects` : ''
      },
    },
    xAxis: { type: 'category', data: Array.from({ length: 10 }, (_, i) => String(i + 1)), name: 'column', nameLocation: 'middle', nameGap: 26, nameTextStyle: { color: t.muted, fontSize: 11 }, ...axisChrome(t), splitLine: { show: false } },
    yAxis: { type: 'category', data: Array.from({ length: 10 }, (_, i) => String(i + 1)), inverse: true, name: 'row', nameTextStyle: { color: t.muted, fontSize: 11 }, ...axisChrome(t), splitLine: { show: false } },
    series: [{ type: 'heatmap', data: centreData, emphasis: { itemStyle: { borderColor: t.fg, borderWidth: 1 } } }],
  }

  const resolution = stats.resolution
  const resolutionOption = {
    grid: { left: 8, right: 16, top: 24, bottom: 42, containLabel: true },
    tooltip: { ...tooltipStyle(t), formatter: (p: unknown) => { const v = (p as { value?: [number, number] }).value; return v ? `${fmt(v[0])} × ${fmt(v[1])} px` : '' } },
    xAxis: { type: 'value', name: 'width (px)', nameLocation: 'middle', nameGap: 26, nameTextStyle: { color: t.muted, fontSize: 11 }, ...axisChrome(t) },
    yAxis: { type: 'value', name: 'height (px)', nameTextStyle: { color: t.muted, fontSize: 11 }, ...axisChrome(t) },
    series: [{ type: 'scatter', symbolSize: 4, itemStyle: { color: t.info, opacity: 0.6 }, data: resolution.map((r) => [r.w, r.h]) }],
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Geometry &amp; image quality</h2>
        <p className="mt-0.5 text-sm text-muted-foreground">Object scale, frame coverage and the sharpness of the source images.</p>
      </div>
      <Card className="flex flex-wrap items-center gap-x-4 gap-y-2 p-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">Image statistics</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {stats.scanned ? `${fmt(stats.scanned)} images scanned at ${geometry.imgsz}px training size.` : 'No image scan yet — resolution, brightness and blur are unmeasured.'}
            {' '}Covers every image in the dataset; the version selector does not apply to this scan.
          </p>
        </div>
        <Badge>{fmt(stats.scanned)} scanned</Badge>
        <Button variant="outline" size="sm" onClick={() => run.mutate()} disabled={run.isPending || running}
          title={running ? 'A scan is already running' : undefined}>
          {running || run.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : <RotateCw className="h-3.5 w-3.5" aria-hidden="true" />}
          {running ? 'Scanning…' : stats.scanned ? 'Rescan' : 'Run scan'}
        </Button>
      </Card>

      {running && (
        <div role="status" className="rounded-lg border px-4 py-3 text-sm">
          <div className="flex items-center gap-2"><span className="font-medium">{job?.status === 'queued' ? 'Scan queued' : 'Scanning images…'}</span><span className="ml-auto text-xs tabular-nums text-muted-foreground">{Math.round(job?.progress ?? 0)}%</span></div>
          <Progress className="mt-2" value={job?.progress ?? 0} />
          <p className="mt-2 text-xs text-muted-foreground">This page refreshes automatically when the scan finishes.</p>
        </div>
      )}
      {job?.status === 'failed' && !running && (
        <p role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-2.5 text-sm text-destructive">
          The last image scan failed: {job.error || 'unknown error'}
        </p>
      )}
      {stats.stale && !running && (
        <div role="status" className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border border-warning/40 bg-warning/10 px-4 py-2.5 text-sm">
          <AlertTriangle className="h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
          <p className="min-w-0 flex-1">Images changed since this scan — rescan for current numbers.</p>
        </div>
      )}

      <ChartCard
        title="Box width vs height"
        desc={`Every annotated box at ${px}px training size, on log axes. Colour marks the class.`}
        ariaLabel={`Log-log scatter of ${fmt(points.length)} annotation boxes by width and height.`}
        option={{
          grid: { left: 8, right: 16, top: 24, bottom: 44, containLabel: true },
          tooltip: { ...tooltipStyle(t), formatter: (p: unknown) => { const d = p as { data?: { value?: [number, number]; name?: string; split?: string } }; const v = d.data?.value; return v ? `${d.data?.name ?? 'Box'} · ${d.data?.split ?? ''}<br/>${fmt(v[0])} × ${fmt(v[1])} px` : '' } },
          xAxis: { type: 'log', name: 'width (px)', nameLocation: 'middle', nameGap: 28, nameTextStyle: { color: t.muted, fontSize: 11 }, ...axisChrome(t) },
          yAxis: { type: 'log', name: 'height (px)', nameTextStyle: { color: t.muted, fontSize: 11 }, ...axisChrome(t) },
          series: [{ type: 'scatter', symbolSize: 4, progressive: 2000, progressiveThreshold: 2500, data: boxData }],
        }}
        table={{
          caption: `Annotation boxes by class and split.${points.length > TABLE_CAP ? ` Showing the first ${fmt(TABLE_CAP)} of ${fmt(points.length)}.` : ''}`,
          columns: ['Class', 'Split', 'Width (px)', 'Height (px)', 'Area (px²)'],
          rows: boxTable.map((p) => [p.class, p.split, Math.round(p.w * px), Math.round(p.h * px), Math.round(p.w * p.h * px * px)]),
        }}
        empty={points.length ? undefined : 'No boxes measured in this scope yet.'}
        footnote={(
          <span className="block space-y-1">
            {classLegend}
            {geometry.sampled && <span className="block">Scatter is sampled server-side; the table lists every plotted box.</span>}
          </span>
        )}
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Object area buckets"
          desc={`COCO small / medium / large at ${geometry.imgsz}px training size.`}
          ariaLabel={`Bar chart of small, medium and large object counts at ${geometry.imgsz} pixels.`}
          option={areaOption}
          table={{
            caption: `Objects per COCO size bucket at ${geometry.imgsz}px.`,
            columns: ['Bucket', 'Threshold', 'Objects'],
            rows: areaData.map((d) => [d.label, d.hint, d.count]),
          }}
          empty={areaData.some((d) => d.count > 0) ? undefined : 'No annotations measured yet.'}
          footnote={`At 640 px the COCO thresholds are 32² and 96²; they scale with the selected ${geometry.imgsz}px size.`}
        />

        <ChartCard
          title="Aspect ratio"
          desc="Width ÷ height buckets across annotated images."
          ariaLabel={`Bar chart of ${aspectRows.length} aspect-ratio buckets.`}
          option={aspectOption}
          table={{
            caption: 'Annotations by aspect-ratio bucket.',
            columns: ['Bucket', 'Count'],
            rows: aspectRows.map((r) => [r.bucket, r.count]),
          }}
          empty={aspectRows.length ? undefined : 'No geometry measured yet.'}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Object centres"
          desc="Where boxes sit in the frame; 10 × 10 grid, row 1 at the top."
          ariaLabel={`Heatmap of object centres for ${centreClass || 'all classes'}.`}
          option={centreOption}
          height={340}
          actions={(
            <Select value={centreClass} onChange={(e) => setCentreClass(e.target.value)} aria-label="Class for the object-centre heatmap" className="h-8 text-xs">
              <option value="">All classes</option>
              {classes.map((c) => <option key={c.id} value={c.name}>{c.name}</option>)}
            </Select>
          )}
          table={{
            caption: `Object counts per centre cell for ${centreClass || 'all classes'}.`,
            columns: ['Row', ...Array.from({ length: 10 }, (_, i) => `Col ${i + 1}`)],
            rows: Array.from({ length: 10 }, (_, r) => [String(r + 1), ...cells.slice(r * 10, r * 10 + 10)]),
          }}
          empty={geometry.centres.length ? undefined : 'No annotated objects yet.'}
        />

        <ChartCard
          title="Image resolution"
          desc="Width and height of scanned images."
          ariaLabel={`Scatter of ${resolution.length} image resolutions by width and height.`}
          option={resolutionOption}
          height={340}
          table={{
            caption: `Scanned image resolutions.${resolution.length > TABLE_CAP ? ` Showing the first ${fmt(TABLE_CAP)} of ${fmt(resolution.length)}.` : ''}`,
            columns: ['Width', 'Height'],
            rows: resolution.slice(0, TABLE_CAP).map((r) => [r.w, r.h]),
          }}
          empty={resolution.length ? undefined : 'Run the image scan to measure resolutions.'}
          footnote={stats.scanned ? `Plotted ${fmt(resolution.length)} of ${fmt(stats.scanned)} scanned images.` : undefined}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Brightness"
          desc="Pixel-brightness histogram from the image scan."
          ariaLabel="Histogram of image brightness values."
          option={histOption(stats.brightness, 'brightness', t.warning, t)}
          table={{ caption: 'Images per brightness bin.', columns: ['Bin', 'Images'], rows: stats.brightness.map((r) => [String(r.bin), r.count]) }}
          empty={stats.brightness.length ? undefined : 'No brightness data yet — run the image scan.'}
        />
        <ChartCard
          title="Blur"
          desc="Laplacian-variance histogram; low values are soft images."
          ariaLabel="Histogram of image blur scores."
          option={histOption(stats.blur, 'blur score', cssColor(classColor(6)), t)}
          table={{ caption: 'Images per blur bin.', columns: ['Bin', 'Images'], rows: stats.blur.map((r) => [String(r.bin), r.count]) }}
          empty={stats.blur.length ? undefined : 'No blur data yet — run the image scan.'}
        />
      </div>
    </div>
  )
}
