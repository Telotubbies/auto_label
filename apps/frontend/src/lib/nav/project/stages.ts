/**
 * Stage tabs: a tab is a sub-surface of one rail stage, never a destination of its own, so the rail
 * never lists the same screen twice. Pure (no React) because `tests/stage-tabs.test.mjs` runs this
 * module directly under Node type stripping.
 */
export interface StageTab {
  id: string
  label: string
  /** Project permission the child route already gates on. */
  perm: string
  /** Workspace flag the child route also requires. */
  flag?: string
}

export const STAGE_TABS: Record<string, readonly StageTab[]> = {
  dataset: [
    { id: 'images', label: 'Images', perm: 'project.read' },
    { id: 'versions', label: 'Versions', perm: 'project.export' },
    { id: 'health', label: 'Health', perm: 'project.review' },
  ],
  deploy: [
    { id: 'test', label: 'Test', perm: 'project.models' },
    { id: 'streams', label: 'Streams', perm: 'project.streams', flag: 'task_10b' },
  ],
}

/** Old sibling URLs; the route files keep them alive as redirects into the tab. */
export const LEGACY_TAB_PATHS = {
  versions: 'dataset?tab=versions',
  streams: 'deploy?tab=streams',
  'model-insights': 'models',
} as const

/**
 * The tabs this member can open. An unloaded flag reads as off, so a tab never appears before the
 * permission or flag that unlocks it. While permissions load, the caller passes no filter and the
 * row still paints; each child keeps its own `PermGate`.
 */
export function tabsFor(
  stage: string,
  can: (perm: string) => boolean = () => true,
  flags?: ReadonlySet<string>,
): readonly StageTab[] {
  return (STAGE_TABS[stage] ?? []).filter((tab) => can(tab.perm) && (!tab.flag || !!flags?.has(tab.flag)))
}

/** The tab a URL asks for; empty or unknown values fall back to the first tab and say nothing. */
export function resolveTab(stage: string, value: string | null | undefined): string {
  const tabs = STAGE_TABS[stage] ?? []
  return tabs.some((tab) => tab.id === value) ? (value as string) : (tabs[0]?.id ?? '')
}

export function tabHref(stage: string, tab: string): string {
  return `?tab=${resolveTab(stage, tab)}`
}
