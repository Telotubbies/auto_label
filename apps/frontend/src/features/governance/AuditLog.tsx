import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Download, ScrollText, Video } from 'lucide-react'
import { useParams } from 'react-router-dom'
import { api, download } from '@/lib/api'
import type { AuditFilters } from '@/lib/types'
import { Badge, Button, Card, EmptyState, Field, Input, PageHeader, Spinner, fmtDate, toast } from '@/components/ui'

const LIMIT = 100

const fmtClock = (t: number) => new Date(t * 1000).toLocaleTimeString(undefined, {
  hour: '2-digit', minute: '2-digit', second: '2-digit',
})

/** Date input (YYYY-MM-DD) to epoch seconds, at the start or end of that local day. */
const dayEpoch = (value: string, end = false) => {
  if (!value) return undefined
  const [y, m, d] = value.split('-').map(Number)
  if (!y || !m || !d) return undefined
  const t = new Date(y, m - 1, d, end ? 23 : 0, end ? 59 : 0, end ? 59 : 0).getTime()
  return Math.floor(t / 1000)
}

const isStreamView = (action: string) => action === 'stream.view' || action.startsWith('stream.view.')

function ActionChip({ action }: { action: string }) {
  if (isStreamView(action)) {
    return (
      <Badge className="border border-info/40 bg-info/10 font-mono text-foreground">
        <Video className="h-3 w-3 text-info" aria-hidden />stream.view
      </Badge>
    )
  }
  return <Badge className="font-mono text-foreground">{action}</Badge>
}

function SkeletonRows() {
  return (
    <div role="status" aria-label="Loading audit entries" className="space-y-2 p-4">
      {Array.from({ length: 8 }, (_, i) => (
        <div key={i} className="flex gap-3">
          <span className="skeleton h-4 w-24" />
          <span className="skeleton h-4 w-28" />
          <span className="skeleton h-4 w-32" />
          <span className="skeleton h-4 flex-1" />
        </div>
      ))}
    </div>
  )
}

export default function AuditLog() {
  const { ws = '' } = useParams()
  const [form, setForm] = useState({ action: '', user: '', from: '', to: '', q: '' })
  const [filters, setFilters] = useState<AuditFilters>({})
  const [offset, setOffset] = useState(0)
  const [exporting, setExporting] = useState(false)

  const q = useQuery({
    queryKey: ['audit-log', ws, filters, offset],
    queryFn: () => api.audit(ws, { ...filters, limit: LIMIT, offset }),
    enabled: !!ws,
  })
  const rows = q.data ?? []
  const hasFilters = Object.keys(filters).length > 0

  const apply = (e: React.FormEvent) => {
    e.preventDefault()
    const next: AuditFilters = {}
    if (form.action.trim()) next.action = form.action.trim()
    if (form.user.trim()) next.user = form.user.trim()
    if (form.q.trim()) next.q = form.q.trim()
    const since = dayEpoch(form.from)
    const until = dayEpoch(form.to, true)
    if (since) next.since = since
    if (until) next.until = until
    setOffset(0)
    setFilters(next)
  }

  const reset = () => {
    setForm({ action: '', user: '', from: '', to: '', q: '' })
    setFilters({})
    setOffset(0)
  }

  const exportCsv = async () => {
    setExporting(true)
    try {
      await download(api.auditExportPath(ws, filters), `audit-${ws}.csv`)
      toast.ok('Audit export downloaded')
    } catch (e) {
      toast.err(e as Error)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="anim-page max-w-6xl">
      <PageHeader
        title="Audit log"
        desc="Every sensitive action in this workspace, including each view of stream footage."
        actions={
          <>
            <Badge className="hidden bg-card/70 text-foreground sm:inline-flex"><ScrollText className="h-3 w-3" aria-hidden />Retained by policy</Badge>
            <Button variant="outline" onClick={exportCsv} disabled={exporting || !ws}>
              {exporting ? <Spinner className="h-4 w-4" /> : <Download className="h-4 w-4" aria-hidden />}
              {exporting ? 'Exporting…' : 'Export CSV'}
            </Button>
          </>
        }
      />

      <div className="space-y-4 px-4 pb-10 sm:px-8">
        <Card className="p-4">
          <form onSubmit={apply} aria-label="Filter audit log">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              <Field label="Action" hint="Exact action, or a prefix without a dot.">
                <Input value={form.action} onChange={(e) => setForm({ ...form, action: e.target.value })} placeholder="stream or stream.view" autoComplete="off" />
              </Field>
              <Field label="User">
                <Input value={form.user} onChange={(e) => setForm({ ...form, user: e.target.value })} placeholder="Email or name" autoComplete="off" />
              </Field>
              <Field label="From">
                <Input type="date" value={form.from} max={form.to || undefined} onChange={(e) => setForm({ ...form, from: e.target.value })} />
              </Field>
              <Field label="To">
                <Input type="date" value={form.to} min={form.from || undefined} onChange={(e) => setForm({ ...form, to: e.target.value })} />
              </Field>
              <Field label="Search">
                <Input value={form.q} onChange={(e) => setForm({ ...form, q: e.target.value })} placeholder="Target or details" autoComplete="off" />
              </Field>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Button type="submit">Apply filters</Button>
              <Button type="button" variant="ghost" onClick={reset} disabled={!hasFilters && !form.action && !form.user && !form.from && !form.to && !form.q}>Reset</Button>
              <span className="ml-auto text-xs text-muted-foreground">Dates are local time · newest first</span>
            </div>
          </form>
        </Card>

        <Card className="overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-3">
            <h2 className="text-sm font-semibold">Entries</h2>
            <p role="status" aria-live="polite" className="text-xs text-muted-foreground">
              {q.isLoading ? 'Loading entries…' : q.isError ? 'Could not load entries' : `${rows.length} shown${hasFilters ? ' · filtered' : ''}`}
            </p>
          </div>

          {q.isLoading ? (
            <SkeletonRows />
          ) : q.isError ? (
            <div className="flex flex-col items-center gap-2 px-4 py-10 text-center">
              <p role="alert" className="text-sm text-destructive">{q.error instanceof Error ? q.error.message : 'Could not load the audit log.'}</p>
              <Button variant="outline" size="sm" onClick={() => void q.refetch()}>Try again</Button>
            </div>
          ) : !rows.length ? (
            <div className="py-6">
              <EmptyState
                icon={<ScrollText className="h-8 w-8 text-muted-foreground/50" aria-hidden />}
                title={hasFilters ? 'No entries match these filters.' : 'No audit entries yet.'}
                hint={hasFilters ? 'Widen the date range or clear the action prefix.' : 'Uploads, exports, role changes and stream views will appear here.'}
                action={hasFilters ? <Button variant="outline" size="sm" onClick={reset}>Clear filters</Button> : undefined}
              />
            </div>
          ) : (
            <div className="overflow-x-auto" role="region" aria-label="Audit entries" tabIndex={0}>
              <table className="w-full min-w-[46rem] text-sm">
                <caption className="sr-only">Audit entries, newest first</caption>
                <thead className="bg-muted/60 text-left text-xs text-muted-foreground">
                  <tr>
                    <th scope="col" className="whitespace-nowrap px-4 py-2 font-medium">When</th>
                    <th scope="col" className="px-4 py-2 font-medium">User</th>
                    <th scope="col" className="px-4 py-2 font-medium">Action</th>
                    <th scope="col" className="px-4 py-2 font-medium">Target</th>
                    <th scope="col" className="px-4 py-2 font-medium">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((a) => {
                    const metaKeys = Object.keys(a.meta ?? {})
                    return (
                      <tr key={a.id} className="border-t align-top">
                        <td className="whitespace-nowrap px-4 py-2.5 text-muted-foreground">
                          <time dateTime={new Date(a.created * 1000).toISOString()} title={`${fmtDate(a.created)} ${fmtClock(a.created)}`}>{fmtDate(a.created)}</time>
                          <div className="text-xs">{fmtClock(a.created)}</div>
                        </td>
                        <td className="max-w-40 px-4 py-2.5"><span className="block truncate" title={a.user}>{a.user || '—'}</span></td>
                        <td className="px-4 py-2.5"><ActionChip action={a.action} /></td>
                        <td className="max-w-48 px-4 py-2.5"><span className="block truncate" title={a.target}>{a.target || '—'}</span></td>
                        <td className="px-4 py-2.5 text-xs text-muted-foreground">
                          {metaKeys.length ? (
                            <details>
                              <summary className="cursor-pointer text-xs text-foreground marker:text-muted-foreground">{metaKeys.length} field{metaKeys.length === 1 ? '' : 's'}</summary>
                              <pre className="mt-1 max-w-xs overflow-x-auto whitespace-pre-wrap break-words rounded bg-muted p-2 text-xs">{JSON.stringify(a.meta, null, 2)}</pre>
                            </details>
                          ) : '—'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-2 border-t px-4 py-3">
            <span className="text-xs text-muted-foreground">
              {rows.length ? `Rows ${offset + 1}–${offset + rows.length}` : 'No rows'}
            </span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={offset === 0 || q.isFetching} onClick={() => setOffset(Math.max(0, offset - LIMIT))}>
                <ChevronLeft className="h-4 w-4" aria-hidden /> Previous
              </Button>
              <Button variant="outline" size="sm" disabled={rows.length < LIMIT || q.isFetching} onClick={() => setOffset(offset + LIMIT)}>
                Next <ChevronRight className="h-4 w-4" aria-hidden />
              </Button>
            </div>
          </div>
        </Card>

        <p className="text-xs text-muted-foreground">
          Exports contain the same rows as the current filters. Stream access is logged as <code className="font-mono">stream.view</code> for every viewer.
        </p>
      </div>
    </div>
  )
}
