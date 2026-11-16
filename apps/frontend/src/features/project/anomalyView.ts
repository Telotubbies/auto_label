// Overlay rules for the good-only anomaly heatmap. Kept free of React so the scoring rules can
// be exercised directly by the Node test runner; the page only positions what these return.

/** A cell worth painting. `row`/`col` index the station heatmap grid; opacity is 0..0.9. */
export interface HeatCell {
  row: number
  col: number
  value: number
  opacity: number
}

/** Cells below this fraction of the station threshold are sensor noise, not a defect hint. */
const NOISE_RATIO = 0.5
const MAX_OPACITY = 0.9

/** Viridis stops (STANDARDS: heatmaps use viridis) from low to high intensity. */
const VIRIDIS: [number, number, number][] = [
  [68, 1, 84],
  [59, 82, 139],
  [33, 145, 140],
  [94, 201, 98],
  [253, 231, 37],
]

/**
 * Paint strength for one heatmap cell. Anything at or below half the station threshold is
 * dropped; above it the overlay fades in with the score up to a 0.9 cap so the image stays
 * readable underneath.
 */
export function cellOpacity(value: number, threshold: number): number {
  const safeThreshold = Math.max(threshold, 1e-6)
  const ratio = Math.max(0, value) / safeThreshold
  if (ratio <= NOISE_RATIO) return 0
  return Math.min(MAX_OPACITY, 0.3 * ratio)
}

/** The visible cells of a heatmap, in row-major order; fully transparent cells are omitted. */
export function hotCells(values: number[][], threshold: number): HeatCell[] {
  const out: HeatCell[] = []
  values.forEach((row, r) => row.forEach((value, c) => {
    const opacity = cellOpacity(value, threshold)
    if (opacity > 0) out.push({ row: r, col: c, value, opacity })
  }))
  return out
}

/** Viridis colour for a cell score, normalised against the station threshold. */
export function heatColor(value: number, threshold: number): string {
  const safeThreshold = Math.max(threshold, 1e-6)
  const ratio = Math.max(0, value) / safeThreshold
  const intensity = Math.min(1, Math.max(0, (ratio - NOISE_RATIO) / (3 - NOISE_RATIO)))
  const pos = intensity * (VIRIDIS.length - 1)
  const i = Math.min(VIRIDIS.length - 2, Math.floor(pos))
  const f = pos - i
  const rgb = VIRIDIS[i].map((c, k) => Math.round(c + (VIRIDIS[i + 1][k] - c) * f))
  return `rgb(${rgb[0]} ${rgb[1]} ${rgb[2]})`
}
