/**
 * Engine jobs above the engines table (T-1009): host, phase, percent, the last five log lines, the
 * full log in a sheet, and a cancel that asks first. The list polls every 2 s only while a job is
 * active; when one leaves the list it is read once more so the card can say how it ended and the
 * engines table can refetch. A done card dismisses itself after five seconds; a failed one keeps its
 * log and copy action. Nothing lives only in a toast, so a reload shows the same cards.
 */
import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Button, Card, Progress, Spinner, toast } from '@/components/ui'
import { inferenceCancelJob, inferenceJob, inferenceJobs } from '@/lib/api/inference'
import type { InferenceJob } from '@/lib/types'
import {
  cancelCopy, isTerminal, jobCopy, phaseLabel, tailLines, visibleLog,
} from './engineRows'
import JobLogSheet from './JobLogSheet'

const POLL_MS = 2000
const DONE_LINGER_MS = 5000

const SkeletonCard = () => (
  <Card className="p-4" aria-busy="true" aria-label="Loading engine job">
    <div className="h-4 w-48 animate-pulse rounded bg-muted" />
    <div className="mt-2 h-1.5 w-full animate-pulse rounded bg-muted" />
    <div className="mt-2 h-16 w-full animate-pulse rounded bg-muted" />
  </Card>
)

export default function InstallProgress({ ws, onSettled }: {
  ws: string
  /** Called once per job that reaches a terminal status, so the engines table refetches. */
  onSettled: () => void
}) {
  const list = useQuery({
    queryKey: ['inference-jobs', ws],
    enabled: !!ws,
    retry: false,
    queryFn: () => inferenceJobs(ws),
    // Poll only while the list has work: an idle tab must not spend a request every two seconds.
    refetchInterval: (query) => ((query.state.data ?? []).length ? POLL_MS : false),
  })
  const [settled, setSettled] = useState<InferenceJob[]>([])
  const [cancelling, setCancelling] = useState('')
  const [logId, setLogId] = useState('')
  const [logSnapshot, setLogSnapshot] = useState<InferenceJob | null>(null)
  const seen = useRef(new Set<string>())
  const handled = useRef(new Set<string>())
  const timers = useRef<number[]>([])

  const active = list.data ?? []
  const idsKey = active.map((job) => job.id).join(',')

  // A job that leaves the active list is read once more: how it ended is what the card says next.
  useEffect(() => {
    const current = new Set(idsKey ? idsKey.split(',') : [])
    const gone = [...seen.current].filter((id) => !current.has(id))
    seen.current = current
    for (const id of gone) {
      if (handled.current.has(id)) continue
      handled.current.add(id)
      inferenceJob(ws, id).then((job) => {
        setSettled((rows) => [...rows.filter((row) => row.id !== job.id), job])
        if (isTerminal(job)) onSettled()
        if (job.status === 'done') {
          timers.current.push(window.setTimeout(
            () => setSettled((rows) => rows.filter((row) => row.id !== job.id)), DONE_LINGER_MS))
        }
      }).catch(() => undefined)         // a job that vanished is only history now; the poll carries on
    }
  }, [idsKey, ws, onSettled])

  useEffect(() => () => timers.current.forEach((timer) => window.clearTimeout(timer)), [])

  const rows = [...active, ...settled.filter((job) => !active.some((row) => row.id === job.id))]
  const logJob = rows.find((job) => job.id === logId) ?? logSnapshot

  const openLog = (job: InferenceJob) => {
    setLogSnapshot(job)
    setLogId(job.id)
  }

  const copyLog = (job: InferenceJob) => {
    navigator.clipboard?.writeText(visibleLog(job).join('\n'))
      .then(() => toast.ok('Log copied'))
      .catch(() => toast.err('Could not copy the log'))
  }

  const cancel = async (job: InferenceJob) => {
    if (!window.confirm(cancelCopy(job.host, job.action))) return
    setCancelling(job.id)
    try {
      await inferenceCancelJob(ws, job.id)
      await list.refetch()
    } catch (err) {
      toast.err(err instanceof Error ? err.message : 'The cancel request did not reach the server.')
    } finally {
      setCancelling('')
    }
  }

  if (list.isLoading) return <SkeletonCard />

  if (list.isError) {
    return (
      <Card className="p-4">
        <p className="text-sm text-destructive">This job did not load.</p>
        <Button variant="outline" size="sm" className="mt-2" onClick={() => void list.refetch()}>Retry</Button>
      </Card>
    )
  }

  if (!rows.length) {
    return <p className="text-sm text-muted-foreground">No engine job is running.</p>
  }

  return (
    <div className="space-y-3">
      {rows.map((job) => {
        const live = !isTerminal(job)
        const failed = job.status === 'failed'
        const lines = tailLines(job)
        return (
          <Card key={job.id} className="p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="text-sm font-medium" role={failed ? 'alert' : undefined}>{jobCopy(job)}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {job.host}{failed ? ` · ${phaseLabel(job)}` : ''}
                </p>
              </div>
              <span className="text-sm tabular-nums text-muted-foreground">{Math.round(job.progress)}%</span>
            </div>
            {live && <Progress className="mt-2" value={job.progress} label={jobCopy(job)} />}
            {!!lines.length && (
              <pre className="mt-2 max-h-24 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-2 font-mono text-xs leading-5">
                {lines.join('\n')}
              </pre>
            )}
            <div className="mt-2 flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => openLog(job)}>View log</Button>
              {failed && (
                <Button variant="outline" size="sm" onClick={() => copyLog(job)}>Copy log</Button>
              )}
              {live && job.status !== 'cancelling' && (
                <Button variant="outline" size="sm" disabled={cancelling === job.id}
                  onClick={() => void cancel(job)}>
                  {cancelling === job.id ? <><Spinner className="h-3 w-3" /> Cancelling…</> : 'Cancel'}
                </Button>
              )}
            </div>
          </Card>
        )
      })}
      <JobLogSheet job={logJob} open={!!logId} onClose={() => setLogId('')} />
    </div>
  )
}
