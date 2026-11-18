import { Link, useParams } from 'react-router-dom'
import { Activity, CircleCheck, Cpu, PlugZap, TriangleAlert } from 'lucide-react'
import { Button, Card, EmptyState, PageHeader, Progress, Spinner, Stat } from '@/components/ui'
import { cn } from '@/lib/utils'
import { useCompute } from './useCompute'
import { STATE_VIEW, fmtLeft, jobLine, vramShare, type ComputeData } from './computeView'

const TINT = {
  primary: 'bg-primary/10 text-primary',
  success: 'bg-success/10 text-success',
  destructive: 'bg-destructive/10 text-destructive',
  warning: 'bg-warning/15 text-warning',
} as const
const SHAPE_ICON = { pulse: Activity, ring: CircleCheck, bar: Cpu, cross: PlugZap } as const
const STATUS_WORD: Record<string, string> = { queued: 'Waiting', cancelling: 'Stopping', running: 'Running' }

/** The factory-floor board: one big state, four numbers, the jobs on the line, what sits in GPU memory. */
export default function Compute() {
  const { ws = '' } = useParams()
  const q = useCompute(ws)

  return (
    <div className="anim-page pb-10">
      <PageHeader title="Compute" desc="Is anything using the GPU, and what is waiting? Updates every few seconds." />
      <div className="mx-8 space-y-4">
        {q.isLoading && <div className="py-16 text-center"><Spinner /></div>}
        {q.isError && (
          <Card role="alert" className="flex items-center gap-2 border-destructive/40 bg-destructive/10 p-4 text-sm">
            <TriangleAlert className="h-4 w-4 shrink-0 text-destructive" /> Compute status could not be read. It retries on its own.
          </Card>
        )}
        {q.data && <Board d={q.data} ws={ws} />}
      </div>
    </div>
  )
}

function Board({ d, ws }: { d: ComputeData; ws: string }) {
  const v = STATE_VIEW[d.state]
  const Icon = SHAPE_ICON[v.shape]
  const gpu = d.gpus[0]
  return (
    <>
      <Card className={cn('flex flex-wrap items-center gap-5 p-6 shadow-none', TINT[v.tone])} role="status" aria-live="polite">
        <span className="grid h-16 w-16 shrink-0 place-items-center rounded-full bg-card">
          <Icon className={cn('h-8 w-8', v.shape === 'pulse' && 'motion-safe:animate-pulse')} aria-hidden />
        </span>
        <div className="min-w-0">
          <p className="text-4xl font-bold uppercase tracking-tight">{v.word}</p>
          <p className="mt-1 text-base text-foreground">{d.label}</p>
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Workers online" value={`${d.workers.online} of ${d.workers.total}`} tone={d.workers.online ? 'success' : 'destructive'}
          sub={d.workers.online ? `${d.workers.busy} busy` : 'Start labeldesk-worker on a GPU machine'} />
        <Stat label="GPU" value={gpu ? gpu.name : '—'} sub={gpu?.vram_mb ? `${Math.round(gpu.vram_mb / 1024)} GB memory` : 'not reported'} />
        <Stat label="Running" value={d.queue.running} tone={d.queue.running ? 'primary' : undefined} />
        <Stat label="Waiting" value={d.queue.queued} tone={d.queue.queued ? 'warning' : undefined}
          sub={d.queue.oldest_wait_s != null ? `oldest ${fmtLeft(Math.round(d.queue.oldest_wait_s))}` : 'nothing queued'} />
      </div>

      <Card className="shadow-none">
        <h2 className="border-b px-4 py-3 text-sm font-semibold">On the line</h2>
        {d.jobs.length === 0 ? (
          <EmptyState title="Nothing is running." hint="Training, auto-label and batch jobs show up here while they work."
            action={<Link to={`/${ws}/models`}><Button size="sm" variant="outline">Open Models</Button></Link>} />
        ) : (
          <ul className="divide-y">
            {d.jobs.map((j) => (
              <li key={j.id} className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-2 px-4 py-3 sm:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_5rem]">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{jobLine(j)}</p>
                  <p className="text-xs text-muted-foreground">{STATUS_WORD[j.status] ?? j.status}</p>
                </div>
                <div className="col-span-2 flex items-center gap-3 sm:col-span-1">
                  <Progress value={j.progress} label={`${jobLine(j)} progress`} className="h-2" />
                  <span className="w-10 shrink-0 text-right text-sm font-semibold tabular-nums">{Math.round(j.progress)}%</span>
                </div>
                <p className="row-start-1 text-right text-xs tabular-nums text-muted-foreground sm:row-start-auto">
                  {j.status === 'running' ? `${fmtLeft(j.eta_s)} left` : ''}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="p-4 shadow-none">
        <div className="mb-2 flex items-baseline justify-between text-sm">
          <h2 className="font-semibold">Models in this server GPU memory</h2>
          <span className="tabular-nums text-muted-foreground">
            {(d.api_gpu.used_mb / 1024).toFixed(1)} of {(d.api_gpu.budget_mb / 1024).toFixed(1)} GB
          </span>
        </div>
        <Progress value={vramShare(d.api_gpu.used_mb, d.api_gpu.budget_mb)} label="GPU memory in use" className="h-2" />
        <p className="mt-2 text-xs text-muted-foreground">
          {d.api_gpu.models.length
            ? d.api_gpu.models.map((m) => `${m.key} ${(m.vram_mb / 1024).toFixed(1)} GB`).join(' · ')
            : 'No model is loaded here. Training runs on the workers above.'}
        </p>
      </Card>
    </>
  )
}
