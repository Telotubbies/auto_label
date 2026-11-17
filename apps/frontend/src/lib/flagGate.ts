import { projectNav } from './nav.ts'

export type FlagDecision = 'loading' | 'render' | 'off'

/**
 * One question, three answers. A flag that has not loaded is not "off" — saying so would flash
 * the notice on every cold load. Anything the workspace does not report as enabled is off, which
 * matches `services/flags.py`: unknown keys are never on.
 */
export function flagDecision({ loading, enabled, flag }: {
  loading: boolean
  enabled: readonly string[]
  flag: string
}): FlagDecision {
  if (loading) return 'loading'
  return enabled.includes(flag) ? 'render' : 'off'
}

/**
 * The gated surface's own nav label, read from the registry the sidebar renders, so the notice
 * and the rail cannot disagree. Detail routes (`streams/:sid`) name their parent surface.
 */
export function flagSurfaceLabel(pathname: string): string {
  const surface = pathname.split('/')[3] ?? ''
  return projectNav.flatMap((g) => g.items).find((i) => i.to === surface)?.label ?? 'This surface'
}
