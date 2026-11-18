import { useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import type { ModelItem } from '@/lib/types'
import { pct1 } from '@/lib/format'
import { Button, Card, EmptyState, Field, Input, Select, StatusPill } from '@/components/ui'
import { headlineScore, searchModels } from './modelFinder'

const STATUSES = ['ready', 'training', 'queued', 'failed'] as const
const TASKS = [['detect', 'Detection'], ['segment', 'Segmentation'], ['classify', 'Classification']] as const

/** Find a trained model by name, architecture or class; narrow by status and task; best score first. */
export function ModelSearch({ models, onPick }: { models: ModelItem[]; onPick: (id: string) => void }) {
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const [task, setTask] = useState('')
  const found = useMemo(() => searchModels(models, { q, status, task }), [models, q, status, task])
  const filtered = !!(q || status || task)

  return (
    <div className="space-y-3">
      <Card className="p-4 shadow-none">
        <div className="grid gap-3 sm:grid-cols-[minmax(0,2fr)_1fr_1fr]">
          <Field label="Search models">
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
              <Input className="pl-8" type="search" value={q} onChange={(e) => setQ(e.target.value)}
                placeholder="Name, architecture or class" />
            </div>
          </Field>
          <Field label="Status">
            <Select className="w-full" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All statuses</option>
              {STATUSES.map((s) => <option key={s} value={s}>{s[0].toUpperCase() + s.slice(1)}</option>)}
            </Select>
          </Field>
          <Field label="Task">
            <Select className="w-full" value={task} onChange={(e) => setTask(e.target.value)}>
              <option value="">All tasks</option>
              {TASKS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
            </Select>
          </Field>
        </div>
        <p className="mt-3 text-sm text-muted-foreground" aria-live="polite">
          {found.length} of {models.length} models{filtered ? ' match' : ''}, best score first.
        </p>
      </Card>

      {found.length === 0 ? (
        <EmptyState title="No model matches." hint="Try a shorter search or clear the filters."
          action={filtered && <Button size="sm" variant="outline" onClick={() => { setQ(''); setStatus(''); setTask('') }}>Clear filters</Button>} />
      ) : (
        <Card className="overflow-hidden shadow-none">
          <ul className="divide-y" aria-label="Matching models">
            {found.map((m) => (
              <li key={m.id}>
                <button type="button" onClick={() => onPick(m.id)}
                  className="grid w-full cursor-pointer grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 px-4 py-3 text-left hover:bg-muted/60">
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium">{m.name}</span>
                    <span className="block truncate text-sm text-muted-foreground">
                      {m.arch} · v{m.version ?? '—'} · {m.classes.length} classes
                    </span>
                  </span>
                  <span className="flex items-center gap-3">
                    <span className="text-right">
                      <span className="block text-sm font-semibold tabular-nums">{pct1(headlineScore(m))}</span>
                      <span className="block text-xs text-muted-foreground">{m.task === 'classify' ? 'top-1' : 'mAP@50'}</span>
                    </span>
                    <StatusPill status={m.status} />
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}
