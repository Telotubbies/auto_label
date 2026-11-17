import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ListChecks } from 'lucide-react'
import { api } from '@/lib/api'
import { useFlag } from '@/lib/flags'
import { activeCount, isActive } from '@/lib/jobs'
import { JobPanel } from './JobTray'

/** The top bar's Jobs trigger: active count, a dot for a result the panel has not shown, and the panel. */
export function JobButton() {
  const on = useFlag('task_470')
  const { ws = '' } = useParams()
  const buttonRef = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)
  const [dot, setDot] = useState(false)
  const doneIds = useRef<Set<string> | null>(null)
  const q = useQuery({
    queryKey: ['ws-jobs', ws], enabled: on && !!ws, retry: false,
    queryFn: () => api.jobsList(ws),
    refetchInterval: (query) => ((query.state.data ?? []).some(isActive) ? 2500 : 15_000),
  })
  const jobs = q.data ?? []
  // The first list is history, not news: only a job that finishes while the shell is open sets the dot.
  useEffect(() => {
    if (!q.data) return
    const done = q.data.filter((j) => !isActive(j)).map((j) => j.id)
    if (doneIds.current === null) { doneIds.current = new Set(done); return }
    if (done.some((id) => !doneIds.current!.has(id))) setDot(true)
    for (const id of done) doneIds.current.add(id)
  }, [q.data])
  if (!on) return null
  const active = activeCount(jobs)
  return (
    <>
      <button ref={buttonRef} type="button" onClick={() => { setOpen((o) => !o); setDot(false) }}
        aria-expanded={open} aria-controls="job-panel"
        className="relative flex h-8 cursor-pointer items-center gap-1.5 rounded-full px-2.5 text-sm hover:bg-accent hover:text-accent-foreground">
        <ListChecks className="h-4 w-4" aria-hidden />
        <span className="sr-only sm:not-sr-only">Jobs</span>
        {active > 0 && <span className="min-w-4 rounded-full bg-primary px-1 text-center text-xs font-semibold tabular-nums text-primary-foreground">{active}</span>}
        {dot && <span className="sr-only">new result</span>}
        {dot && <span aria-hidden className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-primary" />}
      </button>
      <JobPanel open={open} onClose={() => setOpen(false)} triggerRef={buttonRef} />
    </>
  )
}
