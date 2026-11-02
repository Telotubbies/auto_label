/** Class-panel search: filter by name, and map the 1–9 hotkeys onto the rows actually on screen. */
export interface NamedClass {
  name: string
}

export function normalizeSearch(query: string): string {
  return query.trim().toLowerCase()
}

export function visibleClasses<T extends NamedClass>(classes: T[], query: string): T[] {
  const q = normalizeSearch(query)
  return q ? classes.filter((c) => c.name.toLowerCase().includes(q)) : classes
}

/** `key` is a raw KeyboardEvent.key; digits outside 1–9 and empty results give null. */
export function hotkeyClass<T>(visible: T[], key: string): T | null {
  if (!/^[1-9]$/.test(key)) return null
  return visible[Number(key) - 1] ?? null
}

/** Text for the aria-live status line under the search field. */
export function classResultText(total: number, shown: number, query: string): string {
  if (!normalizeSearch(query)) return `${total} ${total === 1 ? 'class' : 'classes'}`
  if (!shown) return 'No class matches'
  return `${shown} of ${total} classes`
}
