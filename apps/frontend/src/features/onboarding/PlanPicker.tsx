import { useQuery } from '@tanstack/react-query'
import { coreApi } from '@/lib/api/core'
import { get } from '@/lib/api/client'
import { cn } from '@/lib/utils'

/** One tier as the API states it: the allowance it grants, never a price. */
export type PlanOption = { id: string; label: string; projects: number; credits: number; seats: number }

/** The chip selected before anyone picks another. A paid choice is a request, not a grant. */
export const DEFAULT_PLAN = 'free'

/**
 * The tier chips on the creation form. The line under each name is the API's plan catalogue, so
 * it says what the tier unlocks and nothing about money: no price has been set on this
 * deployment, so none is shown and nothing charges.
 */
export function PlanPicker({ value, onChange }: { value?: string; onChange?: (id: string) => void }) {
  // Signup has no workspace yet, so the surface is gated by the process flag in /config.
  const cfg = useQuery({
    queryKey: ['config'],
    queryFn: () => get<{ plan_choice?: boolean }>('/config'),
    staleTime: 5 * 60_000,
  })
  const on = Boolean(cfg.data?.plan_choice)
  const plans = useQuery({ queryKey: ['plans'], queryFn: coreApi.plans, enabled: on, staleTime: 5 * 60_000 })
  if (!on || !plans.data?.length) return null

  const selected = value || DEFAULT_PLAN
  return (
    <fieldset>
      <legend className="mb-1.5 block text-sm font-medium text-foreground">Plan</legend>
      <div className="grid gap-2">
        {plans.data.map((p) => (
          <label
            key={p.id}
            className={cn(
              'flex cursor-pointer flex-wrap items-center justify-between gap-x-3 gap-y-0.5 rounded-lg border px-3 py-2 transition-colors',
              'has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring',
              selected === p.id
                ? 'border-primary/60 bg-primary/10 ring-1 ring-primary/40 ring-inset'
                : 'border-border/70 bg-muted/40 hover:bg-muted/70',
            )}
          >
            <input
              type="radio"
              name="plan"
              value={p.id}
              checked={selected === p.id}
              onChange={() => onChange?.(p.id)}
              className="sr-only"
            />
            <span className="text-sm font-medium text-foreground">{p.label}</span>
            <span className="text-xs text-muted-foreground">
              {p.projects.toLocaleString('en-US')} projects · {p.credits.toLocaleString('en-US')} credits
            </span>
          </label>
        ))}
      </div>
      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
        Seats count per person who opens the editor. Paid plans start from Settings → Plan once billing
        is available; no payment is taken here.
      </p>
    </fieldset>
  )
}
