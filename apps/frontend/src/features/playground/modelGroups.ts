/** Registry rows grouped by family, in first-appearance order, so the vendor prints once per group. */
export function groupModels<T extends { family: string }>(items: T[]): { family: string; items: T[] }[] {
  const groups = new Map<string, T[]>()
  for (const item of items) {
    const rows = groups.get(item.family)
    if (rows) rows.push(item)
    else groups.set(item.family, [item])
  }
  return Array.from(groups, ([family, rows]) => ({ family, items: rows }))
}
