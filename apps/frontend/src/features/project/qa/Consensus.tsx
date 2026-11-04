import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, ChevronDown, Minus } from 'lucide-react'
import { api } from '@/lib/api'
import type { ConsensusJob } from '@/lib/types'
import { Button, Card, EmptyState, Field, Input, Progress, Spinner, fmtDate, toast } from '@/components/ui'
import { cn } from '@/lib/utils'
import { ErrorNote, Loading, pct } from './shared'

const JOB_TONE: Record<ConsensusJob['status'], string> = {
  collecting: 'bg-info/15 text-info',
  ready: 'bg-success/15 text-success',
  merged: 'bg-secondary text-secondary-foreground',
}

function JobDetail({ ws, slug, jobId }: { ws: string; slug: string; jobId: string }) {
  const q = useQuery({ queryKey: ['labeling-job', ws, slug, jobId], queryFn: () => api.labelingJob(ws, slug, jobId) })
  if (q.isLoading) return <div className="border-t py-6 text-center"><Spinner /></div>
  if (q.isError) return <div className="border-t pt-3"><ErrorNote error={q.error} /></div>
  const images = q.data?.images ?? []
  if (!images.length) return <p className="border-t pt-3 text-sm text-muted-foreground">No images assigned yet.</p>
  return (
    <ul className="space-y-2 border-t pt-3">
      {images.map((im) => (
        <li key={im.image_id} className="rounded-md border p-2.5">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            <span className="min-w-0 flex-1 truncate font-medium">{im.name}</span>
            <span className="text-xs text-muted-foreground">{im.submissions} submissions</span>
            <span className="text-xs font-semibold tabular-nums">Agreement {pct(im.agreement)}</span>
          </div>
          <div className="mt-1.5 flex flex-wrap gap-1">
            {im.assignees.map((a) => (
              <span key={a.user_id} title={a.submitted ? 'Submitted' : 'Not submitted'}
                className={cn('inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[11px]',
                  a.submitted ? 'border-success/40 text-success' : 'text-muted-foreground')}>
                {a.submitted ? <Check className="h-3 w-3" aria-hidden /> : <Minus className="h-3 w-3" aria-hidden />}
                {a.name}{a.count ? ` · ${a.count}` : ''}
                <span className="sr-only">{a.submitted ? 'submitted' : 'not submitted'}</span>
              </span>
            ))}
            {!im.assignees.length && <span className="text-[11px] text-muted-foreground">No assignees yet.</span>}
          </div>
        </li>
      ))}
    </ul>
  )
}

function JobRow({ job, ws, slug, onMerge, merging }: {
  job: ConsensusJob; ws: string; slug: string; onMerge: () => void; merging: boolean
}) {
  const [open, setOpen] = useState(false)
  const progress = job.assignments ? (job.submitted / job.assignments) * 100 : 0
  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold capitalize', JOB_TONE[job.status])}>
          {job.status}
        </span>
        <span className="text-xs text-muted-foreground">K <b className="font-medium text-foreground tabular-nums">{job.k}</b></span>
        <span className="text-xs text-muted-foreground">IoU <b className="font-medium text-foreground tabular-nums">{job.iou_threshold.toFixed(2)}</b></span>
        <span className="text-xs text-muted-foreground"><b className="font-medium text-foreground tabular-nums">{job.images}</b> images</span>
        <span className="text-xs text-muted-foreground">Agreement <b className="font-medium text-foreground tabular-nums">{pct(job.agreement)}</b></span>
        <span className="text-xs text-muted-foreground">{fmtDate(job.created)}</span>
        <div className="ml-auto flex items-center gap-2">
          {job.status === 'ready' && (
            <Button size="sm" disabled={merging} onClick={onMerge}>
              {merging ? <Spinner className="h-3.5 w-3.5" /> : null} Merge consensus
            </Button>
          )}
          <Button size="sm" variant="outline" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
            {open ? 'Hide' : 'Details'}
            <ChevronDown className={cn('h-3.5 w-3.5 transition-transform', open && 'rotate-180')} aria-hidden />
          </Button>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <span className="shrink-0">Submitted</span>
        <Progress value={progress} className="min-w-24 max-w-64 flex-1" />
        <span className="tabular-nums">{job.submitted} / {job.assignments}</span>
      </div>
      {open && <div className="mt-3"><JobDetail ws={ws} slug={slug} jobId={job.id} /></div>}
    </Card>
  )
}

export default function Consensus({ ws, slug }: { ws: string; slug: string }) {
  const qc = useQueryClient()
  const [k, setK] = useState('3')
  const [iou, setIou] = useState('0.5')
  const [count, setCount] = useState('20')
  const nK = Number(k), nIou = Number(iou), nCount = Number(count)
  const valid = nK >= 2 && nK <= 10 && nCount >= 1 && nCount <= 100 && nIou >= 0.1 && nIou <= 0.95

  const jobs = useQuery({ queryKey: ['labeling-jobs', ws, slug], queryFn: () => api.labelingJobs(ws, slug) })
  const create = useMutation({
    mutationFn: () => api.createConsensus(ws, slug, { count: nCount, k: nK, iou_threshold: nIou }),
    onSuccess: (job) => {
      toast.ok(`Consensus job created for ${job.images} images`)
      qc.invalidateQueries({ queryKey: ['labeling-jobs', ws, slug] })
      qc.invalidateQueries({ queryKey: ['labeling-dashboard', ws, slug] })
    },
    onError: (e) => toast.err(e as Error),
  })
  const merge = useMutation({
    mutationFn: (id: string) => api.mergeConsensus(ws, slug, id),
    onSuccess: (r) => {
      toast.ok(`Merged ${r.merged} images · ${r.skipped} skipped`)
      qc.invalidateQueries({ queryKey: ['labeling-jobs', ws, slug] })
      qc.invalidateQueries({ queryKey: ['labeling-job', ws, slug] })
      qc.invalidateQueries({ queryKey: ['images', ws, slug] })
      qc.invalidateQueries({ queryKey: ['project', ws, slug] })
      qc.invalidateQueries({ queryKey: ['labeling-dashboard', ws, slug] })
    },
    onError: (e) => toast.err(e as Error),
  })
  const onMerge = (job: ConsensusJob) => {
    if (!confirm(`Merge consensus for ${job.images} images into the dataset?`)) return
    merge.mutate(job.id)
  }

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <h2 className="text-lg font-semibold tracking-tight">New consensus job</h2>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Send each image to K labelers. When every draft is in, the job becomes ready to merge with an IoU-based agreement score.
        </p>
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <Field label="Labelers (K)" hint="2–10 per image">
            <Input className="w-28" type="number" min={2} max={10} step={1} value={k} onChange={(e) => setK(e.target.value)} />
          </Field>
          <Field label="IoU threshold" hint="0.10–0.95">
            <Input className="w-32" type="number" min={0.1} max={0.95} step={0.05} value={iou} onChange={(e) => setIou(e.target.value)} />
          </Field>
          <Field label="Images" hint="1–100">
            <Input className="w-28" type="number" min={1} max={100} step={1} value={count} onChange={(e) => setCount(e.target.value)} />
          </Field>
          <Button className="mb-5" disabled={!valid || create.isPending} onClick={() => create.mutate()}>
            {create.isPending ? <Spinner className="h-4 w-4" /> : null} Create job
          </Button>
        </div>
      </Card>

      {jobs.isLoading ? <Loading /> : jobs.isError ? <ErrorNote error={jobs.error} /> : !jobs.data?.jobs.length ? (
        <Card className="p-4">
          <EmptyState title="No consensus jobs yet." hint="Create one above to compare several labelers on the same images." />
        </Card>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">{jobs.data.jobs.length} jobs · newest first</p>
          {jobs.data.jobs.map((job) => (
            <JobRow key={job.id} job={job} ws={ws} slug={slug} onMerge={() => onMerge(job)}
              merging={merge.isPending && merge.variables === job.id} />
          ))}
        </div>
      )}
    </div>
  )
}
