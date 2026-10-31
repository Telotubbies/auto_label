import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Boxes, Download, Rocket, Trash2, X } from 'lucide-react'
import { api, del, fileUrl, post } from '@/lib/api'
import { useApp } from '@/lib/store'
import type { ModelItem } from '@/lib/types'
import { Button, Card, EmptyState, PageHeader, Progress, Stat, StatusPill, fmtDate, toast } from '@/components/ui'
import { cn } from '@/lib/utils'
import { useProject } from './ProjectLayout'

export const pct = (v?: number | null) => (v == null ? '—' : `${(v * 100).toFixed(1)}%`)

export function headline(m: ModelItem) {
  return m.task === 'classify' ? pct(m.metrics.accuracy_top1) : pct(m.metrics.map50)
}

function Charts({ m }: { m: ModelItem }) {
  const k = m.task === 'segment' ? '(M)' : '(B)'
  const series = m.task === 'classify'
    ? [['metrics/accuracy_top1', 'Top-1 acc', '#7c3aed'], ['metrics/accuracy_top5', 'Top-5 acc', '#22c55e']]
    : [[`metrics/mAP50${k}`, 'mAP50', '#7c3aed'], [`metrics/mAP50-95${k}`, 'mAP50-95', '#3b82f6'], [`metrics/precision${k}`, 'Precision', '#22c55e'], [`metrics/recall${k}`, 'Recall', '#f97316']]
  const loss = Object.keys(m.history[0] ?? {}).filter((x) => x.startsWith('val/') && x.endsWith('loss'))
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card className="p-4"><h3 className="mb-2 text-sm font-semibold">Accuracy over epochs</h3>
        <div className="h-60"><ResponsiveContainer><LineChart data={m.history}><CartesianGrid strokeDasharray="3 3" stroke="#eee" /><XAxis dataKey="epoch" tick={{ fontSize: 11 }} /><YAxis tick={{ fontSize: 11 }} domain={[0, 1]} /><Tooltip formatter={(v: number) => v.toFixed(3)} /><Legend wrapperStyle={{ fontSize: 11 }} />
          {series.map(([key, name, color]) => <Line key={key} dataKey={key} name={name} stroke={color} dot={false} strokeWidth={2} />)}</LineChart></ResponsiveContainer></div></Card>
      <Card className="p-4"><h3 className="mb-2 text-sm font-semibold">Validation loss</h3>
        <div className="h-60"><ResponsiveContainer><LineChart data={m.history}><CartesianGrid strokeDasharray="3 3" stroke="#eee" /><XAxis dataKey="epoch" tick={{ fontSize: 11 }} /><YAxis tick={{ fontSize: 11 }} /><Tooltip formatter={(v: number) => v.toFixed(3)} /><Legend wrapperStyle={{ fontSize: 11 }} />
          {loss.map((key, i) => <Line key={key} dataKey={key} name={key.replace('val/', '')} stroke={['#ef4444', '#eab308', '#14b8a6'][i % 3]} dot={false} strokeWidth={2} />)}</LineChart></ResponsiveContainer></div></Card>
    </div>
  )
}

export default function Models() {
  const { project, ws } = useProject()
  const [sp, setSp] = useSearchParams()
  const nav = useNavigate()
  const qc = useQueryClient()
  const can = useApp((s) => s.can)
  const models = useQuery({ queryKey: ['models', ws, project.slug], queryFn: () => api.models(ws, project.slug),
    refetchInterval: (q) => (q.state.data?.some((m) => ['queued', 'training'].includes(m.status)) ? 2500 : false) })
  const list = models.data ?? []
  const sel = list.find((m) => m.id === sp.get('model')) ?? list[0]
  return (
    <div className="anim-page">
      <PageHeader title="Models" desc="Trained models, their metrics and training curves." actions={can('admin') && <Button onClick={() => nav('../train')}>Train new model</Button>} />
      {models.isSuccess && !list.length ? <EmptyState icon={<Boxes className="h-8 w-8 text-muted-foreground/50" />} title="No models yet." action={can('admin') && <Button size="sm" onClick={() => nav('../train')}>Train your first model</Button>} /> : (
        <div className="flex gap-6 px-8 pb-10">
          <div className="w-64 shrink-0 space-y-1.5">
            {list.map((m) => (
              <button key={m.id} onClick={() => setSp({ model: m.id })} className={cn('w-full cursor-pointer rounded-lg border px-3 py-2.5 text-left text-sm', sel?.id === m.id ? 'border-primary bg-accent/40' : 'hover:bg-muted')}>
                <div className="flex items-center justify-between gap-2"><span className="truncate font-medium">{m.name}</span><StatusPill status={m.status} /></div>
                <div className="mt-0.5 text-[11px] text-muted-foreground">v{m.version} · {m.arch} · {headline(m)}</div>
              </button>
            ))}
          </div>
          {sel && (
            <div className="min-w-0 flex-1 space-y-4">
              <div className="flex items-start justify-between">
                <div><h2 className="text-xl font-bold">{sel.name}</h2><p className="text-sm text-muted-foreground">{sel.arch} · trained on v{sel.version} · {fmtDate(sel.created)} · {sel.classes.length} classes</p></div>
                <div className="flex gap-2">
                  {sel.status === 'ready' && <Button onClick={() => nav(`../deploy?model=${sel.id}`)}><Rocket className="h-4 w-4" /> Deploy & Test</Button>}
                  {sel.weightsUrl && <a href={fileUrl(sel.weightsUrl)}><Button variant="outline"><Download className="h-4 w-4" /> Weights (.pt)</Button></a>}
                  {['queued', 'training'].includes(sel.status) && sel.jobId && can('reviewer') && <Button variant="outline" onClick={() => post(`${api.P(ws, project.slug)}/jobs/${sel.jobId}/cancel`).then(() => toast.ok('Stopping after this epoch')).catch(toast.err)}><X className="h-4 w-4" /> Stop</Button>}
                  {can('admin') && <Button variant="ghost" size="icon" onClick={() => confirm('Delete this model?') && del(`${api.P(ws, project.slug)}/models/${sel.id}`).then(() => qc.invalidateQueries({ queryKey: ['models', ws, project.slug] })).catch(toast.err)}><Trash2 className="h-4 w-4" /></Button>}
                </div>
              </div>
              {['queued', 'training'].includes(sel.status) && (
                <Card className="p-4">
                  <div className="mb-2 flex items-center justify-between text-sm"><span>{sel.status === 'queued' ? 'Waiting for a worker…' : `Epoch ${sel.history.length} of ${sel.job?.params.options?.epochs ?? '?'}`}</span><span className="tabular-nums">{Math.round(sel.job?.progress ?? 0)}%</span></div>
                  <Progress value={sel.job?.progress ?? 0} />
                  {sel.status === 'queued' && <p className="mt-2 text-xs text-muted-foreground">Training needs a worker: the built-in one, or <code>labeldesk-worker</code> on a GPU machine.</p>}
                </Card>
              )}
              {sel.status === 'failed' && <Card className="border-destructive/40 bg-red-50 p-4 text-sm text-red-900">Training failed: {sel.job?.error || 'see worker logs'}</Card>}
              <div className="grid gap-3 md:grid-cols-4">
                {sel.task === 'classify' ? <>
                  <Stat label="Top-1 accuracy" value={pct(sel.metrics.accuracy_top1)} />
                  <Stat label="Top-5 accuracy" value={pct(sel.metrics.accuracy_top5)} />
                </> : <>
                  <Stat label="mAP@50" value={pct(sel.metrics.map50)} />
                  <Stat label="mAP@50-95" value={pct(sel.metrics.map5095)} />
                  <Stat label="Precision" value={pct(sel.metrics.precision)} />
                  <Stat label="Recall" value={pct(sel.metrics.recall)} />
                </>}
              </div>
              {sel.history.length > 0 && <Charts m={sel} />}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
