/**
 * The project rail's manifest (T-477): five numbered stages inside three purpose groups, plus the
 * unnumbered destinations each group holds. Pure — no React — because `tests/stage-manifest.test.mjs`
 * and `tests/nav.test.mjs` execute it directly with Node's type stripping; relative imports carry
 * `.ts` for the same reason.
 *
 * The rail lists each screen once: a stage's sub-surfaces are tabs on its own page (T-479), never a
 * second sibling row. `settings` closes the rail below a rule, outside the groups.
 */
import type { Job, Project, ProjectRole, StageFacts, Version } from '../../types.ts'
import type { NavIcon, ProjectNavItem } from '../types.ts'
import { dataNav } from './data.ts'
import { modelsNav } from './models.ts'
import { settingsNav } from './settings.ts'

export type StageId = 'upload' | 'annotate' | 'dataset' | 'train' | 'deploy'
export type RailId = StageId | 'insights' | 'classes' | 'models' | 'model-search' | 'active-learning'

/** The state words the rail uses, in precedence order: blocked, needs-you, then done. */
export type StageStateWord = 'done' | 'needs-you' | 'blocked' | 'not-started' | 'running' | 'unknown'

export interface StageDef {
  id: StageId
  number: 1 | 2 | 3 | 4 | 5
  label: string
  to: string
  perm: string
}

/** The five stages, in pipeline order. Only these are numbered. */
export const STAGES: readonly StageDef[] = [
  // EVERY member may open Upload and Dataset; the action itself is gated on the page.
  { id: 'upload', number: 1, label: 'Upload', to: 'upload', perm: 'project.read' },
  { id: 'annotate', number: 2, label: 'Annotate', to: 'annotate', perm: 'project.annotate' },
  { id: 'dataset', number: 3, label: 'Dataset', to: 'dataset', perm: 'project.read' },
  { id: 'train', number: 4, label: 'Train', to: 'train', perm: 'project.train' },
  { id: 'deploy', number: 5, label: 'Deploy', to: 'deploy', perm: 'project.models' },
] as const

/** The rail's shape, in render order: three purposes, sentence case, stages in the pipeline order. */
export const GROUPS = [
  { id: 'data', label: 'Data', items: ['upload', 'annotate', 'dataset', 'insights', 'classes'] },
  { id: 'models', label: 'Models', items: ['train', 'models', 'model-search'] },
  { id: 'deploy', label: 'Deploy', items: ['deploy', 'active-learning'] },
] as const

/** Below the rule, outside the groups. */
export const SECONDARY: readonly ProjectNavItem[] = [
  { ...settingsNav.items[0], label: 'Project settings' },
]

const STAGE_ICONS: Record<StageId, NavIcon> = {
  upload: 'upload', annotate: 'annotate', dataset: 'dataset', train: 'train', deploy: 'deploy',
}

/** The shipped group files keep the unnumbered entries they already own. */
const EXISTING: Record<string, ProjectNavItem> = Object.fromEntries(
  [...dataNav.items, ...modelsNav.items].map((i) => [i.to, i]),
)

/**
 * Destinations whose surface a later card builds: T-269–T-272 (model search) and T-653 (active
 * learning). They are listed so the rail is complete; the row opens the page that will host them.
 */
const PLANNED: Record<string, ProjectNavItem> = {
  'model-search': { to: 'models?tab=search', label: 'Model search', icon: 'models', perm: 'project.models' },
  'active-learning': { to: 'deploy?view=active-learning', label: 'Active learning', icon: 'deploy', perm: 'project.models' },
}

export interface StageRow extends ProjectNavItem {
  id: RailId
  /** Pipeline position, on the five stages only. */
  number?: number
  /** The role cannot act on it: dimmed with a lock, never dropped. */
  locked: boolean
}

export function railItem(id: RailId): StageRow {
  const stage = STAGES.find((s) => s.id === id)
  if (stage) {
    return { id, to: stage.to, label: stage.label, perm: stage.perm, icon: STAGE_ICONS[stage.id],
      number: stage.number, locked: false }
  }
  // Every rail id has an entry: the shipped group files, or the two planned surfaces above.
  return { ...(EXISTING[id] ?? PLANNED[id]), id, locked: false }
}

/**
 * Derive the facts from the three calls the project shell already makes: the project payload
 * (images, statusCounts, models, classes), `GET /versions` and `GET /ws/{ws}/jobs`. An argument
 * left `undefined` (still loading, or failed) derives `null`, which the rail renders as a skeleton
 * or `unknown` — never as a zero.
 */
export function stageFacts({ project, versions, jobs }: {
  project: Pick<Project, 'slug' | 'images' | 'models' | 'statusCounts' | 'classes'>
  versions?: Version[] | null
  jobs?: Job[] | null
}): StageFacts {
  const counts = project.statusCounts
  const list = versions ?? null
  // A job without a project came from the project-scoped endpoint, so it belongs to this project.
  const runs = jobs ? jobs.filter((j) => j.kind === 'train' && (!j.project || j.project === project.slug)) : null
  const last = runs?.length ? runs.reduce((a, b) => (b.created > a.created ? b : a)) : null
  const ready = list?.filter((v) => v.status === 'ready') ?? []
  return {
    uploaded: project.images,
    approved: counts ? (counts.done ?? 0) : null,
    toLabel: counts ? (counts.unassigned ?? 0) + (counts.annotating ?? 0) : null,
    inReview: counts ? (counts.review ?? 0) : null,
    versions: list?.length ?? null,
    latestVersion: ready.length ? Math.max(...ready.map((v) => v.number)) : null,
    runs: runs?.length ?? null,
    lastRun: runs === null ? null
      : last === null ? 'none'
        : last.status === 'done' ? 'ok'
          : last.status === 'failed' ? 'failed'
            : last.status === 'cancelled' ? 'cancelled' : 'running',
    models: project.models,
    classes: project.classes ? project.classes.length : null,
    // No deployment record exists in the API yet (T-314 owns it): null, drawn as `—`.
    deployed: null,
  }
}

/** The state word for one stage. Blocked outranks needs-you, which outranks done. */
export function stageState(f: StageFacts, id: StageId): StageStateWord {
  switch (id) {
    case 'upload':
      return f.uploaded > 0 ? 'done' : 'needs-you'
    case 'annotate':
      if (f.toLabel === null || f.inReview === null) return 'unknown'
      if (f.uploaded === 0) return 'not-started'
      return f.toLabel + f.inReview > 0 ? 'needs-you' : 'done'
    case 'dataset':
      if (f.uploaded === 0) return 'not-started'
      if (f.approved === null) return 'unknown'
      if (f.approved === 0) return 'blocked'
      if (f.versions === null) return 'unknown'
      return f.versions > 0 ? 'done' : 'needs-you'
    case 'train':
      if (f.versions === null || f.lastRun === null) return 'unknown'
      if (f.versions === 0) return 'not-started'
      if (f.lastRun === 'failed') return 'blocked'
      if (f.lastRun === 'running') return 'running'
      return f.lastRun === 'ok' ? 'done' : 'not-started'
    case 'deploy':
      // No deployment record yet, so nothing can be claimed as deployed.
      return 'not-started'
  }
}

const WORDS: Record<StageStateWord, string> = {
  done: 'done', 'needs-you': 'needs you', blocked: 'blocked', 'not-started': 'not started',
  running: 'running', unknown: 'unknown',
}

export function stageWord(state: StageStateWord): string {
  return WORDS[state]
}

/** The badge number, or null when the API has not answered for that number yet. */
export function stageCount(f: StageFacts, id: RailId): number | null {
  switch (id) {
    case 'upload': return f.uploaded
    // Everything still at the annotate stage: to label plus to review.
    case 'annotate': return f.toLabel === null || f.inReview === null ? null : f.toLabel + f.inReview
    case 'dataset': return f.versions
    case 'train': return f.runs
    case 'models': return f.models
    case 'classes': return f.classes
    case 'deploy': return f.deployed
    case 'insights': case 'model-search': case 'active-learning': return null
  }
}

/** One line of text under the stage, or null while its number is still unknown. */
export function stageLine(f: StageFacts, id: StageId): string | null {
  switch (id) {
    case 'upload':
      return f.uploaded > 0 ? `${f.uploaded} uploaded` : 'no images yet'
    case 'annotate':
      if (f.toLabel === null || f.inReview === null) return null
      if (f.toLabel > 0) return `${f.toLabel} to label`
      if (f.inReview > 0) return `${f.inReview} to review`
      return `${f.approved ?? 0} approved`
    case 'dataset':
      if (f.uploaded === 0) return 'no images yet'
      if (f.approved === null) return null
      if (f.approved === 0) return 'blocked by annotate'
      if (f.versions === null) return null
      if (f.versions === 0) return 'no version yet'
      return `${f.versions} version${f.versions === 1 ? '' : 's'} · ${f.approved} approved`
    case 'train':
      if (f.versions === null || f.lastRun === null) return null
      if (f.versions === 0) return 'no version to train on'
      if (f.lastRun === 'failed') return 'last run failed'
      if (f.lastRun === 'cancelled') return 'last run cancelled'
      if (f.lastRun === 'running') return 'training now'
      return f.lastRun === 'ok' ? 'last run ok' : 'no run yet'
    case 'deploy':
      return 'not deployed yet'
  }
}

/** What a collapsed group still says, so collapsing never hides an alert. */
export function groupSummary(f: StageFacts, groupId: string): string | null {
  const group = GROUPS.find((g) => g.id === groupId)
  const waiting = (group?.items ?? []).filter((id) =>
    STAGES.some((s) => s.id === id) && stageState(f, id as StageId) === 'needs-you').length
  return waiting ? `${waiting} ${waiting === 1 ? 'needs' : 'need'} you` : null
}

/** The first stage that is not done, which is where the header's primary action points. */
export function nextStage(f: StageFacts): StageId | null {
  return STAGES.find((s) => stageState(f, s.id) !== 'done')?.id ?? null
}

/** One sentence for the page header, following the earliest open stage. */
export function primaryLabel(f: StageFacts, role?: ProjectRole | null): string {
  const open = (f.toLabel ?? 0) + (f.inReview ?? 0)
  // A labeler's job is the annotate stage: they never get a review, train or deploy sentence.
  if (role === 'labeler') return open > 0 ? `Label ${open} images` : 'Nothing to label'
  switch (nextStage(f)) {
    case 'upload': return 'Upload images'
    case 'annotate': return f.toLabel ? `Label ${f.toLabel} images` : `Review ${f.inReview ?? 0} labels`
    case 'dataset': return 'Create a version'
    case 'train': return f.latestVersion === null ? 'Train a model' : `Train on v${f.latestVersion}`
    case 'deploy': return 'Test the model'
    default: return 'All five steps are done'
  }
}
