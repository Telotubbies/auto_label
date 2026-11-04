/** Selection rules for the Compare tab picker.
 *
 * The compare endpoint only accepts models from the same dataset version and task, so the picker
 * works in those groups. The default must land on a group that can actually be compared: anchoring
 * on the newest model alone used to leave every other pill disabled and the tab on its empty state.
 */
export interface ComparableModel {
  id: string
  versionId: string
  task: string
}

export const MAX_COMPARE = 4

const comparable = (a: ComparableModel, b: ComparableModel) =>
  a.id !== b.id && a.versionId === b.versionId && a.task === b.task

/** First (version, task) group holding at least two models, taken in catalogue order. */
export function firstPair(models: ComparableModel[]): string[] {
  for (const model of models) {
    const peer = models.find((other) => comparable(model, other))
    if (peer) return [model.id, peer.id]
  }
  return models.length ? [models[0].id] : []
}

/** Anchor on `modelParam` when it has a peer, else on the first comparable group; never on a lone run. */
export function defaultCompare(models: ComparableModel[], modelParam?: string): string[] {
  const anchor = models.find((model) => model.id === modelParam)
  if (anchor) {
    const peer = models.find((other) => comparable(anchor, other))
    if (peer) return [anchor.id, peer.id]
  }
  return firstPair(models)
}

/** Toggle one model. Removing the last selection is allowed: an empty picker re-enables every
 * pill, which is the reset for a catalogue where no two models share a version and task. */
export function toggleSelection(models: ComparableModel[], current: string[], id: string): string[] {
  if (current.includes(id)) return current.filter((x) => x !== id)
  if (current.length >= MAX_COMPARE) return current
  const next = new Set([...current, id])
  return models.filter((model) => next.has(model.id)).map((model) => model.id)
}
