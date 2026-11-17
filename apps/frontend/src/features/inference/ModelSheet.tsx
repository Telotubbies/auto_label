/**
 * The download sheet (T-1012): the T-1010 plan read before one job is queued — files, bytes, disk
 * before and after, the gate, the token state and the licence. A block replaces the button, so a
 * download that cannot run is never offered. Only the basename of a file is shown; the repo path
 * stays on the server.
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ExternalLink } from 'lucide-react'
import { Button, Modal, Spinner } from '@/components/ui'
import { ApiError } from '@/lib/api/client'
import { inferenceDownloadModel, inferencePlanModel } from '@/lib/api/inference'
import type { InferenceHost, InferenceModel, InferenceModelVariant, ModelPlan } from '@/lib/types'
import { blockCopy, gib } from './modelRows'

const basename = (path: string) => path.split('/').pop() || path
const MIB = 1024 ** 2
/** A config file is not 0.0 GB: keep one decimal, but in the unit the reader can see. */
const fileSize = (bytes: number) =>
  (bytes >= 1024 ** 3 ? gib(bytes) : bytes >= MIB ? `${(bytes / MIB).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`)
const CONFLICT = 'A job is already running on this host, or this variant is installed.'

/** ApiError carries a string detail; a 409 (busy host, installed variant) gets the sentence the sheet owns. */
function inlineError(err: unknown, conflict: string) {
  if (!(err instanceof ApiError)) {
    return { message: 'The request did not reach the host. Check the connection and try again.', conflict: false }
  }
  return err.status === 409 ? { message: conflict, conflict: true } : { message: err.message, conflict: false }
}

export default function ModelSheet({ ws, host, row, variant, open, onClose, onQueued }: {
  ws: string; host: InferenceHost; row: InferenceModel; variant: InferenceModelVariant
  open: boolean; onClose: () => void
  /** The queued job and the row/variant it belongs to, so the table can read `Queued`. */
  onQueued: (jobId: string, rowId: string, variantId: string) => void
}) {
  const plan = useQuery({
    queryKey: ['inference-model-plan', ws, host.id, row.id, variant.id],
    enabled: open,
    retry: false,
    queryFn: () => inferencePlanModel(ws, { host: host.id, id: row.id, variant: variant.id }),
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<{ message: string; conflict: boolean } | null>(null)
  const body: ModelPlan | undefined = plan.data
  const copy = body ? blockCopy(body) : null

  const download = async () => {
    setBusy(true); setError(null)
    try {
      const { job } = await inferenceDownloadModel(ws, { host: host.id, id: row.id, variant: variant.id })
      onQueued(job.id, row.id, variant.id)
      onClose()
    } catch (err) {
      setError(inlineError(err, CONFLICT))
    } finally { setBusy(false) }
  }

  return (
    <Modal open={open} onClose={busy ? () => {} : onClose} title={`Download ${row.name}?`}>
      <div className="flex h-[calc(100dvh-9rem)] flex-col sm:h-auto sm:min-h-0">
        <p className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{variant.quant}</span> · {variant.engine} ·{' '}
          {variant.format} · <span className="tabular-nums">{gib(variant.bytes)}</span> on{' '}
          <span className="font-medium text-foreground">{host.host}</span>
        </p>

        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
          <a href={row.licence.url} target="_blank" rel="noreferrer noopener"
            className="inline-flex items-center gap-1 rounded-full bg-secondary px-2 py-0.5 font-medium hover:underline">
            {row.licence.name}<ExternalLink className="h-3 w-3" aria-hidden />
          </a>
          {row.licence.gated && (
            <span className="rounded-full bg-warning/15 px-2 py-0.5 font-medium text-warning">Gated</span>
          )}
          {row.licence.non_commercial && (
            <span className="rounded-full bg-warning/15 px-2 py-0.5 font-medium text-warning">
              Non-commercial licence
            </span>
          )}
        </div>

        {plan.isLoading ? (
          <p role="status" className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner /> Building the plan…
          </p>
        ) : plan.isError ? (
          <div className="mt-4 space-y-2">
            <p className="text-sm text-destructive">The plan could not be built.</p>
            <p className="text-sm text-muted-foreground">{inlineError(plan.error, CONFLICT).message}</p>
            <Button variant="outline" size="sm" onClick={() => void plan.refetch()}>Retry</Button>
          </div>
        ) : body && (
          <>
            <ul className="mt-3 min-h-24 flex-1 space-y-1 overflow-auto rounded-md border p-2 text-sm sm:max-h-40 sm:flex-none">
              {body.files.map((file) => (
                <li key={file.path} className="flex items-baseline justify-between gap-3">
                  <span className="min-w-0 truncate font-mono text-xs">{basename(file.path)}</span>
                  <span className="shrink-0 tabular-nums text-muted-foreground">{fileSize(file.bytes)}</span>
                </li>
              ))}
            </ul>

            <dl className="mt-3 grid grid-cols-3 gap-2 text-sm">
              <div>
                <dt className="text-xs text-muted-foreground">Total</dt>
                <dd className="tabular-nums">{gib(body.total_bytes)}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Disk free now</dt>
                <dd className="tabular-nums">{body.disk_free_gb === null ? 'unknown' : `${body.disk_free_gb.toFixed(1)} GB`}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Disk after</dt>
                <dd className="tabular-nums">{body.disk_after_gb === null ? 'unknown' : `${body.disk_after_gb.toFixed(1)} GB`}</dd>
              </div>
            </dl>

            <p className="mt-3 text-sm">
              Hugging Face token: {body.token_present
                ? <span className="text-success">present on {host.host}</span>
                : <span className="text-muted-foreground">none on {host.host}</span>}
            </p>
            {body.gate.gated && body.token_present && (
              <p className="mt-1 text-sm text-muted-foreground">
                The operator accepted this licence on the host's Hugging Face account.
              </p>
            )}
            {copy?.note && <p className="mt-1 text-sm text-warning">{copy.note}</p>}            {!!body.warnings.length && (
              <ul className="mt-3 space-y-1 text-sm text-warning">
                {body.warnings.map((line) => <li key={line}>{line}</li>)}
              </ul>
            )}
            {copy?.block && <p role="alert" className="mt-3 text-sm text-destructive">{copy.block}</p>}
          </>
        )}

        <div className="mt-auto pt-4">
          {error && (
            <div className="mb-3 space-y-1.5">
              <p role="alert" className="text-sm text-destructive">{error.message}</p>
              {error.conflict && (
                <Button variant="outline" size="sm" onClick={() => { setError(null); void plan.refetch() }}>
                  Review the plan again
                </Button>
              )}
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose} disabled={busy}>Cancel</Button>
            {!copy?.block && (
              <Button onClick={() => void download()} disabled={busy || !body}>
                {busy ? <><Spinner className="h-3 w-3" /> Queuing…</> : 'Download'}
              </Button>
            )}
          </div>
        </div>
      </div>
    </Modal>
  )
}
