// Stream analytics (Task 20c): event volume per rule/zone/class, dwell distribution,
// hourly heatmap and top cameras for a project's streams.
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity } from 'lucide-react'
import { api } from '@/lib/api'
import { classColor, viridis } from '@/lib/theme'
import type { StreamAnalytics as StreamAnalyticsData, TimelineSeries } from '@/lib/types'
import { Card, EmptyState, PageHeader, Select, Stat, fmtAgo } from '@/components/ui'
import {
  ChartCard, DataTable, EChart, ErrorState, PageSkeleton, axisLine, axisText, chartBase, legendBase, splitLine, toRgb,
  useChartTheme, type ChartOption, type ChartTheme, type ExportRows,
} from '@/features/insights/charts'
import { useProject } from '@/features/project/ProjectLayout'

const DIMS = [
  { id: 'by_rule', label: 'Rule' },
  { id: 'by_zone', label: 'Zone' },
  { id: 'by_class', label: 'Class' },
] as const

type Dim = (typeof DIMS)[number]['id']

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const fmtInt = (n: number) => Math.round(n).toLocaleString()

/** UTC+07:00 / UTC−04:30 for axis and export labels. */
function tzLabel(offset: number): string {
  const sign = offset < 0 ? '−' : '+'
  const abs = Math.abs(Math.round(offset))
  return `UTC${sign}${String(Math.floor(abs / 60)).padStart(2, '0')}:${String(abs % 60).padStart(2, '0')}`
}

/** Viewer offset east of UTC in minutes, so buckets land on local days and hours. */
function localTzOffset(): number {
  return -new Date().getTimezoneOffset()
}

/** 3m 12s / 1h 4m style dwell time. */
function fmtDwell(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  if (total < 60) return `${total}s`
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  return h ? `${h}h ${m}m` : `${m}m ${s}s`
}

const pct = (part: number, whole: number) => (whole > 0 ? `${Math.round((part / whole) * 100)}%` : '—')

/** Class palette for a handful of series, viridis when the legend would get too busy. */
function seriesColor(i: number, total: number): string {
  if (total <= 8) return toRgb(classColor(i))
  return toRgb(viridis(0.12 + (0.76 * i) / Math.max(1, total - 1)))
}

function overTimeOption(dates: string[], series: TimelineSeries[], theme: ChartTheme): ChartOption {
  const colors = series.map((_, i) => seriesColor(i, series.length))
  return chartBase(theme, {
    grid: { left: 24, right: 16, top: 30, bottom: 24, containLabel: true },
    legend: legendBase(theme),
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category', data: dates, boundaryGap: false,
      axisLabel: { ...axisText(theme), hideOverlap: true },
      axisTick: { show: false }, axisLine: axisLine(theme),
    },
    yAxis: {
      type: 'value', minInterval: 1,
      axisLabel: axisText(theme), axisLine: axisLine(theme), splitLine: splitLine(theme),
    },
    series: series.map((s, i) => ({
      type: 'line' as const, name: s.name, data: dates.map((_, d) => s.values[d] ?? 0),
      showSymbol: dates.length <= 31, symbolSize: 3, smooth: false,
      lineStyle: { width: 1.8, color: colors[i] }, itemStyle: { color: colors[i] },
      emphasis: { focus: 'series' as const },
    })),
  })
}

function dwellOption(buckets: string[], counts: number[], theme: ChartTheme): ChartOption {
  return chartBase(theme, {
    grid: { left: 8, right: 16, top: 24, bottom: 38, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: {
      type: 'category', data: buckets,
      axisLabel: { ...axisText(theme), interval: 0, rotate: buckets.length > 7 ? 30 : 0, overflow: 'truncate', width: 80 },
      axisTick: { show: false }, axisLine: axisLine(theme),
    },
    yAxis: {
      type: 'value', minInterval: 1, name: 'Events', nameTextStyle: axisText(theme),
      axisLabel: axisText(theme), axisLine: axisLine(theme), splitLine: splitLine(theme),
    },
    // Narrow cards cannot fit six horizontal bucket labels; stand them up instead of overlapping.
    media: [{
      query: { maxWidth: 640 },
      option: {
        grid: { bottom: 58 },
        xAxis: { axisLabel: { rotate: 60, interval: 0 } },
      },
    }],
    series: [{
      type: 'bar', barMaxWidth: 48, itemStyle: { color: theme.primary, borderRadius: [3, 3, 0, 0] },
      data: counts,
    }],
  })
}

function heatmapOption(grid: number[][], dayLabels: string[], hourLabels: string[], max: number, theme: ChartTheme, tz = 'UTC'): ChartOption {
  const cells: [number, number, number][] = []
  grid.forEach((row, day) => row.forEach((count, hour) => { cells.push([hour, day, count]) }))
  const colors = Array.from({ length: 10 }, (_, i) => toRgb(viridis(i / 9)))
  const hourText = (hour: number) => {
    const label = hourLabels[hour] ?? String(hour).padStart(2, '0')
    return label.length === 2 ? `${label}:00` : label
  }
  return chartBase(theme, {
    grid: { left: 8, right: 16, top: 12, bottom: 56, containLabel: true },
    tooltip: {
      formatter: (p: unknown) => {
        const v = (p as { value?: [number, number, number] }).value
        if (!v) return ''
        return `${dayLabels[v[1]]} · ${hourText(v[0])}<br/>${fmtInt(v[2])} events`
      },
    },
    xAxis: {
      type: 'category', data: hourLabels, name: `Hour (${tz})`, nameLocation: 'middle', nameGap: 26,
      nameTextStyle: axisText(theme), axisLabel: { ...axisText(theme), interval: 1 },
      axisTick: { show: false }, axisLine: axisLine(theme), splitArea: { show: false },
    },
    yAxis: {
      type: 'category', data: dayLabels, inverse: true,
      axisLabel: axisText(theme), axisTick: { show: false }, axisLine: axisLine(theme), splitArea: { show: false },
    },
    visualMap: {
      min: 0, max: max || 1, calculable: true, orient: 'horizontal', left: 'center', bottom: 0,
      itemWidth: 10, itemHeight: 90, textStyle: { color: theme.muted, fontSize: 10 },
      inRange: { color: colors },
    },
    series: [{
      type: 'heatmap',
      data: cells.map(([hour, day, count]) => ({
        value: [hour, day, count],
        itemStyle: count ? undefined : { color: 'transparent' },
      })),
      itemStyle: { borderColor: theme.card, borderWidth: 1 },
      emphasis: { itemStyle: { borderColor: theme.fg, borderWidth: 1 } },
    }],
  })
}

function ChartEmpty({ title, hint }: { title: string; hint?: string }) {
  return <div className="flex h-[260px] items-center justify-center"><EmptyState title={title} hint={hint} /></div>
}

function StreamAnalyticsView({ data, dim, onDim, theme }: {
  data: StreamAnalyticsData
  dim: Dim
  onDim: (dim: Dim) => void
  theme: ChartTheme
}) {
  const totals = data.totals
  const dates = data.over_time.dates
  const series = data.over_time[dim]
  const tz = tzLabel(data.window.tz_offset ?? 0)
  const dimLabel = DIMS.find((d) => d.id === dim)?.label ?? 'Rule'
  // The API's per-day total counts each event once; summing the class series would double-count.
  const dayTotal = (i: number) => data.over_time.total[i] ?? 0
  const grandTotal = dates.reduce((n, _, i) => n + dayTotal(i), 0)
  const overCsv: ExportRows = [
    [`Date (${tz})`, ...series.map((s) => s.name), 'Total'],
    ...dates.map((date, i) => [date, ...series.map((s) => s.values[i] ?? 0), dayTotal(i)]),
  ]

  const dwellRows: ExportRows = data.dwell.buckets.map((bucket, i) => [bucket, data.dwell.counts[i] ?? 0])

  const dayLabels = WEEKDAYS.map((d, i) => data.hourly.days[i] ?? d)
  const hourLabels = Array.from({ length: 24 }, (_, h) => data.hourly.hours[h] ?? String(h).padStart(2, '0'))
  const grid = Array.from({ length: 7 }, () => new Array<number>(24).fill(0))
  for (const [day, hour, count] of data.hourly.values) {
    if (day >= 0 && day < 7 && hour >= 0 && hour < 24) grid[day][hour] += count
  }
  const heatMax = Math.max(0, ...grid.flat())
  const heatRows: ExportRows = dayLabels.map((day, i) => [day, ...grid[i]])

  const lastEvent = totals.last_event > 0 ? (
    <time dateTime={new Date(totals.last_event * 1000).toISOString()} title={new Date(totals.last_event * 1000).toLocaleString()}>
      {fmtAgo(totals.last_event)}
    </time>
  ) : '—'

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Stat label="Events" value={<span className="tabular-nums">{fmtInt(totals.events)}</span>} sub={`Last ${data.window.days} days`} />
        <Stat label="Reviewed" value={<span className="tabular-nums">{fmtInt(totals.reviewed)}</span>} sub={`${pct(totals.reviewed, totals.events)} of events`} />
        <Stat label="Cameras" value={<span className="tabular-nums">{fmtInt(totals.cameras)}</span>} sub="Active in the window" />
        <Stat label="Total dwell" value={<span className="tabular-nums">{fmtDwell(totals.dwell_seconds)}</span>} sub="Summed event dwell" />
        <Stat label="Last event" value={<span className="tabular-nums">{lastEvent}</span>} sub="Most recent event" />
      </div>

      <ChartCard
        title="Events over time"
        description={`Daily events split by ${dimLabel.toLowerCase()}, ${tz} local days. ${series.length} series; the API folds the long tail into “Other”.`}
        summary={`Daily events by ${dimLabel.toLowerCase()} over ${dates.length} days: ${fmtInt(grandTotal)} events across ${series.length} series.`}
        exportName={`stream-events-${dim}`}
        csvRows={overCsv}
        jsonData={{ dimension: dim, dates, series }}
        actions={(
          <Select value={dim} onChange={(e) => onDim(e.target.value as Dim)}
            aria-label="Split events over time by" className="h-8 text-xs">
            {DIMS.map((d) => <option key={d.id} value={d.id}>{d.label}</option>)}
          </Select>
        )}
        table={(
          <DataTable caption={`Events per day by ${dimLabel.toLowerCase()} (${tz}), with the daily total; each event counts once.`}
            head={[`Date (${tz})`, ...series.map((s) => s.name), 'Total']}
            rows={dates.map((date, i) => [date, ...series.map((s) => s.values[i] ?? 0), dayTotal(i)])} />
        )}
      >
        {series.length ? (
          <EChart option={overTimeOption(dates, series, theme)} height={300}
            ariaLabel={`Line chart of daily events by ${dimLabel.toLowerCase()} over ${dates.length} days. A table view lists every series and the daily total.`} />
        ) : <ChartEmpty title="No breakdown for this window" hint="Events exist but no rule, zone or class labels were recorded." />}
      </ChartCard>

      <div className="grid items-start gap-4 lg:grid-cols-2">
        <ChartCard
          title="Dwell distribution"
          description={`Time spent in frame per event. ${fmtInt(data.dwell.samples)} samples, longest ${fmtDwell(data.dwell.max)}.`}
          summary={`Bar chart of ${data.dwell.buckets.length} dwell buckets covering ${fmtInt(data.dwell.samples)} samples.`}
          exportName="stream-dwell"
          csvRows={[['Dwell bucket', 'Events'], ...dwellRows]}
          jsonData={data.dwell}
          table={<DataTable caption="Events per dwell bucket." head={['Dwell bucket', 'Events']} rows={dwellRows} />}
        >
          {data.dwell.buckets.length ? (
            <EChart option={dwellOption(data.dwell.buckets, data.dwell.counts, theme)} height={260}
              ariaLabel={`Bar chart of ${fmtInt(data.dwell.samples)} dwell samples across ${data.dwell.buckets.length} buckets. A table view lists the same counts.`} />
          ) : <ChartEmpty title="No dwell samples" hint="Dwell rules record a duration once something stays in frame." />}
        </ChartCard>

        <Card className="min-w-0 p-4">
          <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
            <div className="min-w-0">
              <h3 className="text-sm font-semibold">Top cameras</h3>
              <p className="mt-0.5 text-xs text-muted-foreground">Busiest cameras in the window, in API order.</p>
            </div>
            <span className="text-xs tabular-nums text-muted-foreground">{fmtInt(data.top_cameras.length)} listed</span>
          </div>
          <div className="mt-3 overflow-x-auto">
            {data.top_cameras.length ? (
              <DataTable
                caption="Cameras ranked by event volume; reviewed % is reviewed ÷ events."
                head={['Camera', 'Events', 'Reviewed', 'Reviewed %', 'Last event']}
                rows={data.top_cameras.map((cam) => [
                  <span key={cam.id} title={cam.id}>{cam.name || cam.id}</span>,
                  fmtInt(cam.events),
                  fmtInt(cam.reviewed),
                  pct(cam.reviewed, cam.events),
                  cam.last_event > 0
                    ? <time key="last" dateTime={new Date(cam.last_event * 1000).toISOString()}>{fmtAgo(cam.last_event)}</time>
                    : '—',
                ])}
              />
            ) : <EmptyState title="No cameras reported events" hint="Camera activity appears once a stream ingests events." />}
          </div>
        </Card>
      </div>

      <ChartCard
        title="Hourly heatmap"
        description={`Events per weekday and hour of day in ${tz} local time across the window. Busiest cell: ${fmtInt(heatMax)} events.`}
        summary={`Heatmap of 7 weekdays by 24 hours (${tz}); busiest cell has ${fmtInt(heatMax)} events. A table view lists all 168 cells.`}
        exportName="stream-hourly"
        csvRows={[[`Day (${tz})`, ...hourLabels], ...heatRows]}
        jsonData={{ days: dayLabels, hours: hourLabels, tz_offset: data.window.tz_offset, values: data.hourly.values }}
        table={<DataTable caption={`Events per weekday and hour (${tz}).`} head={[`Day (${tz})`, ...hourLabels]} rows={heatRows} />}
      >
        {data.hourly.values.length ? (
          <EChart option={heatmapOption(grid, dayLabels, hourLabels, heatMax, theme, tz)} height={300}
            ariaLabel={`Heatmap of events by weekday and hour in ${tz}; the busiest cell has ${fmtInt(heatMax)} events. A table view lists all 168 cells.`} />
        ) : <ChartEmpty title="No hourly activity" hint="Events in this window have no hourly timestamps." />}
      </ChartCard>
    </div>
  )
}

export default function StreamAnalytics() {
  const { project, ws } = useProject()
  const [days, setDays] = useState(30)
  const [dim, setDim] = useState<Dim>('by_rule')
  const theme = useChartTheme()
  const tzOffset = useMemo(localTzOffset, [])
  const q = useQuery({
    queryKey: ['stream-analytics', ws, project.slug, days, tzOffset],
    queryFn: () => api.streamAnalytics(ws, project.slug, days, tzOffset),
  })

  return (
    <div className="anim-page">
      <PageHeader
        title="Stream analytics"
        desc="Event volume, dwell time and camera activity across the project's streams."
        actions={(
          <label htmlFor="stream-analytics-days" className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
            Window
            <Select id="stream-analytics-days" value={days} onChange={(e) => setDays(Number(e.target.value))} className="h-8 text-xs">
              {[7, 30, 90, 365].map((d) => <option key={d} value={d}>Last {d} days</option>)}
            </Select>
          </label>
        )}
      />
      <div className="space-y-4 px-4 pb-10 sm:px-8">
        {q.isLoading ? <PageSkeleton /> : q.isError ? (
          <ErrorState title="Stream analytics could not be loaded" message={(q.error as Error).message} onRetry={() => q.refetch()} />
        ) : !q.data ? null : q.data.totals.events === 0 ? (
          <Card className="p-6">
            <EmptyState icon={<Activity className="h-8 w-8 text-muted-foreground/50" />} title="No stream events in this window"
              hint="Events appear here once a running stream fires a rule. Widen the window or start a stream." />
          </Card>
        ) : (
          <StreamAnalyticsView data={q.data} dim={dim} onDim={setDim} theme={theme} />
        )}
      </div>
    </div>
  )
}
