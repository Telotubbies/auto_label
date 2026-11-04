import { Badge, Stat } from '@/components/ui'
import { classColor, viridis } from '@/lib/theme'
import type { InsightDistribution, InsightSummary } from '@/lib/types'
import { axisChrome, ChartCard, cssColor, tooltipStyle, useChartTheme } from './Chart'

const fmt = (n: number) => n.toLocaleString()
const pct = (n: number, total: number) => (total ? Math.round((n / total) * 100) : 0)

const SPLIT_SERIES = [
  { key: 'train', label: 'Train', color: cssColor(classColor(4)) },
  { key: 'valid', label: 'Valid', color: cssColor(classColor(2)) },
  { key: 'test', label: 'Test', color: cssColor(classColor(5)) },
] as const

export function Overview({ summary, distribution }: { summary: InsightSummary; distribution: InsightDistribution }) {
  const t = useChartTheme()
  const maxCount = Math.max(0, ...summary.classes.map((c) => c.count))
  const minCount = Math.min(...summary.classes.filter((c) => c.count > 0).map((c) => c.count), maxCount || 1)
  const imbalance = summary.classes.length > 1 ? Math.round((maxCount / Math.max(1, minCount)) * 10) / 10 : 1

  const splitRows = distribution.split_classes
  const classNames = splitRows.map((r) => r.class)
  const splitOption = {
    grid: { left: 8, right: 16, top: 36, bottom: 76, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...tooltipStyle(t) },
    legend: { top: 0, textStyle: { color: t.muted, fontSize: 11 } },
    xAxis: { type: 'category', data: classNames, ...axisChrome(t), axisLabel: { ...axisChrome(t).axisLabel, interval: 0, rotate: 42, overflow: 'truncate', width: 96 } },
    yAxis: { type: 'value', ...axisChrome(t) },
    series: SPLIT_SERIES.map((s) => ({
      name: s.label, type: 'bar', stack: 'split', barMaxWidth: 44,
      itemStyle: { color: s.color },
      data: splitRows.map((r) => r[s.key]),
    })),
  }

  const instanceRows = distribution.instances_vs_images
  const instancesOption = {
    grid: { left: 8, right: 16, top: 36, bottom: 76, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...tooltipStyle(t) },
    legend: { top: 0, textStyle: { color: t.muted, fontSize: 11 } },
    xAxis: { type: 'category', data: instanceRows.map((r) => r.class), ...axisChrome(t), axisLabel: { ...axisChrome(t).axisLabel, interval: 0, rotate: 42, overflow: 'truncate', width: 96 } },
    yAxis: { type: 'value', ...axisChrome(t) },
    series: [
      { name: 'Instances', type: 'bar', barMaxWidth: 26, itemStyle: { color: t.primary }, data: instanceRows.map((r) => r.instances) },
      { name: 'Images', type: 'bar', barMaxWidth: 26, itemStyle: { color: cssColor(classColor(1)) }, data: instanceRows.map((r) => r.images) },
    ],
  }

  const co = distribution.cooccurrence
  const coMax = Math.max(1, ...co.matrix.flat())
  const coData = co.matrix.flatMap((row, y) => row.map((value, x) => ({
    value: [x, y, value],
    itemStyle: { color: value ? cssColor(viridis(value / coMax)) : 'transparent', borderColor: t.card, borderWidth: 1 },
  })))
  const coOption = {
    grid: { left: 8, right: 16, top: 12, bottom: 84, containLabel: true },
    tooltip: {
      ...tooltipStyle(t),
      formatter: (p: unknown) => {
        const v = (p as { value?: [number, number, number] }).value
        return v ? `${co.classes[v[1]] ?? ''} × ${co.classes[v[0]] ?? ''}: ${fmt(v[2])}` : ''
      },
    },
    xAxis: { type: 'category', data: co.classes, ...axisChrome(t), splitLine: { show: false }, axisLabel: { ...axisChrome(t).axisLabel, interval: 0, rotate: 45, overflow: 'truncate', width: 90 } },
    yAxis: { type: 'category', data: co.classes, ...axisChrome(t), splitLine: { show: false }, axisLabel: { ...axisChrome(t).axisLabel, interval: 0, overflow: 'truncate', width: 90 } },
    series: [{ type: 'heatmap', data: coData, emphasis: { itemStyle: { borderColor: t.fg, borderWidth: 1 } } }],
  }

  const annRows = distribution.annotations_per_image
  const annOption = {
    grid: { left: 8, right: 16, top: 24, bottom: 48, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...tooltipStyle(t) },
    xAxis: { type: 'category', data: annRows.map((r) => r.bucket), name: 'Annotations per image', nameLocation: 'middle', nameGap: 30, nameTextStyle: { color: t.muted, fontSize: 11 }, ...axisChrome(t) },
    yAxis: { type: 'value', ...axisChrome(t) },
    series: [{ type: 'bar', barMaxWidth: 36, itemStyle: { color: t.primary, borderRadius: [3, 3, 0, 0] }, data: annRows.map((r) => r.images) }],
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-lg font-semibold tracking-tight">Dataset overview</h2>
        {summary.version
          ? <Badge className="bg-accent text-accent-foreground">Version {summary.version.name}</Badge>
          : <Badge>All images</Badge>}
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Images" value={fmt(summary.images)} sub={`${fmt(summary.null_images)} without annotations`} />
        <Stat label="Annotations" value={fmt(summary.annotations)} sub={`${summary.images ? (summary.annotations / summary.images).toFixed(1) : '0'} per image`} />
        <Stat label="Classes" value={fmt(summary.classes.length)} sub={`${fmt(summary.sources.length)} label ${summary.sources.length === 1 ? 'source' : 'sources'}`} />
        <Stat label="Class imbalance" value={`${imbalance}×`} sub="most common ÷ rarest" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Class distribution per split"
          desc="Annotations of each class in train, valid and test."
          ariaLabel={`Stacked bar chart of class distribution per split across ${classNames.length} classes.`}
          option={splitOption}
          table={{
            caption: 'Annotations per class and split.',
            columns: ['Class', 'Train', 'Valid', 'Test'],
            rows: splitRows.map((r) => [r.class, r.train, r.valid, r.test]),
          }}
          empty={splitRows.length ? undefined : 'No labelled classes in this scope yet.'}
        />

        <ChartCard
          title="Instances vs images"
          desc="How many boxes a class draws compared with how many images contain it."
          ariaLabel={`Grouped bar chart comparing annotation instances and image counts for ${instanceRows.length} classes.`}
          option={instancesOption}
          table={{
            caption: 'Annotation instances and image counts per class.',
            columns: ['Class', 'Instances', 'Images', 'Per image'],
            rows: instanceRows.map((r) => [r.class, r.instances, r.images, r.images ? (r.instances / r.images).toFixed(1) : '0']),
          }}
          empty={instanceRows.length ? undefined : 'No annotations in this scope yet.'}
        />

        <ChartCard
          title="Class co-occurrence"
          desc="How often two classes share an image; darker cells are stronger pairs."
          ariaLabel={`Heatmap of class co-occurrence across ${co.classes.length} classes.`}
          option={coOption}
          height={320}
          table={{
            caption: 'Images containing each pair of classes (diagonal = images with that class).',
            columns: ['Class', ...co.classes],
            rows: co.classes.map((name, y) => [name, ...co.matrix[y].map((n) => n)]),
          }}
          empty={co.classes.length ? undefined : 'At least two classes are needed to measure co-occurrence.'}
          footnote={co.classes.length ? `${co.classes.length} classes; diagonal counts images containing that class.` : undefined}
        />

        <ChartCard
          title="Annotations per image"
          desc="Distribution of annotation counts across the image set."
          ariaLabel={`Histogram of annotation counts across ${fmt(summary.images)} images.`}
          option={annOption}
          table={{
            caption: 'Number of images by annotation-count bucket.',
            columns: ['Annotations', 'Images', 'Share'],
            rows: annRows.map((r) => [r.bucket, r.images, `${pct(r.images, summary.images)}%`]),
          }}
          empty={annRows.length ? undefined : 'No annotated images in this scope yet.'}
        />
      </div>
    </div>
  )
}
