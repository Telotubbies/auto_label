import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { AlertTriangle, Loader2, RotateCw, ShieldCheck } from 'lucide-react'
import { api, fileUrl } from '@/lib/api'
import { classColor } from '@/lib/theme'
import type { InsightLeakage } from '@/lib/types'
import { Badge, Button, Card, EmptyState, Progress, toast } from '@/components/ui'
import { axisChrome, ChartCard, cssColor, tooltipStyle, useChartTheme } from './Chart'

const fmt = (n: number) => n.toLocaleString()
const SPLIT_COLOR: Record<string, string> = {
  train: cssColor(classColor(4)), valid: cssColor(classColor(2)), test: cssColor(classColor(5)),
}
const splitColor = (s: string) => SPLIT_COLOR[s] ?? cssColor(classColor(0))
const distanceText = (d: number) => (Number.isInteger(d) ? fmt(d) : d.toFixed(3))

function SplitBadge({ split }: { split: string }) {
  return (
    <Badge className="capitalize">
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: splitColor(split) }} aria-hidden="true" />
      {split}
    </Badge>
  )
}

export function Leakage({ ws, slug, leakage, versionLabel, version }: {
  ws: string
  slug: string
  leakage: InsightLeakage
  versionLabel?: string
  version?: string
}) {
  const t = useChartTheme()
  const qc = useQueryClient()
  const job = leakage.job
  const running = !!job && (job.status === 'queued' || job.status === 'running')
  const run = useMutation({
    mutationFn: () => api.insights.scanLeakage(ws, slug, version || undefined),
    onSuccess: () => { toast.ok('Leakage scan queued'); qc.invalidateQueries({ queryKey: ['insights'] }) },
    onError: (e) => toast.err(e as Error),
  })

  const pairs = [...leakage.split_pairs].sort((a, b) => b.count - a.count)
  const pairOption = {
    grid: { left: 8, right: 24, top: 20, bottom: 30, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...tooltipStyle(t) },
    xAxis: { type: 'value', ...axisChrome(t) },
    yAxis: { type: 'category', inverse: true, data: pairs.map((p) => `${p.a} ↔ ${p.b}`), ...axisChrome(t) },
    series: [{
      type: 'bar', barMaxWidth: 26,
      itemStyle: { color: cssColor(classColor(5)), borderRadius: [0, 3, 3, 0] },
      label: { show: true, position: 'right', color: t.muted, fontSize: 10 },
      data: pairs.map((p) => p.count),
    }],
  }

  const emptyCopy = leakage.total_pairs === 0
    ? 'No cross-split near-duplicates found'
    : undefined

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Split leakage</h2>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Near-identical images that could make evaluation look better than the model really is.
          {versionLabel
            ? ` Pairs use the splits frozen in ${versionLabel}, not each image's current split.`
            : ' Pairs use the split currently set on each image.'}
        </p>
      </div>
      <Card className="flex flex-wrap items-center gap-x-4 gap-y-2 p-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">Near-duplicate scan</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            pHash comparison across splits; the gallery shows the closest pairs first.
          </p>
        </div>
        <Badge className="tabular-nums">{fmt(leakage.total_pairs)} cross-split {leakage.total_pairs === 1 ? 'pair' : 'pairs'}</Badge>
        <Button variant="outline" size="sm" onClick={() => run.mutate()} disabled={run.isPending || running}
          title={running ? 'A scan is already running' : undefined}>
          {running || run.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : <RotateCw className="h-3.5 w-3.5" aria-hidden="true" />}
          {running ? 'Scanning…' : 'Scan for leakage'}
        </Button>
      </Card>

      {running && (
        <div role="status" className="rounded-lg border px-4 py-3 text-sm">
          <div className="flex items-center gap-2"><span className="font-medium">{job?.status === 'queued' ? 'Scan queued' : 'Comparing image hashes…'}</span><span className="ml-auto text-xs tabular-nums text-muted-foreground">{Math.round(job?.progress ?? 0)}%</span></div>
          <Progress className="mt-2" value={job?.progress ?? 0} />
          <p className="mt-2 text-xs text-muted-foreground">This page refreshes automatically when the scan finishes.</p>
        </div>
      )}
      {job?.status === 'failed' && !running && (
        <p role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-2.5 text-sm text-destructive">
          The last leakage scan failed: {job.error || 'unknown error'}
        </p>
      )}
      {leakage.stale && !running && (
        <div role="status" className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border border-warning/40 bg-warning/10 px-4 py-2.5 text-sm">
          <AlertTriangle className="h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
          <p className="min-w-0 flex-1">The dataset changed since this scan — run it again for current pairs.</p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <Card className="border-l-4 border-l-warning p-4">
          <div className="text-xs font-medium text-muted-foreground">Cross-split pairs</div>
          <div className="mt-1 text-2xl font-bold tabular-nums">{fmt(leakage.total_pairs)}</div>
          <div className="mt-0.5 text-xs text-muted-foreground">near-duplicates to review</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs font-medium text-muted-foreground">Split combinations</div>
          <div className="mt-1 text-2xl font-bold tabular-nums">{fmt(leakage.split_pairs.length)}</div>
          <div className="mt-0.5 text-xs text-muted-foreground">split {leakage.split_pairs.length === 1 ? 'combination' : 'combinations'} affected</div>
        </Card>
        <Card className="col-span-2 p-4 md:col-span-1">
          <div className="text-xs font-medium text-muted-foreground">Leakage moved{versionLabel ? ` in ${versionLabel}` : ''}</div>
          <div className="mt-1 text-2xl font-bold tabular-nums">
            {versionLabel && leakage.leakage_moved != null ? fmt(leakage.leakage_moved) : '—'}
          </div>
          <div className="mt-0.5 text-xs text-muted-foreground">
            {versionLabel
              ? leakage.leakage_moved == null ? 'no move count recorded for this version' : 'images regrouped when the version was built'
              : 'select a version to see moves'}
          </div>
        </Card>
      </div>

      <ChartCard
        title="Pairs per split combination"
        desc="Which splits share near-identical images, and how many."
        ariaLabel={`Bar chart of near-duplicate counts across ${pairs.length} split combinations.`}
        option={pairOption}
        height={Math.max(220, 48 + pairs.length * 34)}
        table={{
          caption: 'Cross-split near-duplicate pairs by split combination.',
          columns: ['Splits', 'Pairs'],
          rows: pairs.map((p) => [`${p.a} ↔ ${p.b}`, p.count]),
        }}
        empty={pairs.length ? undefined : emptyCopy}
      />

      <section aria-labelledby="leakage-gallery">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 id="leakage-gallery" className="text-lg font-semibold tracking-tight">Pair gallery</h2>
            <p className="mt-0.5 text-sm text-muted-foreground">Open either image to fix its split, or version again with near-duplicate grouping.</p>
          </div>
          <span className="text-xs text-muted-foreground">{fmt(leakage.pairs.length)} shown</span>
        </div>
        {leakage.pairs.length ? (
          <ul className="mt-2 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {leakage.pairs.map(({ a, b, distance }) => (
              <li key={`${a.image_id}-${b.image_id}`}>
                <Card className="p-2">
                  <div className="grid grid-cols-2 gap-2">
                    {[a, b].map((img) => (
                      <Link key={img.image_id} to={`/${ws}/${slug}/images/${img.image_id}`}
                        className="group relative block overflow-hidden rounded-md border bg-muted"
                        aria-label={`Open ${img.name} (${img.split}) in the editor`}>
                        {img.thumb
                          ? <img src={fileUrl(img.thumb)} alt={img.name} loading="lazy" className="h-24 w-full object-cover transition-transform group-hover:scale-[1.02]" />
                          : <span className="block h-24 w-full bg-muted" aria-hidden="true" />}
                        <span className="absolute left-1 top-1"><SplitBadge split={img.split} /></span>
                        <span className="absolute inset-x-0 bottom-0 truncate border-t bg-card/95 px-2 py-1 text-[10px] text-card-foreground">{img.name}</span>
                      </Link>
                    ))}
                  </div>
                  <div className="mt-2 flex items-center justify-between gap-2 text-xs">
                    <span className="text-muted-foreground">pHash distance</span>
                    <Badge className="tabular-nums">{distanceText(distance)}</Badge>
                  </div>
                </Card>
              </li>
            ))}
          </ul>
        ) : (
          <Card className="mt-2 p-6">
            <EmptyState
              icon={<ShieldCheck className="h-6 w-6 text-success" />}
              title={leakage.total_pairs ? 'No pair thumbnails returned.' : 'No cross-split near-duplicates found'}
              hint={leakage.total_pairs ? 'The counts are available but the gallery is empty.' : 'Train, valid and test look clean. Run the scan again after importing new images.'}
              action={!running && (
                <Button variant="outline" size="sm" onClick={() => run.mutate()} disabled={run.isPending}>
                  <RotateCw className="h-3.5 w-3.5" aria-hidden="true" /> Run scan
                </Button>
              )}
            />
          </Card>
        )}
      </section>
    </div>
  )
}
