// The grid slice and the row height must follow the same breakpoints as the row's classes
// (grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5); otherwise the virtualiser folds five
// images into a two-column row and leaves holes.
export function colsForWidth(width: number): 2 | 3 | 4 | 5 {
  if (width >= 1280) return 5
  if (width >= 1024) return 4
  if (width >= 640) return 3
  return 2
}

// Opaque tile chrome (meta row and the row slack the 180 px row already had) is 36 px, so a row is
// its image plus 36. Narrower tiles get a taller image; the five-column desktop row is unchanged.
export function rowHeightForWidth(width: number): number {
  const cols = colsForWidth(width)
  return cols === 2 ? 216 : cols === 3 ? 200 : cols === 4 ? 188 : 180
}

/** Page buttons for the footer pager: first, last and the neighbours of the current page, `…` for gaps. 1-based. */
export function pageWindow(page: number, pages: number): (number | '…')[] {
  const keep = new Set([1, pages, page - 1, page, page + 1].filter((n) => n >= 1 && n <= pages))
  const out: (number | '…')[] = []
  let last = 0
  for (const n of [...keep].sort((a, b) => a - b)) {
    if (n - last > 1) out.push('…')
    out.push(n)
    last = n
  }
  return out
}
