import type { BoardCard } from '../../lib/types.ts'

export type BoardSort = 'newest' | 'name' | 'images'

/** A new array of cards in the chosen order; the input is never mutated. */
export function sortCards(cards: readonly BoardCard[], by: BoardSort): BoardCard[] {
  const out = [...cards]
  if (by === 'name') return out.sort((a, b) => a.batchName.localeCompare(b.batchName))
  if (by === 'images') return out.sort((a, b) => b.images - a.images)
  return out.sort((a, b) => b.created - a.created)
}
