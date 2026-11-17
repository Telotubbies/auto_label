import { Link } from 'react-router-dom'
import { Lock } from 'lucide-react'
import { Card } from '@/components/ui'
import { projectPath } from '@/lib/routes'
import { cn } from '@/lib/utils'
import type { StageCardView, StageState } from './overviewModel'

/** The shipped status idiom (`StatusPill`), so a state never brings its own colour. */
const CHIP: Record<StageState, string> = {
  done: 'bg-success/15 text-success',
  'needs-you': 'bg-info/15 text-info',
  blocked: 'bg-destructive/15 text-destructive',
  'not-started': 'bg-secondary text-secondary-foreground',
  unknown: 'bg-warning/15 text-warning',
}

const DOT: Record<StageState, string> = {
  done: 'bg-success',
  'needs-you': 'bg-info',
  blocked: 'bg-destructive',
  'not-started': 'bg-muted-foreground',
  unknown: 'bg-warning',
}

/**
 * One pipeline card: number, state chip, title, one sentence, the count and exactly one action.
 * The action is a link (or Retry), never a primary button: the header owns the screen's one primary.
 */
export function StageCard({ stage, ws, project, onRetry }: {
  stage: StageCardView
  ws: string
  project: string
  onRetry: () => void
}) {
  const to = stage.to ? projectPath(ws, project, stage.to) : null
  return (
    <li className="h-full">
      <Card className={cn('flex h-full min-h-[168px] flex-col p-4', stage.locked && 'opacity-60')}>
        <div className="flex items-center justify-between gap-2">
          <span aria-hidden className="flex h-6 w-6 items-center justify-center rounded-full bg-secondary text-xs font-semibold tabular-nums">
            {stage.number}
          </span>
          <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', CHIP[stage.state])}>{stage.chip}</span>
        </div>
        <h2 className="mt-2 flex items-center gap-1.5 text-sm font-semibold">
          <span aria-hidden className={cn('h-2 w-2 shrink-0 rounded-full', DOT[stage.state])} />
          {stage.title}
          {stage.locked && <Lock className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">{stage.sentence}</p>
        <div className="mt-auto flex items-center justify-between gap-2 pt-2">
          <span className="text-sm font-semibold tabular-nums">{stage.count}</span>
          {stage.action === 'retry' ? (
            <button type="button" onClick={onRetry} className="inline-flex min-h-6 items-center text-sm font-medium text-primary hover:underline">{stage.actionLabel}</button>
          ) : to ? (
            <Link to={to} className="inline-flex min-h-6 items-center text-sm font-medium text-primary hover:underline">{stage.actionLabel}</Link>
          ) : (
            <span className="text-sm text-muted-foreground">{stage.actionLabel}</span>
          )}
        </div>
      </Card>
    </li>
  )
}
