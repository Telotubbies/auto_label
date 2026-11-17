/**
 * The engine sheet (T-1007): the plan T-1006 built, read and acknowledged before one job is queued,
 * and the second confirmation that uninstalls. The argv is shown as it came back and is never sent
 * anywhere; the request carries ids, versions and runtime enums (see `installRequest`).
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Button, Modal, Spinner } from '@/components/ui'
import { ApiError } from '@/lib/api/client'
import { inferenceInstallEngines, inferencePlanEngines, inferenceUninstallEngine } from '@/lib/api/inference'
import type { EngineAvailability, InferenceHost } from '@/lib/types'
import { argvText, engineChoices, installRequest } from './engineRows'

const EMPTY: Set<string> = new Set()
const NOTHING = 'Nothing to install.'

/** ApiError carries a string detail; a 409 (busy host or stale plan) gets the sentence the sheet owns.
 *  The API also puts the running job's id in the 409 body, so a busy host can offer that job. */
function inlineError(err: unknown, conflict: string) {
  if (!(err instanceof ApiError)) {
    return { message: 'The request did not reach the host. Check the connection and try again.', conflict: false, jobId: '' }
  }
  const detail = (err.body as { detail?: { job_id?: unknown } } | undefined)?.detail
  const jobId = typeof detail?.job_id === 'string' ? detail.job_id : ''
  return err.status === 409
    ? { message: conflict, conflict: true, jobId }
    : { message: err.message, conflict: false, jobId: '' }
}

export default function EngineSheet({ ws, host, open, onClose, rows = [], selected = EMPTY,
  runtimes = {}, uninstall = null, onQueued }: {
  ws: string; host: InferenceHost; open: boolean; onClose: () => void
  rows?: EngineAvailability[]; selected?: Set<string>; runtimes?: Record<string, string>
  uninstall?: EngineAvailability | null
  /** The queued job id and the engine ids it covers, so the tab can mark those rows. */
  onQueued: (jobId: string, ids: string[]) => void
}) {
  const picked = rows.filter((row) => selected.has(row.id))
  const plan = useQuery({
    queryKey: ['inference-plan', ws, host.id,
      picked.map((row) => `${row.id}:${runtimes[row.id] ?? row.runtimes[0]}`).join(',')],
    enabled: open && !uninstall,
    retry: false,
    queryFn: () => inferencePlanEngines(ws, { host: host.id, engines: engineChoices(rows, selected, runtimes) }),
  })
  const [ack, setAck] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<{ message: string; conflict: boolean; jobId: string } | null>(null)
  const step = plan.data
  const nameOf = (id: string) => rows.find((row) => row.id === id)?.name ?? id
  const gb = (mb: number) => `${(mb / 1024).toFixed(1)} GB`

  const install = async () => {
    if (!step) return
    setBusy(true); setError(null)
    try {
      const { job } = await inferenceInstallEngines(ws,
        installRequest(host.id, rows, selected, runtimes, step.plan_id))
      onQueued(job.id, picked.map((row) => row.id))
      onClose()
    } catch (err) {
      setError(inlineError(err, 'An engine job is already running on this host, or the plan is out of date.'))
    } finally { setBusy(false) }
  }

  const remove = async () => {
    if (!uninstall) return
    setBusy(true); setError(null)
    try {
      const { job } = await inferenceUninstallEngine(ws, { host: host.id, id: uninstall.id, confirm: true })
      onQueued(job.id, [uninstall.id])
      onClose()
    } catch (err) {
      setError(inlineError(err, 'An engine job is already running on this host.'))
    } finally { setBusy(false) }
  }
  return (
    <Modal open={open} onClose={busy ? () => {} : onClose}
      title={uninstall ? `Uninstall ${uninstall.name}?` : 'Review install plan'}>
      {/* The dialog spends 4rem on its margins and ~6rem on a title block and padding, so a
          viewport-tall child put Install below the fold. Cap the sheet inside that chrome and let
          the body scroll; the acknowledgement and the buttons stay where the eye ends. */}
      <div className="flex max-h-[calc(100dvh-10rem)] flex-col">
        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto">
          <p className="text-sm text-muted-foreground">
            Host <span className="font-medium text-foreground">{host.host}</span>
          </p>

          {uninstall ? (
            <p className="text-sm">
              This removes <span className="font-medium">{uninstall.name} {uninstall.version}</span> and the
              virtual environment it owns on <span className="font-medium">{host.host}</span>. Shared system
              packages are not touched.
            </p>
          ) : plan.isLoading ? (
            <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground">
              <Spinner /> Building the plan…
            </p>
          ) : plan.isError ? (
            <div className="space-y-2">
              <p className="text-sm text-destructive">The plan could not be built.</p>
              <p className="text-sm text-muted-foreground">{inlineError(plan.error, 'The host changed. Build the plan again.').message}</p>
              <Button variant="outline" size="sm" onClick={() => void plan.refetch()}>Retry</Button>
            </div>
          ) : step && (
            <>
              <ul className="space-y-2">
                {step.steps.map((row) => (
                  <li key={row.id} className="rounded-md border p-3">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <span className="text-sm font-medium">{nameOf(row.id)}</span>
                      <span className="font-mono text-xs text-muted-foreground">{row.version} · {row.runtime}</span>
                    </div>
                    {row.status === 'installed'
                      ? <p className="mt-1 text-sm text-muted-foreground">Already installed at {row.installed_version ?? row.version}.</p>
                      : row.status === 'blocked'
                        ? <p className="mt-1 text-sm text-destructive">{row.reason ?? 'Blocked on this host.'}</p>
                        : <pre className="mt-1.5 overflow-x-auto rounded-md bg-muted p-2 font-mono text-xs">{argvText(row)}</pre>}
                  </li>
                ))}
              </ul>

              <dl className="grid grid-cols-3 gap-2 text-sm">
                <div>
                  <dt className="text-xs text-muted-foreground">Total download</dt>
                  <dd className="tabular-nums">{gb(step.total_disk_mb)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Disk free now</dt>
                  <dd className="tabular-nums">{step.disk_free_gb === null ? 'unknown' : `${step.disk_free_gb} GB`}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Disk after</dt>
                  <dd className="tabular-nums">{step.disk_after_gb === null ? 'unknown' : `${step.disk_after_gb} GB`}</dd>
                </div>
              </dl>

              {!!step.warnings.length && (
                <ul className="space-y-1 text-sm text-warning">
                  {step.warnings.map((line) => <li key={line}>{line}</li>)}
                </ul>
              )}
              {!!step.blocked.length && (
                <ul className="space-y-1 text-sm text-destructive">
                  {step.blocked.map((row) => <li key={row.id}>{nameOf(row.id)}: {row.reason}</li>)}
                </ul>
              )}
            </>
          )}
        </div>

        <div className="mt-auto pt-4">
          {error && (
            <div className="mb-3 space-y-1.5">
              <p role="alert" className="text-sm text-destructive">{error.message}</p>
              {error.conflict && (
                <div className="flex flex-wrap gap-2">
                  {error.jobId && (
                    <Button variant="outline" size="sm" onClick={onClose}>View job</Button>
                  )}
                  <Button variant="outline" size="sm" onClick={() => { setError(null); void plan.refetch() }}>
                    Review the plan again
                  </Button>
                </div>
              )}
            </div>
          )}
          {!uninstall && step && !step.noop && (
            <label className="mb-3 flex items-start gap-2 text-sm">
              <input type="checkbox" className="mt-0.5 h-4 w-4 accent-primary" checked={ack}
                onChange={(e) => setAck(e.target.checked)} />
              I understand this installs software on {host.host}
            </label>
          )}
          {!uninstall && step?.noop && <p className="mb-3 text-xs text-muted-foreground">{NOTHING}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose} disabled={busy}>Cancel</Button>
            {uninstall ? (
              <Button variant="destructive" onClick={() => void remove()} disabled={busy}>
                {busy ? <><Spinner className="h-3 w-3" /> Uninstalling…</> : 'Uninstall'}
              </Button>
            ) : (
              <Button onClick={() => void install()} disabled={!ack || busy || !step || step.noop}>
                {busy ? <><Spinner className="h-3 w-3" /> Installing…</> : 'Install'}
              </Button>
            )}
          </div>
        </div>
      </div>
    </Modal>
  )
}
