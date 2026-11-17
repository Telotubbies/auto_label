/**
 * What is installed on this host (T-1013): the disk needle, one row per installed model with its size
 * and the date the host reported, the engine line, and one confirmed removal. It sits above the
 * catalogue in the Models tab and reads the host the tab already loaded, reusing the catalogue and
 * job queries by key so the panel costs no extra request. The remedy for a full disk lives here,
 * because telling an admin to use the host's shell is not a product.
 */
import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { Button, Card, Modal, Spinner, toast, Progress } from '@/components/ui'
import { ApiError } from '@/lib/api/client'
import { inferenceJobs, inferenceModels, inferenceRemoveModel } from '@/lib/api/inference'
import type { InferenceHost, InferenceJob } from '@/lib/types'
import {
  LOW_DISK, diskPct, emptyCopy, engineLine, gib, installedModels, lowDisk, removeCopy,
} from './assets'
import JobLogSheet from './JobLogSheet'

type Row = ReturnType<typeof installedModels>[number]
/** `variant` is the catalogue's quant label for the copy; `variantId` is what the API takes. */
type Picked = { row: Row; name: string; variant: string; variantId: string }

/** The disk line: `812 GB free of 1.8 TB`; total switches unit past 1024 GB, the size the host reports. */
function diskText(free?: number, total?: number) {
  if (typeof free !== 'number' || typeof total !== 'number') return null
  const whole = total >= 1024 ? `${(total / 1024).toFixed(1)} TB` : `${Math.round(total)} GB`
  return `${Math.round(free)} GB free of ${whole}`
}

export default function AssetsPanel({ ws, host }: { ws: string; host: InferenceHost | null }) {
  const hostId = host?.id ?? ''
  const qc = useQueryClient()
  // The same keys ModelsTab and InstallProgress use: one fetch feeds the names, the busy state and the rows.
  const models = useQuery({
    queryKey: ['inference-models', ws, hostId],
    enabled: !!hostId,
    retry: false,
    queryFn: () => inferenceModels(ws, hostId),
  })
  const jobs = useQuery({
    queryKey: ['inference-jobs', ws],
    enabled: !!ws,
    retry: false,
    queryFn: () => inferenceJobs(ws),
  })
  const [open, setOpen] = useState(true)
  const [seenHost, setSeenHost] = useState(hostId)
  const [confirm, setConfirm] = useState<Picked | null>(null)
  const [working, setWorking] = useState(false)
  const [notice, setNotice] = useState('')
  const [logJob, setLogJob] = useState<InferenceJob | null>(null)

  // A different host is a different disk, inventory and job: nothing said about the old one carries over.
  if (seenHost !== hostId) {
    setSeenHost(hostId)
    setConfirm(null)
    setNotice('')
  }

  const inventory = host?.inventory ?? null
  const disk = inventory?.disk
  const rows = installedModels(inventory)
  const empty = emptyCopy(inventory)
  const engines = engineLine(inventory)
  const pct = diskPct(disk)
  const low = lowDisk(disk)
  const busy = (jobs.data ?? []).find((job) => job.host === hostId) ?? null

  // A host that reported no variant still names one in the catalogue. An exact byte match picks the
  // variant the host actually holds; otherwise the first installed one is the only signal there is.
  // shortcut: a host that reports neither a variant nor matching bytes can get the wrong variant id,
  // upgrade when the inventory carries the variant (T-1001's shape, not this panel's to change).
  const variantOf = (row: Row): string => {
    const candidates = models.data?.models.find((model) => model.id === row.id)?.variants
      .filter((variant) => variant.installed) ?? []
    return row.variant ?? (candidates.find((variant) => variant.bytes === row.bytes) ?? candidates[0])?.id ?? ''
  }
  const nameOf = (row: Row): string =>
    models.data?.models.find((model) => model.id === row.id)?.name ?? row.id ?? ''
  const labelOf = (row: Row, variant: string): string =>
    models.data?.models.find((model) => model.id === row.id)?.variants
      .find((item) => item.id === variant)?.quant ?? variant

  const remove = async () => {
    if (!host || !confirm) return
    setWorking(true)
    setNotice('')
    try {
      await inferenceRemoveModel(ws, {
        host: host.id, id: confirm.row.id ?? '', variant: confirm.variantId, confirm: true,
      })
      setConfirm(null)
      setNotice(`Removal queued on ${host.host}. The rows and the disk follow the job.`)
      void qc.invalidateQueries({ queryKey: ['inference-jobs', ws] })
      void qc.invalidateQueries({ queryKey: ['inference-hosts', ws] })
      void qc.invalidateQueries({ queryKey: ['inference-models', ws, host.id] })
    } catch (err) {
      // The 404 is the one the admin can meet honestly: the model left the host while the sheet was open.
      if (err instanceof ApiError && err.status === 404) {
        setConfirm(null)
        setNotice('That model is no longer on this host.')
        void qc.invalidateQueries({ queryKey: ['inference-hosts', ws] })
        void qc.invalidateQueries({ queryKey: ['inference-models', ws, host.id] })
      } else {
        toast.err(err instanceof Error ? err.message : 'The removal request did not reach the server.')
      }
    } finally {
      setWorking(false)
    }
  }

  // No host at all is the tab's own empty state, not this panel's.
  if (!host) return null

  const line = diskText(disk?.models_free_gb, disk?.models_total_gb)

  return (
    <Card id="host-assets" className="overflow-hidden">
      <div className="flex flex-col gap-2 p-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <button type="button" aria-expanded={open} aria-controls="host-assets-body"
            onClick={() => setOpen((value) => !value)}
            className="flex items-center gap-1.5 text-sm font-medium">
            {open ? <ChevronDown className="h-4 w-4" aria-hidden /> : <ChevronRight className="h-4 w-4" aria-hidden />}
            Installed on this host
          </button>
          <p className="mt-1 text-xs text-muted-foreground">
            {engines || (inventory ? 'No engine is installed on this host.' : '')}
          </p>
        </div>
        <div className="sm:text-right">
          {line && <p className="text-sm tabular-nums text-muted-foreground">{line}</p>}
          {low && <p className="mt-0.5 text-xs text-warning">{LOW_DISK}</p>}
        </div>
      </div>

      {open && (
        <div id="host-assets-body" className="space-y-3 border-t p-4 pt-3">
          {pct !== null && (
            <Progress value={pct} label={`Free disk on ${host.host}`}
              className={low ? '[&>div]:bg-warning' : undefined} />
          )}

          {empty ? (
            <p className="text-sm text-muted-foreground">{empty}</p>
          ) : (
            <div className="overflow-x-auto" role="region" aria-label="Installed models" tabIndex={0}>
              <table className="w-full min-w-[34rem] text-sm">
                <caption className="sr-only">Models installed on {host.host}, what they take and when the host saw them</caption>
                <thead className="bg-muted/60 text-left text-xs text-muted-foreground">
                  <tr>
                    <th scope="col" className="sticky left-0 z-10 bg-muted/60 px-3 py-2 font-medium">Model</th>
                    <th scope="col" className="px-3 py-2 font-medium">Variant</th>
                    <th scope="col" className="whitespace-nowrap px-3 py-2 font-medium">Size</th>
                    <th scope="col" className="whitespace-nowrap px-3 py-2 font-medium">Installed</th>
                    <th scope="col" className="px-2 py-2"><span className="sr-only">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => {
                    const variant = variantOf(row)
                    return (
                      <tr key={`${row.id}/${row.variant ?? ''}`} className="border-t">
                        <td className="sticky left-0 bg-card px-3 py-2.5 font-medium">{nameOf(row)}</td>
                        <td className="px-3 py-2.5 text-muted-foreground">{labelOf(row, variant) || 'unknown'}</td>
                        <td className="whitespace-nowrap px-3 py-2.5 tabular-nums">{gib(row.bytes)}</td>
                        {/* The host's file mtime, as it reported it; the UI never invents a date. */}
                        <td className="whitespace-nowrap px-3 py-2.5 text-muted-foreground">{row.installed_at || 'unknown'}</td>
                        <td className="px-2 py-2.5 text-right">
                          <Button variant="outline" size="sm" disabled={!variant || !!busy}
                            onClick={() => setConfirm({
                              row, name: nameOf(row), variant: labelOf(row, variant), variantId: variant,
                            })}>
                            Remove
                          </Button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

          {busy && (
            <p className="text-sm text-muted-foreground">
              Removal is paused while a job runs on this host.{' '}
              <button type="button" className="text-primary hover:underline" onClick={() => setLogJob(busy)}>
                View job
              </button>
            </p>
          )}
          {notice && <p role="status" className="text-sm text-muted-foreground">{notice}</p>}
        </div>
      )}

      {confirm && (
        <Modal open onClose={working ? () => {} : () => setConfirm(null)} title="Remove model?">
          <div className="flex h-[calc(100dvh-9rem)] flex-col sm:h-auto sm:min-h-0">
            <p className="text-sm">
              {removeCopy({ ...confirm.row, name: confirm.name, variant: confirm.variant, host: host.host })}
            </p>
            <p className="mt-2 text-xs text-muted-foreground">
              This deletes the model&rsquo;s files on the host. Nothing else on the host is touched.
            </p>
            <div className="mt-auto flex justify-end gap-2 pt-4">
              <Button variant="outline" disabled={working} onClick={() => setConfirm(null)}>Cancel</Button>
              <Button variant="destructive" disabled={working} onClick={() => void remove()}>
                {working ? <><Spinner className="h-3 w-3" /> Removing…</> : 'Remove'}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      <JobLogSheet job={logJob} open={!!logJob} onClose={() => setLogJob(null)} />
    </Card>
  )
}
