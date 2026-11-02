import { Link } from 'react-router-dom'
import { ArrowRight, GitCompareArrows } from 'lucide-react'
import { fileUrl } from '@/lib/api'
import { classColor } from '@/lib/theme'
import type { InsightLabeling, InsightVersionDiff, Version } from '@/lib/types'
import { Badge, Card, EmptyState, Select } from '@/components/ui'
import { axisChrome, ChartCard, cssColor, PanelError, tooltipStyle, useChartTheme } from './Chart'

const fmt = (n: number) => n.toLocaleString()
const pct = (n: number, total: number) => (total ? Math.round((n / total) * 100) : 0)
const ratePct = (r: number) => Math.round((r <= 1 ? r * 100 : r) * 10) / 10
const day = (d: string) => (d.length > 10 ? d.slice(5, 10) : d)
const SPLIT_COLOR: Record<string, string> = {
  train: cssColor(classColor(4)), valid: cssColor(classColor(2)), test: cssColor(classColor(5)),
}

type DiffImage = InsightVersionDiff['added'][number]

function ImageList({ ws, slug, title, items, empty }: { ws: string; slug: string; title: string; items: DiffImage[]; empty: string }) {
  return (
    <div className="min-w-0">
      <h4 className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
        {title}<Badge className="tabular-nums">{fmt(items.length)}</Badge>
      </h4>
      {items.length ? (
        <ul className="mt-1.5 max-h-48 space-y-1 overflow-y-auto pr-1">
          {items.map((x) => (
            <li key={x.image_id}>
              <Link to={`/${ws}/${slug}/images/${x.image_id}`} className="flex items-center gap-2 rounded-md px-1 py-1 text-xs hover:bg-accent"
                aria-label={`${x.name} in the ${x.split} split`}>
                {x.thumb
                  ? <img src={fileUrl(x.thumb)} alt="" loading="lazy" className="h-8 w-11 shrink-0 rounded border object-cover" />
                  : <span className="h-8 w-11 shrink-0 rounded border bg-muted" aria-hidden="true" />}
                <span className="min-w-0 flex-1 truncate">{x.name}</span>
                <span className="flex shrink-0 items-center gap-1 capitalize text-muted-foreground">
                  <span className="h-1.5 w-1.5 rounded-full" style={{ background: SPLIT_COLOR[x.split] ?? cssColor(classColor(0)) }} aria-hidden="true" />
                  {x.split}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : <p className="mt-2 text-xs text-muted-foreground">{empty}</p>}
    </div>
  )
}

function VersionPicker({ versions, base, target, onBase, onTarget }: {
  versions: Version[]
  base: string
  target: string
  onBase: (id: string) => void
  onTarget: (id: string) => void
}) {
  const options = versions.map((v) => <option key={v.id} value={v.id}>v{v.number} · {v.name}</option>)
  return (
    <Card className="flex flex-wrap items-end gap-3 p-3">
      <label className="flex flex-col gap-1 text-xs text-muted-foreground">
        Base version
        <Select value={base} onChange={(e) => onBase(e.target.value)} disabled={!versions.length} className="min-w-44">{options}</Select>
      </label>
      <ArrowRight className="mb-2.5 hidden h-4 w-4 shrink-0 text-muted-foreground sm:block" aria-hidden="true" />
      <label className="flex flex-col gap-1 text-xs text-muted-foreground">
        Target version
        <Select value={target} onChange={(e) => onTarget(e.target.value)} disabled={!versions.length} className="min-w-44">{options}</Select>
      </label>
      <p className="mb-2 text-xs text-muted-foreground">Added, removed and moved images are measured from base to target.</p>
    </Card>
  )
}

export function VersionsOps({ ws, slug, versions, base, target, onBase, onTarget, diff, diffError, labeling }: {
  ws: string
  slug: string
  versions: Version[]
  base: string
  target: string
  onBase: (id: string) => void
  onTarget: (id: string) => void
  diff: InsightVersionDiff | null
  diffError?: Error | null
  labeling: InsightLabeling
}) {
  const t = useChartTheme()
  const canCompare = !!diff

  const deltaRows = (diff?.class_delta ?? [])
    .filter((r) => r.delta !== 0)
    .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
  const deltaOption = {
    grid: { left: 8, right: 28, top: 16, bottom: 24, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...tooltipStyle(t) },
    xAxis: { type: 'value', ...axisChrome(t) },
    yAxis: { type: 'category', inverse: true, data: deltaRows.map((r) => r.class), ...axisChrome(t) },
    series: [{
      type: 'bar', barMaxWidth: 22,
      data: deltaRows.map((r) => ({ value: r.delta, itemStyle: { color: cssColor(classColor(r.delta >= 0 ? 2 : 5)), borderRadius: r.delta >= 0 ? [0, 3, 3, 0] : [3, 0, 0, 3] } })),
      label: { show: true, position: 'right', color: t.muted, fontSize: 10 },
    }],
  }

  const throughput = labeling.throughput
  const byAssignee = labeling.throughput_basis === 'image_assignee'
  const actorNoun = byAssignee ? 'assignee' : 'author'
  const actorColumn = byAssignee ? 'Assignee' : 'Author'
  const dates = [...new Set(throughput.map((r) => r.date))].sort()
  const totals = new Map<string, number>()
  for (const r of throughput) totals.set(r.labeler, (totals.get(r.labeler) ?? 0) + r.annotations)
  const topLabelers = [...totals.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5).map(([name]) => name)
  const throughputOption = {
    grid: { left: 8, right: 20, top: 34, bottom: 30, containLabel: true },
    tooltip: { trigger: 'axis', ...tooltipStyle(t) },
    legend: { top: 0, textStyle: { color: t.muted, fontSize: 11 } },
    xAxis: { type: 'category', data: dates.map(day), ...axisChrome(t) },
    yAxis: { type: 'value', ...axisChrome(t) },
    series: topLabelers.map((name, i) => ({
      name, type: 'line', smooth: true, symbolSize: 4, connectNulls: true,
      lineStyle: { color: cssColor(classColor(i)), width: 2 }, itemStyle: { color: cssColor(classColor(i)) },
      data: dates.map((d) => throughput.find((r) => r.date === d && r.labeler === name)?.annotations ?? 0),
    })),
  }

  const review = labeling.review
  const reviewOption = {
    grid: { left: 8, right: 48, top: 34, bottom: 30, containLabel: true },
    tooltip: { trigger: 'axis', ...tooltipStyle(t) },
    legend: { top: 0, textStyle: { color: t.muted, fontSize: 11 } },
    xAxis: { type: 'category', data: review.map((r) => day(r.date)), ...axisChrome(t) },
    yAxis: [
      { type: 'value', ...axisChrome(t) },
      { type: 'value', min: 0, max: 100, axisLabel: { ...axisChrome(t).axisLabel, formatter: '{value}%' }, splitLine: { show: false }, axisLine: { lineStyle: { color: t.border } } },
    ],
    series: [
      { name: 'Approved', type: 'bar', stack: 'review', barMaxWidth: 24, itemStyle: { color: cssColor(classColor(2)) }, data: review.map((r) => r.approved) },
      { name: 'Rejected', type: 'bar', stack: 'review', barMaxWidth: 24, itemStyle: { color: cssColor(classColor(5)) }, data: review.map((r) => r.rejected) },
      { name: 'Rejection rate', type: 'line', yAxisIndex: 1, symbolSize: 5, connectNulls: true, lineStyle: { color: t.primary, width: 2 }, itemStyle: { color: t.primary }, data: review.map((r) => ratePct(r.rate)) },
    ],
  }

  const ai = labeling.ai
  const aiSlices = [
    { name: 'Human labels', value: ai.human, color: cssColor(classColor(4)) },
    { name: 'AI still unchanged', value: ai.accepted_ai, color: cssColor(classColor(2)) },
    { name: 'AI on unapproved images', value: Math.max(0, ai.ai - ai.accepted_ai), color: cssColor(classColor(5)) },
  ].filter((s) => s.value > 0)
  const aiTotal = aiSlices.reduce((s, x) => s + x.value, 0)
  const aiOption = {
    tooltip: { ...tooltipStyle(t), formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, textStyle: { color: t.muted, fontSize: 11 } },
    series: [{
      type: 'pie', radius: ['52%', '76%'], center: ['50%', '44%'],
      label: { color: t.fg, fontSize: 10, formatter: '{b}\n{c}' },
      labelLine: { lineStyle: { color: t.border } },
      itemStyle: { borderColor: t.card, borderWidth: 2 },
      data: aiSlices.map((s) => ({ name: s.name, value: s.value, itemStyle: { color: s.color } })),
    }],
  }

  const sources = [...ai.by_source].sort((a, b) => b.count - a.count)
  const sourceTotal = sources.reduce((s, x) => s + x.count, 0)
  const sourceOption = {
    grid: { left: 8, right: 24, top: 12, bottom: 24, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...tooltipStyle(t) },
    xAxis: { type: 'value', ...axisChrome(t) },
    yAxis: { type: 'category', inverse: true, data: sources.map((s) => s.source), ...axisChrome(t) },
    series: [{
      type: 'bar', barMaxWidth: 22,
      data: sources.map((s, i) => ({ value: s.count, itemStyle: { color: cssColor(classColor(i)), borderRadius: [0, 3, 3, 0] } })),
    }],
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="flex items-center gap-2 text-lg font-semibold tracking-tight"><GitCompareArrows className="h-4 w-4 text-muted-foreground" aria-hidden="true" /> Versions &amp; ops</h2>
        <span className="text-sm text-muted-foreground">Compare frozen versions and watch labeling throughput.</span>
      </div>

      <VersionPicker versions={versions} base={base} target={target} onBase={onBase} onTarget={onTarget} />

      {!versions.length ? (
        <Card className="p-6"><EmptyState title="No versions yet." hint="Generate two versions to compare added, removed and moved images." /></Card>
      ) : diffError ? (
        <PanelError error={diffError} />
      ) : !canCompare ? (
        <Card className="p-6"><EmptyState title="Choose two versions to compare." hint="Pick a base and a target above; the newest two are selected by default." /></Card>
      ) : (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Card className="border-l-4 border-l-primary p-4"><div className="text-xs font-medium text-muted-foreground">Added in target</div><div className="mt-1 text-2xl font-bold tabular-nums">{fmt(diff.summary.added)}</div></Card>
          <Card className="border-l-4 border-l-destructive p-4"><div className="text-xs font-medium text-muted-foreground">Removed</div><div className="mt-1 text-2xl font-bold tabular-nums">{fmt(diff.summary.removed)}</div></Card>
          <Card className="border-l-4 border-l-warning p-4"><div className="text-xs font-medium text-muted-foreground">Split moves</div><div className="mt-1 text-2xl font-bold tabular-nums">{fmt(diff.summary.moved)}</div></Card>
          <Card className="p-4"><div className="text-xs font-medium text-muted-foreground">Version hash match</div><div className="mt-1 truncate text-sm font-semibold">{diff.base.version_hash && diff.target.version_hash ? (diff.base.version_hash === diff.target.version_hash ? 'Identical' : 'Different') : '—'}</div><div className="mt-1 text-xs text-muted-foreground">v{diff.base.number} → v{diff.target.number}</div></Card>
        </div>
      )}

      {canCompare && !diffError && (
        <div className="grid gap-4 lg:grid-cols-2">
          <ChartCard
            title="Class-count delta"
            desc="Target minus base annotations per class."
            ariaLabel={`Diverging bar chart of class-count changes across ${deltaRows.length} classes.`}
            option={deltaOption}
            height={Math.max(240, 60 + deltaRows.length * 26)}
            table={{
              caption: `Annotation counts per class, base v${diff.base.number} → target v${diff.target.number}.`,
              columns: ['Class', 'Base', 'Target', 'Delta'],
              rows: deltaRows.map((r) => [r.class, r.base, r.target, r.delta > 0 ? `+${r.delta}` : r.delta]),
            }}
            empty={deltaRows.length ? undefined : 'No class-count changes between these versions.'}
          />

          <Card className="grid gap-4 p-4 sm:grid-cols-2">
            <div className="sm:col-span-2 flex items-center justify-between gap-2">
              <h3 className="text-sm font-semibold">Image changes</h3>
              <span className="text-xs text-muted-foreground">v{diff.base.number} → v{diff.target.number}</span>
            </div>
            <ImageList ws={ws} slug={slug} title="Added" items={diff.added} empty="No images added." />
            <ImageList ws={ws} slug={slug} title="Removed" items={diff.removed} empty="No images removed." />
            <div className="sm:col-span-2 border-t pt-2">
              <h4 className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">Split moves <Badge className="tabular-nums">{fmt(diff.split_moves.length)}</Badge></h4>
              {diff.split_moves.length ? (
                <ul className="mt-1.5 max-h-40 space-y-1 overflow-y-auto pr-1 text-xs">
                  {diff.split_moves.map((m) => (
                    <li key={m.image_id} className="flex items-center gap-2 rounded-md px-1 py-1">
                      <span className="min-w-0 flex-1 truncate">{m.name}</span>
                      <span className="flex shrink-0 items-center gap-1 capitalize text-muted-foreground">
                        {m.from}<ArrowRight className="h-3 w-3" aria-hidden="true" />{m.to}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : <p className="mt-2 text-xs text-muted-foreground">No images changed split.</p>}
            </div>
          </Card>
        </div>
      )}

      <section aria-labelledby="labeling-heading" className="space-y-4 pt-2">
        <div>
          <h2 id="labeling-heading" className="text-lg font-semibold tracking-tight">Labeling operations</h2>
          <p className="mt-0.5 text-sm text-muted-foreground">Throughput, review quality, and how many AI labels on approved images are still unchanged.</p>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <ChartCard
            title={byAssignee ? 'Assignee activity (image-level proxy)' : 'Annotations per author per day'}
            desc={byAssignee
              ? 'Per-annotation authors are not recorded, so this counts annotations on images last updated by each assignee.'
              : 'Annotations completed per day; top five authors by total output.'}
            ariaLabel={`Line chart of daily annotation activity for ${topLabelers.length} ${actorNoun}s.`}
            option={throughputOption}
            table={{
              caption: byAssignee
                ? 'Daily annotations on images last updated by each assignee (top five).'
                : 'Daily annotations and images per author (top five).',
              columns: ['Date', actorColumn, 'Annotations', 'Images'],
              rows: throughput.filter((r) => topLabelers.includes(r.labeler)).map((r) => [r.date, r.labeler, r.annotations, r.images]),
            }}
            empty={throughput.length ? undefined : 'No annotations recorded in this period.'}
          />

          <ChartCard
            title="Review decisions"
            desc="Approved and rejected images per day, with the rejection rate."
            ariaLabel="Stacked bars of approved and rejected reviews with a rejection-rate line."
            option={reviewOption}
            table={{
              caption: 'Daily review outcomes and rejection rate.',
              columns: ['Date', 'Approved', 'Rejected', 'Rejection rate'],
              rows: review.map((r) => [r.date, r.approved, r.rejected, `${ratePct(r.rate)}%`]),
            }}
            empty={review.length ? undefined : 'No review decisions yet.'}
          />
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <ChartCard
            title="AI labels still unchanged on approved images"
            desc={`${fmt(ai.accepted_ai)} of ${fmt(ai.ai)} AI labels on approved images are still unchanged; the chart also shows human label volume for scale.`}
            ariaLabel={`Donut chart of ${fmt(aiTotal)} labels: human, AI still unchanged on approved images, and AI on unapproved images.`}
            option={aiOption}
            table={{
              caption: 'Label volume by origin; AI segments count labels on approved images.',
              columns: ['Segment', 'Labels', 'Share'],
              rows: aiSlices.map((s) => [s.name, s.value, `${pct(s.value, aiTotal)}%`]),
            }}
            empty={aiTotal ? undefined : 'No labels recorded yet.'}
            footnote="“Unchanged” means nobody edited the AI-proposed label after it was applied on an approved image. It is not a record of human acceptance — per-annotation reviewers are not tracked."
          />

          <ChartCard
            title="AI labels by source"
            desc="AI labels on approved images by source, with how many are still unchanged."
            ariaLabel={`Bar chart of AI label counts across ${sources.length} sources.`}
            option={sourceOption}
            height={Math.max(240, 60 + sources.length * 28)}
            table={{
              caption: 'AI labels on approved images by source; unchanged counts are those nobody has edited.',
              columns: ['Source', 'AI labels', 'Unchanged', 'Share'],
              rows: sources.map((s) => [s.source, s.count, s.accepted, `${pct(s.count, sourceTotal)}%`]),
            }}
            empty={sources.length ? undefined : 'No label sources recorded yet.'}
          />
        </div>
      </section>
    </div>
  )
}
