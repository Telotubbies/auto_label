/**
 * The project sidebar's DATA / MODELS / DEPLOY layout. Pure: it only re-arranges the items the
 * registry already filtered by role, flag and project type, so it never invents a destination.
 * Items outside the named order stay reachable at the tail of their group; SETTINGS keeps its own group.
 */
export interface PanelItem { to: string; label: string }
export type PanelEntry<T> = T | 'divider'
export interface PanelSection<T> { id: string; label: string; entries: PanelEntry<T>[] }

const ORDER: Record<string, readonly string[]> = {
  DATA: ['upload', 'annotate', 'browse', 'versions', 'divider', 'insights', 'classes'],
  MODELS: ['train', 'models', 'deploy'],
  DEPLOY: ['deployments'],
}
const LABELS: Record<string, string> = { upload: 'Upload Data', insights: 'Analytics', deploy: 'Test' }
/** Registry group (by label) -> the section its extras land in. */
const HOME: Record<string, string> = { DATA: 'DATA', LABEL: 'DATA', MODELS: 'MODELS', STUDIO: 'MODELS', DEPLOY: 'DEPLOY' }

export function panelSections<T extends PanelItem>(
  groups: { group: string; items: T[] }[], deployments?: T,
): PanelSection<T>[] {
  const all = groups.flatMap((g) => g.items.map((item) => ({ item, home: HOME[g.group] ?? g.group })))
  if (deployments) all.push({ item: deployments, home: 'DEPLOY' })
  const placed = new Set<T>()
  const sections: PanelSection<T>[] = []
  const homes = [...new Set([...Object.keys(ORDER), ...all.map((a) => a.home)])]
  for (const home of homes) {
    const entries: PanelEntry<T>[] = []
    for (const key of ORDER[home] ?? []) {
      if (key === 'divider') { entries.push('divider'); continue }
      const hit = all.find((a) => a.item.to === key || a.item.to.endsWith(`/${key}`))
      if (hit && !placed.has(hit.item)) { placed.add(hit.item); entries.push({ ...hit.item, label: LABELS[key] ?? hit.item.label }) }
    }
    for (const a of all) {
      if (a.home === home && !placed.has(a.item)) { placed.add(a.item); entries.push(a.item) }
    }
    const clean = entries.filter((e, i) => e !== 'divider' || (i > 0 && i < entries.length - 1 && entries[i - 1] !== 'divider'))
    if (clean.some((e) => e !== 'divider')) sections.push({ id: home, label: home, entries: clean })
  }
  return sections
}
