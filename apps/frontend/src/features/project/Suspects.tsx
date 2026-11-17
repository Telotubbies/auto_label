import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, ArrowUpRight, Check, Loader2, RotateCw, ScanSearch, ShieldCheck, ThumbsDown } from 'lucide-react'
import { api } from '@/lib/api'
import { editorPath, projectPath } from '@/lib/routes'
import type { Job, SuspectItem, SuspectKind, SuspectQueue, SuspectVerdict } from '@/lib/types'
import { Badge, Button, Card, EmptyState, PageHeader, Progress, Spinner, Stat, toast } from '@/components/ui'
import { cn } from '@/lib/utils'
import { useProject } from './ProjectLayout'

const KIND_META: Record<SuspectKind, { label: string; tone: string; hint: string }> = {
  wrong_class: {
    label: 'Wrong class',
    tone: 'bg-destructive',
    hint: 'The model recognises an object here but names a different class.',
  },
  shifted_box: {
    label: 'Shifted box',
    tone: 'bg-warning',
    hint: 'The model finds the right class, but the box is badly aligned with the label.',
  },
  extra_box: {
    label: 'Extra box',
    tone: 'bg-info',
    hint: 'The model sees a confident object elsewhere but nothing at this label.',
  },
}

const KIND_ORDER: SuspectKind[] = ['wrong_class', 'shifted_box', 'extra_box']
const shortId = (id: string) => (id.length > 10 ? `${id.slice(0, 8)}…` : id)
const fmtPct = (score: number) => `${Math.round(score * 100)}%`
const ACTIVE = new Set<Job['status']>(['queued', 'running'])

function isActiveHealth(jobs: Job[] | undefined) {
  return !!jobs?.find((j) => j.kind === 'health' && ACTIVE.has(j.status))
}

function KindPill({ kind }: { kind: SuspectKind }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium">
      <span className={cn('h-2 w-2 shrink-0 rounded-sm', KIND_META[kind].tone)} aria-hidden="true" />
      {KIND_META[kind].label}
    </span>
  )
}

/** What the model says about this label, or "no match" for an unsupported extra box. */
function ModelEvidence({ item }: { item: SuspectItem }) {
  if (item.kind === 'extra_box') return <span className="text-xs text-muted-foreground">No overlapping detection</span>
  const cls = item.predicted_class || item.class
  return (
    <span className="text-xs text-muted-foreground">
      Model: <b className="font-medium text-foreground">{cls || 'object'}</b> · IoU {item.iou.toFixed(2)}
    </span>
  )
}

export default function Suspects() {
  const { project, ws } = useProject()
  const nav = useNavigate()
  const qc = useQueryClient()
  const qk = useMemo(() => ['suspects', ws, project.slug] as const, [ws, project.slug])
  const jobsQk = useMemo(() => ['jobs', ws, project.slug] as const, [ws, project.slug])
  const [kind, setKind] = useState<'all' | SuspectKind>('all')
  const [showReviewed, setShowReviewed] = useState(false)

  const q = useQuery({ queryKey: qk, queryFn: () => api.suspects(ws, project.slug, 500) })
  const jobs = useQuery({
    queryKey: jobsQk,
    queryFn: () => api.jobs(ws, project.slug),
    refetchInterval: (query) => (isActiveHealth(query.state.data) ? 3000 : false),
  })
  const running = isActiveHealth(jobs.data)

  // A finished background scan changes the cached queue; refresh it exactly once on the transition.
  useEffect(() => {
    if (jobs.data && !running) qc.invalidateQueries({ queryKey: qk })
  }, [running, jobs.data, qc, qk])

  const run = useMutation({
    mutationFn: () => api.healthCheck(ws, project.slug),
    onSuccess: () => {
      toast.ok('Health scan queued — the queue refreshes when it finishes')
      qc.invalidateQueries({ queryKey: jobsQk })
    },
    onError: (e) => toast.err(e as Error),
  })

  const feedback = useMutation({
    mutationFn: (v: { item: SuspectItem; verdict: SuspectVerdict }) =>
      api.suspectFeedback(ws, project.slug, v.item.annotation_id, v.verdict),
    onSuccess: (_r, v) => {
      toast.ok(v.verdict === 'confirmed' ? 'Marked as a real label error' : 'Dismissed — label looks right')
      qc.invalidateQueries({ queryKey: qk })
    },
    onError: (e) => toast.err(e as Error),
  })

  const data: SuspectQueue | undefined = q.data
  const stats = data?.stats
  const items = data?.items ?? []
  const open = items.filter((i) => !i.feedback)
  const reviewed = items.filter((i) => !!i.feedback)
  const visible = items.filter((i) => (kind === 'all' || i.kind === kind) && (showReviewed || !i.feedback))
  const openByKind = (k: SuspectKind) => open.filter((i) => i.kind === k).length
  const pendingId = feedback.isPending ? feedback.variables?.item.annotation_id : null
  const canRun = project.models > 0 && project.images > 0

  if (q.isLoading) return <div className="p-10 text-center"><Spinner /></div>
  if (q.isError) {
    return (
      <div className="p-10 text-center">
        <p role="alert" className="text-sm text-destructive">Could not load the suspect queue. {(q.error as Error).message}</p>
        <Button variant="outline" size="sm" className="mt-3" onClick={() => q.refetch()}>Try again</Button>
      </div>
    )
  }

  return (
    <div className="anim-page">
      <PageHeader
        title="Suspect labels"
        desc="The model's disagreements with your labels, ranked by how likely each one is a mistake."
        actions={<Button variant="outline" size="sm" onClick={() => run.mutate()} disabled={run.isPending || running || !canRun}
          title={canRun ? undefined : 'Add images and train a model before running a scan'}>
          {running || run.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCw className="h-3.5 w-3.5" />}
          {running ? 'Scanning…' : data?.job_id ? 'Re-run scan' : 'Run scan'}
        </Button>}
      />

      <div className="space-y-4 px-4 pb-10 sm:px-8">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Open suspects" value={data?.open ?? open.length} sub={`${data?.total ?? items.length} in the latest scan`} />
          <Stat label="Confirmed" value={stats?.confirmed ?? 0} sub="marked as real label errors" />
          <Stat label="Dismissed" value={stats?.dismissed ?? 0} sub="label looked right" />
          <Stat label="Queue precision" value={stats?.precision == null ? '—' : `${Math.round(stats.precision * 100)}%`}
            sub={stats?.reviewed ? `${stats.reviewed} reviewed` : 'review an item to measure'} />
        </div>

        {running && (
          <div role="status" aria-live="polite" className="rounded-lg border border-info/40 bg-info/10 px-4 py-3 text-sm">
            <div className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-info" aria-hidden="true" />
              <span className="font-medium">Health scan running</span>
              <span className="ml-auto text-xs tabular-nums text-muted-foreground">refreshing automatically</span>
            </div>
            <Progress className="mt-2" value={jobs.data?.find((j) => j.kind === 'health')?.progress ?? 0} />
          </div>
        )}

        {data?.stale && !running && (
          <div role="status" className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border border-warning/40 bg-warning/10 px-4 py-2.5 text-sm">
            <AlertTriangle className="h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
            <p className="min-w-0 flex-1">The dataset or labels changed since this scan — scores are out of date.</p>
            <Button variant="outline" size="sm" onClick={() => run.mutate()} disabled={run.isPending || !canRun}>
              <RotateCw className="h-3.5 w-3.5" /> Re-run scan
            </Button>
          </div>
        )}

        <Card className="border-border bg-card p-4 text-card-foreground">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold">Review queue</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {data?.model ? `Scored by ${data.model.name}. ` : ''}
                Scores are ranking hints, not verdicts. Nothing is edited or deleted automatically.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <div role="group" aria-label="Filter by issue kind" className="flex flex-wrap gap-1">
                <button type="button" onClick={() => setKind('all')} aria-pressed={kind === 'all'}
                  className={cn('min-h-8 rounded-md border px-2.5 py-1 text-xs font-medium transition-colors', kind === 'all' ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:bg-accent')}>
                  All <b className="tabular-nums">{open.length}</b>
                </button>
                {KIND_ORDER.map((k) => (
                  <button key={k} type="button" onClick={() => setKind(k)} aria-pressed={kind === k}
                    className={cn('min-h-8 rounded-md border px-2.5 py-1 text-xs font-medium transition-colors', kind === k ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:bg-accent')}>
                    {KIND_META[k].label} <b className="tabular-nums">{openByKind(k)}</b>
                  </button>
                ))}
              </div>
              <Button variant="ghost" size="sm" onClick={() => setShowReviewed((v) => !v)} aria-pressed={showReviewed}>
                {showReviewed ? 'Hide reviewed' : `Show reviewed (${reviewed.length})`}
              </Button>
            </div>
          </div>

          {visible.length ? (
            <ul className="mt-3 divide-y divide-border">
              {visible.map((item) => {
                const meta = KIND_META[item.kind]
                const pending = pendingId === item.annotation_id
                return (
                  <li key={`${item.image_id}-${item.annotation_id}-${item.kind}`} className="py-3">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
                      <div className="flex min-w-0 flex-1 items-start gap-3">
                        <div className="w-14 shrink-0 text-center" aria-hidden="true">
                          <div className="text-sm font-semibold tabular-nums">{fmtPct(item.score)}</div>
                          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
                            <span className={cn('block h-full rounded-full', meta.tone)} style={{ width: `${Math.max(3, Math.min(100, item.score * 100))}%` }} />
                          </div>
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                            <KindPill kind={item.kind} />
                            <span className="text-sm font-medium">{item.class || 'Unknown class'}</span>
                            {item.feedback && (
                              <Badge className={cn('tabular-nums', item.feedback === 'confirmed' ? 'bg-destructive/15 text-destructive' : 'bg-success/15 text-success')}>
                                {item.feedback === 'confirmed' ? 'Confirmed error' : 'Dismissed'}
                              </Badge>
                            )}
                          </div>
                          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                            <ModelEvidence item={item} />
                            <span className="text-xs text-muted-foreground">Image {shortId(item.image_id)}</span>
                            <Link to={editorPath(ws, project.slug, item.image_id)}
                              className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline" aria-label={`Open image ${shortId(item.image_id)} in the editor`}>
                              Open in editor <ArrowUpRight className="h-3 w-3" aria-hidden="true" />
                            </Link>
                          </div>
                          {item.kind === 'extra_box' && <p className="mt-1 text-xs text-muted-foreground">{meta.hint}</p>}
                        </div>
                      </div>
                      <div className="flex shrink-0 gap-2 sm:pl-2">
                        <Button variant="outline" size="sm" disabled={pending}
                          onClick={() => feedback.mutate({ item, verdict: 'confirmed' })}
                          aria-label={`Confirm ${meta.label.toLowerCase()} for annotation ${item.annotation_id}`}>
                          {pending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                          Real error
                        </Button>
                        <Button variant="ghost" size="sm" disabled={pending}
                          onClick={() => feedback.mutate({ item, verdict: 'dismissed' })}
                          aria-label={`Dismiss ${meta.label.toLowerCase()} for annotation ${item.annotation_id}`}>
                          <ThumbsDown className="h-3.5 w-3.5" /> Looks right
                        </Button>
                      </div>
                    </div>
                  </li>
                )
              })}
            </ul>
          ) : (
            <div className="mt-3">
              <EmptyState
                icon={data?.model ? <ShieldCheck className="h-6 w-6 text-success" /> : <ScanSearch className="h-6 w-6 text-muted-foreground" />}
                title={!data?.model ? 'Train a model first' : !data?.job_id ? 'No scan yet' : kind !== 'all' || showReviewed ? 'Nothing matches this filter' : 'No suspect labels found'}
                hint={!data?.model
                  ? 'The queue compares your labels with the project’s latest ready model. Train one, then run a health scan.'
                  : !data?.job_id
                    ? 'Run a health scan to score the dataset. The scan is cached; opening this page never starts one.'
                    : kind !== 'all' || showReviewed
                      ? 'Try another issue kind or show reviewed items.'
                      : 'The model agrees with every label it could score. Re-run the scan after adding data.'}
                action={!data?.model
                  ? <Button size="sm" onClick={() => nav(projectPath(ws, project.slug, 'train'))}>Train a model</Button>
                  : !data?.job_id
                    ? <Button size="sm" variant="outline" onClick={() => run.mutate()} disabled={run.isPending || !canRun}>Run scan</Button>
                    : undefined}
              />
            </div>
          )}
        </Card>

        <section aria-labelledby="suspect-method" className="rounded-lg border border-border bg-muted/40 p-4 text-xs text-muted-foreground">
          <h2 id="suspect-method" className="text-sm font-semibold text-foreground">How scores are computed</h2>
          <ul className="mt-2 grid gap-2 sm:grid-cols-3">
            {KIND_ORDER.map((k) => (
              <li key={k} className="flex items-start gap-2">
                <span className={cn('mt-1.5 h-2 w-2 shrink-0 rounded-sm', KIND_META[k].tone)} aria-hidden="true" />
                <span><b className="font-medium text-foreground">{KIND_META[k].label}:</b> {KIND_META[k].hint}</span>
              </li>
            ))}
          </ul>
          <p className="mt-2">Every verdict feeds the precision statistic above; the model is not retrained by this page.</p>
        </section>
      </div>
    </div>
  )
}
