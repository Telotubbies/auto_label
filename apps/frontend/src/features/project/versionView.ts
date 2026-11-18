/** Pure display helpers for the Versions list and the trained-model block. */
export const f1Score = (precision?: number, recall?: number): number | undefined =>
  precision == null || recall == null || precision + recall === 0 ? undefined : (2 * precision * recall) / (precision + recall)

/** "320×320" when the version resizes, else undefined. */
export function resizeLabel(settings: Record<string, any>): string | undefined {
  const r = settings?.preprocessing?.resize
  return r ? `${r.width}×${r.height}` : undefined
}

/** Preprocessing steps other than resize, as short words. */
export const preprocessSteps = (settings: Record<string, any>): string[] =>
  Object.entries(settings?.preprocessing ?? {}).filter(([k, v]) => v && k !== 'resize').map(([k]) => k.replace(/_/g, ' '))
