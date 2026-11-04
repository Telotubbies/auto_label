import { Badge } from '@/components/ui'
import type { PlaygroundRuntime, PlaygroundRuntimeState } from '@/lib/types'
import { cn } from '@/lib/utils'

const TONE: Record<PlaygroundRuntimeState, string> = {
  ready: 'bg-success/10 text-success',
  cold: 'bg-muted text-muted-foreground',
  loading: 'bg-info/10 text-info',
  sleeping: 'bg-warning/10 text-warning',
  gpu_busy: 'bg-warning/10 text-warning',
  unavailable: 'bg-destructive/10 text-destructive',
}

const LABEL: Record<PlaygroundRuntimeState, string> = {
  ready: 'Ready',
  cold: 'Cold start',
  loading: 'Loading',
  sleeping: 'Asleep',
  gpu_busy: 'GPU busy',
  unavailable: 'Unavailable',
}

/** One badge and one reason per selected model. The server decides the state; this only renders it. */
export function RuntimeStates({ states }: { states: (PlaygroundRuntime & { name: string })[] }) {
  return (
    <ul aria-label="Model status" aria-live="polite" className="space-y-1.5">
      {states.map((s) => (
        <li key={s.ref} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-xs">
          <Badge className={cn('shrink-0', TONE[s.state])}>{LABEL[s.state]}</Badge>
          <span className="min-w-0 flex-1 truncate font-medium" title={s.name}>{s.name}</span>
          <span className="w-full text-muted-foreground">{s.message}</span>
        </li>
      ))}
    </ul>
  )
}
