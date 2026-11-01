import { useMemo, useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle, ArrowUpRight, Frame, Lightbulb, Link2, Loader2, RotateCw, ScanSearch, ShieldAlert, ShieldCheck,
} from 'lucide-react'
import { api } from '@/lib/api'
import type { Analytics as AnalyticsData, HealthRecommendation, LabelIssueKind } from '@/lib/types'
import { Badge, Button, Card, PageHeader, Progress, Spinner, Stat, fmtAgo, toast } from '@/components/ui'
import { cn } from '@/lib/utils'
import { useProject } from './ProjectLayout'

const KIND_LABEL: Record<LabelIssueKind, string> = {
  tiny: 'Tiny box',
  out_of_bounds: 'Outside image',
  zero_area: 'Zero area',
  duplicate: 'Duplicate',
}

const KIND_ORDER: LabelIssueKind[] = ['tiny', 'out_of_bounds', 'zero_area', 'duplicate']

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

const SIZE_META = [
  { key: 'small', label: 'Small', hint: '< 32² px', tone: 'bg-warning' },
  { key: 'medium', label: 'Medium', hint: '< 96² px', tone: 'bg-info' },
  { key: 'large', label: 'Large', hint: '≥ 96² px', tone: 'bg-success' },
] as const

const fmt = (n: number) => n.toLocaleString()
const pct = (n: number, total: number) => (total ? Math.round((n / total) * 100) : 0)
const shortId = (id?: string | null) => (!id ? '—' : id.length > 10 ? `${id.slice(0, 8)}…` : id)

function boxText(box: number[] | undefined) {
  if (!box || box.length < 4) return 'unknown box'
  // The contract says pixels, but the shipped worker stores normalised boxes; support both.
  if (box.every((n) => n >= -0.01 && n <= 1.01)) {
    const [x, y, w, h] = box
    return `${Math.round(x * 100)}%, ${Math.round(y * 100)}% · ${Math.round(w * 100)}% × ${Math.round(h * 100)}%`
  }
  const [x, y, w, h] = box.map((n) => Math.round(n))
  return `${x},${y} · ${w}×${h} px`
}

function suggestText(v: unknown): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'boolean') return v ? 'on' : 'off'
  if (Array.isArray(v)) return v.map(suggestText).join(', ')
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

/** Clickable horizontal bar. A real <button> keeps mouse, keyboard and screen-reader users on the same control. */
function BarRow({ label, value, width, meta, onClick, ariaLabel, tone = 'bg-primary', badge }: {
  label: string; value: number; width: number; meta?: string; onClick: () => void
  ariaLabel: string; tone?: string; badge?: string
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
          <span className={cn('block h-full rounded-full', tone)} style={{ width: `${Math.max(value ? 2 : 0, Math.min(100, width))}%` }} />
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

function HealthCardHead({ icon, title, desc, aside }: {
  icon: ReactNode; title: string; desc: string; aside?: ReactNode
}) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="flex min-w-0 items-start gap-2.5">
        <span className="mt-0.5 shrink-0 text-muted-foreground" aria-hidden="true">{icon}</span>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold">{title}</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">{desc}</p>
        </div>
      </div>
      {aside && <div className="shrink-0">{aside}</div>}
    </div>
  )
}

/** The health cards are scroll targets, so they are programmatically focusable. */
function HealthCard({ id, children }: { id: string; children: ReactNode }) {
  return (
    <Card id={id} tabIndex={-1} className="h-full scroll-mt-24 border-border bg-card p-4 text-card-foreground">
      {children}
    </Card>
  )
}

function LinkButton({ to, children, className }: { to: string; children: ReactNode; className?: string }) {
  return (
    <Link to={to}
      className={cn('inline-flex min-h-8 cursor-pointer items-center justify-center gap-1.5 rounded-md border border-input bg-card px-3 py-1.5 text-xs font-medium transition-colors hover:bg-accent hover:text-accent-foreground', className)}>
      {children}
    </Link>
  )
}

export default function Analytics() {
  const { project, ws } = useProject()
  const nav = useNavigate()
  const qc = useQueryClient()
  const qk = useMemo(() => ['analytics', ws, project.slug] as const, [ws, project.slug])

  const q = useQuery({
    queryKey: qk,
    queryFn: () => api.analytics(ws, project.slug),
    // The missing-box scan is a background job; poll only while it is still moving.
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

  const [showAllIssues, setShowAllIssues] = useState(false)
  const [showAllMissing, setShowAllMissing] = useState(false)

  if (!a) {
    if (q.isError) return <div className="p-10 text-center text-sm text-destructive">{(q.error as Error).message}</div>
    return <div className="p-10 text-center"><Spinner /></div>
  }

  const checks = a.checks
  const job = a.health_job
  const hasModel = project.models > 0
  const runningJob = job && (job.status === 'queued' || job.status === 'running') ? job : null
  const failed = job?.status === 'failed'
  const recs = a.recommendations ?? []
  const scanLabel = runningJob ? 'Check running' : failed ? 'Last check failed'
    : job?.finished ? `Last check ${fmtAgo(job.finished)}` : hasModel ? 'Not checked yet' : 'No trained model yet'

  /** Every click builds a fresh URLSearchParams and pins status=all so the grid matches analytics. */
  const goBrowse = (params: Record<string, string | number> = {}, status = 'all') => {
    const p = new URLSearchParams()
    p.set('status', status)
    for (const [k, v] of Object.entries(params)) p.set(k, String(v))
    nav(`/${ws}/${project.slug}/browse?${p.toString()}`)
  }

  const editorHref = (imageId: string) => `/${ws}/${project.slug}/images/${imageId}`

  const focusHealth = (id: string) => {
    const el = document.getElementById(id)
    if (!el) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' })
    el.focus({ preventScroll: true })
  }

  /** One-click follow-up per recommendation; values stay suggestions, never auto-applied. */
  const recAction = (r: HealthRecommendation): { label: string; onClick: () => void } | null => {
    const s = r.suggest ?? {}
    if (typeof s.imgsz === 'number') return { label: `Train at ${s.imgsz}px`, onClick: () => nav(`/${ws}/${project.slug}/train?imgsz=${s.imgsz}`) }
    if (s.filter === 'label_quality') return { label: 'Review flagged labels', onClick: () => focusHealth('health-label-quality') }
    if (s.filter === 'missing_boxes') return { label: 'Review missing boxes', onClick: () => focusHealth('health-missing') }
    if (s.fix === 'leakage') return { label: 'Version again', onClick: () => nav(`/${ws}/${project.slug}/versions`) }
    return null
  }

  const sizeBuckets = checks.size_buckets
  const sizeTotal = sizeBuckets.small + sizeBuckets.medium + sizeBuckets.large
  const smallShare = pct(sizeBuckets.small, sizeTotal)
  const sizeRows = SIZE_META.map((m) => {
    const count = sizeBuckets[m.key]
    return { ...m, count, share: sizeTotal ? (count / sizeTotal) * 100 : 0, pct: pct(count, sizeTotal) }
  })

  const issueCounts: Record<LabelIssueKind, number> = { tiny: 0, out_of_bounds: 0, zero_area: 0, duplicate: 0 }
  const issueList = checks.label_quality
  for (const x of issueList) issueCounts[x.kind] += 1
  const missingList = checks.missing_boxes
  const visibleIssues = showAllIssues ? issueList : issueList.slice(0, 8)
  const visibleMissing = showAllMissing ? missingList : missingList.slice(0, 8)

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

  return (
    <div className="anim-page">
      <PageHeader title="Dataset Health Check" desc="Class balance, object scale, label quality and where objects sit in the frame." />
      <div className="space-y-4 px-4 pb-10 sm:px-8">
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

        {/* --- health check -------------------------------------------------------------- */}
        <div className="flex flex-wrap items-end justify-between gap-3 pt-2">
          <div>
            <h2 className="text-lg font-semibold tracking-tight">Health check</h2>
            <p className="mt-0.5 text-sm text-muted-foreground">Object scale, label geometry, missed objects and split leakage.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-muted-foreground">{scanLabel}</span>
            <Button variant="outline" size="sm" onClick={() => run.mutate()}
              disabled={run.isPending || !!runningJob || !a.images || !hasModel}
              title={hasModel ? undefined : 'Train a model first — the missing-box check compares its predictions with your labels'}>
              {runningJob ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCw className="h-3.5 w-3.5" />}
              {runningJob ? 'Checking…' : job ? 'Re-run check' : 'Run check'}
            </Button>
          </div>
        </div>

        {job && a.health_stale && !runningJob && (
          <div role="status" className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border border-warning/40 bg-warning/10 px-4 py-2.5 text-sm">
            <AlertTriangle className="h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
            <p className="min-w-0 flex-1 text-foreground">Dataset changed since this check ran — re-run for current results.</p>
            <Button variant="outline" size="sm" onClick={() => run.mutate()} disabled={run.isPending}>
              <RotateCw className="h-3.5 w-3.5" /> Re-run check
            </Button>
          </div>
        )}

        {(
          <div className="grid items-stretch gap-4 md:grid-cols-2">
            {/* --- object size --------------------------------------------------------- */}
            <HealthCard id="health-object-size">
              <HealthCardHead icon={<Frame className="h-4 w-4" />} title={`Object size at ${checks.imgsz}px`}
                desc="Share of annotated objects in each COCO size bucket." />
              <div className="mt-4 flex h-3 w-full overflow-hidden rounded-full bg-muted" role="img"
                aria-label={`Object sizes at ${checks.imgsz}px: ${sizeRows.map((r) => `${r.label} ${fmt(r.count)}`).join(', ')}`}>
                {sizeRows.map((r) => (r.count > 0 ? (
                  <span key={r.key} className={cn('h-full', r.tone)} style={{ width: `${r.share}%` }} />
                ) : null))}
              </div>
              <dl className="mt-3 grid grid-cols-3 gap-2">
                {sizeRows.map((r) => (
                  <div key={r.key} className="min-w-0">
                    <dt className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <span className={cn('h-2 w-2 shrink-0 rounded-sm', r.tone)} aria-hidden="true" />
                      <span className="truncate">{r.label}</span>
                    </dt>
                    <dd className="mt-0.5 text-lg font-semibold leading-tight tabular-nums">{fmt(r.count)}</dd>
                    <dd className="text-xs tabular-nums text-muted-foreground">{r.pct}%</dd>
                  </div>
                ))}
              </dl>
              {sizeTotal > 0 && smallShare >= 30 && (
                <p className="mt-3 flex items-start gap-1.5 text-xs font-medium text-warning">
                  <AlertTriangle className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  {smallShare}% of objects are small at {checks.imgsz}px — a larger training size or tiling would help.
                </p>
              )}
              <p className="mt-3 text-xs text-muted-foreground">COCO buckets: &lt;32² px small, &lt;96² px medium</p>
            </HealthCard>

            {/* --- label quality ------------------------------------------------------- */}
            <HealthCard id="health-label-quality">
              <HealthCardHead icon={<ShieldAlert className="h-4 w-4" />} title="Label quality"
                desc="Annotations that are too small, outside the image, zero-area or duplicated."
                aside={<Badge className={cn('tabular-nums', issueList.length ? 'bg-destructive/15 text-destructive' : 'bg-success/15 text-success')}>{fmt(issueList.length)}</Badge>} />
              <ul className="mt-3 flex flex-wrap gap-1.5">
                {KIND_ORDER.map((kind) => (
                  <li key={kind}>
                    <span className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-muted-foreground">
                      {KIND_LABEL[kind]}
                      <b className={cn('tabular-nums', issueCounts[kind] ? 'text-destructive' : 'text-muted-foreground')}>{fmt(issueCounts[kind])}</b>
                    </span>
                  </li>
                ))}
              </ul>
              {visibleIssues.length ? (
                <>
                  <ul className="mt-2 divide-y divide-border">
                    {visibleIssues.map((x) => (
                      <li key={`${x.image_id}-${x.annotation_id}-${x.kind}`}>
                        <Link to={editorHref(x.image_id)} title={`${KIND_LABEL[x.kind]} — open image in the editor`}
                          aria-label={`${KIND_LABEL[x.kind]} annotation ${shortId(x.annotation_id)} in image ${shortId(x.image_id)} — open in the editor`}
                          className="group flex min-h-9 items-center gap-2.5 rounded-md px-1.5 py-2 text-sm transition-colors hover:bg-accent focus-visible:bg-accent">
                          <span className={cn('h-1.5 w-1.5 shrink-0 rounded-full', x.kind === 'duplicate' ? 'bg-warning' : 'bg-destructive')} aria-hidden="true" />
                          <span className="min-w-0 flex-1 truncate">
                            {KIND_LABEL[x.kind]} <span className="text-muted-foreground">· {shortId(x.image_id)}</span>
                          </span>
                          <span className="shrink-0 text-xs text-muted-foreground">Open</span>
                          <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" aria-hidden="true" />
                        </Link>
                      </li>
                    ))}
                  </ul>
                  {issueList.length > 8 && (
                    <Button variant="ghost" size="sm" className="mt-2" onClick={() => setShowAllIssues((v) => !v)}>
                      {showAllIssues ? 'Show fewer' : `Show all ${fmt(issueList.length)}`}
                    </Button>
                  )}
                </>
              ) : (
                <p className="mt-3 flex items-center gap-1.5 text-sm text-muted-foreground">
                  <ShieldCheck className="h-4 w-4 text-success" aria-hidden="true" /> No geometry problems found
                </p>
              )}
            </HealthCard>

            {/* --- missing boxes ------------------------------------------------------- */}
            <HealthCard id="health-missing">
              <HealthCardHead icon={<ScanSearch className="h-4 w-4" />} title="Missing boxes"
                desc="Objects the model finds but the labels do not contain."
                aside={(
                  <span className="flex h-5 min-w-5 items-center justify-center">
                    {runningJob
                      ? <Spinner className="h-4 w-4 text-info" />
                      : <Badge className={cn('tabular-nums', missingList.length ? 'bg-warning/15 text-warning' : 'bg-success/15 text-success')}>{fmt(missingList.length)}</Badge>}
                  </span>
                )} />
              {runningJob ? (
                <div role="status" aria-live="polite" className="mt-3">
                  <div className="flex items-center gap-2 text-sm">
                    <span className="font-medium">{runningJob.status === 'queued' ? 'Check queued' : 'Scanning images…'}</span>
                    <span className="ml-auto text-xs tabular-nums text-muted-foreground">{Math.round(runningJob.progress)}%</span>
                  </div>
                  <Progress className="mt-2" value={runningJob.progress} />
                  <p className="mt-2 text-xs text-muted-foreground">
                    {runningJob.status === 'queued'
                      ? 'Waiting for a worker to pick up the check. This page refreshes automatically.'
                      : 'Comparing model predictions with the saved boxes. This page refreshes automatically.'}
                  </p>
                </div>
              ) : failed ? (
                <div role="alert" className="mt-3 text-sm">
                  <p className="flex items-center gap-1.5 font-medium text-destructive">
                    <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" /> The last check failed.
                  </p>
                  {job?.error && <p className="mt-1 break-words text-xs text-muted-foreground">{job.error}</p>}
                  <Button variant="outline" size="sm" className="mt-2" onClick={() => run.mutate()} disabled={run.isPending}>
                    <RotateCw className="h-3.5 w-3.5" /> Retry check
                  </Button>
                </div>
              ) : visibleMissing.length ? (
                <>
                  <ul className="mt-2 divide-y divide-border">
                    {visibleMissing.map((x, i) => {
                      const cls = x.class || 'Object'
                      return (
                        <li key={`${x.image_id}-${i}`}>
                          <Link to={editorHref(x.image_id)} title={`Missing ${cls} box — open image in the editor`}
                            aria-label={`Missing ${cls} box at ${boxText(x.box)} in image ${shortId(x.image_id)} — open in the editor`}
                            className="group flex min-h-9 items-center gap-2.5 rounded-md px-1.5 py-2 text-sm transition-colors hover:bg-accent focus-visible:bg-accent">
                            <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-warning" aria-hidden="true" />
                            <span className="min-w-0 flex-1 truncate">
                              <b className="font-medium">{cls}</b> <span className="text-muted-foreground">· {boxText(x.box)}</span>
                            </span>
                            <span className="shrink-0 text-xs text-muted-foreground">Open</span>
                            <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" aria-hidden="true" />
                          </Link>
                        </li>
                      )
                    })}
                  </ul>
                  {missingList.length > 8 && (
                    <Button variant="ghost" size="sm" className="mt-2" onClick={() => setShowAllMissing((v) => !v)}>
                      {showAllMissing ? 'Show fewer' : `Show all ${fmt(missingList.length)}`}
                    </Button>
                  )}
                </>
              ) : (
                <div className="mt-3">
                  <p className="flex items-start gap-1.5 text-sm text-muted-foreground">
                    <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden="true" />
                    {project.models ? 'No missed objects found.' : 'No trained model yet — train one to check for missed objects.'}
                  </p>
                  {!project.models && (
                    <Button variant="outline" size="sm" className="mt-2" onClick={() => nav(`/${ws}/${project.slug}/train`)}>
                      Train a model
                    </Button>
                  )}
                </div>
              )}
            </HealthCard>

            {/* --- split leakage ------------------------------------------------------- */}
            <HealthCard id="health-leakage">
              <HealthCardHead icon={<Link2 className="h-4 w-4" />} title="Split leakage"
                desc="Near-identical images (pHash) in the dataset that may leak between splits."
                aside={<Badge className={cn('tabular-nums', checks.leakage_pairs ? 'bg-warning/15 text-warning' : 'bg-success/15 text-success')}>{fmt(checks.leakage_pairs)}</Badge>} />
              <div className="mt-4">
                <div className="text-2xl font-bold tabular-nums leading-none tracking-tight">{fmt(checks.leakage_pairs)}</div>
                <div className="mt-1 text-xs text-muted-foreground">{checks.leakage_pairs === 1 ? 'near-duplicate pair' : 'near-duplicate pairs'}</div>
              </div>
              <p className="mt-3 text-sm text-muted-foreground">
                {checks.leakage_pairs
                  ? 'The same scene can land in both train and test, so evaluation scores look better than the model really is.'
                  : 'No near-duplicate images found, so evaluation splits should hold up.'}
              </p>
              <LinkButton to={`/${ws}/${project.slug}/versions`} className="mt-3">
                Version again with near-duplicate grouping <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
              </LinkButton>
            </HealthCard>
          </div>
        )}

        {/* --- recommendations --------------------------------------------------------- */}
        {(
          <section aria-labelledby="health-recommendations">
            <div className="flex items-center gap-2 pt-2">
              <Lightbulb className="h-4 w-4 text-primary" aria-hidden="true" />
              <h2 id="health-recommendations" className="text-lg font-semibold tracking-tight">Recommendations</h2>
            </div>
            {recs.length ? (
              <ul className="mt-2 space-y-2">
                {recs.map((r) => {
                  const action = recAction(r)
                  const values = Object.entries(r.suggest ?? {}).filter(([k]) => k !== 'filter' && k !== 'fix')
                  return (
                    <li key={r.key}
                      className="flex flex-col gap-2 rounded-lg border border-border border-l-4 border-l-warning bg-card p-3 text-card-foreground sm:flex-row sm:items-center sm:justify-between">
                      <div className="min-w-0">
                        <p className="text-sm">{r.message}</p>
                        {!!values.length && (
                          <div className="mt-1.5 flex flex-wrap gap-1.5">
                            {values.map(([k, v]) => (
                              <span key={k} className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[11px]">
                                <span className="text-muted-foreground">{k}</span> = <b>{suggestText(v)}</b>
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                      {action && (
                        <Button size="sm" variant="outline" className="shrink-0 self-start sm:self-auto" onClick={action.onClick}>
                          {action.label} <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
                        </Button>
                      )}
                    </li>
                  )
                })}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-muted-foreground">Nothing to change — the health check found no actionable issues.</p>
            )}
            <p className="mt-2 text-xs text-muted-foreground">Suggestions only. Nothing is applied automatically; use these values when you build a version or start training.</p>
          </section>
        )}

        {/* --- dataset distribution ----------------------------------------------------- */}
        <div className="pt-2">
          <h2 className="text-lg font-semibold tracking-tight">Dataset distribution</h2>
          <p className="mt-0.5 text-sm text-muted-foreground">Counts include every status. Click a bar or row to open the matching images in the dataset grid.</p>
        </div>

        <Card className="p-4">
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
                  tone="bg-primary"
                  onClick={() => goBrowse({ class: c.id })}
                  ariaLabel={`Show images containing the ${c.name} class in the dataset grid`} />
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-muted-foreground">No classes defined yet.</p>
          )}
        </Card>

        <div className="grid items-start gap-4 lg:grid-cols-3">
          <Card className="p-4">
            <h3 className="text-sm font-semibold">Annotations per image</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">Click a bar to filter by annotation count.</p>
            <ul className="mt-2 max-h-72 space-y-0.5 overflow-y-auto pr-1">
              {a.annotations_per_image.map((d) => {
                const n = Number(d.n)
                const filter: Record<string, string | number> = d.n === '20+' || !Number.isFinite(n)
                  ? { min_ann: 20 }
                  : { min_ann: n, max_ann: n }
                return (
                  <BarRow key={d.n} label={String(d.n)} value={d.images} width={(d.images / annMax) * 100}
                    tone="bg-primary"
                    onClick={() => goBrowse(filter)}
                    ariaLabel={`Show images with ${d.n === '20+' ? '20 or more' : d.n} annotations in the dataset grid`} />
                )
              })}
            </ul>
            {!a.annotations_per_image.length && <p className="mt-3 text-sm text-muted-foreground">No annotations yet.</p>}
          </Card>

          <Card className="p-4">
            <h3 className="text-sm font-semibold">Image size</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">Click a bar to filter by megapixels.</p>
            <ul className="mt-2 space-y-0.5">
              {sizeData.map((d) => (
                <BarRow key={d.bucket} label={d.bucket} value={d.images} width={(d.images / sizeMax) * 100}
                  tone="bg-primary"
                  onClick={() => goBrowse(SIZE_FILTERS[d.bucket] ?? {})}
                  ariaLabel={`Show images in the ${d.bucket} size range in the dataset grid`} />
              ))}
            </ul>
          </Card>

          <Card className="p-4">
            <h3 className="text-sm font-semibold">Aspect ratio</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">Click a bar to filter by width ÷ height.</p>
            <ul className="mt-2 space-y-0.5">
              {aspectData.map((d) => (
                <BarRow key={d.bucket} label={d.bucket} value={d.images} width={(d.images / aspectMax) * 100}
                  tone="bg-primary"
                  onClick={() => goBrowse(ASPECT_FILTERS[d.bucket] ?? {})}
                  ariaLabel={`Show ${d.bucket} images in the dataset grid`} />
              ))}
            </ul>
          </Card>
        </div>

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
    </div>
  )
}
