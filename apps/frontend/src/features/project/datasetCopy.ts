import { fmtInt } from '../../lib/format.ts'

const images = (n: number) => `${fmtInt(n)} ${n === 1 ? 'image' : 'images'}`

/** The dataset subtitle: the plain total when nothing is filtered out, otherwise "24 of 40 images match". */
export function countLine(matching: number, total: number): string {
  return matching === total ? images(total) : `${fmtInt(matching)} of ${images(total)} match`
}
