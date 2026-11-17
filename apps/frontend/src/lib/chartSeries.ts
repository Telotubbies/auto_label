// One source of series colour and legend style for every chart (T-523): the shipped Okabe-Ito
// class palette in lib/theme.ts, and a 12 px foreground legend key so a key never falls below AA.
import { createElement } from 'react'

/** Series colour by index, straight from the shipped class palette. No new palette. */
export { classColor as seriesColor } from './theme.ts'

/** Legend props every chart spreads: a text-xs key in the foreground role, not 11 px in muted grey. */
export const legendProps = {
  formatter: (value: string) => createElement('span', { className: 'text-xs text-foreground' }, value),
}

/** True when a chart would draw something other than a flat line of zeros. */
export const hasSeries = (values: number[]): boolean => values.some((v) => v !== 0)
