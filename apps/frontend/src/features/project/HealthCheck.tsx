import { useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AlertTriangle, ArrowUpRight, Focus, Frame, Lightbulb, Link2, Loader2, RotateCw, ScanSearch, ShieldAlert, ShieldCheck } from 'lucide-react'
import type { HealthChecks, HealthRecommendation, Job, LabelIssueKind, QualityClass } from '@/lib/types'
import { Badge, Button, Card, Progress, Spinner, fmtAgo } from '@/components/ui'
import { cn } from '@/lib/utils'

const KIND_LABEL: Record<LabelIssueKind, string> = {
  tiny: 'Tiny box',
  out_of_bounds: 'Outside image',
  zero_area: 'Zero area',
  duplicate: 'Duplicate',
}

const KIND_ORDER: LabelIssueKind[] = ['tiny', 'out_of_bounds', 'zero_area', 'duplicate']

const SIZE_META = [
  { key: 'small', label: 'Small', tone: 'bg-warning' },
  { key: 'medium', label: 'Medium', tone: 'bg-info' },
  { key: 'large', label: 'Large', tone: 'bg-success' },
] as const

/** Thresholds mirror services/quality.py; shown so the card explains its own verdicts. */
const QUALITY_META = [
  { kind: 'blurry', label: 'Blurry', tone: 'bg-warning' },
  { kind: 'dark', label: 'Too dark', tone: 'bg-destructive' },
  { kind: 'ok', label: 'Good', tone: 'bg-success' },
] as const

const QUALITY_ACTION: Record<QualityClass, string> = {
  blurry: 'View blurry images',
  dark: 'View dark images',
  ok: 'View good images',
  unknown: 'View unscored images',
}

const fmt = (n: number) => n.toLocaleString()
const pct = (n: number, total: number) => (total ? Math.round((n / total) * 100) : 0)
const shortId = (id?: string | null) => (!id ? '—' : id.length > 10 ? `${id.slice(0, 8)}…` : id)

function boxText(box: number[] | undefined) {
  if (!box || box.length < 4) return 'unknown box'
  // The contract is normalised [x, y, w, h]; tolerate pixel boxes from older scans.
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

/** Health cards are scroll targets, so they are programmatically focusable. */
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

/** One quality bucket; a real button so the whole bar is a click-through to the filtered grid. */
function QualityRow({ label, count, share, tone, onSelect }: {
  label: string; count: number; share: number; tone: string; onSelect: () => void
}) {
  return (
    <li>
      <button type="button" onClick={onSelect} aria-label={`Show ${fmt(count)} ${label.toLowerCase()} images in the dataset grid`}
        title={`Show ${label.toLowerCase()} images in the dataset`}
        className="group flex w-full cursor-pointer items-center gap-2 rounded-md px-1.5 py-1.5 text-left text-sm transition-colors hover:bg-accent focus-visible:bg-accent">
        <span className="w-20 shrink-0 truncate text-muted-foreground group-hover:text-foreground">{label}</span>
        <span className="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-muted" aria-hidden="true">
          <span className={cn('block h-full rounded-full', tone)} style={{ width: `${Math.max(count ? 2 : 0, Math.min(100, share))}%` }} />
        </span>
        <span className="w-12 shrink-0 text-right font-medium tabular-nums">{fmt(count)}</span>
        <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" aria-hidden="true" />
      </button>
    </li>
  )
}

export function HealthCheck({ ws, slug, models, checks, job, stale, recommendations, onRun, runPending, hasImages }: {
  ws: string
  slug: string
  /** Number of trained models in the project (any status): without one the scan cannot find misses. */
  models: number
  checks: HealthChecks
  job: Job | null
  stale: boolean
  recommendations: HealthRecommendation[]
  onRun: () => void
  runPending: boolean
  hasImages: boolean
}) {
  const nav = useNavigate()
  const [showAllIssues, setShowAllIssues] = useState(false)
  const [showAllMissing, setShowAllMissing] = useState(false)

  const runningJob = job && (job.status === 'queued' || job.status === 'running') ? job : null
  const failed = job?.status === 'failed'
  const scanLabel = runningJob ? 'Check running'
    : failed ? 'Last check failed'
      : job?.finished ? `Last check ${fmtAgo(job.finished)}`
        : models ? 'Not checked yet' : 'No trained model yet'

  const editorHref = (imageId: string) => `/${ws}/${slug}/images/${imageId}`

  const focusHealth = (id: string) => {
    const el = document.getElementById(id)
    if (!el) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' })
    el.focus({ preventScroll: true })
  }

  const browseQuality = (kind: QualityClass) =>
    nav(`/${ws}/${slug}/browse?${new URLSearchParams({ status: 'all', quality: kind }).toString()}`)

  /** One-click follow-up per recommendation; values stay suggestions, never auto-applied. */
  const recAction = (r: HealthRecommendation): { label: string; onClick: () => void } | null => {
    const s = r.suggest ?? {}
    if (typeof s.quality === 'string' && s.quality in QUALITY_ACTION) {
      const kind = s.quality as QualityClass
      return { label: QUALITY_ACTION[kind], onClick: () => browseQuality(kind) }
    }
    if (typeof s.imgsz === 'number') return { label: `Train at ${s.imgsz}px`, onClick: () => nav(`/${ws}/${slug}/train?imgsz=${s.imgsz}`) }
    if (s.filter === 'label_quality') return { label: 'Review flagged labels', onClick: () => focusHealth('health-label-quality') }
    if (s.filter === 'missing_boxes') return { label: 'Review missing boxes', onClick: () => focusHealth('health-missing') }
    if (s.fix === 'leakage') return { label: 'Version again', onClick: () => nav(`/${ws}/${slug}/versions`) }
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

  const quality = checks.quality
  const qualityTotal = Object.values(quality.counts).reduce((s, n) => s + n, 0)
  const qualityRows = QUALITY_META.map((m) => ({
    ...m, count: quality.counts[m.kind], share: qualityTotal ? (quality.counts[m.kind] / qualityTotal) * 100 : 0,
  }))
  const flaggedQuality = quality.counts.blurry + quality.counts.dark

  return (
    <>
      <section aria-labelledby="health-heading" className="pt-2">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 id="health-heading" className="text-lg font-semibold tracking-tight">Health check</h2>
            <p className="mt-0.5 text-sm text-muted-foreground">Object scale, label geometry, missed objects and split leakage.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-muted-foreground">{scanLabel}</span>
            <Button variant="outline" size="sm" onClick={onRun}
              disabled={runPending || !!runningJob || !hasImages || !models}
              title={models ? undefined : 'Train a model first — the missing-box check compares its predictions with your labels'}>
              {runningJob || runPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCw className="h-3.5 w-3.5" />}
              {runningJob ? 'Checking…' : job ? 'Re-run check' : 'Run check'}
            </Button>
          </div>
        </div>

        {stale && !runningJob && (
          <div role="status" className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border border-warning/40 bg-warning/10 px-4 py-2.5 text-sm">
            <AlertTriangle className="h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
            <p className="min-w-0 flex-1 text-foreground">Dataset changed since this check ran — re-run for current results.</p>
            <Button variant="outline" size="sm" onClick={onRun} disabled={runPending}>
              <RotateCw className="h-3.5 w-3.5" /> Re-run check
            </Button>
          </div>
        )}

        <div className="mt-4 grid items-stretch gap-4 md:grid-cols-2">
          <HealthCard id="health-object-size">
            <HealthCardHead icon={<Frame className="h-4 w-4" />} title={`Object size at ${checks.imgsz}px`}
              desc="Share of annotated objects in each COCO size bucket." />
            <div className="mt-4 flex h-3 w-full overflow-hidden rounded-full bg-muted" role="img"
              aria-label={`Object sizes at ${checks.imgsz}px: ${sizeRows.map((r) => `${r.label} ${fmt(r.count)}`).join(', ')}`}>
              {sizeRows.map((r) => (r.count > 0 ? <span key={r.key} className={cn('h-full', r.tone)} style={{ width: `${r.share}%` }} /> : null))}
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
            <p className="mt-3 text-xs text-muted-foreground">COCO buckets: &lt;32² px small, &lt;96² px medium. Measured per annotation, so these bars cannot filter the image grid.</p>
          </HealthCard>

          <HealthCard id="health-image-quality">
            <HealthCardHead icon={<Focus className="h-4 w-4" />} title="Image quality"
              desc="Sharpness and brightness measured once, when each image was uploaded."
              aside={<Badge className={cn('tabular-nums', flaggedQuality ? 'bg-warning/15 text-warning' : 'bg-success/15 text-success')}>{fmt(flaggedQuality)}</Badge>} />
            <ul className="mt-2 space-y-0.5" aria-label="Images by quality">
              {qualityRows.map((r) => (
                <QualityRow key={r.kind} label={r.label} count={r.count} share={r.share} tone={r.tone}
                  onSelect={() => browseQuality(r.kind)} />
              ))}
            </ul>
            <p className="mt-2 text-xs text-muted-foreground">
              Blurry under the 0.005 sharpness floor · too dark under 10% mean brightness. Click a row to open those images.
            </p>
            {quality.counts.unknown > 0 && (
              <p className="mt-1 text-xs text-muted-foreground">
                {fmt(quality.counts.unknown)} {quality.counts.unknown === 1 ? 'image has' : 'images have'} no score (uploaded before scoring) — they are not counted as good.
              </p>
            )}
          </HealthCard>

          <HealthCard id="health-label-quality">
            <HealthCardHead icon={<ShieldAlert className="h-4 w-4" />} title="Label quality"
              desc="Human labels that are too small, outside the image, zero-area or duplicated."
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

          <HealthCard id="health-missing">
            <HealthCardHead icon={<ScanSearch className="h-4 w-4" />} title="Missing boxes"
              desc="Objects the model finds but the human labels do not contain."
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
                    : 'Comparing model predictions with the saved human boxes. This page refreshes automatically.'}
                </p>
              </div>
            ) : failed ? (
              <div role="alert" className="mt-3 text-sm">
                <p className="flex items-center gap-1.5 font-medium text-destructive">
                  <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" /> The last check failed.
                </p>
                {job?.error && <p className="mt-1 break-words text-xs text-muted-foreground">{job.error}</p>}
                <Button variant="outline" size="sm" className="mt-2" onClick={onRun} disabled={runPending}>
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
                  {models ? 'No missed objects found.' : 'No trained model yet — train one to check for missed objects.'}
                </p>
                {!models && (
                  <Button variant="outline" size="sm" className="mt-2" onClick={() => nav(`/${ws}/${slug}/train`)}>
                    Train a model
                  </Button>
                )}
              </div>
            )}
          </HealthCard>

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
            <LinkButton to={`/${ws}/${slug}/versions`} className="mt-3">
              Version again with near-duplicate grouping <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
            </LinkButton>
          </HealthCard>
        </div>
      </section>

      <section aria-labelledby="health-recommendations" className="pt-2">
        <div className="flex items-center gap-2">
          <Lightbulb className="h-4 w-4 text-primary" aria-hidden="true" />
          <h2 id="health-recommendations" className="text-lg font-semibold tracking-tight">Recommendations</h2>
        </div>
        {recommendations.length ? (
          <ul className="mt-2 space-y-2">
            {recommendations.map((r) => {
              const action = recAction(r)
              const values = Object.entries(r.suggest ?? {}).filter(([k]) => k !== 'filter' && k !== 'fix' && k !== 'quality')
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
    </>
  )
}
