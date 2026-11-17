/**
 * The engine job's log (T-1009): the last 200 lines in a solid panel, the job id in the footer and
 * one copy action. It shows what the worker wrote and the API redacted; nothing here edits it.
 * The sheet is a full-height overlay, and the log itself stays opaque so the text stays readable.
 */
import { Button, Modal, toast } from '@/components/ui'
import type { InferenceJob } from '@/lib/types'
import { logText, visibleLog } from './engineRows'

export default function JobLogSheet({ job, open, onClose }: {
  job: InferenceJob | null; open: boolean; onClose: () => void
}) {
  if (!job) return null
  const lines = visibleLog(job)
  const engines = job.result?.engines ?? []
  const copy = () => {
    navigator.clipboard?.writeText(logText(job))
      .then(() => toast.ok('Log copied'))
      .catch(() => toast.err('Could not copy the log'))
  }

  return (
    <Modal open={open} onClose={onClose}
      title={job.action === 'uninstall' ? 'Removal log' : 'Install log'}>
      <div className="flex min-h-[calc(100dvh-8rem)] flex-col">
        {!!engines.length && (
          <div className="mb-3">
            <p className="text-xs font-medium text-muted-foreground">
              {job.status === 'failed' ? 'Engines built before it stopped' : 'Engines'}
            </p>
            <ul className="mt-1 space-y-0.5 text-sm">
              {engines.map((engine) => (
                <li key={engine.id}>{engine.id} {engine.version}</li>
              ))}
            </ul>
          </div>
        )}
        {lines.length ? (
          <pre aria-label="Job log"
            className="flex-1 overflow-auto whitespace-pre-wrap rounded-lg border bg-card p-3 font-mono text-xs leading-5">
            {lines.join('\n')}
          </pre>
        ) : (
          <p className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
            Waiting for the worker…
          </p>
        )}
        <div className="mt-auto flex flex-wrap items-center justify-between gap-2 pt-3">
          <p className="text-xs text-muted-foreground">Job <span className="font-mono">{job.id}</span></p>
          <Button variant="outline" size="sm" disabled={!lines.length} onClick={() => void copy()}>
            Copy log
          </Button>
        </div>
      </div>
    </Modal>
  )
}
