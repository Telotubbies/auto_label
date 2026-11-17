import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { AlertTriangle, BadgeCheck, Search, Sparkles } from 'lucide-react'
import { api, fileUrl } from '@/lib/api'
import type { EventSearchFrame, EventSearchResult, Job } from '@/lib/types'
import { useProjectPermissions } from '@/lib/perms'
import { dateLocale } from '@/lib/theme'
import { Badge, Button, Card, EmptyState, Field, Input, PageHeader, Progress, Spinner, toast } from '@/components/ui'
import { cn } from '@/lib/utils'

const TERMINAL = new Set<Job['status']>(['done', 'failed', 'cancelled'])
const DAY = 24 * 3600

/** datetime-local wants a local wall clock; Date#toISOString would shift it to UTC. */
function localInput(ms: number): string {
  const offset = new Date(ms).getTimezoneOffset() * 60_000
  return new Date(ms - offset).toISOString().slice(0, 16)
}

function epoch(value: string): number | undefined {
  const ms = new Date(value).getTime()
  return Number.isFinite(ms) ? Math.floor(ms / 1000) : undefined
}

export default function EventSearch() {
  const { ws = '', project: slug = '' } = useParams()
  const { can } = useProjectPermissions(ws, slug)
  const canConfirm = can('project.review')

  const [query, setQuery] = useState('')
  const [from, setFrom] = useState(() => localInput(Date.now() - DAY * 1000))
  const [to, setTo] = useState(() => localInput(Date.now()))
  const [sample, setSample] = useState(300)
  const [jobId, setJobId] = useState<string | null>(null)
  const [decisions, setDecisions] = useState<Record<string, boolean>>({})

  const start = useMutation({
    mutationFn: () => api.eventSearch(ws, slug, {
      query: query.trim(), from_ts: epoch(from), to_ts: epoch(to), sample,
    }),
    onSuccess: (job) => {
      setJobId(job.id)
      setDecisions({})
    },
    onError: (e) => toast.err(e as Error),
  })

  const job = useQuery({
    queryKey: ['event-search-job', ws, slug, jobId],
    queryFn: () => api.job(ws, slug, jobId as string),
    enabled: !!jobId,
    refetchInterval: (q) => {
      const status = q.state.data?.status
      return status && TERMINAL.has(status) ? false : 1_200
    },
  })

  const confirm = useMutation({
    mutationFn: (body: { id: string; confirmed: boolean }) =>
      api.confirmEventSearch(ws, slug, body.id, body.confirmed),
    onSuccess: (frame) => {
      setDecisions((prev) => ({ ...prev, [frame.id]: frame.confirmed }))
      toast.ok(frame.confirmed ? 'Candidate confirmed' : 'Confirmation removed')
    },
    onError: (e) => toast.err(e as Error),
  })

  const fromTs = epoch(from)
  const toTs = epoch(to)
  const queryOk = query.trim().length > 0 && query.trim().length <= 500
  const windowOk = fromTs !== undefined && toTs !== undefined && fromTs < toTs
  const running = start.isPending || (job.data ? !TERMINAL.has(job.data.status) : false)
  const result = job.data?.status === 'done' ? (job.data.result as unknown as EventSearchResult) : null

  return (
    <div className="space-y-4 pb-10">
      <PageHeader
        title="Event search"
        desc="Search back through sampled stream events and footage in plain language."
        actions={null}
      />

      <div className="mx-4 space-y-4 sm:mx-8">
        <Card className="flex items-start gap-3 border-warning/40 bg-warning/10 p-4">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warning" aria-hidden />
          <div className="space-y-1">
            <h2 className="text-sm font-semibold">Ranked candidates — a person must confirm</h2>
            <p className="text-sm text-muted-foreground">
              These are probabilistic matches from sampled frames, not detections. Confirm each hit before
              acting on it; a confirmed hit records who accepted it.
            </p>
          </div>
        </Card>

        <Card className="space-y-4 p-5">
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault()
              if (queryOk && windowOk && !running) start.mutate()
            }}
          >
            <Field label="What are you looking for?" hint="Describe people, vehicles, objects or actions. Up to 500 characters.">
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g. worker without a helmet near the loading bay"
                maxLength={500}
                autoFocus
              />
            </Field>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <Field label="From">
                <Input type="datetime-local" value={from} onChange={(e) => setFrom(e.target.value)} />
              </Field>
              <Field label="To">
                <Input type="datetime-local" value={to} onChange={(e) => setTo(e.target.value)} />
              </Field>
              <Field label="Frames to sample" hint={`At most ${sample} frames, spread across the window.`}>
                <Input
                  type="number"
                  min={1}
                  max={1000}
                  value={sample}
                  onChange={(e) => setSample(Math.max(1, Math.min(1000, Number(e.target.value) || 1)))}
                />
              </Field>
            </div>

            {!windowOk && <p role="alert" className="text-sm text-destructive">The start time must be before the end time.</p>}
            {start.isError && <p role="alert" className="text-sm text-destructive">{(start.error as Error).message}</p>}

            <div className="flex flex-wrap items-center gap-3">
              <Button type="submit" disabled={!queryOk || !windowOk || running}>
                <Search className="h-4 w-4" aria-hidden />
                {running ? 'Searching…' : 'Search frames'}
              </Button>
              <p className="text-xs text-muted-foreground">
                A window is limited to 31 days. Searches run as a background job and pages poll for the result.
              </p>
            </div>
          </form>
        </Card>

        {job.data && !TERMINAL.has(job.data.status) && (
          <Card className="space-y-2 p-5" role="status">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Spinner /> Indexing and ranking frames…
            </div>
            <Progress value={job.data.progress} />
            <p className="text-xs text-muted-foreground">
              Job {job.data.id.slice(0, 8)} · {Math.round(job.data.progress)}%
            </p>
          </Card>
        )}

        {job.data?.status === 'failed' && (
          <Card className="space-y-2 border-destructive/40 p-5" role="alert">
            <h2 className="text-sm font-semibold text-destructive">Search failed</h2>
            <p className="text-sm text-muted-foreground">{job.data.error || 'The background job stopped unexpectedly.'}</p>
            <Button variant="outline" size="sm" onClick={() => start.mutate()}>Try again</Button>
          </Card>
        )}

        {result && <ResultPanel result={result} decisions={decisions} canConfirm={canConfirm}
          confirming={confirm.isPending} onConfirm={(id, confirmed) => confirm.mutate({ id, confirmed })} />}

        {!jobId && (
          <Card>
            <EmptyState
              icon={<Search className="h-8 w-8 text-muted-foreground" aria-hidden />}
              title="No search yet"
              hint="Describe an event and a time window. The search samples frames from recorded footage and stream events, then ranks them for you to confirm."
            />
          </Card>
        )}
      </div>
    </div>
  )
}

function Score({ value }: { value?: number }) {
  if (value === undefined) return null
  const pct = Math.round(value * 100)
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11px] font-medium"
      title="Relative rank inside this result list; not a calibrated probability">
      <span className="relative h-1.5 w-10 overflow-hidden rounded-full bg-secondary" aria-hidden>
        <span className="absolute inset-y-0 left-0 rounded-full bg-primary" style={{ width: `${pct}%` }} />
      </span>
      {pct}% relative rank
    </span>
  )
}

function ResultPanel({ result, decisions, canConfirm, confirming, onConfirm }: {
  result: EventSearchResult
  decisions: Record<string, boolean>
  canConfirm: boolean
  confirming: boolean
  onConfirm: (id: string, confirmed: boolean) => void
}) {
  return (
    <section aria-labelledby="event-search-results" className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 id="event-search-results" className="text-lg font-semibold">Ranked candidates</h2>
          <p className="text-xs text-muted-foreground">
            {result.results.length} of {result.candidates} sampled frames · {result.query}
          </p>
        </div>
        <Badge className={cn(result.ranking === 'clip+lexical' ? 'bg-success/15 text-success' : 'bg-warning/15 text-warning')}>
          {result.ranking === 'clip+lexical' ? 'CLIP + text match' : 'Text match only'}
        </Badge>
      </div>

      {result.ranking === 'lexical' && (
        <p className="rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-muted-foreground">
          CLIP is not available in this install, so this list comes from file-name, tag and rule words only —
          not visual similarity.
        </p>
      )}

      {result.results.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Sparkles className="h-8 w-8 text-muted-foreground" aria-hidden />}
            title="No candidate matched this query"
            hint="Widen the time window or raise the sample size and search again."
          />
        </Card>
      ) : (
        <ul className="space-y-3">
          {result.results.map((frame) => (
            <li key={frame.id}>
              <Candidate frame={frame} confirmed={decisions[frame.id] ?? frame.confirmed}
                canConfirm={canConfirm} busy={confirming} onConfirm={onConfirm} />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function Candidate({ frame, confirmed, canConfirm, busy, onConfirm }: {
  frame: EventSearchFrame
  confirmed: boolean
  canConfirm: boolean
  busy: boolean
  onConfirm: (id: string, confirmed: boolean) => void
}) {
  const when = new Date(frame.ts * 1000).toLocaleString(dateLocale())
  return (
    <Card className="overflow-hidden">
      <div className="flex flex-col gap-4 p-4 sm:flex-row">
        <img src={fileUrl(frame.image)} alt={`Candidate frame at ${when}`} loading="lazy"
          className="h-40 w-full shrink-0 rounded-md border bg-muted object-cover sm:w-56" />
        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <Badge>{frame.source === 'stream' ? 'Stream event' : 'Footage'}</Badge>
            <span className="text-xs text-muted-foreground">{when}</span>
            <span className="ml-auto"><Score value={frame.score} /></span>
          </div>
          <p className="text-sm">{frame.label || 'No stored label for this frame'}</p>
          <p className="truncate text-xs text-muted-foreground" title={frame.source_name || frame.source_id}>
            {frame.source_name || (frame.source === 'stream' ? `Stream ${frame.stream_id?.slice(0, 8) ?? ''}` : 'Recorded footage')}
          </p>
          <div className="flex flex-wrap items-center gap-2 pt-1">
            {canConfirm ? (
              <Button size="sm" variant={confirmed ? 'outline' : 'primary'} disabled={busy}
                onClick={() => onConfirm(frame.id, !confirmed)}>
                {confirmed ? 'Remove confirmation' : 'Confirm candidate'}
              </Button>
            ) : (
              <span className="text-xs text-muted-foreground">A reviewer confirms candidates.</span>
            )}
            {confirmed && (
              <Badge className="bg-success/15 text-success">
                <BadgeCheck className="h-3.5 w-3.5" aria-hidden /> Confirmed by a person
              </Badge>
            )}
          </div>
        </div>
      </div>
    </Card>
  )
}
