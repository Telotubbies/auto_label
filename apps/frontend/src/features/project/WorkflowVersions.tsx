import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { History, RotateCcw } from 'lucide-react'
import { api } from '@/lib/api'
import type { Workflow } from '@/lib/types'
import { Button, EmptyState, Spinner, fmtAgo, toast } from '@/components/ui'

export function WorkflowVersions({ ws, project, workflow, onRestored }: {
  ws: string; project: string; workflow: Workflow; onRestored: (w: Workflow) => void
}) {
  const qc = useQueryClient()
  const [busy, setBusy] = useState<number | null>(null)
  const q = useQuery({
    queryKey: ['workflow-versions', ws, project, workflow.id],
    queryFn: () => api.workflowVersions(ws, project, workflow.id),
  })
  const restore = async (version: number) => {
    setBusy(version)
    try {
      const w = await api.restoreWorkflow(ws, project, workflow.id, version)
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['workflows', ws, project] }),
        qc.invalidateQueries({ queryKey: ['workflow-versions', ws, project, workflow.id] }),
      ])
      onRestored(w)
      toast.ok(`Restored version ${version}`)
    } catch (e) { toast.err(e as Error) } finally { setBusy(null) }
  }
  return (
    <section aria-labelledby="workflow-versions" className="rounded-xl border bg-card">
      <div className="flex items-center gap-2 border-b px-3 py-2">
        <History className="h-4 w-4 text-muted-foreground" aria-hidden />
        <h2 id="workflow-versions" className="text-sm font-medium">Versions</h2>
        <span className="ml-auto text-xs text-muted-foreground">current v{workflow.version}</span>
      </div>
      {q.isLoading && <div className="flex justify-center p-4"><Spinner /></div>}
      {q.isError && <p className="p-3 text-sm text-destructive">{(q.error as Error).message}</p>}
      {q.data?.length === 0 && <EmptyState title="No versions yet" hint="Save the workflow once." />}
      <ul className="divide-y">
        {(q.data ?? []).map((v) => (
          <li key={v.id} className="flex items-center gap-2 px-3 py-2 text-sm">
            <span className="font-medium tabular-nums">v{v.number}</span>
            <span className="min-w-0 flex-1 truncate text-muted-foreground">{v.note || v.name}</span>
            <time className="shrink-0 text-xs text-muted-foreground" dateTime={new Date(v.created * 1000).toISOString()}>{fmtAgo(v.created)}</time>
            <Button variant="ghost" size="sm" disabled={busy !== null}
              onClick={() => restore(v.number)} aria-label={`Restore version ${v.number}`}>
              <RotateCcw className="h-3.5 w-3.5" /> Restore
            </Button>
          </li>
        ))}
      </ul>
    </section>
  )
}
