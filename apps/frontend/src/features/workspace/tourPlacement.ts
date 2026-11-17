/** Pure rules for the first-run tour card: which corner it takes, and whether a step may scroll. */

export type Corner = 'bottom-left' | 'bottom-right' | 'top-left' | 'top-right'

export interface Rect {
  x: number
  y: number
  width: number
  height: number
}

export interface Viewport {
  width: number
  height: number
}

/** Desktop card is `22rem` wide and about this tall; inset matches the `4` (1rem) page margin. */
const CARD = { width: 352, height: 224, inset: 16 }

/** Where the card sits for a corner, so a caller can prove it clears the ringed target. */
export function cornerBox(corner: Corner, viewport: Viewport): Rect {
  const width = Math.min(CARD.width, viewport.width - CARD.inset * 2)
  const height = Math.min(CARD.height, viewport.height - CARD.inset * 2)
  const x = corner.endsWith('left') ? CARD.inset : viewport.width - CARD.inset - width
  const y = corner.startsWith('top') ? CARD.inset : viewport.height - CARD.inset - height
  return { x, y, width, height }
}

/** The corner opposite the target: a right-hand target gets a left corner, a low target a top one. */
export function placeCard(target: Rect, viewport: Viewport): Corner {
  const side = target.y + target.height / 2 > viewport.height / 2 ? 'top' : 'bottom'
  const edge = target.x + target.width / 2 > viewport.width / 2 ? 'left' : 'right'
  return `${side}-${edge}` as Corner
}

/** `none` when the whole target is already on screen; otherwise one nearest-aligned scroll. */
export function scrollBlock(target: Rect, viewport: Viewport): 'none' | 'nearest' {
  const visible = target.x >= 0 && target.y >= 0
    && target.x + target.width <= viewport.width && target.y + target.height <= viewport.height
  return visible ? 'none' : 'nearest'
}
