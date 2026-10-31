import { useState } from 'react'
import type { Annotation, LabelClass } from '@/lib/types'
import { Badge, Button, Input } from '@/components/ui'
import { cn } from '@/lib/utils'
import { Check, Copy, Send } from 'lucide-react'

export interface EditorComment {
  id: string
  author: string
  text: string
  at: number
}

export interface LogEntry {
  id: string
  action: string
  detail?: string
  at: number
}

export const ATTRIBUTE_KEYS = ['occluded', 'truncated', 'difficult', 'crowd'] as const

const fmtTime = (t: number) =>
  new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })

function PanelHeader({ title, count, children }: { title: string; count?: number; children?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between px-4 pt-4">
      <h3 className="text-sm font-semibold">
        {title} {typeof count === 'number' && <Badge>{count}</Badge>}
      </h3>
      {children}
    </div>
  )
}

/** Per-annotation attribute checkboxes for the selected annotation. */
export function AttributesPanel({
  anns,
  selId,
  onSelect,
  classOf,
  values,
  onToggle,
}: {
  anns: Annotation[]
  selId: string | null
  onSelect: (id: string) => void
  classOf: (classId: string) => LabelClass
  values: Record<string, boolean>
  onToggle: (key: string) => void
}) {
  const sel = anns.find((a) => a.id === selId) ?? null
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <PanelHeader title="Attributes" count={anns.length} />
      <div className="flex-1 overflow-y-auto px-4 pb-4">
        <div className="pt-3">
          {anns.length === 0 && (
            <p className="text-xs text-muted-foreground">No annotations yet. Draw one on the canvas to attach attributes.</p>
          )}
          {anns.map((a) => {
            const c = classOf(a.classId)
            return (
              <button
                key={a.id}
                onClick={() => onSelect(a.id)}
                className={cn(
                  'flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm cursor-pointer',
                  a.id === selId ? 'bg-accent text-accent-foreground' : 'hover:bg-muted',
                )}
              >
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: c.color }} />
                <span className="capitalize">{c.name}</span>
                <span className="text-xs text-muted-foreground">{a.shape.kind}</span>
                <span className="ml-auto font-mono text-[10px] text-muted-foreground">{a.id}</span>
              </button>
            )
          })}
        </div>
        {sel ? (
          <div className="mt-4 rounded-lg border p-3">
            <div className="mb-2 text-xs font-medium text-muted-foreground">
              Attributes for <span className="font-mono">{sel.id}</span>
            </div>
            {ATTRIBUTE_KEYS.map((k) => (
              <label key={k} className="flex cursor-pointer items-center gap-2 rounded px-1 py-1.5 text-sm hover:bg-muted">
                <input
                  type="checkbox"
                  className="h-3.5 w-3.5 accent-violet-600"
                  checked={!!values[k]}
                  onChange={() => onToggle(k)}
                />
                <span className="capitalize">{k}</span>
              </label>
            ))}
          </div>
        ) : (
          anns.length > 0 && (
            <p className="pt-3 text-xs text-muted-foreground">Select an annotation above or on the canvas to edit attributes.</p>
          )
        )}
      </div>
    </div>
  )
}

/** Local comment thread for the current image. */
export function CommentsPanel({ comments, onAdd }: { comments: EditorComment[]; onAdd: (text: string) => void }) {
  const [text, setText] = useState('')
  const submit = () => {
    const t = text.trim()
    if (!t) return
    onAdd(t)
    setText('')
  }
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <PanelHeader title="Comments" count={comments.length} />
      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
        {comments.length === 0 && (
          <div className="rounded-lg border border-dashed p-3 text-center text-xs text-muted-foreground">
            No Comments Yet
            <br />
            Start a thread on this image below.
          </div>
        )}
        {comments.map((c) => (
          <div key={c.id} className="rounded-lg border bg-card p-2.5">
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-violet-100 text-[10px] font-semibold text-violet-700">
                {c.author.slice(0, 2).toUpperCase()}
              </span>
              <span className="text-xs font-medium">{c.author}</span>
              <span className="ml-auto text-[10px] text-muted-foreground">{fmtTime(c.at)}</span>
            </div>
            <p className="pt-1.5 text-sm">{c.text}</p>
          </div>
        ))}
      </div>
      <div className="border-t p-3">
        <div className="flex gap-1.5">
          <Input
            placeholder="Write a comment…"
            className="h-8"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') submit()
            }}
          />
          <Button size="sm" className="h-8" onClick={submit}>
            <Send className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  )
}

/** Chronological list of annotation actions derived from the undo history. */
export function HistoryPanel({ log }: { log: LogEntry[] }) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <PanelHeader title="History" count={log.length} />
      <div className="flex-1 overflow-y-auto px-4 py-2">
        {log.length === 0 && (
          <p className="pt-2 text-xs text-muted-foreground">
            No actions yet. Add, edit or delete annotations and they will show up here.
          </p>
        )}
        {[...log].reverse().map((e) => (
          <div key={e.id} className="flex items-center gap-2 border-b border-muted py-2 text-sm">
            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-violet-500" />
            <span className="whitespace-nowrap">{e.action}</span>
            {e.detail && <span className="truncate text-xs text-muted-foreground">{e.detail}</span>}
            <span className="ml-auto whitespace-nowrap text-[10px] text-muted-foreground">{fmtTime(e.at)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

/** Read-only JSON dump of the current image and its annotations. */
export function RawDataPanel({ payload }: { payload: unknown }) {
  const [copied, setCopied] = useState(false)
  const json = JSON.stringify(payload, null, 2)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(json)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard unavailable */
    }
  }
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <PanelHeader title="Raw Data">
        <Button variant="outline" size="sm" className="h-7 text-xs" onClick={copy}>
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? 'Copied' : 'Copy'}
        </Button>
      </PanelHeader>
      <div className="min-h-0 flex-1 p-4">
        <pre className="h-full overflow-auto rounded-lg border bg-muted/50 p-3 font-mono text-[11px] leading-relaxed">
          {json}
        </pre>
      </div>
    </div>
  )
}
