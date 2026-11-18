import { useState, type ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

/** U+00B7 as an escape: `tests/nav.test.mjs` forbids the character itself in the shell. */
export const SEP = '\u00B7'

/**
 * One collapsible purpose group. The header is a sentence-case 12 px button; collapsing hides the
 * list but keeps its rows mounted, so the destinations stay in the DOM behind `aria-controls`. A
 * group that holds the current route cannot be collapsed shut: the page must never become
 * invisible. While collapsed the header keeps the group's summary, so an alert never hides.
 */
export function RailGroup({ id, label, summary, holdsActive, children }: {
  id: string
  label: string
  summary: string | null
  holdsActive: boolean
  children: ReactNode
}) {
  const [open, setOpen] = useState(true)
  const listId = `rail-group-${id}`
  const expanded = open || holdsActive
  return (
    <div className="mt-4 first:mt-1">
      <button type="button" aria-expanded={expanded} aria-controls={listId} onClick={() => setOpen(!open)}
        className="flex w-full cursor-pointer items-center gap-1.5 rounded px-2 pb-1.5 text-sm font-semibold text-foreground hover:text-primary">
        <span>{label}</span>
        {!expanded && summary && <span className="font-normal text-muted-foreground">{`${SEP} ${summary}`}</span>}
        <ChevronDown className={cn('ml-auto h-4 w-4 text-muted-foreground transition-transform', !expanded && '-rotate-90')} aria-hidden />
      </button>
      <ul id={listId} hidden={!expanded} className="space-y-0.5">{children}</ul>
    </div>
  )
}
