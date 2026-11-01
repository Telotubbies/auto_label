import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Boxes, Rocket } from 'lucide-react'
import { API_ORIGIN, get } from '@/lib/api'
import type { Job, ModelItem } from '@/lib/types'
import { Button, Card, EmptyState, PageHeader, Progress, StatusPill, fmtAgo, fmtDate } from '@/components/ui'
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

export function Deployments() {
  const { ws = '' } = useParams()
  const q = useQuery({ queryKey: ['ws-models', ws], queryFn: () => get<ModelItem[]>(`/ws/${ws}/models`) })
  const ready = (q.data ?? []).filter((m) => m.status === 'ready')
  return (
    <div className="anim-page">
      <PageHeader title="Deployments" desc="Every ready model is served by the hosted inference API." actions={<Link to={`/${ws}/settings/api`}><Button variant="outline">API keys</Button></Link>} />
      <div className="grid gap-4 px-8 pb-10 md:grid-cols-2 xl:grid-cols-3">
        {ready.map((m) => (
          <Card key={m.id} className="p-4">
            <div className="flex items-center gap-2"><Rocket className="h-4 w-4 text-primary" /><span className="truncate font-semibold">{m.name}</span><StatusPill status="ready" /></div>
            <div className="mt-1 text-xs text-muted-foreground">{m.project_name} · {headline(m)}</div>
            <code className="mt-3 block truncate rounded bg-muted px-2 py-1.5 text-[11px]">POST {API_ORIGIN || location.origin}/api/v1/models/{m.id}/predict</code>
            <Link to={`/${ws}/${m.project}/deploy?model=${m.id}`}><Button size="sm" variant="outline" className="mt-3">Test & code samples</Button></Link>
          </Card>
        ))}
        {q.isSuccess && !ready.length && <div className="col-span-full"><EmptyState title="Nothing deployed yet." hint="Train a model in any project — it's served automatically once training finishes." /></div>}
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
