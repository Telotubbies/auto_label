import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Activity, Cpu, FolderKanban, Images, Layers, RefreshCw, Search, Server, ShieldCheck, Users,
} from 'lucide-react'
import { api } from '@/lib/api'
import type { AdminOverview, AdminWorkspace, ComponentStatus, WorkerRow } from '@/lib/types'
import { Badge, Button, Card, EmptyState, Input, PageHeader, Progress, Select, Spinner, Stat, fmtAgo, fmtDate, toast } from '@/components/ui'
import { cn } from '@/lib/utils'

const POLL = 8_000

const duration = (s: number) => (s < 60 ? `${Math.round(s)} s` : s < 3_600 ? `${Math.floor(s / 60)} min` : `${Math.floor(s / 3_600)} h`)
const pct = (used: number, total: number) => (total > 0 ? Math.min(100, (used / total) * 100) : 0)

const STATUS_DOT: Record<ComponentStatus, string> = {
  operational: 'bg-success',
  degraded: 'bg-warning',
  unknown: 'bg-muted-foreground',
}
const STATUS_TEXT: Record<ComponentStatus, string> = { operational: 'Operational', degraded: 'Degraded', unknown: 'Unknown' }

function ErrorLine({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <p role="alert" className="text-sm text-destructive">{message}</p>
      <Button variant="outline" size="sm" onClick={onRetry}>Try again</Button>
    </div>
  )
}

function Kpis({ o }: { o: AdminOverview }) {
  const active = (o.jobs.queued ?? 0) + (o.jobs.running ?? 0)
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Stat label="Workspaces" value={o.workspaces.toLocaleString()} />
      <Stat label="Users" value={o.users.toLocaleString()} />
      <Stat label="Projects" value={o.projects.toLocaleString()} />
      <Stat label="Images" value={o.images.toLocaleString()} />
      <Stat label="Active jobs" value={active} sub={`${o.jobs.queued ?? 0} queued · ${o.jobs.running ?? 0} running`} />
      <Stat label="Workers online" value={o.workers_online} />
      <Card className="p-4">
        <div className="text-xs font-medium text-muted-foreground">GPU memory</div>
        <div className="mt-1 text-2xl font-bold tracking-tight">{Math.round(pct(o.gpu.used_mb, o.gpu.budget_mb))}%</div>
        <Progress className="mt-2" value={pct(o.gpu.used_mb, o.gpu.budget_mb)} />
        <div className="mt-1 text-xs text-muted-foreground">
          {(o.gpu.used_mb / 1024).toFixed(1)} / {(o.gpu.budget_mb / 1024).toFixed(1)} GB · {o.gpu.leases.length} lease{o.gpu.leases.length === 1 ? '' : 's'}
          {o.gpu.holder ? ` · ${o.gpu.holder}` : ''}
        </div>
      </Card>
      <Card className="p-4">
        <div className="text-xs font-medium text-muted-foreground">vLLM</div>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <Badge className="bg-card text-foreground">{o.vllm.configured ? 'Configured' : 'Not configured'}</Badge>
          <Badge className="bg-card text-foreground">{o.vllm.sleeping ? 'Sleeping' : 'Awake'}</Badge>
        </div>
        <div className="mt-2 text-xs text-muted-foreground">Version {o.version} · {fmtAgo(o.generated)}</div>
      </Card>
    </div>
  )
}

export default function AdminConsole() {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [planBusy, setPlanBusy] = useState<string | null>(null)

  const overview = useQuery({ queryKey: ['admin-overview'], queryFn: api.adminOverview, refetchInterval: POLL })
  const jobs = useQuery({ queryKey: ['admin-jobs'], queryFn: () => api.adminJobs({ limit: 30 }), refetchInterval: POLL })
  const workers = useQuery({ queryKey: ['admin-workers'], queryFn: api.adminWorkers, refetchInterval: POLL })
  const status = useQuery({ queryKey: ['admin-status'], queryFn: api.adminStatus, refetchInterval: 10_000 })
  const workspaces = useQuery({
    queryKey: ['admin-workspaces', search], queryFn: () => api.adminWorkspaces(search.trim()),
    refetchInterval: 10_000, placeholderData: (prev) => prev,
  })

  const refresh = () => { void qc.invalidateQueries({ predicate: (q) => String(q.queryKey[0]).startsWith('admin-') }) }
  const setPlan = async (w: AdminWorkspace, plan: string) => {
    if (plan === w.plan) return
    setPlanBusy(w.id)
    try {
      await api.adminSetPlan(w.id, plan)
      await qc.invalidateQueries({ queryKey: ['admin-workspaces'] })
      toast.ok(`${w.name} moved to ${plan}`)
    } catch (e) {
      toast.err(e as Error)
    } finally {
      setPlanBusy(null)
    }
  }

  const activeJobs = (jobs.data?.items ?? []).filter((j) => j.status === 'running' || j.status === 'queued').slice(0, 8)
  const plans = ['free', 'pro', 'enterprise']

  return (
    <div className="anim-page max-w-7xl">
      <PageHeader
        title="Admin console"
        desc="Platform health across every workspace. Read-only except plan changes."
        actions={
          <>
            <Badge className="hidden bg-card/70 text-foreground sm:inline-flex"><ShieldCheck className="h-3 w-3" aria-hidden />Super-admin</Badge>
            <Button variant="outline" size="sm" onClick={refresh} aria-label="Refresh admin data"><RefreshCw className="h-4 w-4" aria-hidden />Refresh</Button>
          </>
        }
      />
      <div className="space-y-4 px-4 pb-10 sm:px-8">
        {overview.isLoading ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" role="status" aria-label="Loading platform overview">
            {Array.from({ length: 8 }, (_, i) => <Card key={i} className="h-28 p-4"><div className="skeleton h-3 w-20" /><div className="skeleton mt-3 h-7 w-16" /></Card>)}
          </div>
        ) : overview.isError ? (
          <Card className="p-5"><ErrorLine message={overview.error instanceof Error ? overview.error.message : 'Could not load the platform overview.'} onRetry={() => void overview.refetch()} /></Card>
        ) : overview.data && <Kpis o={overview.data} />}

        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="p-5">
            <h2 className="flex items-center gap-2 font-semibold"><Activity className="h-4 w-4 text-muted-foreground" aria-hidden />Job queue health</h2>
            {jobs.isLoading ? <p role="status" className="mt-3 flex items-center gap-2 text-sm text-muted-foreground"><Spinner /> Loading jobs…</p>
              : jobs.isError ? <div className="mt-3"><ErrorLine message="Could not load the job queue." onRetry={() => void jobs.refetch()} /></div>
              : jobs.data && (
                <div className="mt-3 space-y-3">
                  <div className="flex flex-wrap gap-2 text-xs">
                    {(['queued', 'running', 'failed', 'done', 'cancelled'] as const).map((s) => (
                      <Badge key={s} className={cn('gap-1 bg-card text-foreground', s === 'failed' && 'border-destructive/40')}>
                        <span className="font-semibold">{jobs.data.counts[s] ?? 0}</span>{s}
                      </Badge>
                    ))}
                    <span className="ml-auto self-center text-muted-foreground">
                      Oldest queued: {jobs.data.oldest_queued_s == null ? 'none' : duration(jobs.data.oldest_queued_s)}
                    </span>
                  </div>
                  {!activeJobs.length ? <p className="text-sm text-muted-foreground">No queued or running jobs.</p> : (
                    <ul className="space-y-2">
                      {activeJobs.map((j) => (
                        <li key={j.id} className="text-sm">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge className="bg-card font-mono text-foreground">{j.kind}</Badge>
                            <span className="min-w-0 flex-1 truncate" title={`${j.workspace} / ${j.project}`}>{j.workspace} / {j.project}</span>
                            <span className="text-xs tabular-nums text-muted-foreground">{Math.round(j.progress)}% · {duration(j.age_s)}</span>
                          </div>
                          <Progress className="mt-1" value={j.progress} />
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
          </Card>

          <Card className="p-5">
            <h2 className="flex items-center gap-2 font-semibold"><Server className="h-4 w-4 text-muted-foreground" aria-hidden />Status</h2>
            {status.isLoading ? <p role="status" className="mt-3 flex items-center gap-2 text-sm text-muted-foreground"><Spinner /> Checking components…</p>
              : status.isError ? <div className="mt-3"><ErrorLine message="Could not load component status." onRetry={() => void status.refetch()} /></div>
              : !status.data?.components.length ? <EmptyState title="No components reported." />
              : (
                <ul className="mt-3 divide-y text-sm">
                  {status.data.components.map((c) => (
                    <li key={c.name} className="flex flex-wrap items-start gap-2 py-2">
                      <span className={cn('mt-1.5 h-2 w-2 shrink-0 rounded-full', STATUS_DOT[c.status])} aria-hidden />
                      <div className="min-w-0 flex-1">
                        <div className="font-medium">{c.name}</div>
                        <div className="text-xs text-muted-foreground">{c.detail}</div>
                      </div>
                      <span className="text-xs text-muted-foreground">{STATUS_TEXT[c.status]}</span>
                    </li>
                  ))}
                </ul>
              )}
            {status.data && <p className="mt-2 text-xs text-muted-foreground">Checked {fmtAgo(status.data.checked)}</p>}
          </Card>
        </div>

        <Card className="overflow-hidden">
          <div className="p-5 pb-4">
            <h2 className="flex items-center gap-2 font-semibold"><Cpu className="h-4 w-4 text-muted-foreground" aria-hidden />Workers</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">Heartbeats older than {workers.data ? duration(workers.data.stale_after) : 'the threshold'} mark a worker stale.</p>
          </div>
          {workers.isLoading ? <p role="status" className="flex items-center gap-2 border-t px-4 py-6 text-sm text-muted-foreground"><Spinner /> Loading workers…</p>
            : workers.isError ? <div className="border-t px-4 py-4"><ErrorLine message="Could not load workers." onRetry={() => void workers.refetch()} /></div>
            : !workers.data?.workers.length ? <EmptyState title="No workers have reported yet." hint="Start a worker with the shared worker token to see heartbeats here." />
            : (
              <div className="overflow-x-auto border-t" role="region" aria-label="Workers" tabIndex={0}>
                <table className="w-full min-w-[46rem] text-sm">
                  <caption className="sr-only">GPU workers and their last heartbeat</caption>
                  <thead className="bg-muted/60 text-left text-xs text-muted-foreground">
                    <tr>
                      <th scope="col" className="px-4 py-2 font-medium">Worker</th>
                      <th scope="col" className="px-4 py-2 font-medium">Kinds</th>
                      <th scope="col" className="px-4 py-2 font-medium">Status</th>
                      <th scope="col" className="px-4 py-2 font-medium">Last seen</th>
                      <th scope="col" className="px-4 py-2 font-medium">Current job</th>
                    </tr>
                  </thead>
                  <tbody>
                    {workers.data.workers.map((w: WorkerRow) => (
                      <tr key={w.id} className="border-t">
                        <td className="px-4 py-2.5"><div className="font-medium">{w.host}</div><div className="font-mono text-xs text-muted-foreground">{w.id.slice(0, 12)}</div></td>
                        <td className="px-4 py-2.5"><div className="flex flex-wrap gap-1">{w.kinds.map((k) => <Badge key={k} className="font-mono">{k}</Badge>)}</div></td>
                        <td className="whitespace-nowrap px-4 py-2.5">
                          <span className="inline-flex items-center gap-1.5"><span className={cn('h-2 w-2 rounded-full', w.online ? 'bg-success' : 'bg-muted-foreground')} aria-hidden />{w.online ? 'Online' : 'Stale'}</span>
                        </td>
                        <td className="whitespace-nowrap px-4 py-2.5 text-muted-foreground"><time dateTime={new Date(w.last_seen * 1000).toISOString()} title={`${fmtDate(w.last_seen)} · started ${fmtAgo(w.started)}`}>{fmtAgo(w.last_seen)}</time></td>
                        <td className="px-4 py-2.5 font-mono text-xs">{w.current_job || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
        </Card>

        <Card className="overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 p-5 pb-4">
            <div>
              <h2 className="flex items-center gap-2 font-semibold"><FolderKanban className="h-4 w-4 text-muted-foreground" aria-hidden />Workspaces</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">Plan, usage and owner for every tenant.</p>
            </div>
            <label className="relative block w-full sm:w-64">
              <span className="sr-only">Search workspaces</span>
              <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" aria-hidden />
              <Input className="pl-8" placeholder="Search name, slug, owner…" value={search} onChange={(e) => setSearch(e.target.value)} />
            </label>
          </div>
          {workspaces.isLoading ? <p role="status" className="flex items-center gap-2 border-t px-4 py-6 text-sm text-muted-foreground"><Spinner /> Loading workspaces…</p>
            : workspaces.isError ? <div className="border-t px-4 py-4"><ErrorLine message="Could not load workspaces." onRetry={() => void workspaces.refetch()} /></div>
            : !workspaces.data?.length ? <EmptyState title={search ? 'No workspaces match.' : 'No workspaces yet.'} action={search ? <Button variant="outline" size="sm" onClick={() => setSearch('')}>Clear search</Button> : undefined} />
            : (
              <div className="overflow-x-auto border-t" role="region" aria-label="Workspaces" tabIndex={0}>
                <table className="w-full min-w-[62rem] text-sm">
                  <caption className="sr-only">Workspace plan and usage</caption>
                  <thead className="bg-muted/60 text-left text-xs text-muted-foreground">
                    <tr>
                      <th scope="col" className="px-4 py-2 font-medium">Workspace</th>
                      <th scope="col" className="px-4 py-2 font-medium">Plan</th>
                      <th scope="col" className="px-4 py-2 font-medium">Owner</th>
                      <th scope="col" className="px-4 py-2 font-medium">Region</th>
                      <th scope="col" className="px-4 py-2 font-medium">Members</th>
                      <th scope="col" className="px-4 py-2 font-medium">Projects</th>
                      <th scope="col" className="px-4 py-2 font-medium">Images</th>
                      <th scope="col" className="px-4 py-2 font-medium">Credits</th>
                    </tr>
                  </thead>
                  <tbody>
                    {workspaces.data.map((w) => {
                      const options = plans.includes(w.plan) ? plans : [w.plan, ...plans]
                      return (
                        <tr key={w.id} className="border-t">
                          <td className="px-4 py-2.5">
                            <div className="font-medium">{w.name}</div>
                            <div className="text-xs text-muted-foreground">{w.slug} · {fmtDate(w.created)}</div>
                          </td>
                          <td className="px-4 py-2.5">
                            <Select className="h-8" aria-label={`Plan for ${w.name}`} value={w.plan} disabled={planBusy === w.id}
                              onChange={(e) => void setPlan(w, e.target.value)}>
                              {options.map((p) => <option key={p} value={p}>{p}</option>)}
                            </Select>
                          </td>
                          <td className="max-w-44 px-4 py-2.5"><span className="block truncate" title={w.owner_email ?? undefined}>{w.owner_email ?? '—'}</span></td>
                          <td className="whitespace-nowrap px-4 py-2.5">{w.region}</td>
                          <td className="px-4 py-2.5 tabular-nums">{w.members.toLocaleString()}</td>
                          <td className="px-4 py-2.5 tabular-nums">{w.projects.toLocaleString()}</td>
                          <td className="px-4 py-2.5 tabular-nums">{w.images.toLocaleString()}</td>
                          <td className="min-w-32 px-4 py-2.5">
                            <div className="text-xs tabular-nums">{w.credits_used.toFixed(1)} / {w.credits_limit.toLocaleString()}</div>
                            <Progress className="mt-1" value={pct(w.credits_used, w.credits_limit)} />
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          <div className="flex flex-wrap items-center gap-2 border-t px-4 py-3 text-xs text-muted-foreground">
            <Layers className="h-3.5 w-3.5" aria-hidden /><Users className="h-3.5 w-3.5" aria-hidden /><Images className="h-3.5 w-3.5" aria-hidden />
            Data refreshes every {POLL / 1000} seconds.
          </div>
        </Card>
      </div>
    </div>
  )
}
