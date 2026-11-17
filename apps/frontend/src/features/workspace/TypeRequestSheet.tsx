import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Button, Field, Input, Modal } from '@/components/ui'

const MAX = 300

/**
 * The wish list behind "Need a different type?" (T-017): one required field, one optional example,
 * one audit row on the server. Nothing else changes — the project is not created here.
 */
export function TypeRequestSheet({ open, onClose, ws }: { open: boolean; onClose: () => void; ws: string }) {
  const [wanted, setWanted] = useState('')
  const [example, setExample] = useState('')
  const [state, setState] = useState<'idle' | 'busy' | 'sent' | 'error'>('idle')

  // Reopening starts a fresh request; the draft is not worth keeping across dialogs.
  useEffect(() => {
    if (open) { setWanted(''); setExample(''); setState('idle') }
  }, [open])

  const submit = async () => {
    setState('busy')
    try {
      await api.requestType(ws, { wanted: wanted.trim(), example: example.trim() || undefined })
      setState('sent')
    } catch {
      setState('error')
    }
  }

  return (
    <Modal open={open} onClose={onClose} aria-label="Ask for a different project type">
      <h1 className="mb-1.5 text-xl font-bold tracking-tight">Need a different type?</h1>
      <p className="mb-5 text-sm text-muted-foreground">Tell us what you would label. We read every request.</p>
      <Field label="What would you label?">
        <textarea
          autoFocus
          rows={3}
          maxLength={MAX}
          value={wanted}
          onChange={(e) => setWanted(e.target.value)}
          placeholder="e.g. dents on car doors on a moving line"
          className="w-full rounded-md border border-input bg-card px-3 py-2 text-sm outline-none focus:border-ring placeholder:text-muted-foreground"
        />
      </Field>
      <div className="mt-4">
        <Field label="Example (optional)" hint="A link or one sentence we can look at.">
          <Input maxLength={MAX} value={example} onChange={(e) => setExample(e.target.value)} />
        </Field>
      </div>
      {state === 'sent' && <p role="status" className="mt-4 text-sm font-medium text-success">Thanks — we logged it.</p>}
      {state === 'error' && <p role="alert" className="mt-4 text-sm font-medium text-destructive">Could not send — try again</p>}
      <div className="mt-6 flex justify-end gap-2 border-t pt-4">
        <Button variant="ghost" onClick={onClose}>Close</Button>
        <Button disabled={!wanted.trim() || state === 'busy' || state === 'sent'} onClick={submit}>
          {state === 'busy' ? 'Sending…' : 'Send request'}
        </Button>
      </div>
    </Modal>
  )
}
