import type { ReactNode } from 'react'
import { Spinner } from '@/components/ui'

export const pct = (v?: number | null) => (v == null ? '—' : `${Math.round(v * 100)}%`)
export const roleLabel = (r: string) => r.charAt(0).toUpperCase() + r.slice(1)

export function Loading() {
  return <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground"><Spinner /> Loading…</div>
}

export function ErrorNote({ error }: { error: unknown }) {
  return (
    <div role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
      {(error as Error)?.message || 'Could not load this section.'}
    </div>
  )
}

export function SectionTitle({ id, title, desc, children }: { id?: string; title: string; desc?: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-2">
      <div>
        <h2 id={id} className="text-lg font-semibold tracking-tight">{title}</h2>
        {desc && <p className="mt-0.5 text-sm text-muted-foreground">{desc}</p>}
      </div>
      {children}
    </div>
  )
}
