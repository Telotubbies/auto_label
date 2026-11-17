import { useEffect, useRef, useState, type KeyboardEvent, type RefObject } from 'react'
import { Link, useMatch, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { api, post } from '@/lib/api'
import { useFlag } from '@/lib/flags'
import { activeCount, cancelPath, etaLabel, isActive, jobPath, resultLine } from '@/lib/jobs'
import { RESERVED_WORKSPACE_SEGMENTS } from '@/lib/nav'
import { PROJECT_ROUTE_MATCH } from '@/lib/routes'
import type { Job } from '@/lib/types'
import { cn } from '@/lib/utils'
import { Glass } from '../glass'
import { Progress, toast } from '../ui'

/** Elements the panel's Tab trap cycles through, in DOM order. */
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/** Flag-off surface: the bottom-right glass tray that reads the current project's jobs. */
function FloatingTray() {
  const m = useMatch(PROJECT_ROUTE_MATCH)
  const ws = m?.params.ws ?? '', project = m?.params.project ?? ''
  const enabled = !!ws && !!project && !RESERVED_WORKSPACE_SEGMENTS.has(project)
  const seen = useRef(new Map<string, Job>())
  const [dismissed, setDismissed] = useState<Set<string>>(new Set())
  const q = useQuery({
    queryKey: ['jobs-tray', ws, project], enabled, retry: false,
    queryFn: () => api.jobs(ws, project),
    refetchInterval: (query) => ((query.state.data ?? []).some(isActive) ? 2500 : 15_000),
  })
  for (const j of q.data ?? []) if (isActive(j) || seen.current.has(j.id)) seen.current.set(j.id, j)
  const rows = enabled ? [...seen.current.values()].filter((j) => !dismissed.has(j.id) && (q.data ?? []).some((x) => x.id === j.id)) : []
  if (!rows.length) return null
  return (
    <Glass as="section" aria-label="Background jobs" className="fixed bottom-4 right-4 z-[150] w-80 space-y-2.5 rounded-2xl p-3 print:hidden">
      {rows.map((j) => {
        const live = isActive(j)
        return (
          <div key={j.id} className="text-sm">
            <div className="flex items-center gap-2">
              <span className="min-w-0 flex-1 truncate font-medium">{resultLine(j)}</span>
              <span className={cn('text-sm tabular-nums', j.status === 'failed' ? 'text-destructive' : 'text-muted-foreground')}>{live ? `${Math.round(j.progress)}%` : j.status}</span>
              {!live && <button type="button" aria-label="Dismiss" onClick={() => setDismissed((d) => new Set(d).add(j.id))} className="flex h-6 w-6 cursor-pointer items-center justify-center rounded-full hover:bg-accent"><X className="h-3.5 w-3.5" /></button>}
            </div>
            {live && <Progress className="mt-1.5" value={j.progress} />}
            {!live && j.kind === 'autolabel' && j.result?.quota_clamped && (
              <p className="mt-1 text-sm text-muted-foreground">
                Stopped at the AI-call allowance after {j.result.images} of {j.result.selected ?? j.result.images} images.
              </p>
            )}
          </div>
        )
      })}
    </Glass>
  )
}

/** The shell's tray: the legacy floating tray while `ui_v3` is off, nothing while the panel owns it. */
export function JobTray() {
  return useFlag('task_470') ? null : <FloatingTray />
}

/**
 * The workspace panel behind the top bar's Jobs button. One list for every project, kept by the
 * shell so leaving a page never cancels or duplicates a row.
 */
export function JobPanel({ open, onClose, triggerRef }: {
  open: boolean
  onClose: () => void
  triggerRef: RefObject<HTMLButtonElement | null>
}) {
  const { ws = '' } = useParams()
  const panelRef = useRef<HTMLDivElement>(null)
  const [dismissed, setDismissed] = useState<Set<string>>(new Set())
  const seen = useRef(new Set<string>())
  const q = useQuery({
    queryKey: ['ws-jobs', ws], enabled: !!ws, retry: false,
    queryFn: () => api.jobsList(ws),
    refetchInterval: (query) => ((query.state.data ?? []).some(isActive) ? 2500 : 15_000),
  })
  const jobs = q.data ?? []
  // A finished row stays only if this shell watched it run; old history is not the panel's news.
  for (const j of jobs) if (isActive(j)) seen.current.add(j.id)
  const active = activeCount(jobs)
  const rows = jobs.filter((j) => isActive(j) || (seen.current.has(j.id) && !dismissed.has(j.id)))

  const close = () => { onClose(); triggerRef.current?.focus() }
  useEffect(() => {
    if (!open) return
    panelRef.current?.focus()
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node
      if (!panelRef.current?.contains(t) && !triggerRef.current?.contains(t)) close()
    }
    const onKey = (e: globalThis.KeyboardEvent) => { if (e.key === 'Escape') close() }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])
  if (!open) return null

  const onKeyDown = (e: KeyboardEvent<HTMLElement>) => {
    if (e.key !== 'Tab') return
    const nodes = [...e.currentTarget.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((n) => n.getClientRects().length > 0)
    if (!nodes.length) return
    const first = nodes[0], last = nodes[nodes.length - 1]
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
  }
  const now = Math.floor(Date.now() / 1000)
  return (
    <div ref={panelRef} tabIndex={-1} onKeyDown={onKeyDown} className="fixed right-4 top-16 z-[150] w-80 print:hidden">
    <Glass strength="overlay" id="job-panel" role="dialog" aria-modal="false" aria-label="Background jobs"
      className="space-y-2 rounded-2xl p-3 text-popover-foreground shadow-2xl">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Jobs{active > 0 && <span className="ml-1.5 font-normal text-muted-foreground">{active} active</span>}</h2>
        <button type="button" aria-label="Close jobs" onClick={close} className="flex h-6 w-6 cursor-pointer items-center justify-center rounded-full hover:bg-accent">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
      <p className="sr-only" aria-live="polite">{`${active} running, ${rows.length - active} finished`}</p>
      {q.isLoading ? (
        <div aria-busy="true" aria-label="Loading jobs" className="space-y-2">
          {[0, 1, 2].map((i) => <div key={i} className="h-9 animate-pulse rounded-lg bg-muted" />)}
        </div>
      ) : q.isError ? (
        <button type="button" onClick={() => q.refetch()} className="text-sm text-destructive hover:underline">Could not load jobs — retry</button>
      ) : !rows.length ? (
        <p className="text-sm text-muted-foreground">Nothing is running. Uploads, versions, training and exports appear here.</p>
      ) : rows.map((j) => {
        const live = isActive(j)
        return (
          <div key={j.id} className="rounded-lg bg-popover p-2.5 text-sm">
            <div className="flex items-center gap-2">
              <span className="min-w-0 flex-1 truncate font-medium">{resultLine(j)}</span>
              {live && j.project ? (
                <button type="button" onClick={() => post(cancelPath(ws, j)).then(() => q.refetch()).catch(toast.err)}
                  className="cursor-pointer text-sm text-muted-foreground hover:text-foreground">Cancel</button>
              ) : !live ? (
                <button type="button" aria-label={`Dismiss ${resultLine(j)}`} onClick={() => setDismissed((d) => new Set(d).add(j.id))}
                  className="flex h-6 w-6 cursor-pointer items-center justify-center rounded-full hover:bg-accent"><X className="h-3.5 w-3.5" /></button>
              ) : null}
            </div>
            {live ? (
              <>
                <Progress className="mt-1.5" value={j.progress} label={resultLine(j)} />
                <p className="mt-1 text-sm tabular-nums text-muted-foreground">{Math.round(j.progress)}% {'\u00B7'} {etaLabel(j, now)}</p>
              </>
            ) : j.status === 'failed' ? (
              <>
                <p className="mt-1 text-sm text-destructive">Failed — {j.error || 'The job stopped before it finished.'}</p>
                <Link to={jobPath(ws, j)} onClick={close} className="mt-1 inline-block text-sm font-medium text-primary hover:underline">Retry</Link>
              </>
            ) : (
              <p className="mt-1 text-sm text-muted-foreground">{j.status === 'done' ? 'Finished' : 'Cancelled'}</p>
            )}
          </div>
        )
      })}
    </Glass>
    </div>
  )
}
