import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Boxes, CheckCircle2, CircleAlert, CircleDashed, Rocket, Send, Undo2 } from 'lucide-react'
import { api, get } from '@/lib/api'
import type { DeploymentAlias, DeploymentProject, Job, ModelItem } from '@/lib/types'
import { Button, Card, EmptyState, PageHeader, Progress, Select, StatusPill, fmtAgo, fmtDate, toast } from '@/components/ui'
import { headline } from '@/features/project/Models'

export function WorkspaceModels() {
  const { ws = '' } = useParams()
  const q = useQuery({ queryKey: ['ws-models', ws], queryFn: () => get<ModelItem[]>(`/ws/${ws}/models`) })
  return (
    <div className="anim-page">
      <PageHeader title="Models" desc="Every model trained across this workspace." />
      <div className="px-8 pb-10">
        {q.isSuccess && !q.data.length ? <EmptyState icon={<Boxes className="h-8 w-8 text-muted-foreground/50" />} title="No models trained yet." /> : (
          <Card className="overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/60 text-left text-xs text-muted-foreground"><tr><th className="px-4 py-2">Model</th><th>Project</th><th>Arch</th><th>Score</th><th>Status</th><th>Trained</th></tr></thead>
              <tbody>{q.data?.map((m) => (
                <tr key={m.id} className="border-t">
                  <td className="px-4 py-2.5 font-medium"><Link className="hover:text-primary" to={`/${ws}/${m.project}/models?model=${m.id}`}>{m.name}</Link></td>
                  <td>{m.project_name}</td><td className="font-mono text-xs">{m.arch}</td><td>{headline(m)}</td><td><StatusPill status={m.status} /></td><td className="text-muted-foreground">{fmtDate(m.created)}</td>
                </tr>
              ))}</tbody>
            </table>
          </Card>
        )}
      </div>
    </div>
  )
}

const ALIASES = ['production', 'staging'] as const
type AliasName = (typeof ALIASES)[number]

const fmtPValue = (p: number) => (p < 0.001 ? '< 0.001' : p.toFixed(3))

function DeploymentsSkeleton() {
  return (
    <div role="status" className="space-y-4">
      <span className="sr-only">Loading deployments…</span>
      {[0, 1].map((card) => (
        <Card key={card} className="p-4 sm:p-5">
          <div className="skeleton h-5 w-44" />
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            {[0, 1].map((row) => (
              <div key={row} className="rounded-md border bg-muted/30 p-3">
                <div className="skeleton h-3 w-24" />
                <div className="skeleton mt-2 h-4 w-40" />
                <div className="skeleton mt-2 h-3 w-52" />
                <div className="mt-3 flex items-end gap-2">
                  <div className="skeleton h-9 flex-1" />
                  <div className="skeleton h-8 w-20" />
                </div>
              </div>
            ))}
          </div>
          <div className="skeleton mt-3 h-8 w-full" />
        </Card>
      ))}
    </div>
  )
}

/** One served alias: current model, promote form and the one-click rollback. */
function AliasCard({ ws, project, aliasName, alias }: {
  ws: string; project: DeploymentProject; aliasName: AliasName; alias?: DeploymentAlias
}) {
  const qc = useQueryClient()
  // model_status is null when the alias points at a deleted model, so that id is not offerable.
  const currentId = alias?.model_status ? alias.model_id : null
  const [modelId, setModelId] = useState(currentId ?? project.ready_models[0]?.id ?? '')
  // Keep the current model selectable even when it is no longer in ready_models.
  const options = currentId && !project.ready_models.some((m) => m.id === currentId)
    ? [{ id: currentId, name: alias?.model_name ?? 'Current model', arch: alias?.model_arch ?? '' }, ...project.ready_models]
    : project.ready_models
  const selectId = `deploy-${project.slug}-${aliasName}`

  const deploy = useMutation({
    mutationFn: (id: string) => api.setDeployment(ws, project.slug, aliasName, id),
    onSuccess: (a) => {
      setModelId(a.model_id ?? '')
      toast.ok(`${a.model_name ?? 'Model'} is now serving ${aliasName}`)
      void qc.invalidateQueries({ queryKey: ['deployments', ws] })
    },
    onError: (e) => toast.err(e as Error),
  })
  const rollback = useMutation({
    mutationFn: () => api.rollbackDeployment(ws, project.slug, aliasName),
    onSuccess: (a) => {
      toast.ok(`Rolled back ${aliasName} to ${a.model_name ?? 'the previous model'}`)
      void qc.invalidateQueries({ queryKey: ['deployments', ws] })
    },
    onError: (e) => toast.err(e as Error),
  })
  const pending = deploy.isPending || rollback.isPending

  return (
    <div className="rounded-md border bg-muted/30 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[11px] font-medium text-muted-foreground">{aliasName}</span>
        {alias?.model_status && <StatusPill status={alias.model_status} />}
      </div>
      <div className="mt-1 flex min-w-0 flex-wrap items-baseline gap-x-2">
        <span className="truncate text-sm font-medium">{alias?.model_name ?? 'Not deployed'}</span>
        {alias?.model_arch && <code className="font-mono text-[11px] text-muted-foreground">{alias.model_arch}</code>}
      </div>
      <p className="mt-0.5 text-xs text-muted-foreground">
        {alias?.updated ? (
          <>
            Updated{' '}
            <time dateTime={new Date(alias.updated * 1000).toISOString()} title={fmtDate(alias.updated)}>{fmtAgo(alias.updated)}</time>
          </>
        ) : alias?.model_id ? 'No deployment time recorded.' : 'Promote a ready model to start serving this alias.'}
      </p>

      <form className="mt-3 flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); if (modelId && !pending) deploy.mutate(modelId) }}>
        <label className="min-w-0 flex-1" htmlFor={selectId}>
          <span className="mb-1 block text-xs text-muted-foreground">Model for {aliasName}</span>
          <Select id={selectId} className="w-full" value={modelId} disabled={!options.length || pending}
            onChange={(e) => setModelId(e.target.value)}>
            <option value="" disabled>Choose a model</option>
            {options.map((m) => <option key={m.id} value={m.id}>{m.name}{m.arch ? ` · ${m.arch}` : ''}</option>)}
          </Select>
        </label>
        <Button type="submit" size="sm" disabled={!modelId || !options.length || pending} aria-busy={deploy.isPending}>
          {deploy.isPending ? 'Deploying…' : 'Deploy'}
        </Button>
      </form>
      {!options.length && <p className="mt-1.5 text-xs text-muted-foreground">Train a model in this project to deploy it.</p>}

      {alias?.previous_model_id && (
        <Button variant="outline" size="sm" className="mt-2 max-w-full" disabled={pending} aria-busy={rollback.isPending}
          title={`Roll ${aliasName} back to ${alias.previous_model_name ?? 'the previous model'}`}
          onClick={() => rollback.mutate()}>
          <Undo2 className="h-3.5 w-3.5 shrink-0" aria-hidden />
          <span className="min-w-0 truncate">Roll back to {alias.previous_model_name ?? 'the previous model'}</span>
        </Button>
      )}
    </div>
  )
}

function DriftStrip({ ws, project }: { ws: string; project: DeploymentProject }) {
  const qc = useQueryClient()
  const drift = project.drift
  const send = useMutation({
    mutationFn: (runId: string) => api.sendDriftToLabeling(ws, project.slug, runId),
    onSuccess: (r) => {
      toast.ok(`${r.sent} sample${r.sent === 1 ? '' : 's'} sent to labeling`)
      void qc.invalidateQueries({ queryKey: ['deployments', ws] })
    },
    onError: (e) => toast.err(e as Error),
  })

  if (!drift) {
    return (
      <div className="mt-3 flex items-center gap-2 rounded-md border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
        <CircleDashed className="h-4 w-4 shrink-0" aria-hidden />
        <span>Not checked yet — no drift check has run for this project.</span>
      </div>
    )
  }

  const source = drift.feature_source
    ? <span className="text-muted-foreground"> · features: {drift.feature_source}</span>
    : null
  const checked = (
    <span className="text-muted-foreground">
      {' '}· checked{' '}
      <time dateTime={new Date(drift.created * 1000).toISOString()} title={fmtDate(drift.created)}>{fmtAgo(drift.created)}</time>
    </span>
  )

  if (drift.status === 'running') {
    return (
      <div className="mt-3 flex items-center gap-2 rounded-md border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
        <CircleDashed className="h-4 w-4 shrink-0" aria-hidden />
        <span>Drift check in progress…{source}</span>
      </div>
    )
  }

  if (drift.status === 'failed') {
    return (
      <div className="mt-3 flex flex-wrap items-center gap-2 rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-xs">
        <AlertTriangle className="h-4 w-4 shrink-0 text-warning" aria-hidden />
        <span className="min-w-0 flex-1">
          <span className="font-medium">Drift check failed</span>
          {drift.error && <span className="text-muted-foreground"> · {drift.error}</span>}
          {checked}
          {source}
        </span>
      </div>
    )
  }

  if (drift.status === 'insufficient') {
    return (
      <div className="mt-3 flex flex-wrap items-center gap-2 rounded-md border bg-muted/30 px-3 py-2 text-xs">
        <CircleDashed className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
        <span className="min-w-0 flex-1">
          <span className="font-medium">Not enough samples</span>
          <span className="text-muted-foreground">
            {' '}· {drift.n_current}/{drift.min_samples} production inputs and {drift.n_reference}/{drift.min_samples} reference images
          </span>
          {checked}
          {source}
        </span>
      </div>
    )
  }

  if (!drift.alert) {
    return (
      <div className="mt-3 flex items-center gap-2 rounded-md border bg-muted/30 px-3 py-2 text-xs">
        <CheckCircle2 className="h-4 w-4 shrink-0 text-success" aria-hidden />
        <span>
          <span className="font-medium">No drift alert</span>
          {checked}
          {source}
        </span>
      </div>
    )
  }

  return (
    <div className="mt-3 flex flex-wrap items-center gap-3 rounded-md border border-warning/40 bg-warning/10 px-3 py-2">
      <AlertTriangle className="h-4 w-4 shrink-0 text-warning" aria-hidden />
      <p className="min-w-0 flex-1 text-sm">
        <span className="font-medium">Data drift detected</span>
        <span className="text-muted-foreground"> · p = {fmtPValue(drift.p_value)}{checked}{source}</span>
      </p>
      <Button variant="outline" size="sm" className="bg-card" disabled={send.isPending} aria-busy={send.isPending}
        onClick={() => send.mutate(drift.run_id)}>
        <Send className="h-3.5 w-3.5" aria-hidden />
        {send.isPending ? 'Sending…' : 'Send samples to labeling'}
      </Button>
    </div>
  )
}

export function Deployments() {
  const { ws = '' } = useParams()
  const nav = useNavigate()
  const q = useQuery({ queryKey: ['deployments', ws], queryFn: () => api.deployments(ws) })
  const projects = (q.data?.projects ?? []).filter((p) => p.ready_models.length > 0 || p.aliases.some((a) => a.model_id))
  const hasProjects = (q.data?.projects.length ?? 0) > 0

  return (
    <div className="anim-page max-w-5xl">
      <PageHeader
        title="Deployments"
        desc="Production and staging aliases serve this workspace's hosted inference API."
        actions={<Button variant="outline" onClick={() => nav(`/${ws}/settings/api`)}>API keys</Button>}
      />
      <div className="space-y-4 px-4 pb-10 sm:px-8">
        {q.isPending ? <DeploymentsSkeleton /> : q.isError ? (
          <Card className="p-6">
            <EmptyState
              icon={<CircleAlert className="h-8 w-8 text-destructive" aria-hidden />}
              title="Couldn't load deployments."
              hint={q.error instanceof Error ? q.error.message : 'Something went wrong — try again.'}
              action={<Button variant="outline" size="sm" onClick={() => void q.refetch()}>Try again</Button>}
            />
          </Card>
        ) : !projects.length ? (
          <Card className="p-6">
            <EmptyState
              icon={<Rocket className="h-8 w-8 text-muted-foreground/50" aria-hidden />}
              title={hasProjects ? 'No deployable models yet.' : 'No projects yet.'}
              hint={hasProjects
                ? 'Train a model in any project. Ready models appear here for production and staging.'
                : 'Create a project and train a model to serve it from the hosted API.'}
              action={!hasProjects ? <Button variant="outline" size="sm" onClick={() => nav(`/${ws}`)}>Go to projects</Button> : undefined}
            />
          </Card>
        ) : (
          projects.map((p) => (
            <Card key={p.id} className="p-4 sm:p-5">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="flex min-w-0 items-center gap-2 font-semibold">
                  <Rocket className="h-4 w-4 shrink-0 text-primary" aria-hidden />
                  <Link className="truncate hover:text-primary" to={`/${ws}/${p.slug}/models`}>{p.name}</Link>
                </h2>
                <span className="text-xs text-muted-foreground">
                  {p.ready_models.length} ready model{p.ready_models.length === 1 ? '' : 's'}
                </span>
              </div>
              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                {ALIASES.map((name) => {
                  const alias = p.aliases.find((a) => a.alias === name)
                  // Remount on a model change so the select defaults to the newly served model.
                  return <AliasCard key={`${p.id}-${name}-${alias?.model_id ?? 'none'}`} ws={ws} project={p} aliasName={name} alias={alias} />
                })}
              </div>
              <DriftStrip ws={ws} project={p} />
            </Card>
          ))
        )}
      </div>
    </div>
  )
}

type AuditRow = { id: string; action: string; target: string; meta: Record<string, unknown>; created: number; user: string }

const KIND: Record<Job['kind'], { label: string; page: string }> = {
  train: { label: 'Training', page: 'models' },
  autolabel: { label: 'Auto-label', page: 'annotate' },
  version: { label: 'Version', page: 'versions' },
  export: { label: 'Export', page: 'versions' },
  export_engine: { label: 'TensorRT export', page: 'models' },
  health: { label: 'Health check', page: 'analytics' },
  insights_images: { label: 'Image stats', page: 'insights' },
  insights_leakage: { label: 'Leakage scan', page: 'insights' },
  insights_embedding: { label: 'Embedding map', page: 'insights' },
}
const kindOf = (kind: Job['kind']) => KIND[kind] ?? { label: kind, page: 'versions' }

export function Activity() {
  const { ws = '' } = useParams()
  const jobs = useQuery({ queryKey: ['ws-jobs', ws], queryFn: () => get<Job[]>(`/ws/${ws}/jobs`), refetchInterval: 4000 })
  const audit = useQuery({ queryKey: ['audit', ws], queryFn: () => get<AuditRow[]>(`/ws/${ws}/audit?limit=100`) })
  const active = (jobs.data ?? []).filter((j) => ['queued', 'running', 'cancelling'].includes(j.status))
  return (
    <div className="anim-page max-w-5xl">
      <PageHeader title="Activity" desc="Background jobs and what your team has been doing." />
      <div className="space-y-4 px-8 pb-10">
        <Card className="p-4">
          <h3 className="mb-3 font-semibold">Jobs</h3>
          {!jobs.data?.length && <p className="text-sm text-muted-foreground">No jobs yet.</p>}
          <div className="space-y-2">
            {[...active, ...(jobs.data ?? []).filter((j) => !active.includes(j)).slice(0, 15)].map((j) => (
              <div key={j.id} className="flex items-center gap-3 text-sm">
                <StatusPill status={j.status} />
                <span className="w-24 capitalize">{kindOf(j.kind).label}</span>
                <Link to={`/${ws}/${j.project}/${kindOf(j.kind).page}`} className="w-48 truncate hover:text-primary">{j.project_name}</Link>
                {['running', 'queued'].includes(j.status) ? <Progress className="flex-1" value={j.progress} /> : <span className="flex-1 truncate text-xs text-muted-foreground">{j.error || (j.result?.format ? `format ${j.result.format}` : '')}</span>}
                <span className="w-24 text-right text-xs text-muted-foreground">{fmtAgo(j.created)}</span>
              </div>
            ))}
          </div>
        </Card>
        <Card className="p-4">
          <h3 className="mb-3 font-semibold">Audit log</h3>
          <div className="divide-y text-sm">
            {audit.data?.map((a) => (
              <div key={a.id} className="flex gap-3 py-2">
                <span className="w-28 shrink-0 text-xs text-muted-foreground">{fmtAgo(a.created)}</span>
                <span className="w-36 shrink-0 truncate font-medium">{a.user}</span>
                <span className="font-mono text-xs text-primary">{a.action}</span>
                <span className="truncate text-muted-foreground">{a.target} {Object.keys(a.meta ?? {}).length ? JSON.stringify(a.meta) : ''}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}
