/**
 * T-484 — the overview's one dynamic primary and the aside's four truthful lines.
 * Pure (no React), so `tests/overview-facts.test.mjs` executes it under Node's type stripping.
 *
 * `primary()` does not derive the pipeline sentence a second time: it reuses the facts the board
 * already derives and only adds the two cases the header owns — a labeler, and the first upload.
 * Shortcut: T-477's `primaryLabel()` is not in the tree yet, so the board's model (`overviewModel`)
 * is the single source; when the stage manifest lands, swap that one delegate — do not fork the
 * sentence logic.
 */
import type { ProjectRole } from '../../lib/types.ts'
import type { OverviewFacts } from './overviewModel.ts'

/** The header's one action: the next real task, in the caller's role. */
export function primary(facts: OverviewFacts, role: ProjectRole | null): { label: string; to: string } {
  // A labeler never gets train or deploy: the board, where their batches wait, is their next task.
  if (role === 'labeler') return { label: 'Start labelling', to: 'annotate' }
  // `upload.count` is `images` in the board's vocabulary, so zero means nothing to work on yet.
  if (facts.stages.upload.count === 0) return { label: 'Upload 20 images', to: 'upload' }
  return facts.primary
}

export interface RunInput {
  mAP50?: number | null
  version?: number | null
}

/**
 * The latest run: its name and mAP50, plus the delta against the run before it. `null` when the
 * project has no finished run, so the aside can say so instead of painting a zero.
 */
export function runLine(run: RunInput | null, previous?: RunInput | null): { label: string; delta: string } | null {
  if (!run) return null
  const map = typeof run.mAP50 === 'number' ? run.mAP50 : null
  const version = run.version ? `v${run.version} · ` : ''
  if (map === null) return { label: `${version}no metric yet`, delta: '' }
  const label = `${version}mAP50 ${map.toFixed(2)}`
  const before = typeof previous?.mAP50 === 'number' ? previous.mAP50 : null
  if (before === null) return { label, delta: 'first run' }
  const diff = map - before
  return { label, delta: `${diff >= 0 ? '+' : ''}${diff.toFixed(2)} vs ${previous?.version ? `v${previous.version}` : 'previous'}` }
}

export interface BlockerFacts {
  toLabel: number
  review: number
  approved: number
  labelIssues: number
  missingBoxes: number
  healthStale: boolean
}

/** One row of "Blocked by": the reason plus the screen that fixes it, never a decorative line. */
export interface Blocker {
  id: string
  text: string
  to: string
}

/**
 * At most three rows, version readiness before health warnings: a version freezes approved labels,
 * so a review backlog stops the pipeline before a stale report does.
 */
export function blockedBy(f: BlockerFacts): Blocker[] {
  const rows: Blocker[] = []
  if (f.review > 0) rows.push({ id: 'review', text: `${f.review} labels are waiting for review`, to: 'annotate' })
  if (f.approved === 0 && f.toLabel > 0) {
    rows.push({ id: 'no-approved', text: 'No approved labels yet, so a version cannot be built', to: 'annotate' })
  }
  if (f.labelIssues > 0) {
    rows.push({
      id: 'label-quality',
      text: `${f.labelIssues} ${f.labelIssues === 1 ? 'label has' : 'labels have'} geometry problems`,
      to: 'dataset?tab=health',
    })
  }
  if (f.missingBoxes > 0) {
    rows.push({
      id: 'missing-boxes',
      text: `${f.missingBoxes} ${f.missingBoxes === 1 ? 'object the model sees is' : 'objects the model sees are'} unlabelled`,
      to: 'dataset?tab=health',
    })
  }
  if (f.healthStale) rows.push({ id: 'health-stale', text: 'The health report is out of date', to: 'dataset?tab=health' })
  return rows.slice(0, 3)
}

export type RingTone = 'success' | 'warning' | 'destructive' | 'muted'

/**
 * The ring's arc and the number beside it. `null` stats mean the call failed: the card says
 * "Unavailable" and offers a Retry, because a zero ring claims every label is missing.
 */
export function healthRing(stats: { approved: number; total: number } | null): {
  value: number | null
  label: string
  tone: RingTone
} {
  if (!stats) return { value: null, label: 'Unavailable', tone: 'muted' }
  if (stats.total <= 0) return { value: 0, label: 'No images yet', tone: 'muted' }
  const value = Math.round((stats.approved / stats.total) * 100)
  const tone: RingTone = value >= 75 ? 'success' : value >= 40 ? 'warning' : 'destructive'
  return { value, label: `${stats.approved} approved of ${stats.total}`, tone }
}
