// T-1015: the Segmentation tab's rules, kept out of React so the node tests load them directly.
// No imports on purpose: the shapes are structural and the verdicts come from T-1014's GET /segmentation.

export type SegLicence = { name: string; url: string; non_commercial: boolean }
export type SegRow = {
  id: string
  name: string
  family: string
  params_m: number
  engine: string
  source_url: string
  note: string
  licence: SegLicence
  /** Megabits at one image, per resolution: the API's `vram` object. */
  vram: { '512': number; '1024': number }
  provisioned: { ok: boolean; reason: string }
  auto_label: { ref: string | null; engine_hint: string; classes_required: boolean }
}

export const NO_PROJECT = 'Choose a project first.'
export const NO_MODEL = 'No segmentation model is provisioned on this host.'
/** Where the operator's setup notes live until the hub's own page ships (T-1022). */
export const SETUP_DOC = 'https://github.com/Telotubbies/auto_label#readme'
export const NO_VERDICT = 'This model is not provisioned on this host.'

/**
 * A row may hand off only when the host has the weights and the registry has the ref; a Ready row
 * with no ref would open a dialog whose dropdown cannot select it.
 */
export const ready = (row: SegRow) => row.provisioned.ok && !!row.auto_label.ref

/** The state chip's word and the sentence under it. The API's reason opens with the chip text. */
export function stateCopy(row: SegRow): { label: string; detail: string } {
  if (ready(row)) return { label: 'Ready', detail: '' }
  const reason = row.provisioned.reason.trim() || NO_VERDICT
  const cut = reason.indexOf(':')
  if (cut < 0) return { label: reason, detail: '' }
  return { label: reason.slice(0, cut).trim(), detail: reason.slice(cut + 1).trim() }
}

/** AGPL and CC-BY-NC are badges, not footnotes: both carry a warning tone and their own word. */
export function licenceTone(row: SegRow): {
  label: string; note: string | null; tone: 'warning' | 'neutral'; className: string
} {
  const { name, non_commercial } = row.licence
  if (non_commercial) {
    return {
      label: name, note: 'Non-commercial', tone: 'warning',
      className: 'bg-warning/15 text-warning',
    }
  }
  // AGPL is the licence's own name, so the badge already prints it; the tone is what warns.
  if (/agpl/i.test(name)) return { label: name, note: null, tone: 'warning', className: 'bg-warning/15 text-warning' }
  return {
    label: name, note: null, tone: 'neutral',
    className: 'bg-secondary text-secondary-foreground',
  }
}

/** Both working resolutions, one decimal, from the API's megabytes. A missing figure says so. */
export function vramCopy(row: SegRow): string {
  const gb = (mb: number) => (mb > 0 ? `${(mb / 1024).toFixed(1)} GB` : 'unknown')
  return `512 px: ${gb(row.vram['512'])} · 1024 px: ${gb(row.vram['1024'])}`
}

/** The deep link T-1016 reads; URLSearchParams encodes the ref's ':' exactly once. */
export function handoffHref(ws: string, project: string, ref: string): string {
  const query = new URLSearchParams({ autolabel: ref })
  return `/${encodeURIComponent(ws)}/p/${encodeURIComponent(project)}/dataset?${query}`
}

/** What the card's one action does, or the sentence that says why it cannot. */
export function action(row: SegRow, ws: string, project: string | null): {
  disabled: boolean; href: string | null; reason: string
} {
  if (!project) return { disabled: true, href: null, reason: NO_PROJECT }
  if (!ready(row) || !row.auto_label.ref) {
    return { disabled: true, href: null, reason: row.provisioned.reason.trim() || NO_VERDICT }
  }
  return { disabled: false, href: handoffHref(ws, project, row.auto_label.ref), reason: '' }
}

/** No "last opened" store exists yet: remember this tab's pick per workspace, guarded for private mode. */
const lastKey = (ws: string) => `ld:seg-project:${ws}`

export function lastProject(ws: string): string | null {
  try { return localStorage.getItem(lastKey(ws)) } catch { return null }
}

export function rememberProject(ws: string, slug: string): void {
  try { localStorage.setItem(lastKey(ws), slug) } catch { /* private mode */ }
}

/** The remembered project when it still exists, else the most recently updated one. */
export function pickProject(
  projects: { slug: string; updated?: number }[], remembered: string | null,
): string {
  if (remembered && projects.some((project) => project.slug === remembered)) return remembered
  const newest = [...projects].sort((a, b) => (b.updated ?? 0) - (a.updated ?? 0))[0]
  return newest?.slug ?? ''
}
