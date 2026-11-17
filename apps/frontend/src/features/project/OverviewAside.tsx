import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'
import { RotateCw } from 'lucide-react'
import { api } from '@/lib/api'
import { Card, fmtAgo } from '@/components/ui'
import { projectPath } from '@/lib/routes'
import { cn } from '@/lib/utils'
import type { Job, Project } from '@/lib/types'
import { blockedBy, healthRing, runLine, type RingTone } from './overviewFacts'

/** The shipped role colours, so the ring brings no new token. */
const TONE: Record<RingTone, string> = {
  success: 'text-success',
  warning: 'text-warning',
  destructive: 'text-destructive',
  muted: 'text-muted-foreground',
}

/** Job kinds this product produces, each with the screen that shows its detail. */
const ACTIVITY: Record<string, { label: string; to: string }> = {
  train: { label: 'Training run', to: 'train' },
  version: { label: 'Version generated', to: 'dataset?tab=versions' },
  export: { label: 'Dataset export', to: 'dataset?tab=versions' },
  autolabel: { label: 'Auto-label', to: 'annotate' },
  health: { label: 'Health check', to: 'dataset?tab=health' },
}

const STATUS_WORD: Record<Job['status'], string> = {
  queued: 'queued', running: 'running', cancelling: 'cancelling', done: 'finished', failed: 'failed', cancelled: 'cancelled',
}

const RADIUS = 26
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

/** A ring whose arc is the approved share; the number is repeated as text, never colour alone. */
function Ring({ value, tone }: { value: number | null; tone: RingTone }) {
  const share = value === null ? 0 : Math.max(0, Math.min(100, value))
  return (
    <div className="relative h-16 w-16 shrink-0">
      <svg viewBox="0 0 64 64" aria-hidden className={cn('h-16 w-16 -rotate-90', TONE[tone])}>
        <circle cx="32" cy="32" r={RADIUS} fill="none" strokeWidth="6" className="stroke-muted" />
        {value !== null && (
          <circle cx="32" cy="32" r={RADIUS} fill="none" strokeWidth="6" strokeLinecap="round" strokeDasharray={CIRCUMFERENCE}
            strokeDashoffset={CIRCUMFERENCE - (CIRCUMFERENCE * share) / 100} className="stroke-current" />
        )}
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-sm font-semibold tabular-nums">
        {value === null ? '—' : `${value}%`}
      </span>
    </div>
  )
}

function SectionHead({ id, children }: { id: string; children: string }) {
  return <h2 id={id} className="text-sm font-semibold">{children}</h2>
}

function Retry({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" onClick={onClick}
      className="inline-flex min-h-6 items-center gap-1 rounded text-sm font-medium text-primary hover:underline">
      <RotateCw className="h-3.5 w-3.5" aria-hidden /> Retry
    </button>
  )
}

/** A link every read-only aside row uses, so no row is decorative. */
function RowLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="inline-flex min-h-6 items-center text-sm font-medium text-primary hover:underline">
      {children}
    </Link>
  )
}

/**
 * The overview's 360 px column: dataset health, the latest run, what blocks the pipeline and what
 * the project last did. Every value comes from a call the page already makes, so a foreign project
 * never reaches it: the shell 404s before this renders.
 */
export function OverviewAside({ ws, project }: { ws: string; project: Project }) {
  const analytics = useQuery({ queryKey: ['analytics', ws, project.slug], queryFn: () => api.analytics(ws, project.slug) })
  const models = useQuery({ queryKey: ['models', ws, project.slug], queryFn: () => api.models(ws, project.slug) })
  const jobs = useQuery({ queryKey: ['jobs', ws, project.slug], queryFn: () => api.jobs(ws, project.slug) })
  const retry = () => { void analytics.refetch(); void models.refetch(); void jobs.refetch() }

  if (analytics.isPending || models.isPending || jobs.isPending) {
    return (
      <div className="space-y-3" aria-busy="true">
        {[0, 1, 2].map((i) => <Card key={i} className="h-24 animate-pulse" />)}
      </div>
    )
  }

  const data = analytics.data
  const healthFailed = analytics.isError || !data
  const ring = healthRing(!healthFailed && project.statusCounts
    ? { approved: project.statusCounts.done ?? 0, total: project.images }
    : null)
  const staleAge = healthFailed ? null
    : data.health_stale ? (data.health_job?.finished ? fmtAgo(data.health_job.finished) : 'Not checked yet') : null

  // Latest finished training first; the run before it is the delta's baseline.
  const runs = (models.data ?? []).filter((m) => m.status === 'ready').sort((a, b) => b.created - a.created)
  const line = runLine(
    runs[0] ? { mAP50: runs[0].metrics.map50, version: runs[0].version } : null,
    runs[1] ? { mAP50: runs[1].metrics.map50, version: runs[1].version } : null,
  )

  const counts = project.statusCounts
  const blockers = blockedBy({
    toLabel: (counts?.unassigned ?? 0) + (counts?.annotating ?? 0),
    review: counts?.review ?? 0,
    approved: counts?.done ?? 0,
    labelIssues: healthFailed ? 0 : data.checks.label_quality.length,
    missingBoxes: healthFailed ? 0 : data.checks.missing_boxes.length,
    healthStale: !healthFailed && data.health_stale,
  })

  const activity = (jobs.data ?? [])
    .filter((j) => ACTIVITY[j.kind])
    .sort((a, b) => (b.finished ?? b.created) - (a.finished ?? a.created))
    .slice(0, 5)

  return (
    <div className="space-y-3">
      <Card className="p-4">
        <SectionHead id="aside-health">Dataset health</SectionHead>
        {healthFailed ? (
          <div role="alert" className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
            <p className="text-sm text-muted-foreground">Health unavailable</p>
            <Retry onClick={retry} />
          </div>
        ) : (
          <div className="mt-2 flex items-center gap-3">
            <Ring value={ring.value} tone={ring.tone} />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium tabular-nums">{ring.label}</p>
              {staleAge && <p className="text-xs text-muted-foreground">{staleAge}</p>}
              <RowLink to={projectPath(ws, project.slug, 'dataset?tab=health')}>
                {staleAge ? 'Run health check' : 'Open health report'}
              </RowLink>
            </div>
          </div>
        )}
      </Card>

      <Card className="p-4">
        <SectionHead id="aside-run">Latest run</SectionHead>
        {models.isError ? (
          <div role="alert" className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
            <p className="text-sm text-muted-foreground">Runs unavailable</p>
            <Retry onClick={retry} />
          </div>
        ) : line === null ? (
          <>
            <p className="mt-2 text-sm text-muted-foreground">No run yet — train when the dataset is clean.</p>
            <RowLink to={projectPath(ws, project.slug, 'train')}>Open train</RowLink>
          </>
        ) : (
          <>
            <p className="mt-2 text-sm font-medium tabular-nums">{line.label}</p>
            {line.delta && <p className="text-xs text-muted-foreground">{line.delta}</p>}
            <RowLink to={projectPath(ws, project.slug, 'train')}>Open runs</RowLink>
          </>
        )}
      </Card>

      <Card className="p-4">
        <SectionHead id="aside-blocked">Blocked by</SectionHead>
        {blockers.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">Nothing is blocked.</p>
        ) : (
          <ul className="mt-1">
            {blockers.map((b) => (
              <li key={b.id}>
                <Link to={projectPath(ws, project.slug, b.to)}
                  className="group flex min-h-8 items-center gap-2 rounded px-1 py-1.5 text-sm hover:bg-accent focus-visible:bg-accent">
                  <span aria-hidden className="h-1.5 w-1.5 shrink-0 rounded-full bg-warning" />
                  <span className="min-w-0 flex-1 group-hover:underline">{b.text}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="p-4">
        <SectionHead id="aside-activity">Recent activity</SectionHead>
        {activity.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">Nothing has run in this project yet.</p>
        ) : (
          <ul className="mt-1">
            {activity.map((j) => (
              <li key={j.id}>
                <Link to={projectPath(ws, project.slug, ACTIVITY[j.kind].to)}
                  className="group flex min-h-8 items-center gap-2 rounded px-1 py-1.5 text-sm hover:bg-accent focus-visible:bg-accent">
                  <span aria-hidden className={cn('h-1.5 w-1.5 shrink-0 rounded-full', j.status === 'failed' ? 'bg-destructive' : j.status === 'done' ? 'bg-success' : 'bg-info')} />
                  <span className="min-w-0 flex-1 truncate group-hover:underline">{ACTIVITY[j.kind].label} · {STATUS_WORD[j.status]}</span>
                  <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{fmtAgo(j.finished ?? j.created)}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
