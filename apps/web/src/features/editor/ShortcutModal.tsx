import { useEffect, useState } from 'react'
import { Button, Modal } from '@/components/ui'
import { cn } from '@/lib/utils'
import {
  DEFAULT_SHORTCUTS, FIXED_SHORTCUTS, MOUSE_SHORTCUTS, SHORTCUT_ACTIONS,
  captureBinding, duplicateIds, keyLabel, saveShortcuts, validateBinding,
  type ShortcutId, type ShortcutMap,
} from './shortcuts'

/** Cheat sheet + per-user remap. Keys are stored in localStorage on Save; a duplicate blocks it. */
export function ShortcutModal({ open, onClose, keys, onSave }: {
  open: boolean
  onClose: () => void
  keys: ShortcutMap
  onSave: (next: ShortcutMap) => void
}) {
  const [draft, setDraft] = useState<ShortcutMap>(keys)
  const [capturing, setCapturing] = useState<ShortcutId | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setCapturing(null)
    setError('')
    if (open) setDraft(keys)
  }, [open, keys])

  // Capture phase on window: it runs before the Modal's own Escape handler, so Esc cancels the
  // recording instead of closing the dialog.
  useEffect(() => {
    if (!capturing) return
    const h = (e: KeyboardEvent) => {
      e.preventDefault()
      e.stopPropagation()
      if (e.key === 'Escape') { setCapturing(null); setError(''); return }
      const binding = captureBinding(e)
      if (!binding) { setError('That key cannot be assigned — pick a letter, a number or Delete.'); return }
      if (/^[1-9]$/.test(binding)) { setError('1–9 are reserved for class hotkeys'); return }
      // A clash is allowed into the draft so the user sees both rows flagged; saving stays blocked.
      const next = { ...draft, [capturing]: binding }
      setDraft(next)
      setCapturing(null)
      setError(validateBinding(binding, next, capturing) ?? '')
    }
    window.addEventListener('keydown', h, true)
    return () => window.removeEventListener('keydown', h, true)
  }, [capturing, draft])

  const duplicates = duplicateIds(draft)
  const changed = SHORTCUT_ACTIONS.some((a) => draft[a.id] !== keys[a.id])
  const reset = () => { setDraft({ ...DEFAULT_SHORTCUTS }); setCapturing(null); setError('') }
  const commit = () => {
    if (!changed) { onClose(); return }
    const storage = typeof window === 'undefined' ? null : window.localStorage
    if (saveShortcuts(draft, storage)) { onSave(draft); onClose() } else {
      setError('Two actions share a key — give each one its own before saving.')
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Keyboard shortcuts" wide>
      <p className="-mt-2 pb-3 text-sm text-muted-foreground">
        Click Change, then press the key you want. Enter, Esc, ? and the arrow keys stay fixed.
      </p>
      <div className="grid grid-cols-1 gap-x-10 gap-y-6 sm:grid-cols-2">
        <section aria-labelledby="shortcut-actions">
          <h3 id="shortcut-actions" className="pb-1 text-xs font-semibold text-muted-foreground">Tools and actions</h3>
          {SHORTCUT_ACTIONS.map((a) => {
            const clash = duplicates.includes(a.id)
            return (
              <div key={a.id} className="flex min-h-9 items-center justify-between gap-3 border-b border-muted py-1.5">
                <span className="min-w-0 text-sm text-muted-foreground">{a.label}</span>
                <span className="flex shrink-0 items-center gap-1.5">
                  {capturing === a.id ? (
                    <span className="rounded border border-primary bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">Press a key…</span>
                  ) : (
                    <kbd aria-invalid={clash || undefined}
                      className={cn('whitespace-nowrap rounded border bg-muted px-2 py-0.5 font-mono text-xs', clash && 'border-destructive text-destructive')}>
                      {keyLabel(draft[a.id])}
                    </kbd>
                  )}
                  <Button size="sm" variant="ghost" className="h-7 min-h-6 px-2 text-xs"
                    aria-label={`Change shortcut for ${a.label}`}
                    onClick={() => { setCapturing(a.id); setError('') }}>
                    Change
                  </Button>
                </span>
              </div>
            )
          })}
          {error && <p role="alert" className="pt-2 text-xs text-destructive">{error}</p>}
        </section>
        <div className="flex flex-col gap-6">
          <section aria-labelledby="shortcut-fixed">
            <h3 id="shortcut-fixed" className="pb-1 text-xs font-semibold text-muted-foreground">Always available</h3>
            {FIXED_SHORTCUTS.map((s) => (
              <div key={s.label} className="flex min-h-9 items-center justify-between gap-3 border-b border-muted py-1.5 text-sm">
                <span className="text-muted-foreground">{s.label}</span>
                <kbd className="whitespace-nowrap rounded border bg-muted px-2 py-0.5 font-mono text-xs">{s.keys}</kbd>
              </div>
            ))}
          </section>
          <section aria-labelledby="shortcut-mouse">
            <h3 id="shortcut-mouse" className="pb-1 text-xs font-semibold text-muted-foreground">Mouse</h3>
            {MOUSE_SHORTCUTS.map((s) => (
              <div key={s.label} className="flex min-h-9 items-center justify-between gap-3 border-b border-muted py-1.5 text-sm">
                <span className="text-muted-foreground">{s.label}</span>
                <kbd className="whitespace-nowrap rounded border bg-muted px-2 py-0.5 font-mono text-xs">{s.keys}</kbd>
              </div>
            ))}
          </section>
        </div>
      </div>
      <div className="mt-5 flex flex-wrap items-center justify-end gap-2 border-t pt-4">
        {duplicates.length > 0 && <p role="status" className="mr-auto text-xs text-destructive">Two actions share a key — saving is blocked.</p>}
        <Button variant="ghost" size="sm" onClick={reset}>Reset to defaults</Button>
        <Button variant="outline" size="sm" onClick={onClose}>Cancel</Button>
        <Button size="sm" onClick={commit} disabled={duplicates.length > 0}>Save shortcuts</Button>
      </div>
    </Modal>
  )
}
