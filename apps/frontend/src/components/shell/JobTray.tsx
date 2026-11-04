import { useRef, useState } from 'react'
import { useMatch } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { api } from '@/lib/api'
import { RESERVED_WORKSPACE_SEGMENTS } from '@/lib/nav'
import type { Job } from '@/lib/types'
import { cn } from '@/lib/utils'
import { Glass } from '../glass'
import { Progress } from '../ui'

const JOB_LABEL: Record<Job['kind'] | 'insights_images' | 'insights_leakage' | 'insights_embedding', string> = {
  train: 'Training', autolabel: 'Auto-label', version: 'Version', export: 'Export', export_engine: 'TensorRT export', health: 'Health check',
  insights_images: 'Image stats', insights_leakage: 'Leakage scan', insights_embedding: 'Embedding map',
}
const ACTIVE = new Set<Job['status']>(['queued', 'running', 'cancelling'])

/** Bottom-right glass tray with determinate progress for long jobs, so users can leave the page. Reads the current project's jobs. */
export function JobTray() {
  const m = useMatch('/:ws/:project/*')
  const ws = m?.params.ws ?? '', project = m?.params.project ?? ''
  const enabled = !!ws && !!project && !RESERVED_WORKSPACE_SEGMENTS.has(project)
  const seen = useRef(new Map<string, Job>())
  const [dismissed, setDismissed] = useState<Set<string>>(new Set())
  const q = useQuery({
    queryKey: ['jobs-tray', ws, project], enabled, retry: false,
    queryFn: () => api.jobs(ws, project),
    refetchInterval: (query) => ((query.state.data ?? []).some((j) => ACTIVE.has(j.status)) ? 2500 : 15_000),
  })
  for (const j of q.data ?? []) if (ACTIVE.has(j.status) || seen.current.has(j.id)) seen.current.set(j.id, j)
  const rows = enabled ? [...seen.current.values()].filter((j) => !dismissed.has(j.id) && (q.data ?? []).some((x) => x.id === j.id)) : []
  if (!rows.length) return null
  return (
    <Glass as="section" aria-label="Background jobs" className="fixed bottom-4 right-4 z-[150] w-80 space-y-2.5 rounded-2xl p-3 print:hidden">
      {rows.map((j) => {
        const live = ACTIVE.has(j.status)
        return (
          <div key={j.id} className="text-sm">
            <div className="flex items-center gap-2">
              <span className="min-w-0 flex-1 truncate font-medium">{JOB_LABEL[j.kind]}{j.project_name ? ` · ${j.project_name}` : ''}</span>
              <span className={cn('text-xs tabular-nums', j.status === 'failed' ? 'text-destructive' : 'text-muted-foreground')}>{live ? `${Math.round(j.progress)}%` : j.status}</span>
              {!live && <button type="button" aria-label="Dismiss" onClick={() => setDismissed((d) => new Set(d).add(j.id))} className="flex h-6 w-6 cursor-pointer items-center justify-center rounded-full hover:bg-accent"><X className="h-3.5 w-3.5" /></button>}
            </div>
            {live && <Progress className="mt-1.5" value={j.progress} />}
            {!live && j.kind === 'autolabel' && j.result?.quota_clamped && (
              <p className="mt-1 text-xs text-muted-foreground">
                Stopped at the AI-call allowance after {j.result.images} of {j.result.selected ?? j.result.images} images.
              </p>
            )}
          </div>
        )
      })}
    </Glass>
  )
}
