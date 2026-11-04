import { useEffect } from 'react'
import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import { Glass } from '@/components/glass'
import { Button } from '@/components/ui'
import { TOUR_STEPS, nextStep, prevStep } from './dashboardRules'

/** Non-modal coach mark: it rings the section it talks about instead of blocking the page. */
export function Tour({ step, onStep, onClose }: { step: number; onStep: (n: number) => void; onClose: () => void }) {
  const current = TOUR_STEPS[step]
  const last = step === TOUR_STEPS.length - 1

  useEffect(() => {
    document.getElementById('home-tour')?.focus()
    const el = document.querySelector<HTMLElement>(`[data-tour="${current.target}"]`)
    if (!el) return
    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    el.scrollIntoView({ block: 'center', behavior: still ? 'auto' : 'smooth' })
    el.classList.add('tour-target')
    return () => el.classList.remove('tour-target')
  }, [current.target])

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])

  return (
    <Glass as="section" strength="overlay" id="home-tour" role="region" aria-label="Guided tour" tabIndex={-1}
      className="fixed bottom-4 right-4 z-[150] w-[min(22rem,calc(100vw-2rem))] rounded-2xl p-4 text-popover-foreground shadow-2xl">
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-medium text-muted-foreground">Step {step + 1} of {TOUR_STEPS.length}</p>
        <button type="button" onClick={onClose} aria-label="End tour"
          className="-mr-1 -mt-1 flex h-7 w-7 cursor-pointer items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground">
          <X className="h-4 w-4" />
        </button>
      </div>
      <h2 className="mt-1 text-base font-semibold">{current.title}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{current.body}</p>
      <div className="mt-4 flex items-center justify-between gap-2">
        <Button variant="ghost" size="sm" disabled={step === 0} onClick={() => onStep(prevStep(step))}>
          <ChevronLeft className="h-3.5 w-3.5" /> Back
        </Button>
        <Button size="sm" onClick={() => (last ? onClose() : onStep(nextStep(step)))}>
          {last ? 'Done' : <><span>Next</span><ChevronRight className="h-3.5 w-3.5" /></>}
        </Button>
      </div>
    </Glass>
  )
}
