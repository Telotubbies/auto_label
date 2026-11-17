import { useEffect, useId, useState } from 'react'
import { TriangleAlert } from 'lucide-react'
import { ApiError } from '@/lib/api'
import { coreApi } from '@/lib/api/core'
import { useFlag } from '@/lib/flags'
import { useApp } from '@/lib/store'
import { cn } from '@/lib/utils'
import { Button, Input, Spinner } from '@/components/ui'
import { isWorkspaceSlug, workspaceLinkCopy, workspaceSlug, type WorkspaceLinkState } from '@/lib/slug'

type Props = {
  value: string
  onChange: (value: string) => void
  /** Shown when the name is blank: the address the account name would derive (signup). */
  fallbackName?: string
  /** Process flag from /config. Signup has no workspace, so `useFlag` alone cannot see it. */
  enabled?: boolean
  disabled?: boolean
  error?: string
  /** First run owns the submit; signup submits with its account form instead. */
  submit?: { label: string; busy?: boolean; onClick: () => void }
  onStatus?: (status: WorkspaceLinkState) => void
}

export function WorkspaceForm({
  value, onChange, fallbackName = '', enabled, disabled, error, submit, onStatus,
}: Props) {
  const flag = useFlag('task_a1_workspace_create')
  const on = enabled || flag
  const authed = useApp((s) => s.authed)
  const id = useId()
  const [state, setState] = useState<WorkspaceLinkState>('empty')
  const [suggestion, setSuggestion] = useState('')

  const shown = value.trim() || fallbackName
  const slug = workspaceSlug(shown)

  useEffect(() => {
    if (!on) { setState('empty'); setSuggestion(''); return }
    if (!isWorkspaceSlug(slug)) { setState('invalid'); return }
    // The availability check is bearer-only. Signup shows the derived address and the server
    // refuses a collision on submit; first run checks before submit.
    if (!authed || !value.trim()) { setState('empty'); return }
    let live = true
    setState('loading')
    const timer = setTimeout(() => {
      coreApi.workspaceSlug(value)
        .then((r) => {
          if (!live) return
          setSuggestion(r.suggestion ?? '')
          setState(r.available ? 'free' : 'taken')
        })
        .catch((ex: unknown) => {
          if (!live) return
          setState(ex instanceof ApiError && ex.status === 422 ? 'invalid' : 'empty')
        })
    }, 350)
    return () => { live = false; clearTimeout(timer) }
  }, [on, authed, value, slug])

  useEffect(() => { onStatus?.(state) }, [state, onStatus])

  return (
    <div className="space-y-4">
      <div>
        <label htmlFor={`${id}-name`} className="mb-1.5 block text-sm font-medium text-foreground">
          Workspace name
        </label>
        <Input
          id={`${id}-name`}
          type="text"
          name="organization"
          autoComplete="organization"
          value={value}
          disabled={disabled}
          aria-invalid={state === 'taken' || state === 'invalid'}
          aria-describedby={on ? `${id}-address` : `${id}-hint`}
          onChange={(e) => onChange(e.target.value)}
        />
        {on ? (
          <p
            id={`${id}-address`}
            role="status"
            aria-live="polite"
            className={cn(
              'mt-1 flex items-start gap-1.5 text-pretty text-xs leading-relaxed',
              state === 'empty' && 'text-muted-foreground',
              state === 'invalid' && 'text-destructive',
              state === 'taken' && 'text-foreground',
            )}
          >
            {state === 'loading' ? <Spinner aria-hidden className="mt-0.5 h-3 w-3 shrink-0" /> : null}
            {state === 'taken' || state === 'invalid'
              ? <TriangleAlert aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0 text-destructive" />
              : null}
            {state === 'taken' ? (
              <span>
                Taken — try{' '}
                <button
                  type="button"
                  onClick={() => onChange(suggestion)}
                  className="rounded-sm font-medium text-primary underline decoration-primary/40 underline-offset-4 hover:decoration-primary focus-visible:outline-2"
                >
                  {suggestion}
                </button>
              </span>
            ) : (
              <span>{workspaceLinkCopy(state, slug, suggestion)}</span>
            )}
          </p>
        ) : (
          <p id={`${id}-hint`} className="mt-1 text-pretty text-xs leading-relaxed text-muted-foreground">
            Optional. Leave it blank and we’ll name it after you.
          </p>
        )}
      </div>

      {error ? (
        <p role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2.5 text-sm font-medium leading-relaxed text-foreground">
          {error}
        </p>
      ) : null}

      {submit ? (
        <Button
          type="button"
          className="h-10 w-full"
          disabled={disabled || submit.busy || !value.trim() || state === 'loading' || state === 'taken' || state === 'invalid'}
          onClick={submit.onClick}
        >
          {submit.busy ? <Spinner className="h-4 w-4" /> : null}
          {submit.busy ? 'Creating…' : submit.label}
        </Button>
      ) : null}
    </div>
  )
}
