import type { WorkflowBlock, WorkflowBlockType } from '../../lib/types'

/** The API rejects more than twelve blocks per workflow. */
export const MAX_BLOCKS = 12

const isSink = (b: WorkflowBlock) => b.type === 'sink'

/**
 * Insert a new block where the chain stays runnable: before the trailing sink.
 * Appending after the sink would make every add action invalid until the user moves it up.
 */
export function insertBlock(blocks: WorkflowBlock[], block: WorkflowBlock): WorkflowBlock[] {
  const last = blocks.length - 1
  if (last >= 0 && isSink(blocks[last])) return [...blocks.slice(0, last), block, blocks[last]]
  return [...blocks, block]
}

/** Whether another block of this type may be added (one sink, at most twelve blocks). */
export function canAddBlock(blocks: WorkflowBlock[], type: WorkflowBlockType): boolean {
  if (blocks.length >= MAX_BLOCKS) return false
  return type !== 'sink' || !blocks.some(isSink)
}

/** Move a block one slot up or down. The sink is pinned last: nothing crosses or moves it.
 *  Returns the same array when the move is blocked, so callers can disable the control. */
export function moveBlock(blocks: WorkflowBlock[], index: number, delta: -1 | 1): WorkflowBlock[] {
  const target = index + delta
  if (index < 0 || index >= blocks.length || target < 0 || target >= blocks.length) return blocks
  if (isSink(blocks[index]) || isSink(blocks[target])) return blocks
  const next = [...blocks]
  ;[next[index], next[target]] = [next[target], next[index]]
  return next
}
