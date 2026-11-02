import { useEffect, useRef } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { ChevronDown, ChevronUp, ChevronsDown, ChevronsUp, Eye, EyeOff, Lock, Unlock, X } from 'lucide-react'
import type { Annotation, LabelClass } from '@/lib/types'
import { cn } from '@/lib/utils'
import { canMove, ORDER_ACTIONS, orderIndexOf, type OrderAction } from './annotationOrder'
import { SourceChip } from './Panels'

const ORDER_LABEL: Record<OrderAction, string> = {
  front: 'To front', forward: 'Forward', backward: 'Backward', back: 'To back',
}
const ORDER_ICON = { front: ChevronsUp, forward: ChevronUp, backward: ChevronDown, back: ChevronsDown }

/**
 * The Objects tab rows. The annotation array is the paint order, so the list shows the front-most
 * annotation first (like a layers panel) and badges each row with its 1-based stack position.
 * Rows are virtualized: a 1,000-object image keeps ~20 rows and their buttons in the DOM.
 */
export function ObjectRows({
  rows, total, classOf, selId, hidden, locked, onSelect, onHide, onLock, onDelete,
}: {
  /** Front-most first. */
  rows: Annotation[]
  total: number
  classOf: (classId: string) => LabelClass
  selId: string | null
  hidden: Set<string>
  locked: Set<string>
  onSelect: (id: string) => void
  onHide: (id: string) => void
  onLock: (id: string) => void
  onDelete: (id: string) => void
}) {
  const parentRef = useRef<HTMLDivElement>(null)
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 32,
    overscan: 6,
    getItemKey: (index) => rows[index].id,
  })
  const selectedRow = selId ? rows.findIndex((a) => a.id === selId) : -1
  // Canvas clicks can select an object that the list has scrolled away from.
  useEffect(() => {
    if (selectedRow >= 0) virtualizer.scrollToIndex(selectedRow, { align: 'auto' })
  }, [selectedRow, virtualizer])

  /**
   * Keyboard navigation is owned by the scroll container, which never unmounts. Deriving the next
   * index from the *current selection* (not from the row that holds focus) is what makes repeated
   * Arrow presses walk the list; focusing the container keeps focus alive when a row scrolls out
   * of the virtual window. A polite live region announces the new selection because the action
   * buttons inside each row make a strict listbox/option structure invalid.
   */
  const onListKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (!rows.length) return
    const current = selId ? rows.findIndex((a) => a.id === selId) : -1
    let next: number
    if (e.key === 'ArrowDown') next = Math.min(rows.length - 1, current + 1)
    else if (e.key === 'ArrowUp') next = Math.max(0, current - 1)
    else if (e.key === 'Home') next = 0
    else if (e.key === 'End') next = rows.length - 1
    else return
    e.preventDefault()
    parentRef.current?.focus()
    onSelect(rows[next].id)
    virtualizer.scrollToIndex(next, { align: 'auto' })
  }

  return (
    <div ref={parentRef} data-testid="object-list" role="group" aria-label="Objects, front-most first"
      tabIndex={0} onKeyDown={onListKeyDown}
      className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-2">
      <p aria-live="polite" className="sr-only">
        {selectedRow >= 0 ? `Selected ${classOf(rows[selectedRow].classId).name}, stack position ${total - selectedRow} of ${total}` : ''}
      </p>
      <div className="relative w-full" style={{ height: virtualizer.getTotalSize() }}>
        {virtualizer.getVirtualItems().map((v) => {
          const a = rows[v.index]
          const c = classOf(a.classId)
          const isHidden = hidden.has(a.id)
          const isLocked = locked.has(a.id)
          const z = total - v.index
          return (
            <div key={a.id} data-testid="object-row" data-object-id={a.id} data-z={z}
              className="absolute left-0 top-0 w-full" style={{ height: v.size, transform: `translateY(${v.start}px)` }}>
              <div onClick={() => { parentRef.current?.focus(); onSelect(a.id) }}
                className={cn('flex h-8 cursor-pointer items-center gap-0.5 rounded px-1 text-sm',
                  selId === a.id ? 'bg-accent text-accent-foreground' : 'hover:bg-muted')}>
                <span className="w-7 shrink-0 pr-1 text-right font-mono text-[10px] tabular-nums text-muted-foreground"
                  title="Stack position — the highest number draws on top">{z}</span>
                <button type="button" data-testid="object-select" aria-current={selId === a.id || undefined}
                  onClick={(e) => { e.stopPropagation(); parentRef.current?.focus(); onSelect(a.id) }}
                  className="flex min-w-0 flex-1 cursor-pointer items-center gap-1.5 text-left">
                  <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: c.color }} aria-hidden />
                  <span className={cn('min-w-0 flex-1 truncate', isHidden && 'text-muted-foreground line-through')}>{c.name}</span>
                  <SourceChip source={a.source} confidence={a.confidence} kind={a.shape.kind === 'class' ? 'label' : a.shape.kind} />
                  <span className="sr-only">, stack position {z} of {total}. Select this object.</span>
                </button>
                <button type="button" aria-pressed={isHidden} aria-label={`${isHidden ? 'Show' : 'Hide'} ${c.name}`} data-testid="object-hide"
                  onClick={(e) => { e.stopPropagation(); onHide(a.id) }}
                  className="flex h-6 w-6 shrink-0 cursor-pointer items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground">
                  {isHidden ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                </button>
                <button type="button" aria-pressed={isLocked} aria-label={`${isLocked ? 'Unlock' : 'Lock'} ${c.name}`} data-testid="object-lock"
                  onClick={(e) => { e.stopPropagation(); onLock(a.id) }}
                  className="flex h-6 w-6 shrink-0 cursor-pointer items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground">
                  {isLocked ? <Lock className="h-3.5 w-3.5" /> : <Unlock className="h-3.5 w-3.5" />}
                </button>
                <button type="button" aria-label={`Delete ${c.name}`} data-testid="object-delete"
                  onClick={(e) => { e.stopPropagation(); onDelete(a.id) }}
                  className="flex h-6 w-6 shrink-0 cursor-pointer items-center justify-center rounded text-muted-foreground hover:text-destructive">
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/** Stack controls for the selected annotation; disabled at the ends of the stack. */
export function OrderControls({ list, id, onMove }: {
  list: Annotation[]
  id: string
  onMove: (action: OrderAction) => void
}) {
  const position = orderIndexOf(list, id)
  if (position === null) return null
  return (
    <section aria-label="Stack order" className="mt-2 rounded-lg border bg-card p-2">
      <div className="flex items-baseline justify-between pb-1.5">
        <h3 className="text-[11px] font-semibold">Stack order</h3>
        <span data-testid="order-position" className="text-[10px] tabular-nums text-muted-foreground">
          {position} of {list.length} · top is front
        </span>
      </div>
      <div className="grid grid-cols-2 gap-1.5">
        {ORDER_ACTIONS.map((action) => {
          const Icon = ORDER_ICON[action]
          const label = ORDER_LABEL[action]
          return (
            <button key={action} type="button" data-testid={`order-${action}`} aria-label={label}
              disabled={!canMove(list, id, action)} onClick={() => onMove(action)}
              className="flex h-7 min-h-6 cursor-pointer items-center gap-1.5 rounded-md border border-input bg-card px-2 text-[11px] font-medium hover:bg-accent hover:text-accent-foreground disabled:cursor-not-allowed disabled:opacity-50">
              <Icon className="h-3.5 w-3.5" aria-hidden /> {label}
            </button>
          )
        })}
      </div>
    </section>
  )
}
