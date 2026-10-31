import { cn } from '@/lib/utils'
import { X } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'

export function Button({ variant = 'primary', size = 'md', className, ...props }: {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'destructive' | 'upgrade'
  size?: 'sm' | 'md' | 'icon'
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors focus-visible:outline-none disabled:opacity-50 disabled:pointer-events-none cursor-pointer',
        variant === 'primary' && 'bg-primary text-primary-foreground hover:bg-primary/90',
        variant === 'secondary' && 'bg-secondary text-secondary-foreground hover:bg-secondary/70',
        variant === 'outline' && 'border border-input bg-card hover:bg-accent hover:text-accent-foreground',
        variant === 'ghost' && 'hover:bg-accent hover:text-accent-foreground',
        variant === 'destructive' && 'bg-destructive text-destructive-foreground hover:bg-destructive/90',
        variant === 'upgrade' && 'bg-upgrade text-black hover:bg-upgrade/90',
        size === 'sm' && 'h-8 px-3 text-xs',
        size === 'md' && 'h-9 px-4 text-sm',
        size === 'icon' && 'h-9 w-9',
        className,
      )}
      {...props}
    />
  )
}

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn('h-9 w-full rounded-md border border-input bg-card px-3 text-sm outline-none focus:ring-2 focus:ring-ring/30 focus:border-ring placeholder:text-muted-foreground', className)} {...props} />
}

export function Badge({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) {
  return <span className={cn('inline-flex items-center gap-1 rounded-md bg-secondary px-2 py-0.5 text-[11px] font-medium text-secondary-foreground', className)} {...props} />
}

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('rounded-lg border bg-card text-card-foreground shadow-sm transition-shadow', className)} {...props} />
}

export function Switch({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)}
      className={cn('relative h-5 w-9 rounded-full transition-colors cursor-pointer', checked ? 'bg-primary' : 'bg-input')}>
      <span className={cn('absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform', checked && 'translate-x-4')} />
    </button>
  )
}

export function Tabs({ tabs, active, onChange }: { tabs: { id: string; label: ReactNode }[]; active: string; onChange: (id: string) => void }) {
  return (
    <div className="flex border-b">
      {tabs.map((t) => (
        <button key={t.id} onClick={() => onChange(t.id)}
          className={cn('flex items-end gap-1.5 border-b-2 px-3 py-2 text-sm transition-colors cursor-pointer',
            active === t.id ? 'border-primary font-medium text-primary' : 'border-transparent text-muted-foreground hover:text-foreground')}>
          {t.label}
        </button>
      ))}
    </div>
  )
}

export function Dropdown({ trigger, items, align = 'left' }: {
  trigger: ReactNode
  items: { label: ReactNode; onClick?: () => void; danger?: boolean; divider?: boolean }[]
  align?: 'left' | 'right'
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const h = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  return (
    <div ref={ref} className="relative">
      <div onClick={() => setOpen(!open)}>{trigger}</div>
      {open && (
        <div className={cn('anim-pop absolute z-50 mt-1 min-w-44 rounded-md border bg-popover py-1 shadow-lg', align === 'right' ? 'right-0' : 'left-0')}>
          {items.map((it, i) => it.divider ? <div key={i} className="my-1 border-t" /> : (
            <button key={i} onClick={() => { it.onClick?.(); setOpen(false) }}
              className={cn('flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-accent cursor-pointer', it.danger && 'text-destructive')}>
              {it.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title?: ReactNode; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])
  if (!open) return null
  return (
    <div className="anim-overlay fixed inset-0 z-[100] flex items-start justify-center overflow-y-auto bg-black/40" onMouseDown={onClose}>
      <div className={cn('anim-modal relative my-8 w-full rounded-xl bg-card shadow-2xl', wide ? 'max-w-5xl' : 'max-w-lg')} onMouseDown={(e) => e.stopPropagation()}>
        <button onClick={onClose} className="absolute right-4 top-4 rounded-md p-1 text-muted-foreground hover:bg-accent cursor-pointer"><X className="h-5 w-5" /></button>
        {title && <div className="px-6 pt-5 text-xl font-semibold">{title}</div>}
        <div className="p-6">{children}</div>
      </div>
    </div>
  )
}

export function Kebab({ items }: { items: { label: ReactNode; onClick?: () => void; danger?: boolean }[] }) {
  return <Dropdown align="right" trigger={<Button variant="ghost" size="icon" className="h-7 w-7"><span className="text-lg leading-none">⋮</span></Button>} items={items} />
}

export function EmptyState({ icon, title, hint, action }: { icon?: ReactNode; title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="flex h-full min-h-40 flex-col items-center justify-center gap-2 text-center">
      {icon}
      <p className="text-sm text-muted-foreground">{title}</p>
      {hint && <p className="max-w-xs text-xs text-muted-foreground/70">{hint}</p>}
      {action}
    </div>
  )
}

export function Select({ className, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cn('h-9 rounded-md border border-input bg-card px-2 text-sm outline-none focus:ring-2 focus:ring-ring/30', className)} {...props} />
}

export function Field({ label, hint, children }: { label: ReactNode; hint?: ReactNode; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-muted-foreground">{hint}</span>}
    </label>
  )
}

export function Spinner({ className }: { className?: string }) {
  return <span className={cn('inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent', className)} />
}

export function Progress({ value, className }: { value: number; className?: string }) {
  return (
    <div className={cn('h-1.5 w-full overflow-hidden rounded-full bg-muted', className)}>
      <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  )
}

export function PageHeader({ title, desc, actions }: { title: ReactNode; desc?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 px-8 pb-4 pt-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {desc && <p className="mt-1 text-sm text-muted-foreground">{desc}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}

export function Stat({ label, value, sub }: { label: ReactNode; value: ReactNode; sub?: ReactNode }) {
  return (
    <Card className="p-4">
      <div className="text-xs font-medium text-muted-foreground">{label}</div>
      <div className="mt-1 text-2xl font-bold tracking-tight">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-muted-foreground">{sub}</div>}
    </Card>
  )
}

export function StatusPill({ status }: { status: string }) {
  const tone: Record<string, string> = {
    done: 'bg-green-100 text-green-800', ready: 'bg-green-100 text-green-800', approved: 'bg-green-100 text-green-800',
    running: 'bg-blue-100 text-blue-800', training: 'bg-blue-100 text-blue-800', generating: 'bg-blue-100 text-blue-800',
    queued: 'bg-amber-100 text-amber-800', cancelling: 'bg-amber-100 text-amber-800',
    failed: 'bg-red-100 text-red-800', rejected: 'bg-red-100 text-red-800', cancelled: 'bg-gray-100 text-gray-700',
  }
  return <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold capitalize', tone[status] ?? 'bg-secondary text-secondary-foreground')}>{status}</span>
}

// --- toasts ------------------------------------------------------------------
type Toast = { id: number; text: ReactNode; tone: 'ok' | 'err' }
let pushToast: (t: Omit<Toast, 'id'>) => void = () => {}
export const toast = {
  ok: (text: ReactNode) => pushToast({ text, tone: 'ok' }),
  err: (text: ReactNode | Error) => pushToast({ text: text instanceof Error ? text.message : (text as ReactNode), tone: 'err' }),
}
export function Toaster() {
  const [items, setItems] = useState<Toast[]>([])
  useEffect(() => {
    pushToast = (t) => {
      const id = Date.now() + Math.random()
      setItems((s) => [...s, { ...t, id }])
      setTimeout(() => setItems((s) => s.filter((x) => x.id !== id)), 4500)
    }
  }, [])
  return (
    <div className="fixed bottom-4 right-4 z-[200] flex flex-col gap-2">
      {items.map((t) => (
        <div key={t.id} className={cn('anim-toast max-w-sm rounded-lg border px-4 py-3 text-sm shadow-lg', t.tone === 'ok' ? 'bg-card' : 'border-destructive/40 bg-red-50 text-red-900')}>{t.text}</div>
      ))}
    </div>
  )
}

export const fmtDate = (t: number) => new Date(t * 1000).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
export const fmtAgo = (t: number) => {
  const s = Date.now() / 1000 - t
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  return `${Math.floor(s / 86400)} days ago`
}
