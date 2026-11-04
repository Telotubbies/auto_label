/**
 * Selection and query rules for the Search + Collections page.
 *
 * Dependency-free on purpose: `node --test tests/search-state.test.mjs` loads this file directly
 * (type-only syntax is stripped by Node), so the rules stay testable without a React renderer.
 */

export interface SearchFilters {
  q: string
  class_id: string
  tag: string
  split: string
  status: string
  annotated: string
}

/** The fields the API accepts on GET search; `q` first so the query keeps its natural reading order. */
export const FILTER_KEYS = ['q', 'class_id', 'tag', 'split', 'status', 'annotated'] as const

export function toggleId(ids: ReadonlySet<string>, id: string): Set<string> {
  const next = new Set(ids)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  return next
}

/** Select-all covers the whole visible result set, not only the checkboxes the user happened to touch. */
export function selectAll(ids: readonly string[], checked: boolean): Set<string> {
  return checked ? new Set(ids) : new Set()
}

/** Only defined, non-blank filters travel in the URL — the API treats an empty string as "no filter". */
export function buildSearchQuery(filters: SearchFilters): Record<string, string> {
  const out: Record<string, string> = {}
  for (const key of FILTER_KEYS) {
    const value = filters[key].trim()
    if (value) out[key] = value
  }
  return out
}

/**
 * Which image ids "Save as collection" sends: the checkbox selection when there is one, otherwise
 * every result. Display order is kept (the API stores the item order) and ids absent from the
 * current results are dropped so a stale selection never adds an unrelated image.
 */
export function collectionTargets(selected: ReadonlySet<string>, results: readonly { id: string }[]): string[] {
  return results.filter((r) => !selected.size || selected.has(r.id)).map((r) => r.id)
}

/** The `query` text stored on a collection: the raw search plus the filters in `key:value` form. */
export function buildCollectionQuery(query: string, filters: SearchFilters): string {
  const { q, ...rest } = buildSearchQuery(filters)
  return [query.trim() || q?.trim() || '', ...Object.entries(rest).map(([k, v]) => `${k}:${v}`)]
    .filter(Boolean)
    .join(' ')
}
