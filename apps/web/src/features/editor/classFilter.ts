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

/** The search only narrows the list — and therefore the 1–9 order — while that list is on screen. */
export function classListQuery(query: string, listVisible: boolean): string {
  return listVisible ? query : ''
}

export interface ClassListState {
  /** Left icon rail; the whole Labels pane (tabs, search, rows) only renders on 'labels'. */
  rail: string
  tab: string
  panelsOpen: boolean
}

/** True only while the class rows are really rendered: Labels rail, Classes tab, panel not folded. */
export function isClassListVisible({ rail, tab, panelsOpen }: ClassListState): boolean {
  return rail === 'labels' && tab === 'classes' && panelsOpen
}

/** Text for the aria-live status line under the search field. */
export function classResultText(total: number, shown: number, query: string): string {
  if (!normalizeSearch(query)) return `${total} ${total === 1 ? 'class' : 'classes'}`
  if (!shown) return 'No class matches'
  return `${shown} of ${total} classes`
}
