import { useMemo, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, ArrowUpRight, BarChart3, Table2 } from 'lucide-react'
import { api } from '@/lib/api'
import type { Analytics as AnalyticsData } from '@/lib/types'
import { Button, Card, Spinner, Stat, toast } from '@/components/ui'
import { useProject } from './ProjectLayout'
import { HealthCheck } from './HealthCheck'

/** Bucket names match the backend; keep the en dash in "0.3–1 MP". */
const SIZE_FILTERS: Record<string, Record<string, string>> = {
  '< 0.3 MP': { max_mp: '0.3' },
  '0.3–1 MP': { min_mp: '0.3', max_mp: '1' },
  '1–4 MP': { min_mp: '1', max_mp: '4' },
  '> 4 MP': { min_mp: '4' },
}

const ASPECT_FILTERS: Record<string, Record<string, string>> = {
  tall: { max_ar: '0.8' },
  square: { min_ar: '0.8', max_ar: '1.25' },
  wide: { min_ar: '1.25', max_ar: '2' },
  'very wide': { min_ar: '2' },
}

const fmt = (n: number) => n.toLocaleString()
const pct = (n: number, total: number) => (total ? Math.round((n / total) * 100) : 0)

/** Clickable horizontal bar. A real <button> keeps mouse, keyboard and screen-reader users on one control. */
function BarRow({ label, value, width, meta, onClick, ariaLabel, badge }: {
  label: string; value: number; width: number; meta?: string; onClick: () => void
  ariaLabel: string; badge?: string
}) {
  return (
    <li>
      <button type="button" onClick={onClick} aria-label={ariaLabel} title={ariaLabel}
        className="group flex w-full cursor-pointer items-center gap-2 rounded-md px-1.5 py-1.5 text-left text-sm transition-colors hover:bg-accent focus-visible:bg-accent">
        <span className="flex w-16 shrink-0 items-center gap-1.5 sm:w-24">
          <span className="truncate text-muted-foreground group-hover:text-foreground">{label}</span>
          {badge && <span className="shrink-0 rounded bg-warning/15 px-1 py-0.5 text-[10px] font-semibold text-warning">{badge}</span>}
        </span>
        <span className="h-2.5 min-w-0 flex-1 overflow-hidden rounded-full bg-muted" aria-hidden="true">
          <span className="block h-full rounded-full bg-primary" style={{ width: `${Math.max(value ? 2 : 0, Math.min(100, width))}%` }} />
        </span>
        <span className="w-8 shrink-0 text-right font-medium tabular-nums sm:w-10">{fmt(value)}</span>
        {meta && <span className="w-10 shrink-0 text-right text-xs tabular-nums text-muted-foreground sm:w-11">{meta}</span>}
        <ArrowUpRight className="hidden h-3.5 w-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100 sm:block" aria-hidden="true" />
      </button>
    </li>
  )
}

function LinkRow({ label, value, onClick, ariaLabel }: {
  label: string; value: number; onClick: () => void; ariaLabel: string
}) {
  return (
    <li>
      <button type="button" onClick={onClick} aria-label={ariaLabel} title={ariaLabel}
        className="group flex w-full cursor-pointer items-center gap-2 rounded-md px-1.5 py-1.5 text-left text-sm transition-colors hover:bg-accent focus-visible:bg-accent">
        <span className="flex-1 capitalize">{label}</span>
        <b className="tabular-nums">{fmt(value)}</b>
        <ArrowUpRight className="h-3.5 w-3.5 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" aria-hidden="true" />
      </button>
    </li>
  )
}

/** Text alternative for the distribution charts (WCAG 2.2: charts have a table view). */
function DistributionTable({ rows }: { rows: { group: string; bucket: string; value: number; share: number }[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <caption className="pb-2 text-left text-xs text-muted-foreground">
          Dataset distribution — the same numbers as the charts, with each row's share of its group.
        </caption>
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th scope="col" className="py-2 pr-3 font-medium">Group</th>
            <th scope="col" className="py-2 pr-3 font-medium">Bucket</th>
            <th scope="col" className="py-2 pr-3 text-right font-medium">Count</th>
            <th scope="col" className="py-2 text-right font-medium">Share</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.group}-${r.bucket}`} className="border-b last:border-0">
              <td className="py-1.5 pr-3 text-muted-foreground">{r.group}</td>
              <td className="py-1.5 pr-3 capitalize">{r.bucket}</td>
              <td className="py-1.5 pr-3 text-right tabular-nums">{fmt(r.value)}</td>
              <td className="py-1.5 text-right tabular-nums text-muted-foreground">{r.share}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ChartCard({ title, desc, children }: { title: string; desc: string; children: ReactNode }) {
  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="mt-0.5 text-xs text-muted-foreground">{desc}</p>
      {children}
    </Card>
  )
}

/** Dataset health check (Task 9): rendered as the Insights "Dataset health" tab. */
export function DatasetHealth() {
  const { project, ws } = useProject()
  const nav = useNavigate()
  const qc = useQueryClient()
  const qk = useMemo(() => ['analytics', ws, project.slug] as const, [ws, project.slug])
  const [tableView, setTableView] = useState(false)

  const q = useQuery({
    queryKey: qk,
    queryFn: () => api.analytics(ws, project.slug),
    // The pHash + missing-box scan is a background job; poll only while it is still moving.
    refetchInterval: (query) => {
      const j = query.state.data?.health_job
      return j && (j.status === 'queued' || j.status === 'running') ? 3000 : false
    },
  })
  const a = q.data

  const run = useMutation({
    mutationFn: () => api.healthCheck(ws, project.slug),
    onSuccess: (j) => {
      toast.ok('Health check queued')
      qc.setQueryData<AnalyticsData>(qk, (prev) => (prev ? { ...prev, health_job: j } : prev))
      qc.invalidateQueries({ queryKey: qk })
    },
    onError: (e) => toast.err(e as Error),
  })

  if (!a) {
    if (q.isError) return <div className="p-10 text-center text-sm text-destructive">{(q.error as Error).message}</div>
    return <div className="p-10 text-center"><Spinner /></div>
  }

  /** Every click builds a fresh URLSearchParams and pins status=all so the grid matches analytics. */
  const goBrowse = (params: Record<string, string | number> = {}, status = 'all') => {
    const p = new URLSearchParams()
    p.set('status', status)
    for (const [k, v] of Object.entries(params)) p.set(k, String(v))
    nav(`/${ws}/${project.slug}/browse?${p.toString()}`)
  }

  const maxHeat = Math.max(1, ...(a.heatmap ?? []).flat())
  const annMax = Math.max(1, ...a.annotations_per_image.map((d) => d.images))
  const sizeData = ['< 0.3 MP', '0.3–1 MP', '1–4 MP', '> 4 MP'].map((bucket) => ({
    bucket, images: a.sizes.find((x) => x.bucket === bucket)?.images ?? 0,
  }))
  const sizeMax = Math.max(1, ...sizeData.map((d) => d.images))
  const aspectData = ['tall', 'square', 'wide', 'very wide'].map((bucket) => ({
    bucket, images: a.aspect.find((x) => x.bucket === bucket)?.images ?? 0,
  }))
  const aspectMax = Math.max(1, ...aspectData.map((d) => d.images))
  const topClass = a.classes[0]?.count || 1
  const annotated = a.classes.reduce((s, c) => s + c.count, 0)
  const tableRows = [
    ...a.classes.map((c) => ({ group: 'Class', bucket: c.name, value: c.count, share: pct(c.count, annotated) })),
    ...a.annotations_per_image.map((d) => ({ group: 'Annotations', bucket: String(d.n), value: d.images, share: pct(d.images, a.images) })),
    ...sizeData.map((d) => ({ group: 'Image size', bucket: d.bucket, value: d.images, share: pct(d.images, a.images) })),
    ...aspectData.map((d) => ({ group: 'Aspect ratio', bucket: d.bucket, value: d.images, share: pct(d.images, a.images) })),
  ]

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-4">
        <Stat label="Images" value={a.images} sub={`${a.null_images} without annotations`} />
        <Stat label="Annotations" value={a.annotations} sub={`${a.avg_annotations} per image`} />
        <Stat label="Average size" value={`${a.avg_width}×${a.avg_height}`} sub={`median ${a.median_size}`} />
        <Stat label="Classes" value={a.classes.length} sub={`imbalance ${a.imbalance_ratio}×`} />
      </div>

      {a.imbalance_ratio > 5 && (
        <div role="status" className="flex items-start gap-2 rounded-lg border border-warning/40 bg-warning/10 px-4 py-2.5 text-sm text-foreground">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
          <span>The most common class has <b>{a.imbalance_ratio}×</b> more labels than the rarest. Consider collecting more of the under-represented classes.</span>
        </div>
      )}

      <HealthCheck ws={ws} slug={project.slug} models={project.models} checks={a.checks} job={a.health_job}
        stale={a.health_stale} recommendations={a.recommendations} onRun={() => run.mutate()}
        runPending={run.isPending} hasImages={a.images > 0} />

      <section aria-labelledby="distribution-heading">
        <div className="flex flex-wrap items-end justify-between gap-3 pt-2">
          <div>
            <h2 id="distribution-heading" className="text-lg font-semibold tracking-tight">Dataset distribution</h2>
            <p className="mt-0.5 text-sm text-muted-foreground">Counts include every status. Click a bar or row to open the matching images in the dataset grid.</p>
          </div>
          <Button variant="outline" size="sm" onClick={() => setTableView((v) => !v)} aria-pressed={tableView}
            title={tableView ? 'Show the charts' : 'Show the same numbers as a table'}>
            {tableView ? <BarChart3 className="h-3.5 w-3.5" /> : <Table2 className="h-3.5 w-3.5" />}
            {tableView ? 'Chart view' : 'Table view'}
          </Button>
        </div>

        {tableView ? (
          <Card className="mt-2 p-4">
            <DistributionTable rows={tableRows} />
          </Card>
        ) : (
          <>
            <Card className="mt-2 p-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h3 className="text-sm font-semibold">Class balance</h3>
                <span className="text-xs text-muted-foreground">{a.classes.length} classes · {a.imbalance_ratio}× imbalance</span>
              </div>
              {a.classes.length ? (
                <ul className="mt-2 space-y-0.5">
                  {a.classes.map((c) => (
                    <BarRow key={c.id} label={c.name} value={c.count} width={(c.count / topClass) * 100}
                      meta={`${pct(c.count, a.annotations)}%`}
                      badge={c.count < topClass * 0.2 ? 'low' : undefined}
                      onClick={() => goBrowse({ class: c.id })}
                      ariaLabel={`Show images containing the ${c.name} class in the dataset grid`} />
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-sm text-muted-foreground">No classes defined yet.</p>
              )}
            </Card>

            <div className="mt-4 grid items-start gap-4 lg:grid-cols-3">
              <ChartCard title="Annotations per image" desc="Click a bar to filter by annotation count.">
                <ul className="mt-2 max-h-72 space-y-0.5 overflow-y-auto pr-1">
                  {a.annotations_per_image.map((d) => {
                    const n = Number(d.n)
                    const filter: Record<string, string | number> = d.n === '20+' || !Number.isFinite(n)
                      ? { min_ann: 20 }
                      : { min_ann: n, max_ann: n }
                    return (
                      <BarRow key={d.n} label={String(d.n)} value={d.images} width={(d.images / annMax) * 100}
                        onClick={() => goBrowse(filter)}
                        ariaLabel={`Show images with ${d.n === '20+' ? '20 or more' : d.n} annotations in the dataset grid`} />
                    )
                  })}
                </ul>
                {!a.annotations_per_image.length && <p className="mt-3 text-sm text-muted-foreground">No annotations yet.</p>}
              </ChartCard>

              <ChartCard title="Image size" desc="Click a bar to filter by megapixels.">
                <ul className="mt-2 space-y-0.5">
                  {sizeData.map((d) => (
                    <BarRow key={d.bucket} label={d.bucket} value={d.images} width={(d.images / sizeMax) * 100}
                      onClick={() => goBrowse(SIZE_FILTERS[d.bucket] ?? {})}
                      ariaLabel={`Show images in the ${d.bucket} size range in the dataset grid`} />
                  ))}
                </ul>
              </ChartCard>

              <ChartCard title="Aspect ratio" desc="Click a bar to filter by width ÷ height.">
                <ul className="mt-2 space-y-0.5">
                  {aspectData.map((d) => (
                    <BarRow key={d.bucket} label={d.bucket} value={d.images} width={(d.images / aspectMax) * 100}
                      onClick={() => goBrowse(ASPECT_FILTERS[d.bucket] ?? {})}
                      ariaLabel={`Show ${d.bucket} images in the dataset grid`} />
                  ))}
                </ul>
              </ChartCard>
            </div>
          </>
        )}
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-4">
          <h3 className="mb-3 text-sm font-semibold">Annotation heatmap <span className="font-normal text-muted-foreground">(object centres)</span></h3>
          <div role="img" aria-label={`Where annotations cluster in the frame; the busiest cell holds ${maxHeat} objects.`}
            className="mx-auto grid aspect-video max-w-md grid-cols-10 gap-0.5 rounded border bg-muted p-0.5">
            {(a.heatmap ?? []).flat().map((v, i) => (
              <div key={i} className="rounded-sm" title={`${v} objects`}
                style={{ background: 'var(--primary)', opacity: v ? 0.12 + 0.88 * (v / maxHeat) : 0.04 }} />
            ))}
          </div>
        </Card>

        <Card className="p-4 text-sm">
          <h3 className="mb-3 font-semibold">Splits &amp; status</h3>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <h4 className="mb-1 text-xs font-semibold text-muted-foreground">Splits</h4>
              <ul>
                {Object.entries(a.splits).map(([k, v]) => (
                  <LinkRow key={k} label={k} value={v}
                    onClick={() => goBrowse({ split: k })}
                    ariaLabel={`Show images in the ${k} split in the dataset grid`} />
                ))}
              </ul>
            </div>
            <div>
              <h4 className="mb-1 text-xs font-semibold text-muted-foreground">Status</h4>
              <ul>
                {Object.entries(a.statuses).map(([k, v]) => (
                  <LinkRow key={k} label={k === 'done' ? 'dataset' : k} value={v}
                    onClick={() => goBrowse({}, k)}
                    ariaLabel={`Show ${k === 'done' ? 'dataset' : k} images in the dataset grid`} />
                ))}
              </ul>
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}
