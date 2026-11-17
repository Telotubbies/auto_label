// Thai-safe display text (T-473). A Thai combining mark belongs to its base character, so every
// shortening and every fit decision works on graphemes, never on UTF-16 code units. No React:
// the clamps live in index.css, and this module decides what text and what "more" to render.
//   shortcut: lineCountFor() approximates advance width at half an em; measure with a canvas if a
//   row ever needs exact pixel heights. Grapheme boundaries are exact either way.

const segmenter = typeof Intl !== 'undefined' && 'Segmenter' in Intl
  ? new Intl.Segmenter(undefined, { granularity: 'grapheme' })
  : null

/** The string as whole graphemes. Falls back to code points, which still never cuts a code unit. */
export function graphemes(text: string): string[] {
  if (!text) return []
  if (segmenter) return [...segmenter.segment(text)].map((s) => s.segment)
  return Array.from(text)
}

/** The first `max` graphemes; an empty name renders an em dash, never an empty box. */
export function excerpt(text: string, max: number): string {
  if (!text) return '—'
  const g = graphemes(text)
  return g.length <= max ? text : g.slice(0, max).join('')
}

/** True when the name does not fit in `max` graphemes, so the caller shows "…more". */
export function needsMore(text: string, max: number): boolean {
  return graphemes(text).length > max
}

/** Approximate wrapped line count for a name at a width; 0 when there is nothing to render. */
export function lineCountFor(text: string, widthPx: number, fontSizePx: number): number {
  if (!text) return 0
  const perLine = Math.max(1, Math.floor(widthPx / (fontSizePx * 0.5)))
  return Math.ceil(graphemes(text).length / perLine)
}
