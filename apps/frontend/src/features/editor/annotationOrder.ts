/**
 * Annotation stack order. The annotation array is the paint order: later items draw on top, and the
 * save endpoint stores the array verbatim, so the order survives a reload without a schema field.
 * Every function is pure and returns the same array reference when the action changes nothing.
 */
export type OrderAction = 'forward' | 'backward' | 'front' | 'back'

/** Button order in the Objects panel, front-most first. */
export const ORDER_ACTIONS: OrderAction[] = ['front', 'forward', 'backward', 'back']

type Identified = { id: string }

/** The array index of `id`, or -1. */
function indexOf(list: Identified[], id: string) {
  for (let i = 0; i < list.length; i++) if (list[i].id === id) return i
  return -1
}

/** True when the action would move the item; drives the disabled state of the four buttons. */
export function canMove(list: Identified[], id: string, action: OrderAction) {
  const at = indexOf(list, id)
  if (at < 0) return false
  if (action === 'forward') return at < list.length - 1
  if (action === 'backward') return at > 0
  if (action === 'front') return at < list.length - 1
  return at > 0
}

/**
 * Move one annotation in the stack. Returns a new array for a real move and the input array for a
 * no-op, so the editor only marks the image dirty (and autosaves) when the order changed.
 */
export function moveAnnotation<T extends Identified>(list: T[], id: string, action: OrderAction): T[] {
  const at = indexOf(list, id)
  if (at < 0 || !canMove(list, id, action)) return list
  const next = list.slice()
  const [item] = next.splice(at, 1)
  const target = action === 'front' ? next.length
    : action === 'back' ? 0
      : action === 'forward' ? at + 1
        : at - 1
  next.splice(target, 0, item)
  return next
}

/** 1-based stack position (1 = back of the stack), matching the `z` badge in the Objects list. */
export function orderIndexOf(list: Identified[], id: string) {
  const at = indexOf(list, id)
  return at < 0 ? null : at + 1
}
