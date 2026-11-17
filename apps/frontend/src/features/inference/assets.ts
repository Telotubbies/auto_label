// T-1013: the host assets panel's rules, kept out of React so the node tests load this file directly.
// No imports on purpose (the same house rule engineRows.ts follows): the shapes below are structural,
// and the panel resolves catalogue names, so nothing here needs the generated API types.

export type DiskLike = { models_free_gb?: number; models_total_gb?: number } | null | undefined
export type InstalledModelLike = {
  id?: string; variant?: string; bytes?: number; installed_at?: string
}
export type InventoryLike = {
  disk?: DiskLike
  engines?: { id?: string; version?: string; ok?: boolean }[]
  models?: InstalledModelLike[]
} | null | undefined

/** The host said nothing about its models; distinct from a host that said it has none. */
export const NO_INVENTORY = 'This host has not reported what it has installed.'
export const NOTHING_INSTALLED = 'Nothing installed yet. Download a model from the catalogue.'
export const LOW_DISK = 'Under 10 GB or 10% free. Remove a model to make room.'

const LOW_SHARE = 0.1
const LOW_GB = 10
const ENGINE_NAME: Record<string, string> = {
  ollama: 'Ollama', vllm: 'vLLM', llamacpp: 'llama.cpp', sglang: 'SGLang',
  tensorrtllm: 'TensorRT-LLM', onnxruntime: 'ONNX Runtime GenAI', triton: 'Triton Inference Server',
}

const freeShare = (disk: DiskLike) => {
  const free = disk?.models_free_gb
  const total = disk?.models_total_gb
  if (typeof free !== 'number' || typeof total !== 'number' || total <= 0) return null
  return free / total
}

/** The bar's whole percent; null when the host reported no disk, so the panel shows no needle. */
export const diskPct = (disk: DiskLike) => {
  const share = freeShare(disk)
  return share === null ? null : Math.round(share * 100)
}

/** PLAN §9: under 10 GB free, or under 10% of the disk. Exactly 10 of either is not "under". */
export const lowDisk = (disk: DiskLike) => {
  const free = disk?.models_free_gb
  const share = freeShare(disk)
  return share !== null && typeof free === 'number' && (free < LOW_GB || share < LOW_SHARE)
}

/** Largest first: disk pressure is the reason this panel exists. A missing size sorts last. */
export const sortBySize = <T extends InstalledModelLike>(rows: T[]): T[] =>
  [...rows].sort((a, b) => (b.bytes ?? 0) - (a.bytes ?? 0))

export const installedModels = (inventory: InventoryLike) =>
  sortBySize((inventory?.models ?? []).filter((model) => !!model?.id))

/** Bytes as one decimal of GB, the unit the models table already uses; 4.4 GB, never 4.4e9. */
export const gib = (bytes?: number) =>
  typeof bytes === 'number' && Number.isFinite(bytes) ? `${(bytes / 1024 ** 3).toFixed(1)} GB` : 'unknown'

/** The confirm sheet's one sentence: model, variant, host, and the bytes the removal frees when known. */
export const removeCopy = (model: InstalledModelLike & { host: string; name?: string }) =>
  `Remove ${model.name || model.id}${model.variant ? ` (${model.variant})` : ''} from ${model.host}?`
  + (typeof model.bytes === 'number' ? ` This frees ${gib(model.bytes)}.` : '')

/** Installed engines only, one compact line; an engine the host marked `ok: false` is omitted. */
export const engineLine = (inventory: InventoryLike) => (inventory?.engines ?? [])
  .filter((engine) => engine.ok !== false && !!engine.id)
  .map((engine) => `${ENGINE_NAME[engine.id as string] ?? engine.id}${engine.version ? ` ${engine.version}` : ''}`)
  .join(' \u00B7 ')

/** The body copy when there is no table to draw: no report at all, or a report of nothing. */
export const emptyCopy = (inventory: InventoryLike): string | null => {
  if (!inventory || !Array.isArray(inventory.models)) return NO_INVENTORY
  return inventory.models.length ? null : NOTHING_INSTALLED
}
