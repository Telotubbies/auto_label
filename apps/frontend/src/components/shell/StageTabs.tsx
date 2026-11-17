import { Suspense, useRef, type KeyboardEvent, type ReactNode } from 'react'
import { Navigate, useParams, useSearchParams } from 'react-router-dom'
import { Card, Spinner } from '@/components/ui'
import { useFlag, useWorkspaceFlags } from '@/lib/flags'
import { useProjectPermissions } from '@/lib/perms'
import { cn } from '@/lib/utils'
import { resolveTab, tabsFor } from '@/lib/nav/project/stages.ts'

const ROW_LABELS: Record<string, string> = { dataset: 'Dataset sections', deploy: 'Deploy sections' }

/**
 * The accessible tab row for a stage. It reads and writes `?tab=` with `replace`, so a refresh and a
 * pasted link land on the same sub-surface, and navigating back leaves the stage in one step.
 */
export default function StageTabs({ stage, children }: { stage: 'dataset' | 'deploy'; children: ReactNode }) {
  const { ws = '', project = '' } = useParams()
  const [sp, setSp] = useSearchParams()
  const { can, ready } = useProjectPermissions(ws, project)
  const flags = useWorkspaceFlags()
  const enabled = flags.data ? new Set(flags.data.enabled) : undefined
  // Permissions may still be loading: the row paints unfiltered and every child keeps its own gate.
  const tabs = tabsFor(stage, ready ? can : () => true, enabled)
  const active = resolveTab(stage, sp.get('tab'))
  const buttons = useRef<Record<string, HTMLButtonElement | null>>({})
  // A URL may name a tab this role cannot open; the row omits it, but one tab stays reachable.
  const selected = tabs.some((tab) => tab.id === active) ? active : tabs[0]?.id

  // No tab this member can open: the stage collapses to the child's own gate, not an empty row.
  if (!tabs.length) return <>{children}</>

  const pick = (id: string) => {
    const next = new URLSearchParams(sp)
    next.set('tab', id)
    setSp(next, { replace: true })
    buttons.current[id]?.focus()
  }

  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
    if (!step) return
    event.preventDefault()
    pick(tabs[(index + step + tabs.length) % tabs.length].id)
  }

  return (
    <>
      <Card className="mx-8 mt-4 overflow-x-auto">
        <div role="tablist" aria-label={ROW_LABELS[stage]} className="flex gap-1 border-b px-2">
          {tabs.map((tab, index) => (
            <button key={tab.id} type="button" role="tab" id={`stage-tab-${stage}-${tab.id}`}
              aria-selected={tab.id === active} aria-controls={`stage-panel-${stage}`}
              tabIndex={tab.id === selected ? 0 : -1}
              ref={(el) => { buttons.current[tab.id] = el }}
              onClick={() => pick(tab.id)} onKeyDown={(e) => onKeyDown(e, index)}
              className={cn('-mb-px cursor-pointer border-b-2 px-3 py-2 text-sm transition-colors',
                tab.id === active
                  ? 'border-primary bg-accent font-medium text-accent-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground')}>
              {tab.label}
            </button>
          ))}
        </div>
      </Card>
      <div role="tabpanel" id={`stage-panel-${stage}`} aria-labelledby={`stage-tab-${stage}-${selected}`}>
        {/* A lazy child may suspend; the row above it stays painted. */}
        <Suspense fallback={<div className="flex h-48 items-center justify-center"><Spinner /></div>}>
          {children}
        </Suspense>
      </div>
    </>
  )
}

/** A legacy sibling URL redirects into its tab while the v3 shell is on; flag off keeps today's page. */
export function LegacyTabRedirect({ to, children }: { to: string; children: ReactNode }) {
  return useFlag('task_470') ? <Navigate replace to={to} /> : <>{children}</>
}
