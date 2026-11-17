import { useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Lock } from 'lucide-react'
import { projectPath } from '@/lib/routes'
import { stageCount, stageLine, stageState, stageWord } from '@/lib/nav/project/stages.ts'
import type { StageId, StageRow, StageStateWord } from '@/lib/nav/project/stages.ts'
import type { StageFacts } from '@/lib/types'
import { cn } from '@/lib/utils'
import { Button, Modal } from '../ui'

/** The shipped roles carry the state; no ring, no second palette. */
const DOT: Record<StageStateWord, string> = {
  done: 'bg-success',
  'needs-you': 'bg-warning',
  blocked: 'bg-destructive',
  running: 'bg-warning',
  'not-started': 'bg-muted-foreground',
  unknown: 'bg-muted-foreground',
}

const ROW = 'group relative flex h-8 items-center gap-2 rounded-md border px-2 text-sm transition-colors'
const PILL = 'shrink-0 rounded-full px-1.5 text-xs tabular-nums'

/**
 * One rail row: its pipeline number (stages only), the label, the count pill, the state word and the
 * state dot. The dot is decoration — the row's own text is the accessible name, in reading order
 * (number, label, state word, count), so the name and the eye never disagree (WCAG 2.5.3) and colour
 * is never the only signal. A locked row is announced by a description, not renamed, and opens the
 * request-access sheet instead of navigating; it is never hidden. The visual height stays 32 px and a
 * `::before` inset lifts the hit area to 44 px (design/labeldesk-v3/REDESIGN.md §13.1).
 */
export function StageItem({ row, facts, ws, slug, active, loading }: {
  row: StageRow
  facts: StageFacts
  ws: string
  slug: string
  active: boolean
  loading: boolean
}) {
  const stage = row.number !== undefined
  const state = stage ? stageState(facts, row.id as StageId) : null
  const count = stageCount(facts, row.id)
  const word = state ? stageWord(state) : ''
  const line = stage ? stageLine(facts, row.id as StageId) : null
  // Only a number the API has not answered for yet is a skeleton; a known count paints at once.
  const pending = loading && count === null
  // A locked row never redirects silently: it opens the sheet that says how to ask for the step.
  const descId = useId()
  const [ask, setAsk] = useState(false)

  // A count that changes while the member works pulses the dot once (opacity only); reduced motion
  // gets the new number with no animation.
  const previous = useRef(count)
  const [pulse, setPulse] = useState(false)
  useEffect(() => {
    if (previous.current === count) return
    previous.current = count
    setPulse(true)
    const timer = setTimeout(() => setPulse(false), 600)
    return () => clearTimeout(timer)
  }, [count])

  const look = cn(
    ROW,
    'before:absolute before:-inset-y-1.5 before:inset-x-0 before:content-[""]',
    active
      ? 'border border-primary bg-accent font-medium text-accent-foreground'
      : 'border border-transparent text-foreground hover:bg-sidebar-accent/60',
  )

  const body = (
    <>
      <span className="w-4 shrink-0 text-xs tabular-nums text-muted-foreground">{row.number}</span>
      <span className="min-w-0 flex-1 truncate">{row.label}</span>
      {word && <span className="shrink-0 text-xs text-muted-foreground">{word}</span>}
      {row.locked && <Lock className="h-3.5 w-3.5 shrink-0" aria-hidden />}
      {state && (
        <span aria-hidden
          className={cn('h-1.5 w-1.5 shrink-0 rounded-full', DOT[state], pulse && 'animate-pulse motion-reduce:animate-none')} />
      )}
      {pending
        ? <span aria-hidden className={cn(PILL, 'h-4 w-6 animate-pulse bg-muted')} />
        : <span className={cn(PILL, 'bg-muted text-muted-foreground')}>{count === null ? '—' : count}</span>}
    </>
  )

  if (row.locked) {
    return (
      <li>
        <button type="button" aria-disabled="true" aria-describedby={descId}
          title={`${row.label}, locked, request access`} onClick={() => setAsk(true)}
          className={cn(look, 'w-full cursor-pointer opacity-60')}>
          {body}
        </button>
        {/* Why the row is dimmed and how to ask for it: a description, so the name stays the row. */}
        <span id={descId} className="sr-only">Locked for your role. Request access from a project manager.</span>
        <Modal open={ask} onClose={() => setAsk(false)} title="Request access">
          <p className="text-sm text-muted-foreground">
            {`${row.label} is locked for your role. Ask a project manager to grant you access.`}
          </p>
          <div className="mt-4 flex justify-end"><Button onClick={() => setAsk(false)}>Close</Button></div>
        </Modal>
      </li>
    )
  }
  return (
    <li>
      <Link to={projectPath(ws, slug, row.to)} aria-current={active ? 'page' : undefined}
        title={line ?? undefined} className={look}>
        {body}
      </Link>
    </li>
  )
}
