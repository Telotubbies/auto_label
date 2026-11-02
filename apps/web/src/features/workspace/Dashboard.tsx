import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowRight, BrainCircuit, Check, CheckCheck, Circle, Compass, Inbox, ListChecks, Rocket, Tag, Upload, Users,
} from 'lucide-react'
import { api, get } from '@/lib/api'
import { useApp } from '@/lib/store'
import type { Job, Project } from '@/lib/types'
import { Badge, Button, Card, EmptyState, Progress, Stat, StatusPill, fmtAgo } from '@/components/ui'
import { cn } from '@/lib/utils'
import {
  hasQueue, hasSeenTour, jobKindLabel, markTourSeen, onboardingSteps, tourKey, type OnboardingFacts,
} from './dashboardRules'
import { Tour } from './Tour'

const ACTIVE = new Set<Job['status']>(['queued', 'running', 'cancelling'])
const fmt = (n: number) => n.toLocaleString()

const STEP_ICON = { project: ListChecks, images: Upload, labels: Tag, model: BrainCircuit, deploy: Rocket, team: Users }

export function WorkspaceDashboard({ ws, projects, onCreateProject }: {
  ws: string; projects: Project[]; onCreateProject: () => void
}) {
  const me = useApp((s) => s.me)
  const can = useApp((s) => s.can)
  const [tour, setTour] = useState<number | null>(null)

  const home = useQuery({ queryKey: ['home', ws], queryFn: () => api.home(ws) })
  const jobs = useQuery({
    queryKey: ['ws-jobs', ws],
    queryFn: () => get<Job[]>(`/ws/${ws}/jobs`),
    refetchInterval: (q) => ((q.state.data ?? []).some((j) => ACTIVE.has(j.status)) ? 4000 : false),
  })
  const members = useQuery({ queryKey: ['members', ws], queryFn: () => api.members(ws) })

  // The first-run tour is per person and per workspace: a second workspace is a new tour.
  useEffect(() => {
    if (!me || !home.isSuccess) return
    if (!hasSeenTour(window.localStorage, tourKey(ws, me.id))) setTour(0)
  }, [me, home.isSuccess, ws])

  const endTour = () => {
    if (me) markTourSeen(window.localStorage, tourKey(ws, me.id))
    setTour(null)
  }

  const steps = useMemo(() => onboardingSteps({
    ws,
    projects: home.data?.stats.projects ?? 0,
    images: home.data?.stats.images ?? 0,
    annotations: home.data?.stats.annotations ?? 0,
    models: home.data?.stats.models ?? 0,
    deployments: home.data?.stats.deployments ?? 0,
    teammates: members.data ? Math.max(0, members.data.members.length - 1 + members.data.invites.length) : 0,
    canInvite: can('admin'),
    firstProject: projects[0]?.slug ?? null,
  } satisfies OnboardingFacts), [home.data, members.data, projects, ws, can])

  if (home.isLoading) {
    return (
      <div className="space-y-4 px-8" aria-busy="true" aria-label="Loading workspace dashboard">
        <div className="h-24 rounded-lg skeleton" />
        <div className="grid gap-4 xl:grid-cols-3"><div className="h-56 rounded-lg skeleton xl:col-span-2" /><div className="h-56 rounded-lg skeleton" /></div>
      </div>
    )
  }
  if (home.isError) {
    return (
      <div className="px-8">
        <Card role="alert" className="flex flex-wrap items-center gap-3 p-4 text-sm">
          <span className="flex-1">Could not load the workspace dashboard: {(home.error as Error).message}</span>
          <Button variant="outline" size="sm" onClick={() => void home.refetch()}>Try again</Button>
        </Card>
      </div>
    )
  }
  if (!home.data) return null

  const { stats, waiting, totals } = home.data
  const recent = (jobs.data ?? []).slice(0, 5)
  const done = steps.filter((s) => s.done).length

  return (
    <>
      <section data-tour="home-stats" aria-labelledby="home-stats-heading" className="px-8 pb-2">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 id="home-stats-heading" className="text-lg font-semibold tracking-tight">At a glance</h2>
            <p className="text-sm text-muted-foreground">Live counts across every project in this workspace.</p>
          </div>
          <Button variant="outline" size="sm" onClick={() => setTour(0)}>
            <Compass className="h-3.5 w-3.5" /> Replay tour
          </Button>
        </div>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
          <Stat label="Datasets" value={fmt(stats.projects)} sub="projects" />
          <Stat label="Images" value={fmt(stats.images)} sub="across all projects" />
          <Stat label="Annotations" value={fmt(stats.annotations)} sub="human and model-assisted" />
          <Stat label="Models" value={fmt(stats.models)} sub="training runs" />
          <Stat label="Deployments" value={fmt(stats.deployments)} sub="ready to serve" />
        </div>
      </section>

      <div className="mt-4 grid items-start gap-4 px-8 xl:grid-cols-3">
        <section data-tour="home-tasks" aria-labelledby="home-tasks-heading" className="xl:col-span-2">
          <Card className="p-4">
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
              <div>
                <h2 id="home-tasks-heading" className="font-semibold">Work waiting for you</h2>
                <p className="text-xs text-muted-foreground">Assigned to you, plus the review and unassigned queues your role can act on.</p>
              </div>
              {hasQueue(totals) && (
                <Badge>
                  {fmt(totals.to_annotate + totals.to_review + totals.unassigned)} items
                </Badge>
              )}
            </div>
            {!hasQueue(totals) ? (
              <EmptyState icon={<CheckCheck className="h-8 w-8 text-success" />} title="You're all caught up."
                hint="New assignments, reviews and unassigned batches appear here." />
            ) : (
              <ul className="divide-y">
                {waiting.map((row) => (
                  <li key={row.project}>
                    <Link to={`/${ws}/${row.project}/annotate`}
                      className="group flex flex-wrap items-center gap-2 rounded-md px-1 py-2.5 hover:bg-accent">
                      <span className="min-w-0 flex-1 truncate font-medium group-hover:text-primary">{row.project_name}</span>
                      {row.to_annotate > 0 && <Badge className="bg-primary/15 text-primary">{fmt(row.to_annotate)} to annotate</Badge>}
                      {row.to_review > 0 && <Badge className="bg-warning/15 text-warning">{fmt(row.to_review)} to review</Badge>}
                      {row.unassigned > 0 && <Badge>{fmt(row.unassigned)} unassigned</Badge>}
                      <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </section>

        <section data-tour="home-checklist" aria-labelledby="home-checklist-heading" className="xl:row-span-2">
          <Card className="p-4">
            <div className="flex items-baseline justify-between gap-2">
              <h2 id="home-checklist-heading" className="font-semibold">Getting started</h2>
              <span className="text-xs tabular-nums text-muted-foreground">{done} of {steps.length} done</span>
            </div>
            <Progress className="mt-2" label={`Getting started: ${done} of ${steps.length} steps done`}
              value={steps.length ? (done / steps.length) * 100 : 0} />
            <ol className="mt-3 space-y-1">
              {steps.map((s) => {
                const Icon = STEP_ICON[s.key]
                return (
                  <li key={s.key} className="flex items-start gap-2 rounded-md px-1 py-1.5">
                    <span className={cn('mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border',
                      s.done ? 'border-success/40 bg-success/15 text-success' : 'text-muted-foreground')}>
                      {s.done ? <Check className="h-3.5 w-3.5" aria-label="Done" /> : <Circle className="h-3 w-3" aria-hidden="true" />}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className={cn('flex items-center gap-1.5 text-sm font-medium', s.done && 'text-muted-foreground line-through')}>
                        <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />{s.title}
                      </span>
                      {!s.done && <span className="mt-0.5 block text-xs text-muted-foreground">{s.hint}</span>}
                    </span>
                    {!s.done && s.action === 'create-project' && (
                      <Button size="sm" variant="outline" onClick={onCreateProject}>Create</Button>
                    )}
                    {!s.done && s.to && (
                      <Link to={s.to}><Button size="sm" variant="ghost">Open</Button></Link>
                    )}
                  </li>
                )
              })}
            </ol>
            {done === steps.length && (
              <p className="mt-3 rounded-md bg-success/10 px-3 py-2 text-sm text-success">Everything is set up. The checklist stays here for reference.</p>
            )}
          </Card>
        </section>

        <section data-tour="home-activity" aria-labelledby="home-activity-heading" className="xl:col-span-2">
          <Card className="p-4">
            <div className="mb-3 flex items-baseline justify-between gap-2">
              <div>
                <h2 id="home-activity-heading" className="font-semibold">Recent activity</h2>
                <p className="text-xs text-muted-foreground">Training, auto-labelling and exports from every project.</p>
              </div>
              <Link to={`/${ws}/activity`} className="text-xs font-medium text-primary hover:underline">View all activity</Link>
            </div>
            {!recent.length ? (
              <EmptyState icon={<Inbox className="h-8 w-8 text-muted-foreground/50" />} title="No background jobs yet."
                hint="Uploads, versions, training and exports appear here." />
            ) : (
              <ul className="space-y-2">
                {recent.map((j) => (
                  <li key={j.id} className="flex flex-wrap items-center gap-2 text-sm">
                    <StatusPill status={j.status} />
                    <span className="w-28 shrink-0">{jobKindLabel(j.kind)}</span>
                    {j.project
                      ? <Link to={`/${ws}/${j.project}`} className="min-w-0 flex-1 truncate text-muted-foreground hover:text-primary">{j.project_name || j.project}</Link>
                      : <span className="min-w-0 flex-1" />}
                    {ACTIVE.has(j.status)
                      ? <><Progress className="w-24" label={`${jobKindLabel(j.kind)} progress`} value={j.progress} /><span className="w-10 text-right text-xs tabular-nums text-muted-foreground">{Math.round(j.progress)}%</span></>
                      : <span className="max-w-48 truncate text-xs text-muted-foreground">{j.error || (j.result?.format ? `format ${j.result.format}` : '')}</span>}
                    <span className="w-20 text-right text-xs text-muted-foreground">{fmtAgo(j.created)}</span>
                  </li>
                ))}
              </ul>
            )}
            {jobs.isError && <p role="alert" className="mt-2 text-xs text-destructive">Could not load recent jobs.</p>}
          </Card>
        </section>
      </div>

      {tour !== null && <Tour step={tour} onStep={setTour} onClose={endTour} />}
    </>
  )
}
