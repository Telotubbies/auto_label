/**
 * The Engines tab (T-1007): one host's engines, what this host can actually install, and one deliberate
 * confirm. The host picker lives in the hub header (Models and Segmentation share it); this panel only
 * consumes the chosen host and clears its ticks when that host changes.
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Lock, MoreHorizontal } from 'lucide-react'
import { Glass } from '@/components/glass'
import { Button, Card, Dropdown, EmptyState, Select, Spinner } from '@/components/ui'
import { inferenceEngines } from '@/lib/api/inference'
import { cn } from '@/lib/utils'
import type { EngineAvailability, EngineStatus, InferenceHost } from '@/lib/types'
import {
  changeHost, footerCopy, rowStatusCopy, selectable, toggle, totals, type Selection,
} from './engineRows'
import EngineSheet from './EngineSheet'

const WORKER = 'labeldesk-worker --kinds train,autolabel,engine_apply,model_pull'
const TONE: Record<EngineStatus, string> = {
  ok: 'bg-success/15 text-success',
  warn: 'bg-warning/15 text-warning',
  blocked: 'bg-destructive/15 text-destructive',
}
const WORD: Record<EngineStatus, string> = { ok: 'Compatible', warn: 'Warning', blocked: 'Blocked' }
const SKELETON = [0, 1, 2, 3, 4]

/** Five skeleton rows while the host list or its engines are still on the wire. */
const SkeletonRows = () => (
  <Card className="divide-y overflow-hidden" aria-busy="true" aria-label="Loading engines">
    {SKELETON.map((i) => (
      <div key={i} className="flex items-center gap-3 p-4">
        <div className="h-4 w-4 animate-pulse rounded bg-muted" />
        <div className="h-4 flex-1 animate-pulse rounded bg-muted" />
        <div className="h-4 w-16 animate-pulse rounded bg-muted" />
      </div>
    ))}
  </Card>
)

export default function EnginesTab({ ws, host, hostsLoading, hostsError, onRetryHosts }: {
  ws: string
  host: InferenceHost | null
  hostsLoading: boolean
  hostsError: boolean
  onRetryHosts: () => void
}) {
  const hostId = host?.id ?? ''
  const engines = useQuery({
    queryKey: ['inference-engines', ws, hostId],
    enabled: !!hostId,
    retry: false,
    queryFn: () => inferenceEngines(ws, hostId),
  })
  const [sel, setSel] = useState<Selection>({ host: hostId, selected: new Set(), notice: null })
  const [runtimes, setRuntimes] = useState<Record<string, string>>({})
  const [queued, setQueued] = useState<Set<string>>(new Set())
  const [queuedOn, setQueuedOn] = useState<string | null>(null)
  const [planOpen, setPlanOpen] = useState(false)
  const [uninstallRow, setUninstallRow] = useState<EngineAvailability | null>(null)

  // A different host is a different inventory: the old ticks, runtimes and queued rows do not carry over.
  if (sel.host !== hostId) {
    setSel(changeHost(sel, hostId))
    setRuntimes({})
    setQueued(new Set())
    setQueuedOn(null)
  }

  const rows = engines.data?.engines ?? []
  const freeGb = host?.inventory?.disk?.models_free_gb ?? null
  const allowInstall = host?.inventory?.allow_install ?? true
  const t = totals(rows, sel.selected)
  const why = footerCopy(t, freeGb, allowInstall, host?.online ?? true)
  const canPlan = t.count > 0 && !!host?.online && allowInstall

  const pick = (row: EngineAvailability) => {
    if (!selectable(row) || queued.has(row.id)) return
    setSel((current) => toggle(current, row.id))
    setQueuedOn(null)
  }
  const queuedRows = (jobId: string, ids: string[]) => {
    setQueued((current) => new Set([...current, ...ids]))
    setQueuedOn(host?.host ?? jobId)
    setSel((current) => ({ ...current, selected: new Set(), notice: null }))
  }

  if (hostsLoading) {
    return <SkeletonRows />
  }

  if (hostsError) {
    return (
      <Card className="p-6">
        <p className="text-sm text-destructive">Engines did not load for this host.</p>
        <Button variant="outline" size="sm" className="mt-2" onClick={onRetryHosts}>Retry</Button>
      </Card>
    )
  }

  return (
    <div className="space-y-3">
      {!host ? (
        <Card className="p-6">
          <EmptyState title="Start a worker, then pick it here."
            hint="A worker reports its engines, disk and GPU when it claims a job."
            action={<code className="mt-1 block max-w-full overflow-x-auto rounded-md bg-muted px-2 py-1 font-mono text-xs">{WORKER}</code>} />
        </Card>
      ) : engines.isLoading ? (
        <SkeletonRows />
      ) : engines.isError ? (
        <Card className="p-6">
          <p className="text-sm text-destructive">Engines did not load for this host.</p>
          <Button variant="outline" size="sm" className="mt-2" onClick={() => void engines.refetch()}>Retry</Button>
        </Card>
      ) : !rows.length ? (
        <Card className="p-6"><EmptyState title="No engine has a verified pin yet." /></Card>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto" role="region" aria-label="Engines" tabIndex={0}>
            <table className="w-full min-w-[56rem] text-sm">
              <caption className="sr-only">Engines, their pinned versions and compatibility with {host.host}</caption>
              <thead className="bg-muted/60 text-left text-xs text-muted-foreground">
                <tr>
                  <th scope="col" className="sticky left-0 z-10 bg-muted/60 px-4 py-2 font-medium">Engine</th>
                  <th scope="col" className="whitespace-nowrap px-4 py-2 font-medium">Pinned version</th>
                  <th scope="col" className="px-4 py-2 font-medium">Runtime</th>
                  <th scope="col" className="px-4 py-2 font-medium">OS / accelerator</th>
                  <th scope="col" className="whitespace-nowrap px-4 py-2 font-medium">Disk</th>
                  <th scope="col" className="px-4 py-2 font-medium">Status</th>
                  <th scope="col" className="px-4 py-2 font-medium">Compatibility</th>
                  <th scope="col" className="px-2 py-2"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const status = rowStatusCopy(row)
                  const blocked = !selectable(row)
                  const running = queued.has(row.id)
                  const reason = blocked ? row.compatibility.reasons[0] : row.compatibility.warnings[0]
                  return (
                    <tr key={row.id} className="border-t align-top">
                      <td className="sticky left-0 z-10 bg-card px-4 py-2.5">
                        <label className="flex items-start gap-2">
                          <input type="checkbox" className="mt-1 h-4 w-4 shrink-0 accent-primary"
                            checked={sel.selected.has(row.id)} disabled={blocked || running}
                            onChange={() => pick(row)} aria-label={`Select ${row.name}`} />
                          <span className="min-w-0">
                            <span className="block font-medium">{row.name}</span>
                            <span className="block max-w-56 text-xs text-muted-foreground">{row.summary}</span>
                          </span>
                        </label>
                      </td>
                      <td className="whitespace-nowrap px-4 py-2.5 font-mono text-xs">{row.version}</td>
                      <td className="px-4 py-2.5">
                        <Select aria-label={`Runtime for ${row.name}`} className="h-8 text-xs"
                          value={runtimes[row.id] ?? row.runtimes[0]}
                          onChange={(e) => setRuntimes((current) => ({ ...current, [row.id]: e.target.value }))}>
                          {row.runtimes.map((runtime) => <option key={runtime} value={runtime}>{runtime}</option>)}
                        </Select>
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground">
                        {row.os.join(', ')}{row.accelerator.length ? ` · ${row.accelerator.join(', ')}` : ''}
                      </td>
                      <td className="whitespace-nowrap px-4 py-2.5 tabular-nums">{`${(row.disk_mb / 1024).toFixed(1)} GB`}</td>
                      <td className="whitespace-nowrap px-4 py-2.5">
                        {running ? (
                          <span className="inline-flex items-center gap-1.5 text-muted-foreground">
                            <Spinner className="h-3 w-3" /> Queued
                          </span>
                        ) : row.installed ? (
                          <span className="inline-flex items-center gap-1.5">
                            <span className="h-2 w-2 rounded-full bg-success" aria-hidden /> {status.label}
                          </span>
                        ) : <span className="text-muted-foreground">{status.label}</span>}
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
                          TONE[row.compatibility.status])}>{WORD[row.compatibility.status]}</span>
                        {reason && (
                          <span className="mt-1 flex items-start gap-1 text-xs text-muted-foreground">
                            {blocked && <Lock className="mt-0.5 h-3 w-3 shrink-0" aria-hidden />}
                            {reason}
                          </span>
                        )}
                      </td>
                      <td className="px-2 py-2.5 text-right">
                        {status.uninstall && !running && (
                          <Dropdown align="right"
                            trigger={<Button variant="ghost" size="icon" aria-label={`Actions for ${row.name}`}>
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>}
                            items={[{ label: 'Uninstall', danger: true, onClick: () => setUninstallRow(row) }]} />
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {queuedOn && (
        <p role="status" className="text-sm text-success">
          Install queued on {queuedOn}. Open the job to follow the log.
        </p>
      )}
      {sel.notice && <p role="status" className="text-sm text-muted-foreground">{sel.notice}</p>}

      <Glass className="sticky bottom-3 z-20 flex flex-wrap items-center justify-between gap-3 rounded-xl px-3 py-2.5">
        <p className="text-sm">{why}</p>
        <Button disabled={!canPlan} onClick={() => setPlanOpen(true)}>Review install plan</Button>
      </Glass>

      {planOpen && host && (
        <EngineSheet ws={ws} host={host} open onClose={() => setPlanOpen(false)}
          rows={rows} selected={sel.selected} runtimes={runtimes} onQueued={queuedRows} />
      )}
      {uninstallRow && host && (
        <EngineSheet ws={ws} host={host} open onClose={() => setUninstallRow(null)}
          rows={rows} uninstall={uninstallRow} onQueued={queuedRows} />
      )}
    </div>
  )
}
