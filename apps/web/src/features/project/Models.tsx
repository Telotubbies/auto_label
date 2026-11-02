import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AlertTriangle, Boxes, ChartLine, Check, Download, Info, Rocket, Trash2, X, Zap } from 'lucide-react'
import { api, del, fileUrl, post } from '@/lib/api'
import { useProjectPermissions } from '@/lib/perms'
import type { JobStage, LeaderboardRow, ModelItem } from '@/lib/types'
import { Badge, Button, Card, EmptyState, PageHeader, Progress, Spinner, Stat, StatusPill, Tabs, fmtDate, toast } from '@/components/ui'
import { EvalPanel } from '@/features/evaluation/EvalPanel'
import { cn } from '@/lib/utils'
import { useProject } from './ProjectLayout'

export const pct = (v?: number | null) => (v == null ? '—' : `${(v * 100).toFixed(1)}%`)

export function headline(m: ModelItem) {
  return m.task === 'classify' ? pct(m.metrics.accuracy_top1) : pct(m.metrics.map50)
}

// ---------- training stages ---------------------------------------------------
const STAGES = [
  { key: 'queue', label: 'Queued' },
  { key: 'acquire_gpu', label: 'GPU' },
  { key: 'materialise', label: 'Dataset' },
  { key: 'resolve_weights', label: 'Weights' },
  { key: 'build_config', label: 'Config' },
  { key: 'train', label: 'Train' },
  { key: 'evaluate', label: 'Evaluate' },
  { key: 'register', label: 'Register' },
  { key: 'release', label: 'Release' },
] as const

const fmtSeconds = (t: number) => (t < 60 ? `${t.toFixed(1)}s` : `${Math.floor(t / 60)}m ${Math.round(t % 60)}s`)

function StageStepper({ stages }: { stages?: Record<string, JobStage> }) {
  return (
    <div className="overflow-x-auto pb-1">
      <ol className="flex min-w-max items-start" aria-label="Training stages">
        {STAGES.map((s, i) => {
          const st = stages?.[s.key]
          const state = st?.status ?? 'pending'
          const prevDone = stages?.[STAGES[i - 1]?.key]?.status === 'done'
          return (
            <li key={s.key} className="flex w-[62px] shrink-0 flex-col items-center gap-1" title={st?.note || s.label}>
              <div className="flex w-full items-center">
                <span className={cn('h-px flex-1', i === 0 ? 'bg-transparent' : prevDone ? 'bg-primary/50' : 'bg-border')} />
                <span className={cn('grid h-5 w-5 shrink-0 place-items-center rounded-full',
                  state === 'done' && 'bg-primary text-primary-foreground',
                  state === 'running' && 'animate-pulse bg-primary/20 text-primary ring-2 ring-primary',
                  state === 'failed' && 'bg-destructive text-destructive-foreground',
                  state === 'pending' && 'border border-border bg-card')}>
                  {state === 'done' ? <Check className="h-3 w-3" /> : state === 'failed' ? <X className="h-3 w-3" /> : null}
                  <span className="sr-only">{state === 'pending' ? 'not started' : state}</span>
                </span>
                <span className={cn('h-px flex-1', i === STAGES.length - 1 ? 'bg-transparent' : state === 'done' ? 'bg-primary/50' : 'bg-border')} />
              </div>
              <span className={cn('text-center text-[10px] leading-tight', state === 'pending' ? 'text-muted-foreground' : 'font-medium')}>{s.label}</span>
              <span className="text-[10px] tabular-nums text-muted-foreground">{st ? fmtSeconds(st.t) : '—'}</span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}


// ---------- leaderboard -------------------------------------------------------
function LeaderboardTab({ rows, loading, onPick }: { rows?: LeaderboardRow[]; loading: boolean; onPick: (id: string) => void }) {
  if (loading) return <div className="py-16 text-center"><Spinner /></div>
  if (!rows?.length) return <EmptyState title="No evaluated models yet" hint="A model appears here once training finishes and its evaluation run completes." />
  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b bg-muted/50 text-left text-xs text-muted-foreground">
              <th scope="col" className="w-10 px-3 py-2 font-medium">#</th>
              <th scope="col" className="px-3 py-2 font-medium">Model</th>
              <th scope="col" className="px-3 py-2 font-medium">Version</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">AP</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Latency</th>
              <th scope="col" className="px-3 py-2 font-medium">Status</th>
              <th scope="col" className="px-3 py-2 font-medium">Comparable</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.id} onClick={() => onPick(r.id)}
                className={cn('cursor-pointer border-b transition-colors last:border-0 hover:bg-muted/60', !r.comparable && 'text-muted-foreground')}>
                <td className="px-3 py-2 tabular-nums text-muted-foreground">{i + 1}</td>
                <td className="px-3 py-2">
                  <button type="button" onClick={(e) => { e.stopPropagation(); onPick(r.id) }}
                    className="block max-w-[22ch] truncate text-left font-medium hover:underline">{r.name}</button>
                  <div className="truncate text-[11px] text-muted-foreground">{r.variant || r.task}</div>
                </td>
                <td className="px-3 py-2 tabular-nums">{r.version == null ? '—' : `v${r.version}`}</td>
                <td className="px-3 py-2 text-right font-semibold tabular-nums">{r.ap == null ? '—' : r.ap.toFixed(3)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{r.latency_ms == null ? '—' : `${Math.round(r.latency_ms)} ms`}</td>
                <td className="px-3 py-2"><StatusPill status={r.status} /></td>
                <td className="px-3 py-2">
                  {r.ap == null
                    ? <span className="text-[11px] text-muted-foreground">not evaluated</span>
                    : r.comparable
                      ? <Badge className="bg-success/15 text-success">comparable</Badge>
                      : <span className="text-[11px] text-muted-foreground">different version</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

// ---------- training curves ---------------------------------------------------
function Charts({ m }: { m: ModelItem }) {
  const k = m.task === 'segment' ? '(M)' : '(B)'
  const ultralytics = m.history.some((h) => `metrics/mAP50${k}` in h)
  const series = m.task === 'classify'
    ? [['metrics/accuracy_top1', 'Top-1 acc', '#7c3aed'], ['metrics/accuracy_top5', 'Top-5 acc', '#22c55e']]
    : ultralytics
      ? [[`metrics/mAP50${k}`, 'mAP50', '#7c3aed'], [`metrics/mAP50-95${k}`, 'mAP50-95', '#3b82f6'], [`metrics/precision${k}`, 'Precision', '#22c55e'], [`metrics/recall${k}`, 'Recall', '#f97316']]
      : [['val/map50', 'mAP50', '#7c3aed'], ['val/map5095', 'mAP50-95', '#3b82f6'], ['val/precision', 'Precision', '#22c55e'], ['val/recall', 'Recall', '#f97316']]
  const loss = Object.keys(m.history[0] ?? {}).filter((x) => x.endsWith('/loss'))
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card className="p-4"><h3 className="mb-2 text-sm font-semibold">Accuracy over epochs</h3>
        <div className="h-60"><ResponsiveContainer><LineChart data={m.history}><CartesianGrid strokeDasharray="3 3" stroke="var(--border)" /><XAxis dataKey="epoch" tick={{ fontSize: 11 }} /><YAxis tick={{ fontSize: 11 }} domain={[0, 1]} /><Tooltip formatter={(v: number) => v.toFixed(3)} /><Legend wrapperStyle={{ fontSize: 11 }} />
          {series.map(([key, name, color]) => <Line key={key} dataKey={key} name={name} stroke={color} dot={false} strokeWidth={2} />)}</LineChart></ResponsiveContainer></div></Card>
      <Card className="p-4"><h3 className="mb-2 text-sm font-semibold">Loss</h3>
        <div className="h-60"><ResponsiveContainer><LineChart data={m.history}><CartesianGrid strokeDasharray="3 3" stroke="var(--border)" /><XAxis dataKey="epoch" tick={{ fontSize: 11 }} /><YAxis tick={{ fontSize: 11 }} /><Tooltip formatter={(v: number) => v.toFixed(3)} /><Legend wrapperStyle={{ fontSize: 11 }} />
          {loss.map((key, i) => <Line key={key} dataKey={key} name={key.replace('val/', '')} stroke={['#ef4444', '#eab308', '#14b8a6'][i % 3]} dot={false} strokeWidth={2} />)}</LineChart></ResponsiveContainer></div></Card>
    </div>
  )
}

export default function Models() {
  const { project, ws } = useProject()
  const [sp, setSp] = useSearchParams()
  const nav = useNavigate()
  const qc = useQueryClient()
  const { can } = useProjectPermissions(ws, project.slug)
  const canManage = can('project.models')
  const [tab, setTab] = useState('evaluation')

  const models = useQuery({ queryKey: ['models', ws, project.slug], queryFn: () => api.models(ws, project.slug),
    refetchInterval: (q) => (q.state.data?.some((m) => ['queued', 'training'].includes(m.status)) ? 2500 : false) })
  const list = models.data ?? []
  const sel = list.find((m) => m.id === sp.get('model')) ?? list[0]

  const detail = useQuery({
    queryKey: ['model', ws, project.slug, sel?.id ?? ''],
    queryFn: () => api.model(ws, project.slug, sel!.id),
    enabled: !!sel?.id,
    refetchInterval: sel && ['queued', 'training'].includes(sel.status) ? 2500 : false,
  })
  const lb = useQuery({
    queryKey: ['leaderboard', ws, project.slug],
    queryFn: () => api.leaderboard(ws, project.slug),
    enabled: tab === 'leaderboard',
  })
  const engineJobs = useQuery({
    queryKey: ['engine-jobs', ws, project.slug],
    queryFn: () => api.jobs(ws, project.slug, 'export_engine'),
    refetchInterval: (q) => (q.state.data?.some((j) => ['queued', 'running'].includes(j.status)) ? 2500 : false),
  })

  // The list poll stops the moment the model flips to ready — pull the fresh eval in at that point.
  const prevStatus = useRef(sel?.status)
  useEffect(() => {
    if (sel?.id && prevStatus.current && prevStatus.current !== sel.status && sel.status === 'ready')
      qc.invalidateQueries({ queryKey: ['model', ws, project.slug, sel.id] })
    prevStatus.current = sel?.status
  }, [sel?.id, sel?.status, qc, ws, project.slug])

  const m = detail.data ?? sel
  const ev = m?.metrics.eval
  const engineJob = engineJobs.data?.find((j) => j.params.model_id === m?.id)
  const engine = m?.runtimeRefs?.engine
  const buildingEngine = !!engineJob && ['queued', 'running'].includes(engineJob.status)

  // The engine build does not change the model status, so refresh the model once its job finishes.
  const engineStatus = engineJob?.status
  useEffect(() => {
    if (engineStatus === 'done') {
      qc.invalidateQueries({ queryKey: ['model', ws, project.slug, m?.id] })
      qc.invalidateQueries({ queryKey: ['models', ws, project.slug] })
    }
  }, [engineStatus, qc, ws, project.slug, m?.id])

  const exportEngine = () => post(`${api.P(ws, project.slug)}/models/${m!.id}/export`, { format: 'engine' })
    .then(() => {
      toast.ok('TensorRT export queued — the engine appears here when it is built')
      qc.invalidateQueries({ queryKey: ['engine-jobs', ws, project.slug] })
    })
    .catch(toast.err)

  const pick = (id: string) => { setSp({ model: id }); setTab('evaluation') }

  return (
    <div className="anim-page">
      <PageHeader title="Models" desc="Trained models, their metrics and training curves." actions={
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Button variant="outline" disabled={!sel} onClick={() => nav(sel ? `../model-insights?model=${sel.id}` : '../model-insights')}>
            <ChartLine className="h-4 w-4" /> Open Insights
          </Button>
          {canManage && <Button onClick={() => nav('../train')}>Train new model</Button>}
        </div>
      } />
      {models.isSuccess && !list.length ? <EmptyState icon={<Boxes className="h-8 w-8 text-muted-foreground/50" />} title="No models yet." action={canManage && <Button size="sm" onClick={() => nav('../train')}>Train your first model</Button>} /> : (
        <div className="flex flex-col gap-6 px-4 pb-10 md:flex-row md:px-8">
          <div className="w-full space-y-1.5 md:w-64 md:shrink-0 md:max-h-[calc(100vh_-_10rem)] md:overflow-y-auto">
            {list.map((x) => (
              <button key={x.id} onClick={() => setSp({ model: x.id })} aria-current={sel?.id === x.id ? 'true' : undefined}
                className={cn('w-full cursor-pointer rounded-lg border px-3 py-2.5 text-left text-sm', sel?.id === x.id ? 'border-primary bg-accent/40' : 'hover:bg-muted')}>
                <div className="flex items-center justify-between gap-2"><span className="truncate font-medium">{x.name}</span><StatusPill status={x.status} /></div>
                <div className="mt-0.5 text-[11px] text-muted-foreground">v{x.version} · {x.arch} · {headline(x)}</div>
              </button>
            ))}
          </div>

          {m && (
            <div className="min-w-0 flex-1 space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="text-xl font-bold">{m.name}</h2>
                  <p className="text-sm text-muted-foreground">{m.arch} · trained on v{m.version} · {fmtDate(m.created)} · {m.classes.length} classes</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {m.status === 'ready' && <Button onClick={() => nav(`../deploy?model=${m.id}`)}><Rocket className="h-4 w-4" /> Deploy & Test</Button>}
                  {m.weightsUrl && <a href={fileUrl(m.weightsUrl)}><Button variant="outline"><Download className="h-4 w-4" /> Weights (.pt)</Button></a>}
                  {m.weightsUrl && m.license && (
                    <span className="self-center text-xs text-muted-foreground" title="Licence reported by the model catalog">
                      Licence: {m.license}
                    </span>
                  )}
                  {engine && <Badge className="gap-1 border border-primary/30 bg-primary/10 text-primary"><Zap className="h-3 w-3" /> TensorRT engine</Badge>}
                  {canManage && m.status === 'ready' && (
                    <Button variant="outline" disabled={buildingEngine} onClick={exportEngine}>
                      <Zap className="h-4 w-4" /> {buildingEngine ? `Building engine… ${Math.round(engineJob?.progress ?? 0)}%` : engine ? 'Rebuild engine' : 'Export TensorRT'}
                    </Button>
                  )}
                  {['queued', 'training'].includes(m.status) && m.jobId && canManage && <Button variant="outline" onClick={() => post(`${api.P(ws, project.slug)}/jobs/${m.jobId}/cancel`).then(() => toast.ok('Stopping after this epoch')).catch(toast.err)}><X className="h-4 w-4" /> Stop</Button>}
                  {canManage && <Button variant="ghost" size="icon" aria-label="Delete model" onClick={() => confirm('Delete this model?') && del(`${api.P(ws, project.slug)}/models/${m.id}`).then(() => qc.invalidateQueries({ queryKey: ['models', ws, project.slug] })).catch(toast.err)}><Trash2 className="h-4 w-4" /></Button>}
                </div>
              </div>

              <Tabs tabs={[{ id: 'evaluation', label: 'Evaluation' }, { id: 'leaderboard', label: 'Leaderboard' }]} active={tab} onChange={setTab} />

              {tab === 'leaderboard' ? (
                <LeaderboardTab rows={lb.data} loading={lb.isLoading} onPick={pick} />
              ) : (
                <>
                  {['queued', 'training'].includes(m.status) && (
                    <Card className="p-4">
                      <StageStepper stages={m.job?.result?.stages} />
                      <div className="mb-2 mt-4 flex items-center justify-between text-sm"><span>{m.status === 'queued' ? 'Waiting for a worker…' : `Epoch ${m.history.length} of ${m.job?.params.options?.epochs ?? '?'}`}</span><span className="tabular-nums">{Math.round(m.job?.progress ?? 0)}%</span></div>
                      <Progress value={m.job?.progress ?? 0} />
                      {m.status === 'queued' && <p className="mt-2 text-xs text-muted-foreground">Training needs a worker: the built-in one, or <code>labeldesk-worker</code> on a GPU machine.</p>}
                    </Card>
                  )}
                  {m.status === 'failed' && <Card className="border-destructive/40 bg-destructive/10 p-4 text-sm">Training failed: {m.job?.error || 'see worker logs'}</Card>}
                  {engineJob?.status === 'failed' && <Card role="alert" className="border-destructive/40 bg-destructive/10 p-4 text-sm">TensorRT export failed: {engineJob.error || 'see worker logs'}</Card>}

                  <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                    {m.task === 'classify' ? <>
                      <Stat label="Top-1 accuracy" value={pct(m.metrics.accuracy_top1)} />
                      <Stat label="Top-5 accuracy" value={pct(m.metrics.accuracy_top5)} />
                    </> : <>
                      <Stat label="mAP@50" value={pct(m.metrics.map50)} />
                      <Stat label="mAP@50-95" value={pct(m.metrics.map5095)} />
                      <Stat label="Precision" value={pct(m.metrics.precision)} />
                      <Stat label="Recall" value={pct(m.metrics.recall)} />
                    </>}
                  </div>

                  {ev ? (
                    m.task === 'classify' || /not evaluated|skipped/i.test(ev.note)
                      ? <Card className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
                          <Info className="h-4 w-4 shrink-0" /> {ev.note || 'COCO evaluation is not available for this model.'}
                        </Card>
                      : <EvalPanel key={m.id} ev={ev} images={detail.data?.evalImages} task={m.task} />
                  ) : m.metrics.eval_error ? (
                    <Card className="flex items-start gap-2 border-warning/60 bg-warning/10 p-4 text-sm">
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
                      <div>
                        <p className="font-medium">Evaluation failed — the model is still usable</p>
                        <p className="mt-0.5 break-words text-muted-foreground">{m.metrics.eval_error}</p>
                      </div>
                    </Card>
                  ) : m.status === 'ready' && (
                    <Card className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
                      <Info className="h-4 w-4 shrink-0" /> Evaluation runs after training — refresh once the job finishes.
                    </Card>
                  )}

                  {m.history.length > 0 && <Charts m={m} />}
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
