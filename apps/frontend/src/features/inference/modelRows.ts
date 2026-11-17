// T-1012: the Models tab's rules, kept out of React so they can be tested without a browser.
// No imports on purpose: the node tests load this file directly, and the shapes are structural.

export type VariantLike = {
  id: string; quant: string; engine: string; bytes: number
  vram_gb: number | null; fits: boolean | null; installed: boolean; blocked: string[]
}
export type ModelLike = {
  id: string; name: string; family: string; params_b: number; installed: boolean; fits: boolean | null
  licence: { name: string; url: string; gated: boolean; non_commercial: boolean }
  variants: VariantLike[]
}
export type ModelFilters = {
  family: string; band: string; quant: string; licence: string; fits: boolean; installed: boolean
}
export type ModelState = {
  state: 'installed' | 'downloading' | 'queued' | 'ready'
  label: string
  actions: { label: string; kind: 'download' | 'manage' }[]
}

export const NO_FILTERS: ModelFilters = {
  family: 'all', band: 'all', quant: 'all', licence: 'all', fits: false, installed: false,
}
/** A download must leave 20% of the host's free space alone; the API refuses on the same line. */
export const DISK_MARGIN = 0.8
export const BANDS = [
  { id: 'small', label: 'Under 10B', max: 10 },
  { id: 'mid', label: '10–30B', max: 30 },
  { id: 'large', label: '30B and up', max: Infinity },
]
const GIB = 1024 ** 3

/** One unit everywhere on the screen: the table, the sheet and the disk sentence all use GiB. */
export const gib = (bytes: number) => `${(bytes / GIB).toFixed(1)} GB`

export const bandOf = (paramsB: number) => BANDS.find((band) => paramsB < band.max)?.id ?? 'large'

/** The rows every filter allows: family, size band, quantisation and licence intersect, then the two toggles. */
export function filterModels<T extends ModelLike>(rows: T[], f: ModelFilters): T[] {
  return rows.filter((row) =>
    (f.family === 'all' || row.family === f.family)
    && (f.band === 'all' || bandOf(row.params_b) === f.band)
    && (f.quant === 'all' || row.variants.some((variant) => variant.quant === f.quant))
    && (f.licence === 'all' || row.licence.name === f.licence)
    && (!f.fits || row.fits === true)
    && (!f.installed || row.installed))
}

/** The smallest variant this host can run; when none fits, the smallest one anyway, so the sheet can say why. */
export function defaultVariant<T extends VariantLike>(row: { variants: T[] }): T {
  const fitting = row.variants.filter((variant) => variant.fits === true)
  return (fitting.length ? fitting : row.variants)
    .reduce((small, variant) => (variant.bytes < small.bytes ? variant : small))
}

/** The job outranks the catalogue: a variant downloading is not "Not installed", and offers no second action. */
export function rowState(row: Pick<ModelLike, 'installed'>,
  job?: { status: string; progress?: number } | null): ModelState {
  if (job && (job.status === 'running' || job.status === 'cancelling')) {
    return { state: 'downloading', label: `Downloading ${Math.round(job.progress ?? 0)}%`, actions: [] }
  }
  if (job && job.status === 'queued') return { state: 'queued', label: 'Queued', actions: [] }
  if (row.installed) {
    return { state: 'installed', label: 'Installed', actions: [{ label: 'Manage on host', kind: 'manage' }] }
  }
  return { state: 'ready', label: 'Not installed', actions: [{ label: 'Download', kind: 'download' }] }
}

export const TOKEN_BLOCK = 'This model needs a Hugging Face token on the worker. Set `HF_TOKEN` there, not here.'
export const NON_COMMERCIAL = 'Non-commercial licence: check the terms before you deploy it.'

/**
 * Why the sheet's button is disabled, and what it must still say. The disk sentence is written from the
 * plan's own numbers so the reader sees the shortfall; any other refusal (pickle weights, GPU fit) is the
 * server's sentence, already ordered. Non-commercial is a note: the row stays downloadable.
 */
export function blockCopy(plan: {
  total_bytes: number; disk_free_gb: number | null; token_present: boolean
  gate: { gated: boolean; non_commercial: boolean }; blocked: string[]
}): { block: string | null; note: string | null } {
  const note = plan.gate.non_commercial ? NON_COMMERCIAL : null
  if (plan.gate.gated && !plan.token_present) return { block: TOKEN_BLOCK, note }
  const free = plan.disk_free_gb
  if (free !== null && plan.total_bytes / GIB > free * DISK_MARGIN) {
    return { block: `Needs ${gib(plan.total_bytes)}, host has ${free.toFixed(1)} GB free.`, note }
  }
  return { block: plan.blocked[0] ?? null, note }
}
